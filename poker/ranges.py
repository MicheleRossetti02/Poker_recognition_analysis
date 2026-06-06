"""
Preflop hand notation and position-based opening ranges.

Hand notation: pairs "AA".."22", suited "AKs", offsuit "AKo" (high card first).
Ranges are intentionally ABC/solid (not a full solver) but cover all 6 common
positions and are used as the preflop layer of the decision engine.
"""

from __future__ import annotations

from .cards import Card, RANK_VALUE

POSITIONS = ["UTG", "MP", "CO", "BTN", "SB", "BB"]


def normalize_hand(card1: Card | str, card2: Card | str) -> str | None:
    """Convert two cards to canonical notation, e.g. 'AKs', 'AKo', 'AA'."""
    def _rs(c: Card | str) -> tuple[str, str]:
        if isinstance(c, Card):
            return c.rank, c.suit
        c = c.strip()
        if len(c) != 2:
            raise ValueError(f"bad card {c!r}")
        return c[0].upper(), c[1].lower()

    r1, s1 = _rs(card1)
    r2, s2 = _rs(card2)
    if r1 not in RANK_VALUE or r2 not in RANK_VALUE:
        return None
    if RANK_VALUE[r1] < RANK_VALUE[r2]:
        r1, r2, s1, s2 = r2, r1, s2, s1
    if r1 == r2:
        return f"{r1}{r2}"
    return f"{r1}{r2}{'s' if s1 == s2 else 'o'}"


# OPEN = hands we open-raise when folded to. 3BET = value/bluff 3bet vs a raise.
# CALL = hands we flat vs a raise.
OPEN_RAISE = {
    "UTG": {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88",
        "AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
        "AKo", "AQo",
    },
    "MP": {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77",
        "AKs", "AQs", "AJs", "ATs", "A9s", "KQs", "KJs", "KTs", "QJs", "QTs", "JTs", "T9s",
        "AKo", "AQo", "AJo", "KQo",
    },
    "CO": {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A5s", "A4s",
        "KQs", "KJs", "KTs", "K9s", "QJs", "QTs", "JTs", "J9s", "T9s", "98s", "87s", "76s",
        "AKo", "AQo", "AJo", "ATo", "KQo", "KJo", "QJo",
    },
    "BTN": {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "QJs", "QTs", "Q9s", "JTs", "J9s",
        "T9s", "T8s", "98s", "97s", "87s", "76s", "65s", "54s",
        "AKo", "AQo", "AJo", "ATo", "A9o", "KQo", "KJo", "KTo", "QJo", "QTo", "JTo",
    },
    "SB": {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A5s", "A4s",
        "KQs", "KJs", "KTs", "K9s", "QJs", "QTs", "JTs", "J9s", "T9s", "98s", "87s", "76s",
        "AKo", "AQo", "AJo", "ATo", "KQo", "KJo", "QJo",
    },
    "BB": {  # used as a default open range when first to act in limped pots
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77",
        "AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
        "AKo", "AQo", "AJo", "KQo",
    },
}

THREE_BET = {
    "UTG": {"AA", "KK", "QQ", "AKs", "AKo"},
    "MP": {"AA", "KK", "QQ", "JJ", "AKs", "AQs", "AKo"},
    "CO": {"AA", "KK", "QQ", "JJ", "AKs", "AQs", "AKo", "A5s"},
    "BTN": {"AA", "KK", "QQ", "JJ", "TT", "AKs", "AQs", "AKo", "A5s", "A4s"},
    "SB": {"AA", "KK", "QQ", "JJ", "AKs", "AQs", "AKo", "A5s"},
    "BB": {"AA", "KK", "QQ", "JJ", "TT", "AKs", "AQs", "AKo", "A5s", "KQs"},
}

CALL_RAISE = {
    "UTG": {"AA", "KK", "QQ", "JJ", "TT", "AKs", "AQs", "AJs", "KQs"},
    "MP": {"JJ", "TT", "99", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "AQo"},
    "CO": {"TT", "99", "88", "77", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs", "AQo", "AJo"},
    "BTN": {"TT", "99", "88", "77", "66", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs", "T9s", "98s", "AQo", "AJo", "KQo"},
    "SB": {"TT", "99", "88", "AQs", "AJs", "KQs", "KJs", "QJs", "AQo"},
    "BB": {  # tightened: OOP defends disciplined, not the kitchen sink
        "TT", "99", "88", "77", "66",
        "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs", "T9s",
        "AQo", "AJo", "KQo",
    },
}


def in_range(hand: str, table: dict, position: str) -> bool:
    return bool(hand) and hand in table.get(position, set())
