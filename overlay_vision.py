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

    hero_pool = [
        det for det in cards
        if det.cy >= h * 0.56 and w * 0.24 <= det.cx <= w * 0.76
    ]
    board_pool = [
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
    }


def _load_model(model_path: Path):
    key = str(model_path.resolve())
    if key not in _MODEL_CACHE:
        from ultralytics import YOLO

        _MODEL_CACHE[key] = YOLO(key)
    return _MODEL_CACHE[key]


def infer_table_state(
    image_path: str | Path,
    model_path: str | Path = DEFAULT_MODEL,
    conf: float = 0.30,
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
    out = classify_card_detections(detections, width, height, conf=conf)
    out["image"] = str(image_path)
    out["model"] = str(model_path)
    return out
