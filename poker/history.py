"""
Hand-history logging & leak analysis (P5).

Writes a compact text hand history and computes a per-position leak report for
a chosen player: net BB by position, showdown rate, and pre-flop tendencies.
Works purely off the HandResult objects produced by the table, so it covers
both cash sessions and tournaments.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


def format_hand(result, big_blind: float = 1.0) -> str:
    """Render one HandResult as a readable text block."""
    lines = [f"# Hand {result.hand_id}"]
    pos = result.positions
    holes = result.holes
    for name in holes:
        cs = " ".join(str(c) for c in holes[name])
        lines.append(f"  Seat {pos.get(name,'?'):<4} {name}: {cs or '--'}")
    street = None
    for nm, st, action, amount in result.actions:
        if st != street:
            street = st
            lines.append(f"  -- {st.upper()} --")
        amt = f" {amount:.1f}" if action in ("call", "raise", "sb", "bb") else ""
        lines.append(f"     {nm} {action}{amt}")
    if result.board:
        lines.append(f"  Board: {' '.join(str(c) for c in result.board)}")
    for nm, d in result.showdown.items():
        lines.append(f"  Showdown {nm}: {d}")
    for nm, amt in result.winners.items():
        if amt > 0:
            lines.append(f"  {nm} wins {amt:.1f}")
    return "\n".join(lines)


def write_history(history, path: str, big_blind: float = 1.0) -> None:
    with open(path, "w") as f:
        for result in history:
            f.write(format_hand(result, big_blind))
            f.write("\n\n")


@dataclass
class PositionLeak:
    position: str
    hands: int = 0
    net: float = 0.0
    vpip: int = 0
    showdowns: int = 0
    wins: int = 0

    def row(self, bb: float) -> dict:
        return {
            "position": self.position,
            "hands": self.hands,
            "net_bb": round(self.net / bb, 1),
            "bb_per_100": round((self.net / bb) / self.hands * 100, 1) if self.hands else 0.0,
            "vpip%": round(100 * self.vpip / self.hands, 0) if self.hands else 0.0,
            "wins": self.wins,
            "sd": self.showdowns,
        }


def leak_report(history, hero: str, big_blind: float = 1.0) -> list[dict]:
    """Per-position net/vpip/showdown breakdown for `hero`."""
    by_pos: dict[str, PositionLeak] = defaultdict(lambda: PositionLeak("?"))
    for result in history:
        if hero not in result.positions:
            continue
        pos = result.positions[hero]
        leak = by_pos.setdefault(pos, PositionLeak(pos))
        leak.hands += 1
        won = result.winners.get(hero, 0.0)
        invested = result.invested.get(hero, 0.0)
        leak.net += won - invested
        # VPIP: voluntarily put chips in beyond blinds.
        voluntary = any(
            nm == hero and act in ("call", "raise") and st == "preflop"
            for nm, st, act, _amt in result.actions
        )
        if voluntary:
            leak.vpip += 1
        if hero in result.showdown:
            leak.showdowns += 1
        if won > 0:
            leak.wins += 1

    order = {p: i for i, p in enumerate(["UTG", "MP", "CO", "BTN", "SB", "BB"])}
    rows = [leak.row(big_blind) for leak in by_pos.values()]
    rows.sort(key=lambda r: order.get(r["position"], 99))
    return rows


def format_leak_report(rows: list[dict], hero: str) -> str:
    out = [f"LEAK REPORT — {hero}",
           f"{'Pos':<5}{'Hands':>7}{'NetBB':>9}{'BB/100':>9}{'VPIP%':>7}{'Wins':>6}{'SD':>5}"]
    out.append("-" * 48)
    for r in rows:
        out.append(f"{r['position']:<5}{r['hands']:>7}{r['net_bb']:>9}"
                   f"{r['bb_per_100']:>9}{r['vpip%']:>7.0f}{r['wins']:>6}{r['sd']:>5}")
    return "\n".join(out)
