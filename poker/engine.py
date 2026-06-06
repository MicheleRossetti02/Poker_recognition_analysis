"""
Decision engine.

Combines a preflop range layer with a postflop equity/pot-odds layer to return
a structured decision: action, sizing (in chips), equity estimate, confidence
and a short human-readable reason.

This is the single source of truth for "what should hero do" and is used both
by the bots in the simulator and by the live overlay coach.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Sequence

from .cards import Card
from .equity import equity
from .ranges import CALL_RAISE, OPEN_RAISE, THREE_BET, in_range, normalize_hand

Action = str  # "fold" | "check" | "call" | "raise"

# ── Engine tuning (P4: stronger, less exploitable) ────────────────────
EQUITY_ITERS = 600
VALUE_THRESHOLD = 0.56        # equity to value-bet/raise heads-up
VALUE_PER_OPP = 0.045         # tighten value range per extra opponent
SEMIBLUFF_LO = 0.30           # min equity to consider a bluff (fold equity + outs)
SEMIBLUFF_HI = 0.52           # below value but enough to barrel
BLUFF_FREQ = 0.30             # how often to fire a bet as a bluff when checked to
BLUFF_RAISE_FREQ = 0.12       # how often to turn a marginal hand into a raise
CALL_MARGIN = 0.0             # extra equity over pot-odds required to call
THREE_BET_BLUFF = {           # suited wheel/blocker hands used as 3bet bluffs
    "CO": {"A5s", "A4s", "KJs"},
    "BTN": {"A5s", "A4s", "A3s", "KJs", "KTs", "QTs"},
    "SB": {"A5s", "A4s", "KJs"},
    "BB": {"A5s", "A4s", "K9s"},
}


def _rng(s) -> random.Random:
    return s.rng if s.rng is not None else random


# When True, postflop equity uses the numpy-vectorised path (much faster for
# large simulations). Default False keeps the scalar, seedable path used by the
# deterministic test-suite.
USE_FAST_EQUITY = False

# N3: when True, equity facing a bet is computed vs a *continuing range* rather
# than vs a random hand, modelling that bettors hold stronger cards. More
# accurate, a bit slower; off by default to keep the fast sims fast.
USE_RANGE_EQUITY = False


def _range_equity_vs_bettor(hole, board, rng):
    """Equity vs a plausible value/betting range (N3). Falls back gracefully."""
    try:
        from .range_model import equity_vs_range, expand_range, STRONG_BETTING_RANGE
        vr = expand_range(STRONG_BETTING_RANGE)
        return equity_vs_range(hole, vr, board, iterations=800, rng=rng)
    except Exception:
        return None


def _equity(hole, board, opponents, iterations, rng):
    if USE_FAST_EQUITY:
        try:
            from .fast_equity import equity_fast
            return equity_fast(hole, board, opponents=opponents,
                               iterations=max(iterations, 1000))
        except Exception:
            pass
    return equity(hole, board, opponents=opponents, iterations=iterations, rng=rng)


@dataclass
class Decision:
    action: Action
    amount: float = 0.0          # total chips to put in this action (for raise: target to-call)
    equity: float = 0.0
    confidence: float = 0.0
    reason: str = ""

    def label(self) -> str:
        if self.action == "raise":
            return f"RAISE to {self.amount:.0f}"
        if self.action == "call":
            return f"CALL {self.amount:.0f}"
        return self.action.upper()


@dataclass
class Situation:
    """Everything the engine needs to make a decision."""

    hole: Sequence[Card]
    board: Sequence[Card]
    position: str                 # UTG/MP/CO/BTN/SB/BB
    street: str                   # preflop/flop/turn/river
    pot: float                    # chips already in the pot
    to_call: float                # chips hero must add to continue
    hero_stack: float             # hero remaining chips
    big_blind: float = 1.0
    num_opponents: int = 1
    facing_raise: bool = False    # preflop: someone has raised before hero
    street_invested: float = 0.0  # chips hero already put in THIS street
    rng: random.Random | None = field(default=None)


def _confidence(equity_val: float, threshold: float) -> float:
    """How far equity sits from the break-even point, mapped to [0.5, 0.99]."""
    gap = abs(equity_val - threshold)
    return round(min(0.99, 0.5 + gap * 1.6), 2)


def decide(s: Situation) -> Decision:
    if len(s.hole) != 2:
        return Decision("fold", reason="carte hero non valide")

    if s.street == "preflop":
        return _decide_preflop(s)
    return _decide_postflop(s)


def _decide_preflop(s: Situation) -> Decision:
    hand = normalize_hand(s.hole[0], s.hole[1])
    if hand is None:
        return Decision("fold", reason="mano non riconosciuta")

    if s.facing_raise:
        if in_range(hand, THREE_BET, s.position):
            size = max(s.to_call * 3.0, 3 * s.big_blind)
            return Decision("raise", min(size, s.hero_stack), 0.0, 0.85,
                            f"{hand}: 3bet value da {s.position}")
        # Balanced 3bet bluffs with blockers (suited wheel aces, etc.)
        if hand in THREE_BET_BLUFF.get(s.position, set()) and _rng(s).random() < 0.55:
            size = max(s.to_call * 3.0, 3 * s.big_blind)
            return Decision("raise", min(size, s.hero_stack), 0.0, 0.6,
                            f"{hand}: 3bet bluff (blocker) da {s.position}")
        if in_range(hand, CALL_RAISE, s.position):
            return Decision("call", s.to_call, 0.0, 0.7, f"{hand}: flat call vs raise")
        return Decision("fold", reason=f"{hand}: fuori range vs raise da {s.position}")

    # No raise before us
    if in_range(hand, OPEN_RAISE, s.position):
        size = max(2.5 * s.big_blind, s.to_call * 2.5)
        return Decision("raise", min(size, s.hero_stack), 0.0, 0.8,
                        f"{hand}: open raise da {s.position}")
    if s.to_call <= 0:
        return Decision("check", reason=f"{hand}: check (nessuna puntata)")
    return Decision("fold", reason=f"{hand}: fuori range open da {s.position}")


OOP_POSITIONS = {"SB", "BB", "UTG"}   # out of position postflop (act early)


def _decide_postflop(s: Situation) -> Decision:
    eq = _equity(s.hole, s.board, max(1, s.num_opponents), EQUITY_ITERS, s.rng)
    rng = _rng(s)

    # N1: out-of-position discipline. OOP we realise less equity, bluffs get
    # floated/called more, so tighten value and cut bluffing.
    oop = s.position in OOP_POSITIONS
    oop_value_bump = 0.04 if oop else 0.0
    oop_bluff_mult = 0.45 if oop else 1.0

    pot_odds = s.to_call / (s.pot + s.to_call) if s.to_call > 0 else 0.0
    # Value range tightens vs more opponents (less folds-out, more showdowns).
    value_threshold = VALUE_THRESHOLD + VALUE_PER_OPP * max(0, s.num_opponents - 1) + oop_value_bump
    # Bluffs work worse multiway and out of position.
    bluff_freq = BLUFF_FREQ / max(1, s.num_opponents) * oop_bluff_mult

    def cap(size: float) -> float:
        return round(min(max(size, s.big_blind), s.hero_stack), 1)

    if s.to_call <= 0:
        # Checked to us: value bet, bluff, or check behind.
        if eq >= value_threshold:
            size = cap(0.7 * s.pot)
            return Decision("raise", size, eq, _confidence(eq, value_threshold),
                            f"value bet {size:.0f}: equity {eq:.0%}")
        if SEMIBLUFF_LO <= eq <= SEMIBLUFF_HI and rng.random() < bluff_freq:
            size = cap(0.5 * s.pot)
            return Decision("raise", size, eq, 0.55,
                            f"(semi)bluff {size:.0f}: equity {eq:.0%} + fold equity")
        return Decision("check", 0.0, eq, _confidence(eq, 0.40),
                        f"check: equity {eq:.0%}")

    # Facing a bet. Equity here is vs a RANDOM hand, but a player betting big
    # has a much stronger range, so we penalise relative to the bet size.
    commit_ratio = s.to_call / max(s.pot, s.big_blind)          # bet-to-pot
    # N3: replace the flat penalty with real equity-vs-range when a big bet
    # comes in (the spot where range disadvantage matters most).
    range_penalty = 0.13 * min(1.5, commit_ratio)               # villain stronger
    if USE_RANGE_EQUITY and commit_ratio >= 0.5:
        req = _range_equity_vs_bettor(s.hole, s.board, rng)
        if req is not None:
            eq = req                       # eq now already accounts for villain strength
            range_penalty = 0.0
    oop_call_penalty = 0.03 if oop else 0.0                     # realise less OOP
    needed_call = pot_odds + range_penalty + CALL_MARGIN + oop_call_penalty
    needed_raise = value_threshold + 0.15 + 0.15 * min(1.5, commit_ratio)

    # A single, capped pot-sized raise — never an uncapped re-raise spiral.
    call_total = s.street_invested + s.to_call
    raise_target = cap(call_total + 0.8 * (s.pot + s.to_call))

    if eq >= needed_raise and s.hero_stack > s.to_call and raise_target > call_total:
        return Decision("raise", raise_target, eq, _confidence(eq, needed_raise),
                        f"raise value {raise_target:.0f}: equity {eq:.0%} (need {needed_raise:.0%})")
    # Bluff-raise only for cheap bets (low commit_ratio) with semibluff equity.
    if (SEMIBLUFF_LO <= eq <= SEMIBLUFF_HI and commit_ratio <= 0.6
            and s.hero_stack > 3 * s.to_call and raise_target > call_total
            and rng.random() < BLUFF_RAISE_FREQ / max(1, s.num_opponents) * oop_bluff_mult):
        return Decision("raise", raise_target, eq, 0.52,
                        f"bluff-raise {raise_target:.0f}: semibluff {eq:.0%}")
    if eq >= needed_call:
        return Decision("call", s.to_call, eq, _confidence(eq, needed_call),
                        f"call: equity {eq:.0%} >= need {needed_call:.0%} (odds {pot_odds:.0%})")
    return Decision("fold", 0.0, eq, _confidence(eq, needed_call),
                    f"fold: equity {eq:.0%} < need {needed_call:.0%}")
