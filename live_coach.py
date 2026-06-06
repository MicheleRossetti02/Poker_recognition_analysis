"""
Live-vision coach adapter (M3).

Bridges the noisy live game state read from the screen into the self-contained
decision engine in `poker/`, so the on-screen coach uses the same strong engine
as the simulator — including real postflop equity advice (the old live path only
had a preflop ABC table and a postflop placeholder string).

All conversions are defensive: any missing / unparseable field falls back to a
safe default so the live loop never crashes on bad OCR.
"""

from __future__ import annotations

from poker.cards import make_card
from poker.engine import Situation, decide

# Live street label -> engine street.
_STREET = {"preflop": "preflop", "flop": "flop", "turn": "turn", "river": "river"}


def _parse_cards(names):
    out = []
    for n in names or []:
        try:
            # Live class names: 'As','Td','Tc'... normalise 'tc'/'Tc' -> 'Tc'.
            if not n or len(n) != 2:
                continue
            out.append(make_card(n))
        except Exception:
            continue
    return out


def live_decision(
    hero_cards,
    board_cards,
    position,
    street,
    pot_bb,
    high_bet_bb,
    raises_count,
    hero_stack_bb,
    num_opponents,
    big_blind: float = 1.0,
):
    """Return an engine Decision for the current live spot, or None if unusable."""
    hole = _parse_cards(hero_cards)
    if len(hole) != 2:
        return None
    board = _parse_cards(board_cards)
    eng_street = _STREET.get((street or "preflop").lower(), "preflop")

    facing = bool(raises_count) or (high_bet_bb or 0) > big_blind
    if eng_street == "preflop":
        to_call = (high_bet_bb or big_blind) if facing else 0.0
    else:
        # Postflop: only treat as facing a bet when there was aggression.
        to_call = (high_bet_bb or 0.0) if raises_count else 0.0

    sit = Situation(
        hole=hole,
        board=board,
        position=position if position and position != "?" else "BB",
        street=eng_street,
        pot=max(0.0, pot_bb or 0.0),
        to_call=max(0.0, to_call),
        hero_stack=max(big_blind, hero_stack_bb or (100 * big_blind)),
        big_blind=big_blind,
        num_opponents=max(1, num_opponents or 1),
        facing_raise=facing,
    )
    try:
        return decide(sit)
    except Exception:
        return None


def format_suggestion(decision, hero_hand: str) -> str:
    """Human-readable coach line for overlay/console."""
    if decision is None:
        return f"{hero_hand} - CHECK"
    label = decision.label()
    if decision.equity:
        return f"{label}  ({decision.reason}, eq {decision.equity:.0%})"
    return f"{label}  ({decision.reason})"
