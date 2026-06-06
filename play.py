#!/usr/bin/env python3
"""
Virtual-chip poker — play & simulate. No real money, no external client.

Modes:
  auto    Watch bots play each other; prints a session report.
  sim     Run many hands fast (no per-hand output) and print the report table.
  play    Interactive: you are the Hero, the engine shows a coach suggestion
          each decision; you choose the action.

Examples:
  python play.py auto  --hands 30 --lineup engine,tag,station,rock
  python play.py sim   --hands 5000 --lineup engine,station
  python play.py play  --villains tag,station,lag --stack 100 --bb 1
"""

from __future__ import annotations

import argparse
import random
import sys

from poker.bots import ARCHETYPES, make_human_strategy
from poker.engine import Decision
from poker.history import format_leak_report, leak_report, write_history
from poker.render import action_color, banner, cards_str
from poker.simulator import run_session
from poker.table import ActionView, Player, Table
from poker.tournament import run_tournament


def _print_report(res) -> None:
    print("\n" + banner(f"SESSION REPORT — {res.hands} hands @ {res.big_blind}BB"))
    rows = res.summary_rows()
    header = f"{'Player':<12}{'Type':<10}{'Net':>10}{'BB/100':>10}{'Won':>7}{'Hands':>7}{'Stack':>10}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['name']:<12}{r['type']:<10}{r['net']:>10}{r['bb100']:>10}"
              f"{r['won']:>7}{r['hands']:>7}{r['end_stack']:>10}")
    print()


def cmd_auto(args) -> None:
    lineup = [(f"P{i+1}_{a}", a) for i, a in enumerate(args.lineup)]
    res = run_session(lineup, hands=args.hands, big_blind=args.bb,
                      start_stack=args.stack, seed=args.seed, verbose=True)
    _print_report(res)


def cmd_sim(args) -> None:
    lineup = [(f"P{i+1}_{a}", a) for i, a in enumerate(args.lineup)]
    res = run_session(lineup, hands=args.hands, big_blind=args.bb,
                      start_stack=args.stack, seed=args.seed, verbose=False)
    _print_report(res)
    if getattr(args, "profiles", False) and res.profiles:
        print("PROFILES (VPIP / PFR / AF / fold / style)")
        for p in res.profiles:
            print(f"  {p['name']:<12} vpip={p['vpip']:.2f} pfr={p['pfr']:.2f} "
                  f"af={p['af']:.2f} fold={p['fold']:.2f}  {p['style']}")
    if getattr(args, "leak", None):
        hero_name = next((n for n, a in lineup if a == args.leak or n == args.leak), None)
        if hero_name:
            print("\n" + format_leak_report(leak_report(res.history, hero_name, args.bb), hero_name))
    if getattr(args, "history", None):
        write_history(res.history, args.history, args.bb)
        print(f"\nHand history written to {args.history}")
    if getattr(args, "save", False):
        from poker.store import StatsStore
        st = StatsStore()
        sid = st.save_session(res)
        st.close()
        print(f"\nSession #{sid} saved to data/poker_stats.db (view: poker_gui.py stats)")


def cmd_tourney(args) -> None:
    lineup = [(f"P{i+1}_{a}", a) for i, a in enumerate(args.lineup)]
    res = run_tournament(lineup, start_stack=args.stack, hands_per_level=args.level_hands,
                         prize_pool=args.prize, seed=args.seed, verbose=args.verbose)
    print("\n" + banner(f"TOURNAMENT — {res.hands_played} hands, {res.levels_played} levels"))
    print(f"{'Place':<7}{'Player':<14}{'Prize':>8}")
    print("-" * 30)
    for i, name in enumerate(res.finish_order, 1):
        print(f"{i:<7}{name:<14}{res.prizes.get(name, 0):>8.1f}")


class Trainer:
    """P6: grade the human's decisions against the engine recommendation."""

    def __init__(self):
        self.decisions = 0
        self.matches = 0
        self.deviations = []

    def grade(self, view: ActionView, suggestion: Decision, action: str):
        self.decisions += 1
        ok = action == suggestion.action
        if ok:
            self.matches += 1
        else:
            self.deviations.append(
                (view.street, view.position, suggestion.action, action, suggestion.reason))
        return ok

    @property
    def score(self) -> float:
        return 100.0 * self.matches / self.decisions if self.decisions else 0.0

    def report(self) -> str:
        out = [f"\nTRAINING SCORE: {self.score:.0f}% "
               f"({self.matches}/{self.decisions} matched the engine)"]
        if self.deviations:
            out.append("Biggest deviations (engine vs you):")
            for st, pos, sug, act, reason in self.deviations[-8:]:
                out.append(f"  [{st}/{pos}] engine={sug.upper()} you={act.upper()} — {reason}")
        return "\n".join(out)


def _make_prompt(trainer: Trainer | None):
    def prompt(v: ActionView, suggestion: Decision):
        action, amount = _human_prompt(v, suggestion)
        if trainer is not None:
            ok = trainer.grade(v, suggestion, action)
            mark = "✅ matches engine" if ok else "⚠️ differs from engine"
            print(f"     {mark}   (session grade so far: {trainer.score:.0f}%)")
        return action, amount
    return prompt


def _human_prompt(v: ActionView, suggestion: Decision):
    print("\n" + "=" * 60)
    print(f"  Street: {v.street.upper()}   Position: {v.position}   Pot: {v.pot:.1f}BB")
    print(f"  Board:  {cards_str(v.board)}")
    print(f"  Your hand: {cards_str(v.hole)}   Stack: {v.hero_stack:.1f}BB")
    if v.to_call > 0:
        print(f"  To call: {v.to_call:.1f}BB   (pot odds {v.to_call/(v.pot+v.to_call):.0%})")
    else:
        print("  To call: 0 (you can check)")
    eq = f"{suggestion.equity:.0%}" if suggestion.equity else "n/a"
    print(f"\n  💡 COACH: {action_color(suggestion.label())}  "
          f"[equity {eq}, conf {suggestion.confidence:.0%}]")
    print(f"     reason: {suggestion.reason}")

    legal = ["f", "c"]
    if v.to_call > 0:
        prompt = "  [f]old  [c]all  [r]aise  (enter = follow coach): "
        legal.append("r")
    else:
        prompt = "  [k]check  [r]aise  (enter = follow coach): "
        legal = ["k", "r"]

    while True:
        choice = input(prompt).strip().lower()
        if choice == "":
            return suggestion.action, suggestion.amount
        if choice in ("f", "fold"):
            return "fold", 0.0
        if choice in ("c", "call"):
            return "call", v.to_call
        if choice in ("k", "check"):
            return "check", 0.0
        if choice in ("r", "raise"):
            default = max(v.min_raise + v.to_call, v.big_blind * 2.5)
            raw = input(f"     raise TO (total this street, default {default:.1f}): ").strip()
            try:
                amt = float(raw) if raw else default
            except ValueError:
                amt = default
            return "raise", amt
        print("  ?")


def cmd_play(args) -> None:
    rng = random.Random(args.seed)
    trainer = Trainer() if args.train else None
    players = [Player("HERO", args.stack, make_human_strategy(_make_prompt(trainer)))]
    for i, a in enumerate(args.villains):
        if a not in ARCHETYPES:
            print(f"Unknown villain type: {a}", file=sys.stderr)
            sys.exit(1)
        players.append(Player(f"V{i+1}_{a}", args.stack, ARCHETYPES[a]))

    table = Table(players, big_blind=args.bb, rng=rng, verbose=True)
    print(banner("VIRTUAL POKER — you are HERO (no real money)"))
    print("Ctrl+C to quit.\n")

    hand_no = 0
    try:
        while True:
            if sum(1 for p in players if p.stack > 0) < 2:
                print("\nNot enough players with chips. Resetting stacks.")
                for p in players:
                    p.stack = args.stack
            hand_no += 1
            print("\n" + banner(f"HAND #{hand_no}"))
            result = table.play_hand()
            if result is None:
                break
            print(f"\n  Board: {cards_str(result.board)}")
            for name, desc in result.showdown.items():
                print(f"    {name}: {desc}")
            for name, amount in result.winners.items():
                if amount > 0:
                    print(f"  🏆 {name} wins {amount:.1f}BB")
            hero = players[0]
            print(f"  HERO stack: {hero.stack:.1f}BB")
            if args.hands and hand_no >= args.hands:
                break
            input("\n  [enter] next hand...")
    except (KeyboardInterrupt, EOFError):
        print("\n\nThanks for playing!")
    hero = players[0]
    print(f"\nFinal HERO stack: {hero.stack:.1f}BB (started {args.stack:.1f})")
    if trainer is not None and trainer.decisions:
        print(trainer.report())


def _archetype_list(text: str) -> list[str]:
    return [a.strip() for a in text.split(",") if a.strip()]


def main() -> None:
    p = argparse.ArgumentParser(description="Virtual-chip poker (no real money).")
    sub = p.add_subparsers(dest="mode", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--bb", type=float, default=1.0)
    common.add_argument("--stack", type=float, default=100.0)
    common.add_argument("--seed", type=int, default=None)
    common.add_argument("--fast", action="store_true",
                        help="use numpy-vectorised equity (big sims, N2)")

    a = sub.add_parser("auto", parents=[common], help="watch bots, verbose")
    a.add_argument("--hands", type=int, default=20)
    a.add_argument("--lineup", type=_archetype_list,
                   default=["engine", "tag", "station", "rock"])
    a.set_defaults(func=cmd_auto)

    s = sub.add_parser("sim", parents=[common], help="fast simulation report")
    s.add_argument("--hands", type=int, default=2000)
    s.add_argument("--lineup", type=_archetype_list,
                   default=["engine", "tag", "station", "rock"])
    s.add_argument("--profiles", action="store_true", help="show opponent profiles (P3)")
    s.add_argument("--leak", type=str, default=None, help="leak report for player/archetype (P5)")
    s.add_argument("--history", type=str, default=None, help="write hand history to file (P5)")
    s.add_argument("--save", action="store_true", help="save session to SQLite (N4/N8)")
    s.set_defaults(func=cmd_sim)

    t = sub.add_parser("tourney", parents=[common], help="sit-n-go tournament (P1)")
    t.add_argument("--lineup", type=_archetype_list,
                   default=["engine", "adaptive", "tag", "station", "rock", "lag"])
    t.add_argument("--level-hands", type=int, default=20)
    t.add_argument("--prize", type=float, default=100.0)
    t.add_argument("--verbose", action="store_true")
    t.set_defaults(func=cmd_tourney)

    pl = sub.add_parser("play", parents=[common], help="interactive, you are hero")
    pl.add_argument("--hands", type=int, default=0, help="0 = unlimited")
    pl.add_argument("--villains", type=_archetype_list,
                    default=["tag", "station", "rock"])
    pl.add_argument("--train", action="store_true",
                    help="grade your decisions against the engine")
    pl.set_defaults(func=cmd_play)

    args = p.parse_args()
    if getattr(args, "fast", False):
        from poker import engine as _engine
        _engine.USE_FAST_EQUITY = True
    args.func(args)


if __name__ == "__main__":
    main()
