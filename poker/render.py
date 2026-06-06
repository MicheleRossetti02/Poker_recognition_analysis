"""Terminal rendering helpers (pure-stdlib, no external deps)."""

from __future__ import annotations

from .cards import Card

_SUIT_GLYPH = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
_RED = "\033[31m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"


def card_str(c: Card, color: bool = True) -> str:
    g = _SUIT_GLYPH[c.suit]
    text = f"{c.rank}{g}"
    if color and c.suit in ("h", "d"):
        return f"{_RED}{text}{_RESET}"
    return text


def cards_str(cards, color: bool = True) -> str:
    if not cards:
        return "--"
    return " ".join(card_str(c, color) for c in cards)


def hidden(n: int = 2) -> str:
    return " ".join("🂠" for _ in range(n))


def banner(text: str) -> str:
    line = "═" * (len(text) + 2)
    return f"{_BOLD}╔{line}╗\n║ {text} ║\n╚{line}╝{_RESET}"


def action_color(action: str) -> str:
    a = action.lower()
    if "raise" in a or "bet" in a:
        return f"{_GREEN}{action}{_RESET}"
    if "fold" in a:
        return f"{_RED}{action}{_RESET}"
    if "call" in a or "check" in a:
        return f"{_YELLOW}{action}{_RESET}"
    return action
