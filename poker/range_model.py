"""
Hand-range modelling (P2).

Expand poker notation ("AA", "AKs", "TT+", "A2s+", "KJo") into concrete
two-card combinations, and estimate hero equity against a *range* (a weighted
set of holdings) rather than a single random hand. This is more accurate than
equity-vs-random whenever the opponent's action implies a non-uniform range
(e.g. a big bet ⇒ strong range).
"""

from __future__ import annotations

import random
from itertools import combinations
from typing import Iterable, Sequence

from .cards import Card, RANKS, RANK_VALUE, full_deck
from .evaluator import evaluate

_R = "23456789TJQKA"


def _expand_token(tok: str) -> set[frozenset]:
    """Expand one token like 'AA', 'AKs', 'AJs+', 'TT+', 'KQo' into card pairs.

    Returns a set of frozensets of (rank,suit) keys; suits are abstract here and
    materialised later. We represent each combo as a frozenset of (rank, suit).
    """
    tok = tok.strip()
    plus = tok.endswith("+")
    core = tok[:-1] if plus else tok
    suited = core.endswith("s")
    offsuit = core.endswith("o")
    base = core[:-1] if (suited or offsuit) else core

    if len(base) != 2:
        raise ValueError(f"bad range token: {tok!r}")
    r1, r2 = base[0].upper(), base[1].upper()
    if r1 not in RANK_VALUE or r2 not in RANK_VALUE:
        raise ValueError(f"bad ranks in token: {tok!r}")

    pairs: list[tuple[str, str]] = []
    if r1 == r2:  # pocket pair, possibly "TT+"
        hi = RANK_VALUE[r1]
        tops = [v for v in range(hi, 15)] if plus else [hi]
        for v in tops:
            rank = RANKS[v - 2]
            pairs.append((rank, rank))
    else:
        hi, lo = (r1, r2) if RANK_VALUE[r1] > RANK_VALUE[r2] else (r2, r1)
        los = []
        if plus:
            for v in range(RANK_VALUE[lo], RANK_VALUE[hi]):
                los.append(RANKS[v - 2])
        else:
            los = [lo]
        for l in los:
            pairs.append((hi, l))

    combos: set[frozenset] = set()
    suits = "shdc"
    for a, b in pairs:
        if a == b:
            for s1, s2 in combinations(suits, 2):
                combos.add(frozenset({(a, s1), (a, s2)}))
        else:
            for s1 in suits:
                for s2 in suits:
                    if suited and s1 != s2:
                        continue
                    if offsuit and s1 == s2:
                        continue
                    if s1 == s2 and a == b:
                        continue
                    combo = frozenset({(a, s1), (b, s2)})
                    if len(combo) == 2:
                        combos.add(combo)
    return combos


def expand_range(tokens: Iterable[str]) -> list[tuple[Card, Card]]:
    """Expand a list of tokens into concrete Card pairs (deduplicated)."""
    seen: set[frozenset] = set()
    for tok in tokens:
        seen |= _expand_token(tok)
    out = []
    for combo in seen:
        (r1, s1), (r2, s2) = tuple(combo)
        out.append((Card(r1, s1), Card(r2, s2)))
    return out


def equity_vs_range(
    hole: Sequence[Card],
    villain_range: Sequence[tuple[Card, Card]],
    board: Sequence[Card] = (),
    iterations: int = 1500,
    rng: random.Random | None = None,
) -> float:
    """Hero equity vs a single opponent drawn from `villain_range`.

    Combos that clash with hero/board cards are skipped. Ties count as 1/2.
    """
    if len(hole) != 2:
        raise ValueError("hole must be exactly 2 cards")
    rng = rng or random.Random()
    blocked = set(hole) | set(board)
    legal = [vr for vr in villain_range if vr[0] not in blocked and vr[1] not in blocked
             and vr[0] != vr[1]]
    if not legal:
        return 0.5

    board = list(board)
    need_board = 5 - len(board)
    wins = 0.0
    for _ in range(iterations):
        vh = legal[rng.randrange(len(legal))]
        used = blocked | {vh[0], vh[1]}
        deck = [c for c in full_deck() if c not in used]
        rng.shuffle(deck)
        run = board + deck[:need_board]
        hero = evaluate(list(hole) + run)
        opp = evaluate(list(vh) + run)
        if hero > opp:
            wins += 1.0
        elif hero == opp:
            wins += 0.5
    return wins / iterations


def equity_vs_ranges(
    hole: Sequence[Card],
    villain_ranges: Sequence[Sequence[tuple[Card, Card]]],
    board: Sequence[Card] = (),
    iterations: int = 1500,
    rng: random.Random | None = None,
) -> float:
    """Hero equity vs several opponents, each drawn from its OWN range (N9).

    More accurate multiway than equity-vs-random: each villain samples from a
    distinct holding range. Combos clashing with hero/board/other villains are
    re-drawn; ties split.
    """
    if len(hole) != 2:
        raise ValueError("hole must be exactly 2 cards")
    if not villain_ranges:
        raise ValueError("need at least one villain range")
    rng = rng or random.Random()
    base_blocked = set(hole) | set(board)
    board = list(board)
    need_board = 5 - len(board)
    wins = 0.0

    for _ in range(iterations):
        used = set(base_blocked)
        opp_hands = []
        ok = True
        for vr in villain_ranges:
            # try a few times to find a non-clashing combo
            chosen = None
            for _try in range(12):
                cand = vr[rng.randrange(len(vr))]
                if cand[0] in used or cand[1] in used or cand[0] == cand[1]:
                    continue
                chosen = cand
                break
            if chosen is None:
                ok = False
                break
            used |= {chosen[0], chosen[1]}
            opp_hands.append(chosen)
        if not ok:
            wins += 0.5
            continue

        deck = [c for c in full_deck() if c not in used]
        rng.shuffle(deck)
        run = board + deck[:need_board]
        hero = evaluate(list(hole) + run)
        best_opp = max(evaluate(list(oh) + run) for oh in opp_hands)
        if hero > best_opp:
            wins += 1.0
        elif hero == best_opp:
            wins += 0.5
    return wins / iterations


# A compact "strong betting range" used as a default continuing range when an
# opponent commits a lot of chips (range disadvantage modelling).
STRONG_BETTING_RANGE = [
    "AA", "KK", "QQ", "JJ", "TT", "99",
    "AKs", "AQs", "AJs", "KQs", "AKo", "AQo",
]
