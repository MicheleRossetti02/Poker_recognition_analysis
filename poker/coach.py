"""
Didactic coach helpers for the web/UI layer.

These functions explain a spot without changing the engine's action logic:
made hand, draw labels, outs-to-improve and a small equity breakdown.
"""

from __future__ import annotations

import random
from collections import Counter
from itertools import combinations
from typing import Sequence

from .cards import Card, full_deck
from .equity import equity
from .evaluator import category_name, evaluate


def _available_cards(hole: Sequence[Card], board: Sequence[Card]) -> list[Card]:
    used = set(hole) | set(board)
    return [c for c in full_deck() if c not in used]


def _straight_outs(hole: Sequence[Card], board: Sequence[Card]) -> list[Card]:
    if len(board) < 3:
        return []
    current = evaluate(list(hole) + list(board))
    if current[0] >= 4:
        return []
    outs = []
    for card in _available_cards(hole, board):
        score = evaluate(list(hole) + list(board) + [card])
        if score[0] >= 4:
            outs.append(card)
    return outs


def _draw_labels(hole: Sequence[Card], board: Sequence[Card]) -> list[str]:
    cards = list(hole) + list(board)
    labels: list[str] = []
    if len(cards) < 5:
        return labels

    suit_counts = Counter(c.suit for c in cards)
    best_suit = max(suit_counts.values(), default=0)
    if best_suit >= 4:
        labels.append("flush draw")
    elif len(board) == 3 and best_suit == 3:
        labels.append("backdoor flush draw")

    straight_outs = _straight_outs(hole, board)
    straight_out_count = len(straight_outs)
    if straight_out_count >= 8:
        labels.append("open-ended straight draw")
    elif straight_out_count >= 4:
        labels.append("gutshot straight draw")

    current = evaluate(cards)
    if current[0] == 0 and board:
        board_high = max(c.value for c in board)
        overcards = sum(1 for c in hole if c.value > board_high)
        if overcards == 2:
            labels.append("two overcards")
        elif overcards == 1:
            labels.append("one overcard")

    return labels


def _outs_to_improve(hole: Sequence[Card], board: Sequence[Card]) -> list[Card]:
    if len(board) >= 5 or len(board) < 3:
        return []
    current = evaluate(list(hole) + list(board))
    outs = []
    for card in _available_cards(hole, board):
        if evaluate(list(hole) + list(board) + [card]) > current:
            outs.append(card)
    return outs


def _improve_by_river_pct(hole: Sequence[Card], board: Sequence[Card]) -> float:
    if len(board) >= 5 or len(board) < 3:
        return 0.0
    current = evaluate(list(hole) + list(board))
    available = _available_cards(hole, board)
    if len(board) == 4:
        hits = sum(1 for card in available if evaluate(list(hole) + list(board) + [card]) > current)
        return hits / len(available) if available else 0.0

    total = 0
    hits = 0
    for c1, c2 in combinations(available, 2):
        total += 1
        if evaluate(list(hole) + list(board) + [c1, c2]) > current:
            hits += 1
    return hits / total if total else 0.0


def equity_breakdown(
    hole: Sequence[Card],
    board: Sequence[Card] = (),
    opponents: int = 1,
    iterations: int = 250,
    rng: random.Random | None = None,
) -> dict[str, float]:
    """Win/tie/loss percentages for the current spot."""
    if len(hole) != 2:
        raise ValueError("hole must contain exactly 2 cards")
    if opponents < 1:
        raise ValueError("opponents must be >= 1")

    rng = rng or random.Random()
    known = set(hole) | set(board)
    available = [c for c in full_deck() if c not in known]
    board = list(board)
    need_board = 5 - len(board)

    wins = 0
    ties = 0
    for _ in range(iterations):
        rng.shuffle(available)
        idx = 0
        sampled_board = board + available[idx: idx + need_board]
        idx += need_board

        opp_hands = []
        for _ in range(opponents):
            opp_hands.append(available[idx: idx + 2])
            idx += 2

        hero_score = evaluate(list(hole) + sampled_board)
        best_opp = max(evaluate(opp + sampled_board) for opp in opp_hands)
        if hero_score > best_opp:
            wins += 1
        elif hero_score == best_opp:
            ties += 1

    win_pct = wins / iterations if iterations else 0.0
    tie_pct = ties / iterations if iterations else 0.0
    lose_pct = max(0.0, 1.0 - win_pct - tie_pct)
    return {
        "equity": win_pct + tie_pct * 0.5,
        "win_pct": win_pct,
        "tie_pct": tie_pct,
        "lose_pct": lose_pct,
    }


def coach_insights(
    hole: Sequence[Card],
    board: Sequence[Card],
    opponents: int,
    facing_raise: bool = False,
    iterations: int = 250,
    rng: random.Random | None = None,
) -> dict[str, object]:
    """Explain a spot for the didactic coach UI."""
    cards = list(hole) + list(board)
    current_name = category_name(evaluate(cards)) if len(cards) >= 5 else "Preflop"
    outs = _outs_to_improve(hole, board)
    breakdown = equity_breakdown(hole, board, opponents=max(1, opponents), iterations=iterations, rng=rng)

    out = {
        "made_hand": current_name,
        "draws": _draw_labels(hole, board),
        "outs": {
            "count": len(outs),
            "next_card_pct": (len(outs) / len(_available_cards(hole, board))) if len(board) < 5 else 0.0,
            "by_river_pct": _improve_by_river_pct(hole, board),
        },
        "equity_breakdown": breakdown,
    }

    if opponents > 1:
        out["heads_up_equity"] = equity(hole, board, opponents=1, iterations=max(150, iterations), rng=rng)

    if facing_raise and board:
        try:
            from .engine import _range_equity_vs_bettor

            range_eq = _range_equity_vs_bettor(hole, board, rng)
            if range_eq is not None:
                out["vs_betting_range_equity"] = range_eq
        except Exception:
            pass

    return out
