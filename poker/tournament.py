"""
Sit-&-Go tournament mode (P1).

Fixed field, no rebuys, blinds rise on a schedule, players bust at zero chips,
prizes paid to the top finishers. Includes an ICM (Independent Chip Model)
equity calculator so mid-tournament chip stacks can be valued in prize terms.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .bots import ARCHETYPES, make_adaptive_bot
from .profiling import ProfileBook
from .table import Player, Table

# (small_blind, big_blind) per level.
DEFAULT_BLINDS = [
    (0.5, 1), (1, 2), (1.5, 3), (2, 4), (3, 6), (5, 10),
    (8, 16), (12, 24), (20, 40), (30, 60), (50, 100),
]
# Standard 9-max single-table payout (fractions of the prize pool).
DEFAULT_PAYOUTS = [0.5, 0.3, 0.2]


@dataclass
class TournamentResult:
    finish_order: list[str]            # winner first
    prizes: dict[str, float]
    levels_played: int
    hands_played: int
    profiles: list = field(default_factory=list)


def icm_equity(stacks: dict[str, float], payouts: list[float]) -> dict[str, float]:
    """ICM prize equity for each player given current chip stacks.

    Recursive finishing-position probability model. payouts are absolute prize
    amounts (index 0 = 1st). Complexity is fine for single-table fields.
    """
    names = [n for n, s in stacks.items() if s > 0]
    total = sum(stacks[n] for n in names)
    pays = list(payouts) + [0.0] * (len(names) - len(payouts))

    def rec(remaining: list[str], place: int) -> dict[str, float]:
        if place >= len(pays) or not remaining:
            return {n: 0.0 for n in remaining}
        if len(remaining) == 1:
            return {remaining[0]: pays[place]}
        tot = sum(stacks[n] for n in remaining)
        eq = {n: 0.0 for n in remaining}
        for n in remaining:
            p_first = stacks[n] / tot if tot else 1.0 / len(remaining)
            eq[n] += p_first * pays[place]
            rest = [m for m in remaining if m != n]
            sub = rec(rest, place + 1)
            for m, val in sub.items():
                eq[m] += p_first * val
        return eq

    return rec(names, 0)


def run_tournament(
    lineup: list[tuple[str, str]],
    start_stack: float = 100.0,
    blinds: list[tuple[float, float]] | None = None,
    hands_per_level: int = 20,
    prize_pool: float = 100.0,
    payouts: list[float] | None = None,
    seed: int | None = None,
    verbose: bool = False,
) -> TournamentResult:
    blinds = blinds or DEFAULT_BLINDS
    payout_fracs = payouts or DEFAULT_PAYOUTS
    prizes_abs = [round(prize_pool * f, 2) for f in payout_fracs]

    rng = random.Random(seed)
    book = ProfileBook()
    players = []
    for name, arch in lineup:
        strat = make_adaptive_bot(book, name) if arch == "adaptive" else ARCHETYPES[arch]
        players.append(Player(name, start_stack, strat))

    table = Table(players, big_blind=blinds[0][1], small_blind=blinds[0][0],
                  rng=rng, verbose=verbose)

    finish_order: list[str] = []     # busted players, earliest bust first
    alive = {p.name for p in players}
    hands = 0
    level = 0

    while len(alive) > 1:
        lvl = min(level, len(blinds) - 1)
        table.small_blind, table.big_blind = blinds[lvl]
        result = table.play_hand()
        if result is None:
            break
        hands += 1
        book.observe(result)

        # Detect new busts (stack <= 0) this hand, order by who had less.
        newly_busted = [p for p in players if p.name in alive and p.stack <= 1e-9]
        for p in sorted(newly_busted, key=lambda x: x.committed_total, reverse=True):
            alive.discard(p.name)
            finish_order.append(p.name)
            if verbose:
                print(f"  💀 {p.name} busted ({len(alive)} left)")

        if hands % hands_per_level == 0:
            level += 1
            if verbose:
                lvl2 = min(level, len(blinds) - 1)
                print(f"  ⬆️  Blinds up: {blinds[lvl2][0]}/{blinds[lvl2][1]}")

    finish_order += list(alive)            # last survivor
    finish_order.reverse()                 # winner first

    prizes = {n: 0.0 for n in finish_order}
    for i, name in enumerate(finish_order):
        if i < len(prizes_abs):
            prizes[name] = prizes_abs[i]

    return TournamentResult(finish_order, prizes, level + 1, hands, book.summary())
