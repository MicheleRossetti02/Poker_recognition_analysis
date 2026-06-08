"""
Opponent profiling & adaptation (P3).

Tracks per-player tendencies from observed hands (VPIP, PFR, aggression
frequency, fold frequency) and exposes a `ProfileBook` the simulator updates
after every hand. An adaptive strategy uses these reads to exploit the table:
bluff more vs nits that over-fold, bluff less / value thinner vs calling
stations.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlayerProfile:
    name: str
    hands: int = 0
    vpip_hands: int = 0       # voluntarily put money in preflop (call/raise)
    pfr_hands: int = 0        # raised preflop
    aggressive: int = 0       # bets/raises (any street)
    passive: int = 0          # calls (any street)
    folds: int = 0
    decisions: int = 0

    @property
    def vpip(self) -> float:
        return self.vpip_hands / self.hands if self.hands else 0.0

    @property
    def pfr(self) -> float:
        return self.pfr_hands / self.hands if self.hands else 0.0

    @property
    def aggression_freq(self) -> float:
        denom = self.aggressive + self.passive
        return self.aggressive / denom if denom else 0.0

    @property
    def fold_freq(self) -> float:
        return self.folds / self.decisions if self.decisions else 0.0

    def style(self) -> str:
        if self.hands < 15:
            return "unknown"
        loose = self.vpip > 0.40
        aggro = self.aggression_freq > 0.45
        if not loose and aggro:
            return "TAG"
        if loose and aggro:
            return "LAG"
        if loose and not aggro:
            return "station"
        return "nit"


class ProfileBook:
    def __init__(self):
        self.profiles: dict[str, PlayerProfile] = {}

    def get(self, name: str) -> PlayerProfile:
        return self.profiles.setdefault(name, PlayerProfile(name))

    def observe(self, result) -> None:
        """Update profiles from a HandResult's action log."""
        seen_vpip: set[str] = set()
        seen_pfr: set[str] = set()
        players_in_hand: set[str] = set()
        for name, street, action, amount in result.actions:
            players_in_hand.add(name)
            if action in ("sb", "bb"):
                continue
            prof = self.get(name)
            prof.decisions += 1
            if action == "raise":
                prof.aggressive += 1
                if street == "preflop":
                    seen_pfr.add(name)
                    seen_vpip.add(name)
            elif action == "call":
                prof.passive += 1
                if street == "preflop":
                    seen_vpip.add(name)
            elif action == "fold":
                prof.folds += 1
        for name in players_in_hand:
            prof = self.get(name)
            prof.hands += 1
            if name in seen_vpip:
                prof.vpip_hands += 1
            if name in seen_pfr:
                prof.pfr_hands += 1

    def table_fold_tendency(self, exclude: str | None = None) -> float:
        profs = [p for n, p in self.profiles.items()
                 if n != exclude and p.decisions >= 10]
        if not profs:
            return 0.5
        return sum(p.fold_freq for p in profs) / len(profs)

    def summary(self) -> list[dict]:
        return [{
            "name": p.name, "hands": p.hands, "vpip": round(p.vpip, 2),
            "pfr": round(p.pfr, 2), "af": round(p.aggression_freq, 2),
            "fold": round(p.fold_freq, 2), "style": p.style(),
        } for p in sorted(self.profiles.values(), key=lambda x: -x.hands)]
