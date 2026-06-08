"""
Session simulator: run N hands of virtual-chip poker between strategies and
collect per-player results (chips won/lost, BB/100, hands played).

Used for the automatic (bot-vs-bot) play mode and for validating engine
changes offline before they ever touch the live overlay.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .bots import ARCHETYPES, make_adaptive_bot
from .profiling import ProfileBook
from .table import Player, Table


@dataclass
class PlayerReport:
    name: str
    archetype: str
    start_stack: float
    end_stack: float
    hands: int = 0
    won: int = 0

    @property
    def net(self) -> float:
        return self.end_stack - self.start_stack

    def bb_per_100(self, big_blind: float) -> float:
        if self.hands == 0:
            return 0.0
        return (self.net / big_blind) / self.hands * 100.0


@dataclass
class SessionResult:
    hands: int
    big_blind: float
    reports: list[PlayerReport]
    history: list = field(default_factory=list)
    profiles: list = field(default_factory=list)

    def summary_rows(self) -> list[dict]:
        rows = []
        for r in sorted(self.reports, key=lambda x: x.net, reverse=True):
            rows.append({
                "name": r.name,
                "type": r.archetype,
                "net": round(r.net, 1),
                "bb100": round(r.bb_per_100(self.big_blind), 1),
                "won": r.won,
                "hands": r.hands,
                "end_stack": round(r.end_stack, 1),
            })
        return rows


def build_table(
    lineup: list[tuple[str, str]],
    big_blind: float = 1.0,
    start_stack: float = 100.0,
    seed: int | None = None,
    verbose: bool = False,
) -> tuple[Table, dict[str, str]]:
    """lineup = [(name, archetype), ...]. Returns (table, name->archetype)."""
    rng = random.Random(seed)
    players = []
    archetypes = {}
    book = ProfileBook()
    for name, arch in lineup:
        if arch == "adaptive":
            strat = make_adaptive_bot(book, name)
        elif arch in ARCHETYPES:
            strat = ARCHETYPES[arch]
        else:
            raise ValueError(f"Unknown archetype: {arch}")
        players.append(Player(name=name, stack=start_stack, strategy=strat))
        archetypes[name] = arch
    table = Table(players, big_blind=big_blind, rng=rng, verbose=verbose)
    table.profile_book = book  # type: ignore[attr-defined]
    return table, archetypes


def run_session(
    lineup: list[tuple[str, str]],
    hands: int = 1000,
    big_blind: float = 1.0,
    start_stack: float = 100.0,
    seed: int | None = None,
    rebuy: bool = True,
    verbose: bool = False,
) -> SessionResult:
    table, archetypes = build_table(lineup, big_blind, start_stack, seed, verbose)
    reports = {
        p.name: PlayerReport(p.name, archetypes[p.name], start_stack, start_stack)
        for p in table.players
    }

    history = []
    for _ in range(hands):
        # Rebuy short stacks so the session keeps running (cash-game style).
        if rebuy:
            for p in table.players:
                if p.stack < big_blind:
                    reports[p.name].start_stack += (start_stack - p.stack)
                    p.stack = start_stack

        result = table.play_hand()
        if result is None:
            break
        history.append(result)
        table.profile_book.observe(result)
        for p in table.players:
            if p.hole:
                reports[p.name].hands += 1
        for name, amount in result.winners.items():
            if amount > 0:
                reports[name].won += 1

    for p in table.players:
        reports[p.name].end_stack = p.stack

    return SessionResult(
        hands=len(history),
        big_blind=big_blind,
        reports=list(reports.values()),
        history=history,
        profiles=table.profile_book.summary(),
    )
