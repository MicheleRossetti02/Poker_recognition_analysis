"""
No-Limit Texas Hold'em table with virtual chips.

Self-contained game-state machine: deals hands, runs the four betting rounds
with correct min-raise / all-in / side-pot handling, resolves showdowns with
the pure-python evaluator and distributes pots. No real money, no network, no
external poker client — everything happens in memory.

Strategies are pluggable: each player exposes `act(view) -> (action, amount)`.
This keeps UI (terminal / overlay) and AI fully decoupled from the rules.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from .cards import Card, Deck
from .evaluator import category_name, evaluate

# Position labels by number of players still in seats, ordered from the button.
# Index 0 is the button itself.
_POSITION_TABLES = {
    2: ["BTN", "BB"],            # heads-up: button posts SB
    3: ["BTN", "SB", "BB"],
    4: ["BTN", "SB", "BB", "CO"],
    5: ["BTN", "SB", "BB", "UTG", "CO"],
    6: ["BTN", "SB", "BB", "UTG", "MP", "CO"],
}


@dataclass
class ActionView:
    """Read-only snapshot handed to a strategy when it must act."""

    hole: list[Card]
    board: list[Card]
    position: str
    street: str
    pot: float
    to_call: float
    min_raise: float
    hero_stack: float
    big_blind: float
    num_active_opponents: int
    facing_raise: bool
    street_invested: float
    rng: random.Random


# A strategy returns (action, amount). For "raise", amount is the TOTAL the
# player wants to have committed on this street (i.e. the new "to" level).
Strategy = Callable[[ActionView], tuple[str, float]]


@dataclass
class Player:
    name: str
    stack: float
    strategy: Strategy
    hole: list[Card] = field(default_factory=list)
    folded: bool = False
    all_in: bool = False
    committed_street: float = 0.0   # chips in pot this street
    committed_total: float = 0.0    # chips in pot this hand (for side pots)
    position: str = "?"

    def reset_hand(self) -> None:
        self.hole = []
        self.folded = False
        self.all_in = False
        self.committed_street = 0.0
        self.committed_total = 0.0
        self.position = "?"

    @property
    def in_hand(self) -> bool:
        return not self.folded and self.stack >= 0


@dataclass
class HandResult:
    hand_id: int
    board: list[Card]
    winners: dict[str, float]            # name -> chips won
    showdown: dict[str, str]             # name -> hand description (if shown)
    actions: list[tuple]                 # (name, street, action, amount)
    positions: dict[str, str] = field(default_factory=dict)   # name -> position
    holes: dict[str, list] = field(default_factory=dict)      # name -> [Card, Card]
    invested: dict[str, float] = field(default_factory=dict)  # name -> chips put in


class Table:
    def __init__(
        self,
        players: list[Player],
        big_blind: float = 1.0,
        small_blind: float | None = None,
        rng: random.Random | None = None,
        verbose: bool = False,
        observer: "Callable[[dict], None] | None" = None,
    ):
        if not 2 <= len(players) <= 6:
            raise ValueError("Table supports 2..6 players")
        self.players = players
        self.big_blind = big_blind
        self.small_blind = small_blind if small_blind is not None else big_blind / 2
        self.rng = rng or random.Random()
        self.verbose = verbose
        self.observer = observer  # optional: fired on every game event (for GUI)
        self.button = 0
        self.hand_id = 0

    # ---- helpers -------------------------------------------------------
    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def _emit(self, kind: str, **data) -> None:
        if self.observer is not None:
            payload = {"kind": kind, "hand_id": self.hand_id, "pot": self._pot(), **data}
            self.observer(payload)

    def _seated(self) -> list[Player]:
        """Players with chips, in seat order starting after the button."""
        return [p for p in self.players if p.stack > 0]

    def _assign_positions(self, order: list[Player]) -> None:
        labels = _POSITION_TABLES[len(order)]
        for i, p in enumerate(order):
            p.position = labels[i]

    def _active(self) -> list[Player]:
        return [p for p in self.players if not p.folded and p.stack >= 0 and p.hole]

    # ---- main entry ----------------------------------------------------
    def play_hand(self) -> Optional[HandResult]:
        contenders = [p for p in self.players if p.stack > 0]
        if len(contenders) < 2:
            return None

        self.hand_id += 1
        for p in self.players:
            p.reset_hand()

        # Seat order from button.
        n = len(self.players)
        # rotate button to a player with chips
        while self.players[self.button].stack <= 0:
            self.button = (self.button + 1) % n

        order = []
        for off in range(n):
            p = self.players[(self.button + off) % n]
            if p.stack > 0:
                order.append(p)
        self._assign_positions(order)

        deck = Deck(self.rng)
        for p in order:
            p.hole = deck.deal(2)

        actions: list[tuple] = []
        board: list[Card] = []

        self._emit("hand_start", button=self.button, board=[])

        # Post blinds.
        self._post_blinds(order, actions)

        # Preflop action starts left of BB (or after button heads-up).
        streets = [
            ("preflop", 0),
            ("flop", 3),
            ("turn", 1),
            ("river", 1),
        ]

        last_aggressor = None
        for street, n_cards in streets:
            if n_cards and street != "preflop":
                board += deck.deal(n_cards)
                self._log(f"  -- {street.upper()} {[str(c) for c in board]} pot={self._pot():.1f}")
                self._emit("street", street=street, board=list(board))
            if street != "preflop":
                for p in order:
                    p.committed_street = 0.0

            if self._only_one_left():
                break
            if self._all_but_one_all_in():
                continue  # no more betting possible; just run out the board

            self._betting_round(order, street, board, actions)

        result = self._showdown(board, actions)
        self.button = (self.button + 1) % n
        return result

    # ---- blinds --------------------------------------------------------
    def _post_blinds(self, order: list[Player], actions: list[tuple]) -> None:
        if len(order) == 2:
            sb_player, bb_player = order[0], order[1]  # button is SB heads-up
        else:
            sb_player, bb_player = order[1], order[2]
        self._commit(sb_player, self.small_blind)
        self._commit(bb_player, self.big_blind)
        actions.append((sb_player.name, "preflop", "sb", self.small_blind))
        actions.append((bb_player.name, "preflop", "bb", self.big_blind))

    def _commit(self, p: Player, amount: float) -> float:
        amount = min(amount, p.stack)
        p.stack -= amount
        p.committed_street += amount
        p.committed_total += amount
        if p.stack <= 1e-9:
            p.stack = 0.0
            p.all_in = True
        return amount

    # ---- betting -------------------------------------------------------
    def _betting_round(self, order, street, board, actions) -> None:
        if street == "preflop":
            start = 3 if len(order) > 2 else 0
        else:
            start = 1 if len(order) > 2 else 0  # first active left of button

        current_bet = max(p.committed_street for p in order)
        min_raise = self.big_blind
        num = len(order)
        to_act = [order[(start + i) % num] for i in range(num)]

        need_action = {p.name for p in order if not p.folded and not p.all_in and p.stack > 0}
        last_raiser = None
        idx = 0
        # We loop until everyone has matched the current bet or folded/all-in.
        acted_since_raise: set[str] = set()
        queue = list(to_act)
        while queue:
            p = queue.pop(0)
            if p.folded or p.all_in or p.stack <= 0:
                continue
            if self._only_one_left():
                return
            if p.name not in need_action and p.committed_street == current_bet and p.name in acted_since_raise:
                continue

            to_call = current_bet - p.committed_street
            view = ActionView(
                hole=p.hole,
                board=board,
                position=p.position,
                street=street,
                pot=self._pot(),
                to_call=to_call,
                min_raise=min_raise,
                hero_stack=p.stack,
                big_blind=self.big_blind,
                num_active_opponents=sum(
                    1 for q in order if q is not p and not q.folded and q.hole
                ),
                facing_raise=(current_bet > self.big_blind) if street == "preflop" else (to_call > 0),
                street_invested=p.committed_street,
                rng=self.rng,
            )
            action, amount = p.strategy(view)
            action, amount = self._sanitize(action, amount, p, current_bet, to_call, min_raise)

            if action == "fold":
                p.folded = True
                actions.append((p.name, street, "fold", 0.0))
                self._log(f"     {p.name} ({p.position}) FOLD")
                self._emit("action", player=p.name, position=p.position,
                           action="fold", amount=0.0, street=street, board=list(board))
            elif action == "check":
                actions.append((p.name, street, "check", 0.0))
                self._log(f"     {p.name} ({p.position}) CHECK")
                self._emit("action", player=p.name, position=p.position,
                           action="check", amount=0.0, street=street, board=list(board))
            elif action == "call":
                paid = self._commit(p, to_call)
                actions.append((p.name, street, "call", paid))
                self._log(f"     {p.name} ({p.position}) CALL {paid:.1f}")
                self._emit("action", player=p.name, position=p.position,
                           action="call", amount=paid, street=street, board=list(board))
            elif action == "raise":
                target = amount  # total committed-this-street level
                raise_by = target - current_bet
                paid = self._commit(p, target - p.committed_street)
                min_raise = max(min_raise, raise_by)
                current_bet = max(current_bet, p.committed_street)
                acted_since_raise = {p.name}
                last_raiser = p
                actions.append((p.name, street, "raise", p.committed_street))
                self._log(f"     {p.name} ({p.position}) RAISE to {p.committed_street:.1f}")
                self._emit("action", player=p.name, position=p.position,
                           action="raise", amount=p.committed_street, street=street,
                           board=list(board))
                # everyone still in must act again
                for q in order:
                    if q is not p and not q.folded and not q.all_in and q.stack > 0:
                        if q not in queue:
                            queue.append(q)
                continue

            acted_since_raise.add(p.name)

    def _sanitize(self, action, amount, p: Player, current_bet, to_call, min_raise):
        """Coerce a strategy's intent into a legal action."""
        if action == "fold":
            if to_call <= 0:
                return "check", 0.0  # never fold when free
            return "fold", 0.0
        if action == "check":
            if to_call > 0:
                return ("call", to_call) if p.stack >= to_call else ("call", p.stack)
            return "check", 0.0
        if action == "call":
            return "call", min(to_call, p.stack)
        if action == "raise":
            min_target = current_bet + min_raise
            max_target = p.committed_street + p.stack  # all-in cap
            target = max(min_target, amount)
            target = min(target, max_target)
            if target <= current_bet or target - p.committed_street <= 0:
                # cannot make a legal raise -> call/check
                if to_call > 0:
                    return "call", min(to_call, p.stack)
                return "check", 0.0
            return "raise", target
        return ("call", min(to_call, p.stack)) if to_call > 0 else ("check", 0.0)

    # ---- state queries -------------------------------------------------
    def _pot(self) -> float:
        return sum(p.committed_total for p in self.players)

    def _only_one_left(self) -> bool:
        return sum(1 for p in self.players if not p.folded and p.hole) <= 1

    def _all_but_one_all_in(self) -> bool:
        live = [p for p in self.players if not p.folded and p.hole]
        can_bet = [p for p in live if not p.all_in and p.stack > 0]
        return len(live) >= 2 and len(can_bet) <= 1

    # ---- showdown & pots ----------------------------------------------
    def _showdown(self, board: list[Card], actions: list[tuple]) -> HandResult:
        live = [p for p in self.players if not p.folded and p.hole]
        winners: dict[str, float] = {}
        showdown: dict[str, str] = {}

        participants = [p for p in self.players if p.hole or p.committed_total > 0]
        positions = {p.name: p.position for p in participants}
        holes = {p.name: list(p.hole) for p in participants}
        invested = {p.name: p.committed_total for p in participants}

        def _meta(hr: HandResult) -> HandResult:
            hr.positions = positions
            hr.holes = holes
            hr.invested = invested
            return hr

        if len(live) == 1:
            p = live[0]
            pot = self._pot()
            p.stack += pot
            winners[p.name] = pot
            self._emit("showdown", board=list(board), winners=dict(winners),
                       showdown=dict(showdown))
            return _meta(HandResult(self.hand_id, board, winners, showdown, actions))

        # Build side pots from committed_total levels.
        contributors = [p for p in self.players if p.committed_total > 0]
        levels = sorted({p.committed_total for p in contributors})
        pots = []  # (amount, [eligible players])
        prev = 0.0
        for lvl in levels:
            amount = 0.0
            for p in contributors:
                amount += min(p.committed_total, lvl) - min(p.committed_total, prev)
            eligible = [p for p in live if p.committed_total >= lvl]
            if amount > 0 and eligible:
                pots.append((amount, eligible))
            prev = lvl

        scores = {p.name: evaluate(p.hole + board) for p in live}
        for p in live:
            showdown[p.name] = category_name(scores[p.name])

        for amount, eligible in pots:
            best = max(scores[p.name] for p in eligible)
            pot_winners = [p for p in eligible if scores[p.name] == best]
            share = amount / len(pot_winners)
            for w in pot_winners:
                w.stack += share
                winners[w.name] = winners.get(w.name, 0.0) + share

        self._emit("showdown", board=list(board), winners=dict(winners),
                   showdown=dict(showdown))
        return _meta(HandResult(self.hand_id, board, winners, showdown, actions))
