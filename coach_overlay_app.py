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
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from poker.cards import make_card
from poker.coach import coach_insights
from poker.engine import Situation, decide


POSITIONS = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
STREETS = ["preflop", "flop", "turn", "river"]
DEFAULT_CAPTURE_ROOT = Path("dataset/raw")
DEFAULT_OVERLAY_OPACITY = 0.94
CLICKTHROUGH_OPACITY = 0.48
CLICKTHROUGH_SECONDS = 10


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


@dataclass
class CaptureRegion:
    x: int = 0
    y: int = 0
    width: int = 960
    height: int = 640
    source: str = "manual"


def region_from_points(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    source: str = "selected",
    min_size: int = 40,
) -> CaptureRegion:
    left = min(int(x1), int(x2))
    top = min(int(y1), int(y2))
    width = abs(int(x2) - int(x1))
    height = abs(int(y2) - int(y1))
    if width < min_size or height < min_size:
        raise ValueError(f"Area troppo piccola: minimo {min_size}x{min_size}px")
    return CaptureRegion(left, top, width, height, source)


def create_capture_session(
    root: Path = DEFAULT_CAPTURE_ROOT,
    fallback_root: Path | None = None,
) -> Path:
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    roots = [root]
    fallback = fallback_root or (Path(tempfile.gettempdir()) / "poker_coach_overlay")
    if fallback != root:
        roots.append(fallback)
    errors = []
    for base in roots:
        session = base / f"overlay_session_{stamp}"
        try:
            (session / "images").mkdir(parents=True, exist_ok=True)
            return session
        except OSError as exc:
            errors.append(f"{base}: {exc}")
    raise OSError("Impossibile creare una sessione dataset: " + " | ".join(errors))


def capture_metadata(
    filename: str,
    region: CaptureRegion,
    spot: OverlaySpot,
    advice: dict[str, object] | None,
    mode: str,
    readout: str = "",
) -> dict[str, object]:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "filename": filename,
        "mode": mode,
        "readout": readout,
        "region": {
            "x": region.x,
            "y": region.y,
            "width": region.width,
            "height": region.height,
            "source": region.source,
        },
        "spot": {
            "hero_cards": spot.hero_cards,
            "board_cards": spot.board_cards,
            "position": spot.position,
            "street": spot.street,
            "pot_bb": spot.pot_bb,
            "to_call_bb": spot.to_call_bb,
            "stack_bb": spot.stack_bb,
            "opponents": spot.opponents,
        },
        "advice": advice or {},
    }


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


def format_estimated_readout(
    spot: OverlaySpot,
    payload: dict[str, object] | None,
    source: str = "manuale",
) -> str:
    """Compact summary that stays visible while the detailed panel is hidden."""
    board = spot.board_cards.strip() or "-"
    hero = spot.hero_cards.strip() or "-"
    label = str(payload.get("label", "in attesa")) if payload else "in attesa"
    equity = ""
    if payload and "equity" in payload:
        equity = f" · eq {int(round(float(payload['equity']) * 100))}%"
    confidence = ""
    if payload and "confidence" in payload:
        confidence = f" · conf {int(round(float(payload['confidence']) * 100))}%"
    draws = ""
    if payload:
        draw_list = payload.get("draws", [])
        if draw_list:
            draws = f" · {', '.join(str(d) for d in draw_list)}"
        elif payload.get("outs") is not None:
            draws = " · nessun draw"
        if payload.get("outs") is not None:
            draws = f"{draws} · outs {payload['outs']}"
    return (
        f"Lettura stimata: {label}{equity}{confidence} | Hero {hero} | Board {board} | "
        f"{spot.street} {spot.position} | pot {spot.pot_bb:.1f}bb | "
        f"call {spot.to_call_bb:.1f}bb | opp {spot.opponents} | fonte {source}{draws}"
    )


def run_app():
    from PyQt6.QtCore import QPoint, QRect, Qt, QTimer
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QRubberBand,
        QSlider,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
    import sys

    def virtual_screen_geometry():
        screens = QApplication.screens()
        if not screens:
            return QRect(0, 0, 1200, 800)
        geo = screens[0].geometry()
        for screen in screens[1:]:
            geo = geo.united(screen.geometry())
        return geo

    class RegionPicker(QWidget):
        def __init__(self, on_done):
            super().__init__()
            self.on_done = on_done
            self.origin_global = QPoint()
            self.rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
            self.setWindowTitle("Seleziona area poker")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.setGeometry(virtual_screen_geometry())
            self.hint = QLabel("Trascina sul tavolo poker. Esc annulla.", self)
            self.hint.setStyleSheet(
                "background:#11161b;color:#ffcf5a;padding:10px;"
                "border:1px solid #5ad17a;border-radius:6px;font-weight:800;"
            )
            self.hint.move(24, 24)

        def mousePressEvent(self, event):
            self.origin_global = event.globalPosition().toPoint()
            origin_local = self.mapFromGlobal(self.origin_global)
            self.rubber.setGeometry(QRect(origin_local, origin_local))
            self.rubber.show()

        def mouseMoveEvent(self, event):
            current = event.globalPosition().toPoint()
            self.rubber.setGeometry(
                QRect(self.mapFromGlobal(self.origin_global), self.mapFromGlobal(current)).normalized()
            )

        def mouseReleaseEvent(self, event):
            current = event.globalPosition().toPoint()
            try:
                region = region_from_points(
                    self.origin_global.x(),
                    self.origin_global.y(),
                    current.x(),
                    current.y(),
                    source="selected",
                )
            except ValueError:
                region = None
            self.close()
            self.on_done(region)

        def keyPressEvent(self, event):
            if event.key() == Qt.Key.Key_Escape:
                self.close()
                self.on_done(None)

    class OverlayWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Poker Coach Overlay")
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.setWindowOpacity(DEFAULT_OVERLAY_OPACITY)
            self.setMinimumWidth(430)
            self.capture_session = create_capture_session()
            self.capture_count = 0
            self.last_payload = None
            self.readout_source = "manuale"
            self.window_choices = []
            self.region_picker = None
            self.mini_mode = False
            self.clickthrough_left = 0
            self.auto_timer = QTimer(self)
            self.auto_timer.timeout.connect(self.auto_capture_tick)
            self.recalc_timer = QTimer(self)
            self.recalc_timer.setSingleShot(True)
            self.recalc_timer.timeout.connect(self.calculate)
            self.clickthrough_timer = QTimer(self)
            self.clickthrough_timer.timeout.connect(self.tick_clickthrough)

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
            self.capture_x = QSpinBox()
            self.capture_x.setRange(-10000, 10000)
            self.capture_y = QSpinBox()
            self.capture_y.setRange(-10000, 10000)
            self.capture_w = QSpinBox()
            self.capture_w.setRange(100, 10000)
            self.capture_w.setValue(960)
            self.capture_h = QSpinBox()
            self.capture_h.setRange(100, 10000)
            self.capture_h.setValue(640)
            self.capture_interval = QDoubleSpinBox()
            self.capture_interval.setRange(0.5, 60)
            self.capture_interval.setValue(2.0)
            self.capture_interval.setDecimals(1)
            self.include_overlay = QCheckBox("Includi overlay nello screenshot")
            self.include_overlay.setChecked(False)

            for widget in (
                self.hero,
                self.board,
                self.position,
                self.street,
                self.pot,
                self.to_call,
                self.stack,
                self.opponents,
            ):
                try:
                    widget.textChanged.connect(self.schedule_recalculate)
                except AttributeError:
                    try:
                        widget.valueChanged.connect(self.schedule_recalculate)
                    except AttributeError:
                        widget.currentTextChanged.connect(self.schedule_recalculate)

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

            capture_form = QGridLayout()
            capture_form.addWidget(QLabel("X"), 0, 0)
            capture_form.addWidget(self.capture_x, 0, 1)
            capture_form.addWidget(QLabel("Y"), 0, 2)
            capture_form.addWidget(self.capture_y, 0, 3)
            capture_form.addWidget(QLabel("W"), 1, 0)
            capture_form.addWidget(self.capture_w, 1, 1)
            capture_form.addWidget(QLabel("H"), 1, 2)
            capture_form.addWidget(self.capture_h, 1, 3)
            capture_form.addWidget(QLabel("Auto s"), 2, 0)
            capture_form.addWidget(self.capture_interval, 2, 1)
            capture_form.addWidget(self.include_overlay, 2, 2, 1, 2)
            self.window_combo = QComboBox()
            self.window_combo.setMinimumWidth(260)
            capture_form.addWidget(QLabel("Finestra"), 3, 0)
            capture_form.addWidget(self.window_combo, 3, 1, 1, 3)

            self.estimated = QLabel("")
            self.estimated.setWordWrap(True)
            self.estimated.setStyleSheet(
                "font-weight:800;color:#ffcf5a;padding:8px;"
                "border:1px solid #39414b;border-radius:6px;background:#11161b;"
            )
            self.mode_status = QLabel("Manuale pronto.")
            self.mode_status.setWordWrap(True)
            self.mode_status.setStyleSheet("color:#9aa3ad;padding:2px 4px;")
            self.result = QLabel("Pronto.")
            self.result.setWordWrap(True)
            self.result.setStyleSheet("font-weight:700;color:#e8eaed;padding:8px;")
            self.capture_status = QLabel(f"Dataset: {self.capture_session}")
            self.capture_status.setWordWrap(True)
            self.capture_status.setStyleSheet("color:#9aa3ad;padding:4px;")
            self.manual_panel = QWidget()
            self.manual_panel.setObjectName("manualPanel")
            self.toggle_manual_btn = QPushButton("Manuale ON")
            self.toggle_manual_btn.clicked.connect(self.toggle_manual_panel)
            self.mini_btn = QPushButton("Mini HUD")
            self.mini_btn.clicked.connect(self.toggle_mini_mode)
            self.always_top = QCheckBox("Sempre sopra")
            self.always_top.setChecked(True)
            self.always_top.toggled.connect(self.set_always_on_top)
            self.clickthrough_btn = QPushButton(f"Click-through {CLICKTHROUGH_SECONDS}s")
            self.clickthrough_btn.clicked.connect(self.temporary_clickthrough)
            self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
            self.opacity_slider.setRange(35, 100)
            self.opacity_slider.setValue(int(DEFAULT_OVERLAY_OPACITY * 100))
            self.opacity_slider.setFixedWidth(100)
            self.opacity_slider.valueChanged.connect(self.set_overlay_opacity)
            self.opacity_label = QLabel("94%")
            calc = QPushButton("Calcola")
            demo = QPushButton("Demo draw")
            lock_window = QPushButton("Aggancia finestra poker")
            refresh_windows = QPushButton("Aggiorna finestre")
            lock_selected = QPushButton("Aggancia selezionata")
            select_area = QPushButton("Seleziona area")
            screenshot = QPushButton("Screenshot")
            self.auto_btn = QPushButton("Auto OFF")
            calc.clicked.connect(self.calculate)
            demo.clicked.connect(self.load_demo)
            lock_window.clicked.connect(self.lock_poker_window)
            refresh_windows.clicked.connect(self.refresh_window_choices)
            lock_selected.clicked.connect(self.lock_selected_window)
            select_area.clicked.connect(self.start_region_picker)
            screenshot.clicked.connect(lambda: self.capture_screen("manual"))
            self.auto_btn.clicked.connect(self.toggle_auto_capture)
            buttons = QHBoxLayout()
            buttons.addWidget(calc)
            buttons.addWidget(demo)
            capture_buttons = QHBoxLayout()
            capture_buttons.addWidget(lock_window)
            capture_buttons.addWidget(refresh_windows)
            capture_buttons.addWidget(lock_selected)
            capture_buttons.addWidget(select_area)
            capture_buttons.addWidget(screenshot)
            capture_buttons.addWidget(self.auto_btn)
            top_controls = QHBoxLayout()
            top_controls.addWidget(self.toggle_manual_btn)
            top_controls.addWidget(self.mini_btn)
            top_controls.addWidget(self.always_top)
            top_controls.addWidget(self.clickthrough_btn)
            top_controls.addWidget(QLabel("Opacita"))
            top_controls.addWidget(self.opacity_slider)
            top_controls.addWidget(self.opacity_label)

            manual_layout = QVBoxLayout(self.manual_panel)
            manual_layout.setContentsMargins(0, 0, 0, 0)
            manual_layout.addLayout(form)
            manual_layout.addLayout(buttons)
            manual_layout.addWidget(self.result)
            manual_layout.addWidget(QLabel("Cattura dataset"))
            manual_layout.addLayout(capture_form)
            manual_layout.addLayout(capture_buttons)
            manual_layout.addWidget(self.capture_status)

            layout = QVBoxLayout(self)
            title = QLabel("Poker Coach Overlay")
            title.setStyleSheet("font-size:18px;font-weight:800;color:#5ad17a;")
            layout.addWidget(title)
            layout.addWidget(self.estimated)
            layout.addLayout(top_controls)
            layout.addWidget(self.mode_status)
            layout.addWidget(self.manual_panel)
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
                QCheckBox { padding:4px; }
            """)
            self.calculate()
            QTimer.singleShot(250, self.refresh_window_choices)

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

        def region(self, source="manual"):
            return CaptureRegion(
                x=self.capture_x.value(),
                y=self.capture_y.value(),
                width=self.capture_w.value(),
                height=self.capture_h.value(),
                source=source,
            )

        def calculate(self):
            self.recalc_timer.stop()
            try:
                self.last_payload = compute_overlay_advice(self.spot())
                self.result.setText(_format_payload(self.last_payload))
            except Exception as exc:
                self.last_payload = None
                self.result.setText(f"Errore: {exc}")
            self.update_estimated_readout()

        def schedule_recalculate(self, *args):
            self.update_estimated_readout()
            self.recalc_timer.start(350)

        def update_estimated_readout(self, *args):
            self.estimated.setText(
                format_estimated_readout(self.spot(), self.last_payload, self.readout_source)
            )

        def toggle_manual_panel(self):
            visible = not self.manual_panel.isVisible()
            self.manual_panel.setVisible(visible)
            self.toggle_manual_btn.setText("Manuale ON" if visible else "Manuale OFF")
            self.mode_status.setText(
                "Comandi manuali visibili." if visible else "Comandi manuali nascosti: resta la lettura stimata."
            )
            self.adjustSize()

        def toggle_mini_mode(self):
            self.mini_mode = not self.mini_mode
            self.manual_panel.setVisible(not self.mini_mode)
            self.mode_status.setVisible(not self.mini_mode)
            self.toggle_manual_btn.setText("Manuale OFF" if self.mini_mode else "Manuale ON")
            self.mini_btn.setText("HUD piena" if self.mini_mode else "Mini HUD")
            self.setMinimumWidth(360 if self.mini_mode else 430)
            self.resize(420 if self.mini_mode else 520, self.height())
            self.adjustSize()

        def set_always_on_top(self, enabled):
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(enabled))
            self.show()
            if enabled:
                self.raise_()
                self.activateWindow()
            self.mode_status.setText(
                "Overlay sempre in primo piano." if enabled else "Sempre sopra disattivato: ora puo passare dietro."
            )

        def set_overlay_opacity(self, value):
            opacity = max(35, min(100, int(value))) / 100
            self.opacity_label.setText(f"{int(value)}%")
            if not self.clickthrough_timer.isActive():
                self.setWindowOpacity(opacity)

        def temporary_clickthrough(self):
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setWindowOpacity(CLICKTHROUGH_OPACITY)
            self.clickthrough_left = CLICKTHROUGH_SECONDS
            self.clickthrough_btn.setEnabled(False)
            self.clickthrough_btn.setText(f"Click {self.clickthrough_left}s")
            self.mode_status.setText("Click-through attivo: clicca pure la finestra sotto.")
            self.capture_status.setText("Click-through attivo: puoi cliccare la finestra sotto.")
            self.clickthrough_timer.start(1000)

        def tick_clickthrough(self):
            self.clickthrough_left -= 1
            if self.clickthrough_left <= 0:
                self.restore_interactive()
                return
            self.clickthrough_btn.setText(f"Click {self.clickthrough_left}s")

        def restore_interactive(self):
            self.clickthrough_timer.stop()
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.setWindowOpacity(self.opacity_slider.value() / 100)
            self.clickthrough_btn.setEnabled(True)
            self.clickthrough_btn.setText(f"Click-through {CLICKTHROUGH_SECONDS}s")
            self.mode_status.setText("Overlay di nuovo cliccabile.")
            self.capture_status.setText("Overlay di nuovo cliccabile.")
            if self.always_top.isChecked():
                self.raise_()

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

        def set_capture_region_from_bounds(self, bounds, source, window_name="poker"):
            self.capture_x.setValue(int(bounds["x"]))
            self.capture_y.setValue(int(bounds["y"]))
            self.capture_w.setValue(int(bounds["width"]))
            self.capture_h.setValue(int(bounds["height"]))
            self.move(int(bounds["x"]) + 20, int(bounds["y"]) + 20)
            self.readout_source = source
            self.update_estimated_readout()
            self.capture_status.setText(f"Agganciata: {window_name} · {bounds}")

        def refresh_window_choices(self):
            try:
                from window_capture import WindowCapture

                capture = WindowCapture(allow_fullscreen_fallback=False)
                windows = capture.list_visible_windows(include_non_poker=False)
                if not windows:
                    windows = [
                        w for w in capture.list_visible_windows(include_non_poker=True)
                        if "poker coach overlay" not in f"{w.get('owner', '')} {w.get('title', '')}".lower()
                    ]
                self.window_choices = windows
                self.window_combo.clear()
                for window in windows:
                    bounds = window["bounds"]
                    name = f"{window['owner']} - {window['title'] or '(senza titolo)'}"
                    self.window_combo.addItem(
                        f"{name[:70]} · {bounds['width']}x{bounds['height']} @ {bounds['x']},{bounds['y']}"
                    )
                if windows:
                    self.capture_status.setText(
                        f"Trovate {len(windows)} finestre. Scegline una e premi Aggancia selezionata."
                    )
                else:
                    self.capture_status.setText(
                        "Nessuna finestra leggibile. Usa Seleziona area oppure controlla permessi Accessibilita."
                    )
            except Exception as exc:
                self.capture_status.setText(f"Errore lettura finestre: {exc}")

        def lock_selected_window(self):
            idx = self.window_combo.currentIndex()
            if idx < 0 or idx >= len(self.window_choices):
                self.capture_status.setText("Nessuna finestra selezionata. Premi Aggiorna finestre.")
                return
            window = self.window_choices[idx]
            name = f"{window['owner']} - {window['title'] or '(senza titolo)'}"
            self.set_capture_region_from_bounds(
                window["bounds"],
                f"finestra: {name}",
                name,
            )

        def start_region_picker(self):
            self.capture_status.setText("Seleziona l'area del tavolo: trascina un rettangolo, Esc annulla.")
            self.hide()

            def finish(region):
                self.show()
                self.raise_()
                self.region_picker = None
                if region is None:
                    self.capture_status.setText("Selezione area annullata o troppo piccola.")
                    return
                self.set_capture_region_from_bounds(
                    {
                        "x": region.x,
                        "y": region.y,
                        "width": region.width,
                        "height": region.height,
                    },
                    "area selezionata",
                    "area selezionata",
                )

            self.region_picker = RegionPicker(finish)
            self.region_picker.show()
            self.region_picker.raise_()
            self.region_picker.activateWindow()

        def lock_poker_window(self):
            try:
                from window_capture import WindowCapture

                capture = WindowCapture(allow_fullscreen_fallback=False)
                bounds = capture.get_current_bounds()
                if not bounds:
                    self.refresh_window_choices()
                    self.capture_status.setText(
                        "Auto non ha trovato una finestra poker. Scegli dal menu e premi Aggancia selezionata."
                    )
                    return
                name = capture.current_window[1] if capture.current_window else "poker"
                self.set_capture_region_from_bounds(bounds, f"finestra: {name}", name)
            except Exception as exc:
                self.capture_status.setText(f"Errore aggancio finestra: {exc}")

        def capture_screen(self, mode):
            success = False
            hidden = False
            try:
                self.calculate()
                region = self.region("manual")
                if mode == "auto":
                    region.source = "auto"
                spot = self.spot()
                advice = self.last_payload
                if not self.include_overlay.isChecked():
                    self.hide()
                    hidden = True
                    QApplication.processEvents()
                screen = QApplication.primaryScreen()
                if screen is None:
                    self.capture_status.setText("Screenshot fallito: nessuno schermo disponibile.")
                    return False
                pixmap = screen.grabWindow(0, region.x, region.y, region.width, region.height)
                if pixmap.isNull():
                    self.capture_status.setText("Screenshot fallito: controlla permessi Registrazione Schermo.")
                    return False
                self.capture_count += 1
                filename = f"overlay_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
                path = self.capture_session / "images" / filename
                if not pixmap.save(str(path), "PNG"):
                    self.capture_status.setText(f"Salvataggio fallito: {path}")
                    return False
                record = capture_metadata(filename, region, spot, advice, mode, self.estimated.text())
                with (self.capture_session / "metadata.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                self.capture_status.setText(
                    f"Salvati {self.capture_count} screenshot · ultimo: {path.name}"
                )
                success = True
            except Exception as exc:
                self.capture_status.setText(f"Screenshot fallito: {exc}")
            finally:
                if hidden:
                    self.show()
                    self.raise_()
            return success

        def auto_capture_tick(self):
            if not self.capture_screen("auto"):
                self.auto_timer.stop()
                self.auto_btn.setText("Auto OFF")
                self.show()
                self.raise_()
                self.capture_status.setText(
                    f"Auto fermo: ultimo screenshot fallito. {self.capture_status.text()}"
                )

        def toggle_auto_capture(self):
            if self.auto_timer.isActive():
                self.auto_timer.stop()
                self.auto_btn.setText("Auto OFF")
                self.capture_status.setText(f"Auto fermo · dataset: {self.capture_session}")
                return
            interval_ms = int(self.capture_interval.value() * 1000)
            self.auto_timer.start(interval_ms)
            self.auto_btn.setText("Auto ON")
            self.capture_status.setText(
                f"Auto ogni {self.capture_interval.value():.1f}s · dataset: {self.capture_session}"
            )

    app = QApplication(sys.argv)
    app.setApplicationName("Poker Coach Overlay")
    win = OverlayWindow()
    screen = app.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        win.move(geo.x() + 80, geo.y() + 80)
    win.resize(520, 720)
    win.show()
    win.raise_()
    win.activateWindow()
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
