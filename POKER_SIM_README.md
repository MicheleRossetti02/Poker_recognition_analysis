# Virtual-Chip Poker — engine, simulator & coach overlay

Self-contained No-Limit Texas Hold'em with **virtual chips only**. No real
money, no gambling, no external poker client, no network. Built to be safe and
fully offline: the whole game lives in memory.

## What's here

| Module | Role |
|---|---|
| `poker/cards.py` | Card / Deck primitives |
| `poker/evaluator.py` | Pure-python 7-card hand evaluator |
| `poker/equity.py` | Monte Carlo equity |
| `poker/ranges.py` | Preflop opening / 3bet / call ranges per position |
| `poker/engine.py` | Decision engine → `{action, sizing, equity, confidence, reason}` |
| `poker/evaluator.py` | `evaluate7`: direct best-of-7 (6× faster than combinations) |
| `poker/table.py` | NLHE state machine: blinds, betting, all-in, **side pots**, showdown |
| `poker/range_model.py` | Range expansion (`AKs`, `TT+`, `A2s+`) + equity-vs-range (P2) |
| `poker/profiling.py` | Opponent VPIP/PFR/aggression tracking (P3) |
| `poker/bots.py` | Strategies: `engine`, `adaptive`, `tag`, `lag`, `station`, `rock`, `random` |
| `poker/simulator.py` | Run N hands, BB/100 reports, profiles |
| `poker/tournament.py` | Sit-&-Go: rising blinds, busts, payouts, **ICM** (P1) |
| `poker/history.py` | Hand-history text + per-position leak report (P5) |
| `play.py` | CLI: `auto`, `sim`, `tourney`, `play` (terminal, zero deps) |
| `poker_gui.py` | PyQt6 graphical table + coach overlay (`--overlay` = floating HUD) |
| `tests/test_poker_engine.py` | 24 tests (evaluator, equity, engine, rules, side pots, ranges, ICM, leaks) |

Stronger engine (P4): 3bet bluffs, value/semibluff/bluff-raise postflop, equity
threshold that rises with bet size to avoid stack-off spirals. The `adaptive` bot
(P3) reads the table and exploits over-folders / stations.

The core (`poker/`, `play.py`) is **pure standard library** — runs and tests
with nothing installed. Only `poker_gui.py` needs PyQt6.

## Run it

```bash
# Terminal — watch bots play (verbose)
python play.py auto --hands 30 --lineup engine,tag,station,rock

# Terminal — fast simulation, just the report
python play.py sim --hands 5000 --lineup engine,station --seed 1

# Terminal — opponent profiles + per-position leak report
python play.py sim --hands 2000 --lineup adaptive,tag,station --profiles --leak adaptive

# Terminal — sit-n-go tournament with rising blinds + ICM payouts
python play.py tourney --lineup engine,adaptive,tag,station,rock,lag --prize 100

# Terminal — YOU play, with coach + training grade
python play.py play --villains tag,station,lag --train

# GUI — graphical table (PyQt6 is in ./venv on this machine)
venv/bin/python poker_gui.py watch --lineup engine,tag,station,rock
venv/bin/python poker_gui.py play  --villains tag,station,lag
venv/bin/python poker_gui.py play  --villains tag,station --overlay   # floating HUD

# Tests
python -m pytest tests/ -q
```

## Modes

- **auto / watch** — bots play each other automatically; you observe.
- **play** — you are HERO. The engine computes a recommendation (action,
  sizing, equity, confidence, reason) shown as an overlay; you decide.

## Design notes

- One decision engine (`poker/engine.py`) drives both the bots and the human
  coach, so the advice you see is exactly what a solid bot would do.
- Chips are conserved exactly (verified by a test): the table never creates or
  destroys chips — correct side-pot accounting.
- Deterministic when seeded (`--seed`) for reproducible sessions and tests.
