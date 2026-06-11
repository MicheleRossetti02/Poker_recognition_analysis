"""Lightweight card reading helpers for the manual coach overlay.

The full live stack lives in ``main_poker_vision_gto.py``.  This module keeps a
small, optional YOLO path for the overlay: read cards from one selected area,
classify hero/board by geometry, and return JSON-friendly metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


DEFAULT_MODEL = Path("POKER_GTO_BOT_V3/weights/best.pt")
RANKS = set("23456789TJQKA")
SUITS = set("cdhs")
_MODEL_CACHE = {}
VALID_BOARD_COUNTS = {0, 3, 4, 5}


@dataclass(frozen=True)
class CardDetection:
    name: str
    conf: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "conf": round(self.conf, 4),
            "box": [round(self.x1, 1), round(self.y1, 1), round(self.x2, 1), round(self.y2, 1)],
            "center": [round(self.cx, 1), round(self.cy, 1)],
        }


def normalize_card_name(name: object) -> str | None:
    text = str(name or "").strip()
    if text.lower() == "tc":
        return "Tc"
    if len(text) != 2:
        return None
    rank = text[0].upper()
    suit = text[1].lower()
    if rank not in RANKS or suit not in SUITS:
        return None
    return f"{rank}{suit}"


def _coerce_detection(raw: Mapping[str, object]) -> CardDetection | None:
    name = normalize_card_name(raw.get("name") or raw.get("card") or raw.get("class"))
    if not name:
        return None
    box = raw.get("box") or raw.get("bbox")
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        conf = float(raw.get("conf", raw.get("confidence", 0.0)))
        x1, y1, x2, y2 = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    return CardDetection(name, conf, x1, y1, x2, y2)


def _best_unique(detections: Iterable[CardDetection]) -> list[CardDetection]:
    by_name: dict[str, CardDetection] = {}
    for det in detections:
        prev = by_name.get(det.name)
        if prev is None or det.conf > prev.conf:
            by_name[det.name] = det
    return list(by_name.values())


def classify_card_detections(
    detections: Iterable[Mapping[str, object]],
    width: int,
    height: int,
    conf: float = 0.30,
    zones: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Split detected card boxes into hero and board candidates.

    The selected area usually contains the whole poker table.  Hero cards are
    expected low and near the horizontal center; board cards are expected around
    the center band and sorted left-to-right.
    """
    w = max(1, int(width))
    h = max(1, int(height))
    cards = [
        det for det in (_coerce_detection(raw) for raw in detections)
        if det is not None and det.conf >= conf
    ]

    hero_zone = _zone_tuple((zones or {}).get("hero"))
    board_zone = _zone_tuple((zones or {}).get("board"))
    hero_pool = _cards_in_zone(cards, hero_zone) if hero_zone else [
        det for det in cards
        if det.cy >= h * 0.56 and w * 0.24 <= det.cx <= w * 0.76
    ]
    board_pool = _cards_in_zone(cards, board_zone) if board_zone else [
        det for det in cards
        if h * 0.28 <= det.cy <= h * 0.66 and w * 0.18 <= det.cx <= w * 0.82
    ]

    hero = sorted(_best_unique(hero_pool), key=lambda det: (-det.cy, -det.conf, det.cx))[:2]
    hero = sorted(hero, key=lambda det: det.cx)
    hero_names = [det.name for det in hero]

    hero_name_set = set(hero_names)
    board = [
        det for det in _best_unique(board_pool)
        if det.name not in hero_name_set
    ]
    board = sorted(board, key=lambda det: det.cx)[:5]
    board_names = [det.name for det in board]

    street = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}.get(len(board_names), "unknown")
    return {
        "hero_cards": hero_names,
        "board_cards": board_names,
        "street": street,
        "confidence": round(min([det.conf for det in hero + board], default=0.0), 3),
        "detections": [det.to_dict() for det in cards],
        "hero_detections": [det.to_dict() for det in hero],
        "board_detections": [det.to_dict() for det in board],
        "zones": {
            "hero": _zone_dict(hero_zone),
            "board": _zone_dict(board_zone),
        },
    }


def _zone_tuple(zone: Mapping[str, object] | None) -> tuple[float, float, float, float] | None:
    if not isinstance(zone, Mapping):
        return None
    try:
        x = float(zone["x"])
        y = float(zone["y"])
        width = float(zone["width"])
        height = float(zone["height"])
    except (KeyError, TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return x, y, x + width, y + height


def _zone_dict(zone: tuple[float, float, float, float] | None) -> dict[str, object] | None:
    if zone is None:
        return None
    x1, y1, x2, y2 = zone
    return {
        "x": round(x1, 1),
        "y": round(y1, 1),
        "width": round(x2 - x1, 1),
        "height": round(y2 - y1, 1),
    }


def _cards_in_zone(
    cards: Iterable[CardDetection],
    zone: tuple[float, float, float, float],
) -> list[CardDetection]:
    x1, y1, x2, y2 = zone
    return [det for det in cards if x1 <= det.cx <= x2 and y1 <= det.cy <= y2]


def vision_is_actionable(state: Mapping[str, object]) -> bool:
    hero = state.get("hero_cards", [])
    board = state.get("board_cards", [])
    return isinstance(hero, list) and len(hero) == 2 and isinstance(board, list) and len(board) in VALID_BOARD_COUNTS


def vision_summary(state: Mapping[str, object]) -> str:
    hero = " ".join(state.get("hero_cards", []) or []) or "--"
    board = " ".join(state.get("board_cards", []) or []) or "-"
    det_count = len(state.get("detections", []) or [])
    raw_count = len(state.get("raw_detections", []) or [])
    conf = float(state.get("confidence", 0.0) or 0.0)
    status = "OK" if vision_is_actionable(state) else "DA VERIFICARE"
    return f"{status}: Hero {hero} | Board {board} | conf {conf:.2f} | det {det_count}/{raw_count}"


def debug_image_path(state: Mapping[str, object]) -> str:
    for key in ("annotated_image", "failure_image", "image"):
        value = state.get(key)
        if value:
            return str(value)
    return ""


def save_annotated_image(
    image_path: str | Path,
    state: Mapping[str, object],
    out_path: str | Path,
) -> bool:
    """Save a debug image with raw/card boxes. Returns False if cv2 is missing."""
    try:
        import cv2
    except Exception:
        return False

    image = cv2.imread(str(image_path))
    if image is None:
        return False

    hero = {d.get("name") for d in state.get("hero_detections", []) or []}
    board = {d.get("name") for d in state.get("board_detections", []) or []}
    for zone_name, color in (("hero", (80, 220, 80)), ("board", (70, 170, 255))):
        zone = (state.get("zones") or {}).get(zone_name)
        if not isinstance(zone, Mapping):
            continue
        try:
            x1 = int(round(float(zone["x"])))
            y1 = int(round(float(zone["y"])))
            x2 = int(round(x1 + float(zone["width"])))
            y2 = int(round(y1 + float(zone["height"])))
        except (KeyError, TypeError, ValueError):
            continue
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)
        cv2.putText(
            image,
            zone_name.upper(),
            (x1, max(18, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )
    for det in state.get("raw_detections", []) or state.get("detections", []) or []:
        box = det.get("box", [])
        if not isinstance(box, list) or len(box) != 4:
            continue
        x1, y1, x2, y2 = [int(round(float(v))) for v in box]
        name = str(det.get("name", "?"))
        conf = float(det.get("conf", 0.0) or 0.0)
        if name in hero:
            color = (80, 220, 80)
        elif name in board:
            color = (70, 170, 255)
        else:
            color = (80, 80, 255) if conf < 0.30 else (220, 220, 80)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            image,
            f"{name} {conf:.2f}",
            (x1, max(16, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(out_path), image))


def _load_model(model_path: Path):
    key = str(model_path.resolve())
    if key not in _MODEL_CACHE:
        from ultralytics import YOLO

        _MODEL_CACHE[key] = YOLO(key)
    return _MODEL_CACHE[key]


def infer_table_state(
    image_path: str | Path,
    model_path: str | Path = DEFAULT_MODEL,
    conf: float = 0.12,
    classify_conf: float = 0.30,
    zones: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Modello carte non trovato: {model_path}")

    model = _load_model(model_path)
    result = model(str(image_path), conf=conf, verbose=False)[0]
    detections = []
    for box in result.boxes:
        cls = int(box.cls[0])
        name = normalize_card_name(result.names.get(cls, ""))
        if not name:
            continue
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
        detections.append({
            "name": name,
            "conf": float(box.conf[0]),
            "box": [x1, y1, x2, y2],
        })

    height, width = result.orig_shape[:2]
    out = classify_card_detections(detections, width, height, conf=classify_conf, zones=zones)
    out["raw_detections"] = [
        {
            "name": det["name"],
            "conf": round(float(det["conf"]), 4),
            "box": [round(float(v), 1) for v in det["box"]],
        }
        for det in detections
    ]
    out["image"] = str(image_path)
    out["model"] = str(model_path)
    out["actionable"] = vision_is_actionable(out)
    out["summary"] = vision_summary(out)
    return out
