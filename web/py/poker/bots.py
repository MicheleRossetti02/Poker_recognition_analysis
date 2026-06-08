"""
Strategy implementations plugged into the table.

Every strategy is `act(ActionView) -> (action, amount)` where for a raise the
amount is the TOTAL chips committed-this-street the player wants to reach.

- engine_bot:   solid GTO-ish play driven by the decision engine.
- tag_bot:      tight-aggressive (folds marginal, bets strong).
- lag_bot:      loose-aggressive (wider, more bluffs).
- station_bot:  calling station (rarely folds, rarely raises).
- rock_bot:     very tight / passive.
- random_bot:   noise baseline.
- human_strategy: defers to a prompt callback (for manual play / overlay).
"""

from __future__ import annotations

import random

from .engine import Situation, decide, _equity as _eq
from .equity import equity
from .ranges import OPEN_RAISE, in_range, normalize_hand
from .table import ActionView


def _to_situation(v: ActionView) -> Situation:
    return Situation(
        hole=v.hole,
        board=v.board,
        position=v.position,
        street=v.street,
        pot=v.pot,
        to_call=v.to_call,
        hero_stack=v.hero_stack,
        big_blind=v.big_blind,
        num_opponents=max(1, v.num_active_opponents),
        facing_raise=v.facing_raise,
        street_invested=v.street_invested,
        rng=v.rng,
    )


def engine_bot(v: ActionView) -> tuple[str, float]:
    d = decide(_to_situation(v))
    if d.action == "raise":
        # engine amount is a target "to" level on this street.
        return "raise", d.amount
    if d.action == "call":
        return "call", v.to_call
    if d.action == "check":
        return "check", 0.0
    return "fold", 0.0


def _equity_decision(v: ActionView, fold_eq: float, raise_eq: float,
                     bluff_freq: float, raise_to: float) -> tuple[str, float]:
    if v.street == "preflop":
        hand = normalize_hand(v.hole[0], v.hole[1])
        playable = hand in OPEN_RAISE.get(v.position, set()) or (
            hand and (hand[0] == hand[1] or hand in OPEN_RAISE["BTN"])
        )
        if v.to_call <= 0:
            if playable and v.rng.random() < 0.6:
                return "raise", max(v.big_blind * 2.5, v.to_call * 2.5)
            return "check", 0.0
        if playable:
            if v.rng.random() < bluff_freq:
                return "raise", v.to_call + raise_to * v.big_blind
            return "call", v.to_call
        return "fold", 0.0

    eq = _eq(v.hole, v.board, max(1, v.num_active_opponents), 600, v.rng)
    if v.to_call <= 0:
        if eq >= raise_eq or v.rng.random() < bluff_freq:
            return "raise", round(0.6 * v.pot, 1)
        return "check", 0.0
    pot_odds = v.to_call / (v.pot + v.to_call)
    if eq >= raise_eq and v.hero_stack > v.to_call:
        return "raise", round(v.pot + v.to_call, 1)
    if eq >= max(fold_eq, pot_odds):
        return "call", v.to_call
    return "fold", 0.0


def tag_bot(v: ActionView) -> tuple[str, float]:
    return _equity_decision(v, fold_eq=0.45, raise_eq=0.62, bluff_freq=0.08, raise_to=3)


def lag_bot(v: ActionView) -> tuple[str, float]:
    return _equity_decision(v, fold_eq=0.30, raise_eq=0.52, bluff_freq=0.22, raise_to=3)


def station_bot(v: ActionView) -> tuple[str, float]:
    # Calls almost anything with any equity, rarely raises.
    if v.street == "preflop":
        if v.to_call <= 0:
            return "check", 0.0
        return ("call", v.to_call) if v.to_call <= v.big_blind * 6 else _equity_decision(
            v, 0.25, 0.99, 0.0, 3)
    eq = _eq(v.hole, v.board, max(1, v.num_active_opponents), 400, v.rng)
    if v.to_call <= 0:
        return "check", 0.0
    return ("call", v.to_call) if eq >= 0.20 else ("fold", 0.0)


def rock_bot(v: ActionView) -> tuple[str, float]:
    return _equity_decision(v, fold_eq=0.55, raise_eq=0.70, bluff_freq=0.0, raise_to=3)


def random_bot(v: ActionView) -> tuple[str, float]:
    r = v.rng.random()
    if v.to_call <= 0:
        if r < 0.7:
            return "check", 0.0
        return "raise", max(v.big_blind * 2, round(0.5 * v.pot, 1))
    if r < 0.45:
        return "fold", 0.0
    if r < 0.85:
        return "call", v.to_call
    return "raise", v.to_call + v.big_blind * 2


def make_adaptive_bot(book, hero_name: str):
    """Engine-driven bot that exploits the table read from a ProfileBook.

    - vs an over-folding table: bluff more (raise marginal hands).
    - vs sticky/calling table: cut bluffs, value-bet thinner.
    """
    from . import engine as eng

    def strategy(v: ActionView) -> tuple[str, float]:
        fold_tend = book.table_fold_tendency(exclude=hero_name)
        d = decide(_to_situation(v))

        # Exploit: convert a marginal check into a bluff vs nits.
        if d.action == "check" and v.to_call <= 0 and v.street != "preflop":
            eq = d.equity
            if fold_tend > 0.55 and eq < eng.VALUE_THRESHOLD and v.rng.random() < (fold_tend - 0.3):
                size = round(min(0.6 * v.pot, v.hero_stack), 1)
                if size > 0:
                    return "raise", size
        # Exploit: vs stations don't bluff-raise, just call/fold on equity.
        if d.action == "raise" and "bluff" in d.reason and fold_tend < 0.40:
            if v.to_call > 0:
                return "call", v.to_call
            return "check", 0.0

        if d.action == "raise":
            return "raise", d.amount
        if d.action == "call":
            return "call", v.to_call
        if d.action == "check":
            return "check", 0.0
        return "fold", 0.0

    return strategy


def make_human_strategy(prompt_fn) -> "callable":
    """Wrap a prompt callback `prompt_fn(view, suggestion) -> (action, amount)`.

    The engine's recommendation is computed and passed alongside so the UI can
    display the coach suggestion before the human chooses.
    """
    def strategy(v: ActionView) -> tuple[str, float]:
        suggestion = decide(_to_situation(v))
        return prompt_fn(v, suggestion)

    return strategy


ARCHETYPES = {
    "engine": engine_bot,
    "tag": tag_bot,
    "lag": lag_bot,
    "station": station_bot,
    "rock": rock_bot,
    "random": random_bot,
}
