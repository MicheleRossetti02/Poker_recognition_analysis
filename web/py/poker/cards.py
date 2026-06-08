"""
Card primitives for the self-contained poker engine.

Notation used everywhere in this package:
- Rank: one of "23456789TJQKA"
- Suit: one of "shdc" (spades, hearts, diamonds, clubs)
- A card string is rank+suit, e.g. "As", "Td", "9c".

Everything here is pure-stdlib so the engine can be tested without any
external dependency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

RANKS = "23456789TJQKA"
SUITS = "shdc"

RANK_VALUE = {r: i for i, r in enumerate(RANKS, start=2)}  # 2..14
VALUE_RANK = {v: r for r, v in RANK_VALUE.items()}


@dataclass(frozen=True)
class Card:
    """An immutable playing card."""

    rank: str
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in RANKS:
            raise ValueError(f"Invalid rank: {self.rank!r}")
        if self.suit not in SUITS:
            raise ValueError(f"Invalid suit: {self.suit!r}")

    @property
    def value(self) -> int:
        return RANK_VALUE[self.rank]

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return f"Card({self})"


def make_card(text: str) -> Card:
    """Parse a 2-char string like 'As' into a Card (suit case-insensitive)."""
    text = text.strip()
    if len(text) != 2:
        raise ValueError(f"Invalid card string: {text!r}")
    rank = text[0].upper()
    suit = text[1].lower()
    return Card(rank, suit)


def full_deck() -> list[Card]:
    return [Card(r, s) for r in RANKS for s in SUITS]


class Deck:
    """A shuffled deck supporting deal and removal of known cards."""

    def __init__(self, rng: random.Random | None = None, exclude: Iterable[Card] = ()):
        self.rng = rng or random.Random()
        excluded = set(exclude)
        self.cards = [c for c in full_deck() if c not in excluded]
        self.rng.shuffle(self.cards)

    def deal(self, n: int = 1) -> list[Card]:
        if n > len(self.cards):
            raise ValueError("Not enough cards left in deck")
        dealt = self.cards[:n]
        self.cards = self.cards[n:]
        return dealt

    def deal_one(self) -> Card:
        return self.deal(1)[0]

    def __len__(self) -> int:
        return len(self.cards)
