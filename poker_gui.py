#!/usr/bin/env python3
"""
Virtual-chip poker — graphical table + coach overlay (PyQt6).

A self-contained poker table rendered with Qt. No real money, no external
client. Two modes:

  watch : bots play each other, you watch the table animate.
  play  : you are HERO; the coach suggestion is shown as an overlay and you
          act with the on-screen buttons.

Run (PyQt6 lives in ./venv on this machine):
  venv/bin/python poker_gui.py play  --villains tag,station,lag
  venv/bin/python poker_gui.py watch --lineup engine,tag,station,rock

The poker engine itself is pure-stdlib, so any Python with PyQt6 works.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
import threading

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QLabel, QSpinBox, QDoubleSpinBox,
)

from poker.bots import ARCHETYPES, make_human_strategy
from poker.engine import Decision
from poker.table import ActionView, Player, Table

SUIT_GLYPH = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
SUIT_COLOR = {"s": QColor(20, 20, 20), "c": QColor(20, 20, 20),
              "h": QColor(200, 30, 30), "d": QColor(200, 30, 30)}


class Bridge(QObject):
    """Thread-safe channel between the game worker and the Qt UI."""

    event = pyqtSignal(dict)
    action_request = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._event = threading.Event()
        self._result = ("fold", 0.0)

    # called from worker thread (blocks until UI responds)
    def request_action(self, view: ActionView, suggestion: Decision):
        self._event.clear()
        self.action_request.emit({
            "to_call": view.to_call, "pot": view.pot, "street": view.street,
            "position": view.position, "hero_stack": view.hero_stack,
            "min_raise": view.min_raise, "big_blind": view.big_blind,
            "suggestion_action": suggestion.action,
            "suggestion_amount": suggestion.amount,
            "suggestion_label": suggestion.label(),
            "suggestion_reason": suggestion.reason,
            "suggestion_equity": suggestion.equity,
            "suggestion_conf": suggestion.confidence,
        })
        self._event.wait()
        return self._result

    # called from UI thread
    def provide_action(self, action, amount):
        self._result = (action, amount)
        self._event.set()


class GameWorker(QThread):
    def __init__(self, table: Table, bridge: Bridge, pace: float,
                 hero_name: str | None, max_hands: int):
        super().__init__()
        self.table = table
        self.bridge = bridge
        self.pace = pace
        self.hero_name = hero_name
        self.max_hands = max_hands
        self._stop = threading.Event()
        self.table.observer = self._on_event

    def _on_event(self, payload: dict):
        # Normalise Card objects to strings for the UI thread.
        if "board" in payload:
            payload["board"] = [str(c) for c in payload["board"]]
        # Attach current player snapshot so the UI can fully redraw.
        payload["players"] = [{
            "name": p.name, "stack": round(p.stack, 1), "position": p.position,
            "hole": [str(c) for c in p.hole], "folded": p.folded,
            "all_in": p.all_in, "is_hero": (p.name == self.hero_name),
        } for p in self.table.players]
        self.bridge.event.emit(payload)
        if self.pace > 0 and payload["kind"] in ("action", "street", "showdown"):
            self.msleep(int(self.pace * 1000))

    def stop(self):
        self._stop.set()

    def run(self):
        hands = 0
        while not self._stop.is_set():
            alive = [p for p in self.table.players if p.stack > 0]
            if len(alive) < 2:
                for p in self.table.players:
                    p.stack = 100.0
            self.table.play_hand()
            hands += 1
            if self.max_hands and hands >= self.max_hands:
                break
            self.msleep(int(max(0.4, self.pace) * 1000))


class TableWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(820, 560)
        self.state = {"players": [], "board": [], "pot": 0.0,
                      "last": {}, "winners": {}, "showdown": {}}
        self.coach = None

    def apply_event(self, ev: dict):
        kind = ev.get("kind")
        if "players" in ev:
            self.state["players"] = ev["players"]
        if "board" in ev:
            self.state["board"] = ev["board"]
        if "pot" in ev:
            self.state["pot"] = ev["pot"]
        if kind == "hand_start":
            self.state["last"] = {}
            self.state["winners"] = {}
            self.state["showdown"] = {}
        if kind == "action":
            label = ev["action"].upper()
            if ev["action"] in ("call", "raise") and ev.get("amount"):
                label += f" {ev['amount']:.1f}"
            self.state["last"][ev["player"]] = label
        if kind == "showdown":
            self.state["winners"] = ev.get("winners", {})
            self.state["showdown"] = ev.get("showdown", {})
        self.update()

    def set_coach(self, coach):
        self.coach = coach
        self.update()

    # ---- drawing -------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(self.rect(), QColor(25, 28, 32))
        # felt
        margin = 70
        felt = QRectF(margin, margin, w - 2 * margin, h - 2 * margin - 40)
        p.setBrush(QBrush(QColor(30, 90, 55)))
        p.setPen(QPen(QColor(90, 60, 30), 10))
        p.drawEllipse(felt)

        cx, cy = felt.center().x(), felt.center().y()

        # board + pot
        self._draw_cards(p, self.state["board"], cx - 95, cy - 40, reveal=True)
        p.setPen(QColor(240, 240, 240))
        p.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        p.drawText(QRectF(cx - 100, cy + 20, 200, 24),
                   Qt.AlignmentFlag.AlignCenter, f"POT {self.state['pot']:.1f}")

        # seats
        players = self.state["players"]
        n = max(1, len(players))
        rx, ry = felt.width() / 2 - 10, felt.height() / 2 - 10
        for i, pl in enumerate(players):
            ang = math.pi / 2 + 2 * math.pi * i / n  # start bottom
            px = cx + rx * math.cos(ang)
            py = cy + ry * math.sin(ang)
            self._draw_seat(p, pl, px, py)

        if self.coach:
            self._draw_coach(p, w, h)

    def _draw_seat(self, p: QPainter, pl: dict, x: float, y: float):
        box = QRectF(x - 70, y - 34, 140, 68)
        hero = pl.get("is_hero")
        folded = pl.get("folded")
        p.setBrush(QBrush(QColor(45, 48, 54) if not folded else QColor(35, 35, 38)))
        p.setPen(QPen(QColor(80, 200, 120) if hero else QColor(110, 110, 120),
                      3 if hero else 1))
        p.drawRoundedRect(box, 8, 8)

        reveal = hero or bool(self.state["showdown"])
        self._draw_cards(p, pl.get("hole", []), x - 34, y - 58, reveal=reveal, small=True)

        p.setPen(QColor(235, 235, 235) if not folded else QColor(120, 120, 120))
        p.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        name = pl["name"][:12]
        p.drawText(QRectF(x - 68, y - 18, 136, 16), Qt.AlignmentFlag.AlignCenter,
                   f"{name}  [{pl['position']}]")
        p.setFont(QFont("Arial", 10))
        p.drawText(QRectF(x - 68, y - 2, 136, 16), Qt.AlignmentFlag.AlignCenter,
                   f"{pl['stack']:.1f} BB")

        last = self.state["last"].get(pl["name"])
        won = self.state["winners"].get(pl["name"])
        if won:
            p.setPen(QColor(255, 215, 0))
            p.drawText(QRectF(x - 68, y + 16, 136, 16), Qt.AlignmentFlag.AlignCenter,
                       f"WIN +{won:.1f}")
        elif last:
            p.setPen(QColor(180, 210, 255))
            p.drawText(QRectF(x - 68, y + 16, 136, 16), Qt.AlignmentFlag.AlignCenter, last)

    def _draw_cards(self, p, cards, x, y, reveal=True, small=False):
        cw, ch, gap = (28, 40, 6) if small else (50, 70, 10)
        for i, c in enumerate(cards):
            r = QRectF(x + i * (cw + gap), y, cw, ch)
            if reveal and isinstance(c, str) and len(c) == 2:
                p.setBrush(QBrush(QColor(245, 245, 245)))
                p.setPen(QPen(QColor(60, 60, 60), 1))
                p.drawRoundedRect(r, 4, 4)
                p.setPen(SUIT_COLOR.get(c[1].lower(), QColor(20, 20, 20)))
                p.setFont(QFont("Arial", 11 if small else 16, QFont.Weight.Bold))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter,
                           f"{c[0]}{SUIT_GLYPH.get(c[1].lower(), '?')}")
            else:
                p.setBrush(QBrush(QColor(40, 60, 120)))
                p.setPen(QPen(QColor(20, 30, 70), 1))
                p.drawRoundedRect(r, 4, 4)

    def _draw_coach(self, p, w, h):
        c = self.coach
        box = QRectF(12, h - 92, 360, 80)
        p.setBrush(QBrush(QColor(15, 15, 18, 235)))
        p.setPen(QPen(QColor(80, 200, 120), 2))
        p.drawRoundedRect(box, 8, 8)
        p.setPen(QColor(80, 220, 130))
        p.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        eq = f"{c['suggestion_equity']:.0%}" if c.get("suggestion_equity") else "n/a"
        p.drawText(QRectF(22, h - 86, 340, 22), Qt.AlignmentFlag.AlignLeft,
                   f"💡 COACH: {c['suggestion_label']}  (eq {eq}, conf {c['suggestion_conf']:.0%})")
        p.setPen(QColor(210, 210, 210))
        p.setFont(QFont("Arial", 10))
        p.drawText(QRectF(22, h - 62, 340, 40), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
                   c.get("suggestion_reason", ""))


class MainWindow(QWidget):
    def __init__(self, mode, lineup, villains, bb, stack, pace, max_hands, seed,
                 overlay=False):
        super().__init__()
        self.setWindowTitle("Virtual Poker — coach overlay (no real money)")
        if overlay:
            # Frameless, translucent, always-on-top floating HUD.
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.setWindowOpacity(0.92)
        self.bridge = Bridge()
        self.bridge.event.connect(self.on_event)
        self.bridge.action_request.connect(self.on_action_request)
        self.pending = None

        self.table_w = TableWidget()
        self.status = QLabel("Starting…")
        self.status.setStyleSheet("color:#ddd;padding:4px;")

        # action buttons (manual mode)
        self.btn_fold = QPushButton("Fold")
        self.btn_call = QPushButton("Check / Call")
        self.btn_raise = QPushButton("Raise to")
        self.raise_amt = QDoubleSpinBox()
        self.raise_amt.setRange(0, 100000)
        self.raise_amt.setDecimals(1)
        self.btn_fold.clicked.connect(lambda: self._act("fold"))
        self.btn_call.clicked.connect(self._act_call)
        self.btn_raise.clicked.connect(lambda: self._act("raise", self.raise_amt.value()))
        for b in (self.btn_fold, self.btn_call, self.btn_raise):
            b.setEnabled(False)

        controls = QHBoxLayout()
        controls.addWidget(self.btn_fold)
        controls.addWidget(self.btn_call)
        controls.addWidget(self.btn_raise)
        controls.addWidget(self.raise_amt)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table_w, 1)
        layout.addWidget(self.status)
        if mode == "play":
            layout.addLayout(controls)

        # build table
        rng = random.Random(seed)
        self.hero_name = None
        players = []
        if mode == "play":
            self.hero_name = "HERO"
            players.append(Player("HERO", stack,
                                  make_human_strategy(self.bridge.request_action)))
            for i, a in enumerate(villains):
                players.append(Player(f"V{i+1}_{a}", stack, ARCHETYPES[a]))
        else:
            for i, a in enumerate(lineup):
                players.append(Player(f"P{i+1}_{a}", stack, ARCHETYPES[a]))

        self.table = Table(players, big_blind=bb, rng=rng)
        self.worker = GameWorker(self.table, self.bridge, pace, self.hero_name, max_hands)
        self.worker.start()

    def on_event(self, ev: dict):
        self.table_w.apply_event(ev)
        kind = ev.get("kind")
        if kind == "hand_start":
            self.table_w.set_coach(None)
            self._enable_buttons(False)
            self.status.setText(f"Hand #{ev.get('hand_id')} — dealing…")
        elif kind == "showdown":
            wins = ", ".join(f"{n} +{a:.1f}" for n, a in ev.get("winners", {}).items() if a > 0)
            self.status.setText(f"Showdown — {wins}")

    def on_action_request(self, info: dict):
        self.pending = info
        self.table_w.set_coach(info)
        self._enable_buttons(True)
        self.btn_call.setText("Check" if info["to_call"] <= 0 else f"Call {info['to_call']:.1f}")
        default = max(info["min_raise"] + info["to_call"], info["big_blind"] * 2.5)
        if info["suggestion_action"] == "raise" and info["suggestion_amount"]:
            default = info["suggestion_amount"]
        self.raise_amt.setValue(round(default, 1))
        self.status.setText(
            f"YOUR TURN — {info['street'].upper()} pos {info['position']} "
            f"pot {info['pot']:.1f}, to call {info['to_call']:.1f}")

    def _enable_buttons(self, on: bool):
        for b in (self.btn_fold, self.btn_call, self.btn_raise):
            b.setEnabled(on)

    def _act_call(self):
        to_call = self.pending["to_call"] if self.pending else 0.0
        self._act("call" if to_call > 0 else "check", to_call)

    def _act(self, action, amount=0.0):
        self._enable_buttons(False)
        self.table_w.set_coach(None)
        self.bridge.provide_action(action, amount)

    def closeEvent(self, e):
        self.worker.stop()
        self.worker.wait(1500)
        e.accept()


def _alist(text):
    return [a.strip() for a in text.split(",") if a.strip()]


def main():
    ap = argparse.ArgumentParser(description="Virtual poker GUI (no real money).")
    ap.add_argument("mode", choices=["watch", "play"])
    ap.add_argument("--lineup", type=_alist, default=["engine", "tag", "station", "rock"])
    ap.add_argument("--villains", type=_alist, default=["tag", "station", "lag"])
    ap.add_argument("--bb", type=float, default=1.0)
    ap.add_argument("--stack", type=float, default=100.0)
    ap.add_argument("--pace", type=float, default=0.8, help="seconds between actions")
    ap.add_argument("--hands", type=int, default=0, help="0 = unlimited")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--overlay", action="store_true",
                    help="frameless, always-on-top, translucent floating HUD")
    args = ap.parse_args()

    for a in (args.lineup + args.villains):
        if a not in ARCHETYPES:
            print(f"Unknown archetype: {a}. Choose from {list(ARCHETYPES)}", file=sys.stderr)
            sys.exit(1)

    app = QApplication(sys.argv)
    win = MainWindow(args.mode, args.lineup, args.villains, args.bb, args.stack,
                     args.pace, args.hands, args.seed, overlay=args.overlay)
    win.resize(900, 640)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
