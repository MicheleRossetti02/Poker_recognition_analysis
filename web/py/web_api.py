"""
Turn-based web game driver (runs in the browser via Pyodide).

The Table runs a hand by calling each player's strategy synchronously, which
does not fit an async web UI. Instead of duplicating the (tested) betting
engine, this driver replays the hand deterministically: the human strategy
pops pre-recorded decisions and, when it runs out, raises `NeedInput`. The
driver catches it, asks the UI, then re-runs the whole hand from a fixed
per-hand seed with the new decision appended. Bots are seeded too, so every
replay reproduces identical cards and bot actions.

All public methods return plain dicts (JSON-friendly) so JavaScript can drive
the UI. No real money, no network — the whole game runs client-side.
"""

from __future__ import annotations

import random

from poker.bots import ARCHETYPES
from poker.coach import coach_insights
from poker.engine import decide
from poker.bots import _to_situation
from poker.table import ActionView, Player, Table


class NeedInput(Exception):
    def __init__(self, view: ActionView):
        self.view = view


def _cards(cs):
    return [str(c) for c in cs]


class WebGame:
    def __init__(self, villains=None, big_blind=1.0, stack=100.0, seed=None):
        villains = villains or ["tag", "station", "lag"]
        self.big_blind = big_blind
        self.start_stack = stack
        self.hero_name = "YOU"
        self._hand_seed = (seed if seed is not None else random.randrange(1 << 30))
        self._human_queue = []
        self._queue_iter = iter(())
        self._pending_view = None
        self._last_result = None
        self.hand_no = 0

        players = [Player(self.hero_name, stack, self._hero_strategy)]
        for i, a in enumerate(villains):
            if a not in ARCHETYPES:
                a = "tag"
            players.append(Player(f"{a.upper()}{i+1}", stack, ARCHETYPES[a]))
        self.table = Table(players, big_blind=big_blind, rng=random.Random())
        self._snapshot = None

    # ---- human strategy (replay-aware) --------------------------------
    def _hero_strategy(self, view: ActionView):
        try:
            return next(self._queue_iter)
        except StopIteration:
            raise NeedInput(view)

    # ---- hand lifecycle ------------------------------------------------
    def start_hand(self):
        # reset stacks if not enough players
        if sum(1 for p in self.table.players if p.stack > 0) < 2:
            for p in self.table.players:
                p.stack = self.start_stack
        self.hand_no += 1
        self._human_queue = []
        self._snapshot = (self.table.button, [p.stack for p in self.table.players])
        return self._resolve()

    def submit(self, action: str, amount: float = 0.0):
        self._human_queue.append((action, float(amount)))
        return self._resolve()

    def _resolve(self):
        while True:
            # restore pre-hand state for a clean deterministic replay
            self.table.button = self._snapshot[0]
            for p, s in zip(self.table.players, self._snapshot[1]):
                p.stack = s
            self.table.rng = random.Random(self._hand_seed)
            self._queue_iter = iter(list(self._human_queue))
            self._pending_view = None
            try:
                result = self.table.play_hand()
            except NeedInput as ni:
                self._pending_view = ni.view
                return self._state(need=True)
            self._last_result = result
            self._hand_seed += 1
            return self._state(need=False, result=result)

    # ---- state serialisation ------------------------------------------
    def _coach(self):
        v = self._pending_view
        if v is None:
            return None
        d = decide(_to_situation(v))
        insights = coach_insights(
            v.hole,
            v.board,
            opponents=max(1, v.num_active_opponents),
            facing_raise=v.facing_raise,
            iterations=220,
            rng=random.Random(self._hand_seed + len(self._human_queue) + 97),
        )
        payload = {
            "action": d.action, "amount": round(d.amount, 1),
            "label": d.label(), "reason": d.reason,
            "equity": round(d.equity, 3), "confidence": round(d.confidence, 2),
            "insights": {
                "made_hand": insights["made_hand"],
                "draws": insights["draws"],
                "outs": {
                    "count": insights["outs"]["count"],
                    "next_card_pct": round(insights["outs"]["next_card_pct"], 3),
                    "by_river_pct": round(insights["outs"]["by_river_pct"], 3),
                },
                "equity_breakdown": {
                    "win_pct": round(insights["equity_breakdown"]["win_pct"], 3),
                    "tie_pct": round(insights["equity_breakdown"]["tie_pct"], 3),
                    "lose_pct": round(insights["equity_breakdown"]["lose_pct"], 3),
                },
            },
        }
        if "heads_up_equity" in insights:
            payload["insights"]["heads_up_equity"] = round(insights["heads_up_equity"], 3)
        if "vs_betting_range_equity" in insights:
            payload["insights"]["vs_betting_range_equity"] = round(insights["vs_betting_range_equity"], 3)
        return payload

    def _legal(self):
        v = self._pending_view
        if v is None:
            return {}
        return {
            "to_call": round(v.to_call, 1),
            "can_check": v.to_call <= 0,
            "min_raise_to": round(v.street_invested + v.to_call + max(v.min_raise, v.big_blind), 1),
            "max_raise_to": round(v.street_invested + v.hero_stack, 1),
            "pot": round(v.pot, 1),
            "street": v.street,
            "position": v.position,
        }

    def _state(self, need: bool, result=None):
        reveal = (result is not None)
        players = []
        for p in self.table.players:
            is_hero = p.name == self.hero_name
            players.append({
                "name": p.name,
                "stack": round(p.stack, 1),
                "position": p.position,
                "folded": p.folded,
                "is_hero": is_hero,
                "hole": _cards(p.hole) if (is_hero or reveal) else [],
            })
        out = {
            "hand_no": self.hand_no,
            "need_action": need,
            "players": players,
            "big_blind": self.big_blind,
        }
        if need:
            out["coach"] = self._coach()
            out["legal"] = self._legal()
            out["board"] = _cards(self._pending_view.board)
            out["hero_hole"] = _cards(self._pending_view.hole)
            out["pot"] = round(self._pending_view.pot, 1)
        if result is not None:
            out["board"] = _cards(result.board)
            out["winners"] = {k: round(v, 1) for k, v in result.winners.items()}
            out["showdown"] = result.showdown
            out["pot"] = round(sum(result.winners.values()), 1)
        return out
