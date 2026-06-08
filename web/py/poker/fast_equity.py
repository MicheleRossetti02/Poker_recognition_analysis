"""
Vectorised Monte Carlo equity with numpy (N2).

A batched 7-card evaluator that scores thousands of hands at once, producing a
single int64 per hand whose ordering matches the pure-python `evaluate7`
tuple ordering. Used to run very large simulations (50k+ trials) in a fraction
of the time of the scalar path.

Score packing (high bits first): category(4b) then 5 tiebreak ranks (4b each).
Higher int == better hand, consistent with evaluator.evaluate7.
"""

from __future__ import annotations

import random
from typing import Sequence

import numpy as np

from .cards import Card, RANK_VALUE, full_deck

# Card index 0..51 -> rank value (2..14) and suit (0..3).
_DECK = full_deck()
_CARD_INDEX = {c: i for i, c in enumerate(_DECK)}
_IDX_RANK = np.array([c.value for c in _DECK], dtype=np.int64)
_IDX_SUIT = np.array(["shdc".index(c.suit) for c in _DECK], dtype=np.int64)


def _straight_high_batch(present: np.ndarray) -> np.ndarray:
    """present: (N,15) bool over rank values 0..14 (1 used as ace-low).

    Returns (N,) highest straight top card, 0 if none.
    """
    n = present.shape[0]
    best = np.zeros(n, dtype=np.int64)
    for high in range(14, 4, -1):  # 14..5
        window = present[:, high - 4:high + 1]  # 5 consecutive ranks
        hit = window.all(axis=1)
        best = np.where((best == 0) & hit, high, best)
    return best


def _top_n_ranks(mask15: np.ndarray, n: int) -> np.ndarray:
    """mask15: (N,15) bool. Return (N,n) of the n highest set rank values, 0-padded."""
    N = mask15.shape[0]
    out = np.zeros((N, n), dtype=np.int64)
    filled = np.zeros(N, dtype=np.int64)
    for rank in range(14, 1, -1):
        have = mask15[:, rank] & (filled < n)
        idx = np.where(have)[0]
        if idx.size:
            out[idx, filled[idx]] = rank
            filled[idx] += 1
    return out


def score7_batch(card_idx: np.ndarray) -> np.ndarray:
    """card_idx: (N,7) int in 0..51 (distinct per row). Returns (N,) int64 scores."""
    ranks = _IDX_RANK[card_idx]           # (N,7) values 2..14
    suits = _IDX_SUIT[card_idx]           # (N,7) 0..3
    N = card_idx.shape[0]

    # rank counts (N,15)
    rank_counts = np.zeros((N, 15), dtype=np.int64)
    np.add.at(rank_counts, (np.arange(N)[:, None], ranks), 1)
    present = rank_counts > 0

    # suit counts (N,4)
    suit_counts = np.zeros((N, 4), dtype=np.int64)
    np.add.at(suit_counts, (np.arange(N)[:, None], suits), 1)
    flush_suit = suit_counts.argmax(axis=1)
    has_flush = suit_counts.max(axis=1) >= 5

    # ranks restricted to the flush suit
    in_flush = suits == flush_suit[:, None]            # (N,7)
    flush_present = np.zeros((N, 15), dtype=bool)
    for k in range(7):
        sel = in_flush[:, k]
        flush_present[np.where(sel)[0], ranks[sel, k]] = True

    # straights
    pres_ace = present.copy()
    pres_ace[:, 1] = present[:, 14]
    straight_high = _straight_high_batch(pres_ace)

    fp_ace = flush_present.copy()
    fp_ace[:, 1] = flush_present[:, 14]
    sf_high = np.where(has_flush, _straight_high_batch(fp_ace), 0)

    # count patterns
    has4 = rank_counts == 4
    has3 = rank_counts == 3
    has2 = rank_counts == 2
    rank_vals = np.arange(15)

    def highest(mask):
        masked = np.where(mask, rank_vals, 0)
        return masked.max(axis=1)

    quad = highest(has4)
    n_trips = has3.sum(axis=1)
    n_pairs = has2.sum(axis=1)
    trips = highest(has3)

    # top pairs (two highest pair ranks)
    pair_top = _top_n_ranks(has2, 2)   # (N,2)
    # kickers (top ranks excluding used ones) computed per category below.

    cat = np.zeros(N, dtype=np.int64)
    tb = np.zeros((N, 5), dtype=np.int64)

    # high card / flush base: top5 of all ranks
    top5_all = _top_n_ranks(present, 5)
    top5_flush = _top_n_ranks(flush_present, 5)

    # Start: high card
    cat[:] = 0
    tb[:] = top5_all

    # one pair
    m = (n_pairs == 1) & (n_trips == 0) & (quad == 0)
    if m.any():
        pair = highest(has2)
        kick = _top_n_ranks(present & ~(rank_vals == pair[:, None]), 3)
        cat = np.where(m, 1, cat)
        tb[m] = np.column_stack([pair, kick[:, 0], kick[:, 1], kick[:, 2], np.zeros(N, dtype=np.int64)])[m]

    # two pair
    m = (n_pairs >= 2) & (n_trips == 0) & (quad == 0)
    if m.any():
        hp = pair_top[:, 0]
        lp = pair_top[:, 1]
        used = (rank_vals == hp[:, None]) | (rank_vals == lp[:, None])
        kick = _top_n_ranks(present & ~used, 1)
        cat = np.where(m, 2, cat)
        tb[m] = np.column_stack([hp, lp, kick[:, 0], np.zeros(N), np.zeros(N)]).astype(np.int64)[m]

    # trips
    m = (n_trips == 1) & (n_pairs == 0) & (quad == 0)
    if m.any():
        kick = _top_n_ranks(present & ~(rank_vals == trips[:, None]), 2)
        cat = np.where(m, 3, cat)
        tb[m] = np.column_stack([trips, kick[:, 0], kick[:, 1], np.zeros(N), np.zeros(N)]).astype(np.int64)[m]

    # straight
    m = (straight_high > 0)
    cat = np.where(m & (cat < 4), 4, cat)
    tb[m & (cat == 4)] = np.column_stack(
        [straight_high, np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N)]).astype(np.int64)[m & (cat == 4)]

    # flush
    m = has_flush
    better = m & (cat < 5)
    cat = np.where(better, 5, cat)
    tb[better] = top5_flush[better]

    # full house (trips + another pair/trips)
    m = (n_trips >= 1) & ((n_pairs >= 1) | (n_trips >= 2))
    if m.any():
        # best pair among ranks with count>=2 excluding the trips rank
        pair_mask = (rank_counts >= 2) & ~(rank_vals == trips[:, None])
        fh_pair = highest(pair_mask)
        cat = np.where(m, 6, cat)
        tb[m] = np.column_stack([trips, fh_pair, np.zeros(N), np.zeros(N), np.zeros(N)]).astype(np.int64)[m]

    # quads
    m = (quad > 0)
    if m.any():
        kick = highest(present & ~(rank_vals == quad[:, None]))
        cat = np.where(m, 7, cat)
        tb[m] = np.column_stack([quad, kick, np.zeros(N), np.zeros(N), np.zeros(N)]).astype(np.int64)[m]

    # straight flush
    m = sf_high > 0
    cat = np.where(m, 8, cat)
    tb[m] = np.column_stack([sf_high, np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N)]).astype(np.int64)[m]

    score = (cat << 20) | (tb[:, 0] << 16) | (tb[:, 1] << 12) | (tb[:, 2] << 8) \
        | (tb[:, 3] << 4) | tb[:, 4]
    return score


def equity_fast(
    hole: Sequence[Card],
    board: Sequence[Card] = (),
    opponents: int = 1,
    iterations: int = 20000,
    seed: int | None = None,
) -> float:
    """Vectorised hero equity vs `opponents` random hands. Ties count 1/2."""
    if len(hole) != 2:
        raise ValueError("hole must be exactly 2 cards")
    rng = np.random.default_rng(seed)

    known = set(hole) | set(board)
    avail = np.array([_CARD_INDEX[c] for c in _DECK if c not in known], dtype=np.int64)
    hole_idx = np.array([_CARD_INDEX[c] for c in hole], dtype=np.int64)
    board_idx = np.array([_CARD_INDEX[c] for c in board], dtype=np.int64)
    need_board = 5 - len(board)
    draws = need_board + 2 * opponents

    N = iterations
    # sample `draws` distinct cards per trial via argsort of random keys
    keys = rng.random((N, avail.size))
    pick = np.argsort(keys, axis=1)[:, :draws]
    sampled = avail[pick]                       # (N, draws)

    board_full = np.broadcast_to(board_idx, (N, len(board)))
    new_board = sampled[:, :need_board]
    full_board = np.concatenate([board_full, new_board], axis=1)  # (N,5)

    hero_cards = np.concatenate(
        [np.broadcast_to(hole_idx, (N, 2)), full_board], axis=1)  # (N,7)
    hero_score = score7_batch(hero_cards)

    best_opp = np.full(N, -1, dtype=np.int64)
    off = need_board
    for o in range(opponents):
        opp_hole = sampled[:, off:off + 2]
        off += 2
        opp_cards = np.concatenate([opp_hole, full_board], axis=1)
        best_opp = np.maximum(best_opp, score7_batch(opp_cards))

    wins = (hero_score > best_opp).sum()
    ties = (hero_score == best_opp).sum()
    return float(wins + 0.5 * ties) / N
