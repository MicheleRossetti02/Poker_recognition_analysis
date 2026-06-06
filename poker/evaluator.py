"""
Pure-python 7-card hand evaluator.

Returns a comparable score: higher score == better hand. The score is a
tuple (category, *tiebreakers) so two hands can be compared directly with
standard tuple ordering.

Categories (high to low):
    8 Straight flush
    7 Four of a kind
    6 Full house
    5 Flush
    4 Straight
    3 Three of a kind
    2 Two pair
    1 One pair
    0 High card

No external dependencies: fast enough for tens of thousands of Monte Carlo
samples per equity call.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Iterable, Sequence

from .cards import Card

CATEGORY_NAMES = {
    8: "Straight Flush",
    7: "Four of a Kind",
    6: "Full House",
    5: "Flush",
    4: "Straight",
    3: "Three of a Kind",
    2: "Two Pair",
    1: "One Pair",
    0: "High Card",
}

HandScore = tuple


def _straight_high(values: Iterable[int]) -> int | None:
    """Return the high card value of a straight from a set of values, else None.

    Treats Ace (14) as also low (1) for the wheel A-2-3-4-5.
    """
    vs = set(values)
    if 14 in vs:
        vs.add(1)
    ordered = sorted(vs, reverse=True)
    run = 1
    for i in range(1, len(ordered)):
        if ordered[i] == ordered[i - 1] - 1:
            run += 1
            if run >= 5:
                return ordered[i] + 4
        else:
            run = 1
    return None


def _score_5(cards: Sequence[Card]) -> HandScore:
    values = sorted((c.value for c in cards), reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1
    straight_high = _straight_high(values)

    counts = Counter(values)
    # Sort by (count, value) descending so pairs/trips lead the tiebreakers.
    by_count = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    pattern = [cnt for _val, cnt in by_count]
    ordered_vals = [val for val, _cnt in by_count]

    if is_flush and straight_high:
        return (8, straight_high)
    if pattern[0] == 4:
        return (7, ordered_vals[0], ordered_vals[1])
    if pattern[0] == 3 and pattern[1] >= 2:
        return (6, ordered_vals[0], ordered_vals[1])
    if is_flush:
        return (5, *values)
    if straight_high:
        return (4, straight_high)
    if pattern[0] == 3:
        return (3, ordered_vals[0], *ordered_vals[1:])
    if pattern[0] == 2 and pattern[1] == 2:
        return (2, ordered_vals[0], ordered_vals[1], ordered_vals[2])
    if pattern[0] == 2:
        return (1, ordered_vals[0], *ordered_vals[1:])
    return (0, *values)


def _count_score(values: list[int]) -> HandScore:
    """Best non-straight, non-flush score from a multiset of rank values."""
    counts = Counter(values)
    # (count, value) descending so pairs/trips lead.
    by_count = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    pattern = [cnt for _v, cnt in by_count]
    ordered = [v for v, _c in by_count]
    all_desc = sorted(values, reverse=True)

    if pattern[0] == 4:
        quad = ordered[0]
        kicker = max(v for v in values if v != quad)
        return (7, quad, kicker)
    if pattern[0] == 3 and pattern[1] >= 2:
        trips = ordered[0]
        pair = max(v for v, c in by_count if v != trips and c >= 2)
        return (6, trips, pair)
    if pattern[0] == 3:
        trips = ordered[0]
        kick = sorted((v for v in values if v != trips), reverse=True)[:2]
        return (3, trips, *kick)
    if pattern[0] == 2 and pattern[1] == 2:
        hp, lp = ordered[0], ordered[1]
        kicker = max(v for v in values if v != hp and v != lp)
        return (2, hp, lp, kicker)
    if pattern[0] == 2:
        pair = ordered[0]
        kick = sorted((v for v in values if v != pair), reverse=True)[:3]
        return (1, pair, *kick)
    return (0, *all_desc[:5])


def evaluate7(cards: Sequence[Card]) -> HandScore:
    """Direct best-of-7 (or 5/6) score without iterating 5-card combinations.

    Returns the max over the candidate categories, which is correct because the
    score's leading element encodes the category rank.
    """
    values = [c.value for c in cards]
    candidates = [_count_score(values)]

    # Straight (use the full value set, ace low handled by _straight_high).
    sh = _straight_high(values)
    if sh:
        candidates.append((4, sh))

    # Flush / straight flush within any suit holding >= 5 cards.
    by_suit: dict[str, list[int]] = {}
    for c in cards:
        by_suit.setdefault(c.suit, []).append(c.value)
    for suit_vals in by_suit.values():
        if len(suit_vals) >= 5:
            top5 = sorted(suit_vals, reverse=True)[:5]
            candidates.append((5, *top5))
            sf = _straight_high(suit_vals)
            if sf:
                candidates.append((8, sf))

    return max(candidates)


def evaluate(cards: Sequence[Card]) -> HandScore:
    """Best 5-card score from 5, 6 or 7 cards. Higher is better."""
    n = len(cards)
    if n < 5:
        raise ValueError("Need at least 5 cards to evaluate")
    if n == 5:
        return _score_5(cards)
    return evaluate7(cards)


def category_name(score: HandScore) -> str:
    return CATEGORY_NAMES.get(score[0], "Unknown")
