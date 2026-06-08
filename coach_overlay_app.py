#!/usr/bin/env python3
"""
Always-on-top manual coach overlay.

This is a lightweight test overlay for real play: type the visible spot
(hero cards, board, street, pot and to-call in BB) and it shows the same engine
recommendation used by the simulator/web coach. It does not use OCR; the live
vision pipeline remains in main_poker_vision_gto.py.

Run:
  venv/bin/python coach_overlay_app.py
  venv312/bin/python coach_overlay_app.py --smoke
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from poker.cards import make_card
from poker.coach import coach_insights
from poker.engine import Situation, decide


POSITIONS = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
STREETS = ["preflop", "flop", "turn", "river"]


@dataclass
class OverlaySpot:
    hero_cards: str
    board_cards: str = ""
    position: str = "BTN"
    street: str = "preflop"
    pot_bb: float = 1.5
    to_call_bb: float = 0.0
    stack_bb: float = 100.0
    opponents: int = 1
    big_blind: float = 1.0


def _parse_card_text(text: str):
    cards = []
    for raw in (text or "").replace(",", " ").split():
        cards.append(make_card(raw))
    return cards


def compute_overlay_advice(spot: OverlaySpot) -> dict[str, object]:
    """Return a JSON-friendly coach payload for the overlay UI."""
    hole = _parse_card_text(spot.hero_cards)
    if len(hole) != 2:
        raise ValueError("Inserisci esattamente 2 carte hero, es. As Kh")

    board = _parse_card_text(spot.board_cards)
    street = (spot.street or "preflop").lower()
    if street not in STREETS:
        raise ValueError(f"Street non valida: {spot.street}")

    expected_board = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}[street]
    if len(board) != expected_board:
        raise ValueError(f"{street}: servono {expected_board} carte board")

    to_call = max(0.0, float(spot.to_call_bb))
    situation = Situation(
        hole=hole,
        board=board,
        position=spot.position if spot.position in POSITIONS else "BB",
        street=street,
        pot=max(0.0, float(spot.pot_bb)),
        to_call=to_call,
        hero_stack=max(float(spot.big_blind), float(spot.stack_bb)),
        big_blind=max(0.1, float(spot.big_blind)),
        num_opponents=max(1, int(spot.opponents)),
        facing_raise=to_call > 0,
    )
    decision = decide(situation)
    insights = coach_insights(
        hole,
        board,
        opponents=max(1, int(spot.opponents)),
        facing_raise=to_call > 0,
        iterations=180,
    )
    return {
        "label": decision.label(),
        "action": decision.action,
        "amount": round(decision.amount, 1),
        "equity": round(decision.equity, 3),
        "confidence": round(decision.confidence, 2),
        "reason": decision.reason,
        "made_hand": insights["made_hand"],
        "draws": list(insights["draws"]),
        "outs": insights["outs"]["count"],
        "win_pct": round(insights["equity_breakdown"]["win_pct"], 3),
        "tie_pct": round(insights["equity_breakdown"]["tie_pct"], 3),
        "lose_pct": round(insights["equity_breakdown"]["lose_pct"], 3),
    }


def _format_payload(payload: dict[str, object]) -> str:
    eq = int(round(float(payload["equity"]) * 100))
    conf = int(round(float(payload["confidence"]) * 100))
    draws = ", ".join(payload["draws"]) if payload["draws"] else "nessun draw"
    return (
        f"{payload['label']}  |  equity {eq}%  conf {conf}%\n"
        f"{payload['reason']}\n"
        f"{payload['made_hand']} · {draws} · outs {payload['outs']}\n"
        f"win {int(round(float(payload['win_pct']) * 100))}% · "
        f"tie {int(round(float(payload['tie_pct']) * 100))}% · "
        f"lose {int(round(float(payload['lose_pct']) * 100))}%"
    )


def run_app():
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QApplication,
        QComboBox,
        QDoubleSpinBox,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
    import sys

    class OverlayWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Poker Coach Overlay")
            self.setWindowFlags(
                Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setWindowOpacity(0.94)
            self.setMinimumWidth(430)

            self.hero = QLineEdit("As Kh")
            self.board = QLineEdit("")
            self.position = QComboBox()
            self.position.addItems(POSITIONS)
            self.position.setCurrentText("BTN")
            self.street = QComboBox()
            self.street.addItems(STREETS)
            self.pot = QDoubleSpinBox()
            self.pot.setRange(0, 10000)
            self.pot.setValue(1.5)
            self.pot.setDecimals(1)
            self.to_call = QDoubleSpinBox()
            self.to_call.setRange(0, 10000)
            self.to_call.setDecimals(1)
            self.stack = QDoubleSpinBox()
            self.stack.setRange(1, 100000)
            self.stack.setValue(100)
            self.stack.setDecimals(1)
            self.opponents = QSpinBox()
            self.opponents.setRange(1, 5)
            self.opponents.setValue(1)

            form = QGridLayout()
            form.addWidget(QLabel("Hero"), 0, 0)
            form.addWidget(self.hero, 0, 1)
            form.addWidget(QLabel("Board"), 1, 0)
            form.addWidget(self.board, 1, 1)
            form.addWidget(QLabel("Street"), 2, 0)
            form.addWidget(self.street, 2, 1)
            form.addWidget(QLabel("Pos"), 3, 0)
            form.addWidget(self.position, 3, 1)
            form.addWidget(QLabel("Pot BB"), 4, 0)
            form.addWidget(self.pot, 4, 1)
            form.addWidget(QLabel("To call BB"), 5, 0)
            form.addWidget(self.to_call, 5, 1)
            form.addWidget(QLabel("Stack BB"), 6, 0)
            form.addWidget(self.stack, 6, 1)
            form.addWidget(QLabel("Opp"), 7, 0)
            form.addWidget(self.opponents, 7, 1)

            self.result = QLabel("Pronto.")
            self.result.setWordWrap(True)
            self.result.setStyleSheet("font-weight:700;color:#e8eaed;padding:8px;")
            calc = QPushButton("Calcola")
            demo = QPushButton("Demo draw")
            calc.clicked.connect(self.calculate)
            demo.clicked.connect(self.load_demo)
            buttons = QHBoxLayout()
            buttons.addWidget(calc)
            buttons.addWidget(demo)

            layout = QVBoxLayout(self)
            title = QLabel("Poker Coach Overlay")
            title.setStyleSheet("font-size:18px;font-weight:800;color:#5ad17a;")
            layout.addWidget(title)
            layout.addLayout(form)
            layout.addLayout(buttons)
            layout.addWidget(self.result)
            self.setStyleSheet("""
                QWidget { background:#161a20; color:#e8eaed; font-size:13px; }
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                    background:#0f1216; border:1px solid #2a3038; padding:5px;
                    border-radius:4px; color:#e8eaed;
                }
                QPushButton {
                    background:#5ad17a; color:#06210f; border:0; padding:8px;
                    border-radius:6px; font-weight:800;
                }
            """)
            self.calculate()

        def spot(self):
            return OverlaySpot(
                hero_cards=self.hero.text(),
                board_cards=self.board.text(),
                position=self.position.currentText(),
                street=self.street.currentText(),
                pot_bb=self.pot.value(),
                to_call_bb=self.to_call.value(),
                stack_bb=self.stack.value(),
                opponents=self.opponents.value(),
            )

        def calculate(self):
            try:
                self.result.setText(_format_payload(compute_overlay_advice(self.spot())))
            except Exception as exc:
                self.result.setText(f"Errore: {exc}")

        def load_demo(self):
            self.hero.setText("Ah Kh")
            self.board.setText("Qh 7c 2h")
            self.street.setCurrentText("flop")
            self.position.setCurrentText("BTN")
            self.pot.setValue(6.0)
            self.to_call.setValue(2.0)
            self.stack.setValue(98.0)
            self.opponents.setValue(1)
            self.calculate()

    app = QApplication(sys.argv)
    win = OverlayWindow()
    win.show()
    sys.exit(app.exec())


def main():
    parser = argparse.ArgumentParser(description="Manual always-on-top poker coach overlay.")
    parser.add_argument("--smoke", action="store_true", help="run a no-GUI calculation smoke test")
    args = parser.parse_args()
    if args.smoke:
        payload = compute_overlay_advice(
            OverlaySpot(hero_cards="Ah Kh", board_cards="Qh 7c 2h",
                        street="flop", pot_bb=6, to_call_bb=2, stack_bb=98)
        )
        print(_format_payload(payload))
        return
    run_app()


if __name__ == "__main__":
    main()
