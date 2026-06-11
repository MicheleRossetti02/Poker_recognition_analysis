# Virtual-Chip Poker — engine, simulator & coach overlay

Self-contained No-Limit Texas Hold'em with **virtual chips only**. No real
money, no gambling, no external poker client. Built to be safe and offline:
the whole game lives in memory.

## 🌐 Play in the browser (for friends — no install)

**https://pokercoach-alpha.vercel.app**

Open the link on any phone/computer. The full Python engine runs in the browser
via Pyodide (WebAssembly) — nothing to install, no terminal, no account. Pick
the bots, play with virtual chips, the coach suggests every move.

To redeploy after engine changes: `python build_web.py && vercel deploy --prod --yes --cwd ./web`

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
| `poker/arena.py` | Round-robin ranking + engine param auto-tuning (N6) |
| `poker/store.py` | SQLite persistence for profiles & sessions (N4) |
| `play.py` | CLI: `auto`, `sim`, `tourney`, `play` (terminal, zero deps) |
| `poker_gui.py` | PyQt6 table + coach overlay (`--overlay` HUD, `replay` mode N5) |
| `model_viewer.py` | Visualise the trained YOLO model's detections on images (N7) |
| `live_coach.py` | Adapter feeding the engine into the live-vision coach (M3) |
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

# Save sessions to SQLite, then view charts (N4/N8)
python play.py sim --hands 2000 --lineup engine,tag,station --save
venv/bin/python poker_gui.py stats

# Visualise the trained model's detections (N7)
python model_viewer.py --dir "Poker-GTO-Production databasev3/test/images" --limit 5

# GUI — graphical table (PyQt6 is in ./venv on this machine)
venv/bin/python poker_gui.py watch  --lineup engine,tag,station,rock   # table + action log
venv/bin/python poker_gui.py play   --villains tag,station,lag         # coach + pot odds
venv/bin/python poker_gui.py play   --villains tag,station --overlay   # floating HUD
venv/bin/python poker_gui.py replay --lineup engine,tag,station --hands 6  # step through hands
venv/bin/python coach_overlay_app.py  # always-on-top manual coach + screenshot dataset capture

# Overlay capture dataset
# Flusso consigliato: premi "Seleziona area", trascina sul tavolo PokerStars
# e l'overlay compilerà automaticamente X/Y/W/H senza leggere la lista finestre.
# L'ultimo rettangolo selezionato viene salvato in ~/.poker_coach_overlay.json
# e ricaricato al prossimo avvio.
# "Solo area" nasconde i controlli finestra/coordinate e lascia il flusso rapido:
# Seleziona area / Usa area salvata -> Screenshot/Auto.
# Per rendere la lettura carte più stabile: apri "HUD piena", premi "Area Hero"
# e seleziona solo le due carte hero, poi "Area Board" e seleziona la zona
# community card. Le zone sono salvate relative al tavolo e riusate da "Leggi".
# "Aggiorna finestre" è opzionale e gira in background: se trova PokerStars,
# scegli la finestra dal menu "Finestra" e premi "Aggancia selezionata".
# "Diagnostica" controlla Quartz, lettura finestre macOS e suggerisce i permessi
# Accessibilità / Registrazione schermo quando servono.
# "Manuale ON/OFF" comprime i comandi lasciando visibile la lettura stimata.
# L'app parte in HUD compatta: mostra azione/equity/carte e il pulsante "Leggi".
# "HUD piena" riapre il pannello completo; "Leggi tavolo" usa il modello YOLO
# su uno screenshot dell'area selezionata e aggiorna Hero/Board/Street quando
# riconosce abbastanza carte. Ogni lettura salva anche un debug annotato in:
#   dataset/raw/overlay_session_YYYYMMDD_HHMMSS/vision_debug/
# Se la lettura non è affidabile, copia immagine+JSON in vision_failures/
# per usarli come esempi da annotare/fine-tunare.
# "Sempre sopra" decide se l'overlay resta davanti; "Click-through" lascia
# passare i click al tavolo per 10s; "Opacita" regola la trasparenza.
# I campi manuali ricalcolano il coach automaticamente dopo una breve pausa.
# "Screenshot" salva manualmente; "Auto" salva a intervallo in:
#   dataset/raw/overlay_session_YYYYMMDD_HHMMSS/images/
# con metadata JSONL accanto alle immagini, inclusa la lettura stimata. Se una
# cattura automatica fallisce, Auto si ferma e mostra l'errore senza chiudere l'app.

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
