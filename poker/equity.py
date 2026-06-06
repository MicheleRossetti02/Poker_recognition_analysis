"""
Monte Carlo equity estimation.

Given hero hole cards, a (possibly empty) board and a number of opponents,
estimate hero's probability of winning (ties counted as fractional wins) by
random rollout. Pure-stdlib, deterministic when a seeded rng is passed.
"""

from __future__ import annotations

import random
from typing import Sequence

from .cards import Card, full_deck
from .evaluator import evaluate


def equity(
    hole: Sequence[Card],
    board: Sequence[Card] = (),
    opponents: int = 1,
    iterations: int = 2000,
    rng: random.Random | None = None,
) -> float:
    """Return hero equity in [0, 1] vs `opponents` random hands.

    `iterations` rollouts are run; each deals the missing board and opponent
    hole cards from the remaining deck.
    """
    if len(hole) != 2:
        raise ValueError("hole must contain exactly 2 cards")
    if opponents < 1:
        raise ValueError("opponents must be >= 1")

    rng = rng or random.Random()
    known = set(hole) | set(board)
    available = [c for c in full_deck() if c not in known]
    board = list(board)
    need_board = 5 - len(board)

    wins = 0.0
    for _ in range(iterations):
        rng.shuffle(available)
        idx = 0
        sampled_board = board + available[idx : idx + need_board]
        idx += need_board

        opp_hands = []
        for _ in range(opponents):
            opp_hands.append(available[idx : idx + 2])
            idx += 2

        hero_score = evaluate(list(hole) + sampled_board)
        best_opp = max(evaluate(oh + sampled_board) for oh in opp_hands)

        if hero_score > best_opp:
            wins += 1.0
        elif hero_score == best_opp:
            wins += 0.5  # split

    return wins / iterations
