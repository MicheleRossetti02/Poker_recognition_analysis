"""
Bot arena & engine auto-tuning (N6).

- round_robin: play a field of archetypes for many hands and rank them by
  BB/100, so you can see which strategies dominate.
- tune_engine: small grid search over a few engine parameters, measuring the
  engine's win-rate vs a fixed field, to auto-pick stronger settings.

Both lean on the numpy-vectorised equity path for speed.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import engine as eng
from .simulator import run_session


@dataclass
class ArenaResult:
    ranking: list[dict]      # sorted by bb/100 desc
    hands: int


def round_robin(archetypes: list[str], hands: int = 5000, big_blind: float = 1.0,
                start_stack: float = 100.0, seed: int | None = 0,
                fast: bool = True) -> ArenaResult:
    """Seat the whole field at one table and rank by BB/100 (no rebuy fountain)."""
    prev = eng.USE_FAST_EQUITY
    eng.USE_FAST_EQUITY = fast
    try:
        lineup = [(f"{a}", a) for a in archetypes]
        # disambiguate duplicate names
        seen: dict[str, int] = {}
        fixed = []
        for name, a in lineup:
            seen[name] = seen.get(name, 0) + 1
            fixed.append((f"{name}{seen[name] if seen[name] > 1 else ''}", a))
        res = run_session(fixed, hands=hands, big_blind=big_blind,
                          start_stack=start_stack, seed=seed, rebuy=True)
    finally:
        eng.USE_FAST_EQUITY = prev

    ranking = sorted(
        ({"name": r.name, "type": r.archetype,
          "bb100": round(r.bb_per_100(big_blind), 1), "net": round(r.net, 1)}
         for r in res.reports),
        key=lambda d: d["bb100"], reverse=True)
    return ArenaResult(ranking, res.hands)


def tune_engine(
    field: list[str] | None = None,
    hands: int = 3000,
    seed: int = 1,
    value_grid=(0.52, 0.56, 0.60),
    bluff_grid=(0.20, 0.30, 0.40),
) -> dict:
    """Grid-search VALUE_THRESHOLD × BLUFF_FREQ; return best by engine BB/100.

    Restores the original engine parameters afterwards.
    """
    field = field or ["tag", "station", "rock", "lag"]
    orig_val, orig_bluff, orig_fast = eng.VALUE_THRESHOLD, eng.BLUFF_FREQ, eng.USE_FAST_EQUITY
    eng.USE_FAST_EQUITY = True
    results = []
    try:
        for v in value_grid:
            for b in bluff_grid:
                eng.VALUE_THRESHOLD = v
                eng.BLUFF_FREQ = b
                lineup = [("engine", "engine")] + [(f"v{i}", a) for i, a in enumerate(field)]
                res = run_session(lineup, hands=hands, seed=seed, rebuy=True)
                eb = next(r for r in res.reports if r.name == "engine")
                results.append({"value_threshold": v, "bluff_freq": b,
                                "bb100": round(eb.bb_per_100(1.0), 1)})
    finally:
        eng.VALUE_THRESHOLD, eng.BLUFF_FREQ, eng.USE_FAST_EQUITY = orig_val, orig_bluff, orig_fast

    best = max(results, key=lambda d: d["bb100"])
    return {"best": best, "grid": results}
