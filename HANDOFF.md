# HANDOFF — Poker_recognition_analysis

Documento di passaggio per chi continua il progetto (es. Codex). Stato al
2026-06-08. Tutto è su `main`, pushato su
`github.com/MicheleRossetti02/Poker_recognition_analysis`.

---

## 1. Cos'è il progetto

Due stack **indipendenti** nello stesso repo:

### A) Virtual-chip poker (nuovo, il cuore attuale)
Motore Texas Hold'em No-Limit **self-contained**, chip finte, zero soldi, zero
client esterni. Core in **pure-stdlib** (gira ovunque, anche in browser WASM).
Un solo motore decisionale guida sia i bot sia il coach umano.

### B) Live vision (preesistente)
`main_poker_vision_gto.py` (file da 2074 righe) legge lo schermo di un client
poker reale via YOLO + easyOCR e suggerisce mosse con overlay. Usa il modello
`POKER_GTO_BOT_V3/weights/best.pt` e il dataset `Poker-GTO-Production databasev3/`.
Ora il suo coach usa il motore nuovo tramite `live_coach.py` (adapter).

---

## 2. Mappa dei file (cosa serve davvero)

```
poker/                      # PACCHETTO MOTORE (pure-stdlib, + numpy opzionale)
  cards.py                  # Card, Deck, parsing
  evaluator.py              # evaluate7 (best-of-7 diretto, 6x più veloce di combinazioni)
  equity.py                 # Monte Carlo scalare (deterministico, seedabile)
  fast_equity.py            # NUMPY: score7_batch vettoriale + equity_fast (order-isomorfo)
  ranges.py                 # range preflop per posizione + normalize_hand
  range_model.py            # espansione notazione (AKs, TT+, A2s+) + equity_vs_range(s)
  engine.py                 # DECISION ENGINE (preflop range + postflop equity/pot-odds)
  table.py                  # macchina a stati NLHE: blinds, betting, all-in, SIDE POTS, showdown
  bots.py                   # strategie: engine/adaptive/tag/lag/station/rock/random
  profiling.py              # tracking avversari VPIP/PFR/aggro + adaptive bot
  simulator.py              # run_session N mani -> report BB/100 + profili
  tournament.py             # sit-n-go: blinds crescenti, bust, payout, ICM
  history.py                # hand-history testuale + leak report per posizione
  store.py                  # SQLite persistenza (usa sqlite3 — NON disponibile in Pyodide)
  arena.py                  # round_robin archetipi + tune_engine (grid search)
  render.py                 # helper terminale (colori carte)
  __init__.py               # export; store/arena import OPZIONALI (try/except) per WASM

play.py                     # CLI: auto | sim | tourney | play   (terminale, zero dep per core)
poker_gui.py                # GUI PyQt6: watch | play | replay | stats (+ --overlay HUD)
model_viewer.py             # carica best.pt e disegna detection su immagini (vision)
live_coach.py               # adapter: stato live -> engine.decide -> stringa coach
web_api.py                  # driver web turn-based (replay deterministico, usa NeedInput)
build_web.py                # copia poker/*.py in web/py/ per Pyodide
make_mac_apps.py            # genera apps/*.app (macOS, double-click, no terminale)

web/                        # WEB APP (Pyodide). Deploy statico Vercel.
  index.html style.css app.js
  manifest.webmanifest sw.js icon-*.png   # PWA
  py/...                    # copia del motore (generata da build_web.py)

tests/test_poker_engine.py  # 30 test (evaluator, equity, engine, regole, side-pot, ICM, ranges, fast_equity)
.github/workflows/tests.yml # CI: gira i test a ogni push (numpy + pytest, no torch)

legacy/                     # codice morto archiviato (vecchio stack vision)
tools/                      # script one-off di training/dataset
POKER_GTO_BOT_V3/weights/best.pt          # MODELLO ATTIVO (vision)
Poker-GTO-Production databasev3/          # DATASET ATTIVO (vision)
```

Documenti: `POKER_SIM_README.md` (motore+CLI+GUI), `DESKTOP_APPS.md` (app Mac),
`OVERPLAY_ROADMAP.md` (roadmap vision originale).

---

## 3. Ambiente / interpreti (IMPORTANTE)

- `venv/` → ha **tutto**: PyQt6 + numpy + torch + ultralytics + easyocr. Usalo per
  GUI, vision, model_viewer.
- `venv312/` → niente PyQt6. Va bene per core/test/CLI terminale.
- I test e il core girano con qualunque python; `fast_equity` e GUI servono numpy/PyQt6.

Comandi tipici:
```bash
venv312/bin/python -m pytest tests/ -q                 # 30 test (~100s, Monte Carlo)
venv312/bin/python play.py auto --hands 20 --lineup engine,tag,station,rock
venv/bin/python    poker_gui.py play --villains tag,station,lag
venv312/bin/python play.py sim --hands 12000 --lineup engine,tag,station --fast   # numpy veloce
python build_web.py && vercel deploy --prod --yes --cwd ./web                      # deploy web
python make_mac_apps.py                                                            # app desktop Mac
```

---

## 4. Decisioni di design / gotcha (NON reintrodurre i bug)

1. **Determinismo test vs velocità**: `engine.USE_FAST_EQUITY=False` di default
   (equity scalare seedabile → test deterministici). `--fast` o il web lo mettono
   True (numpy vettoriale). `fast_equity.score7_batch` è verificato order-isomorfo
   a `evaluator.evaluate7` (0 violazioni su 20k mani).
2. **Pyodide non ha `sqlite3`**: `poker/__init__` importa `store` e `arena` in
   try/except. NON rendere obbligatori. Il web NON include `store.py`.
3. **Leak storico già risolto**: il motore valuta equity vs mano random; facing
   big bet aumenta la soglia equity con la dimensione della puntata
   (`needed_raise`/`needed_call` salgono con `commit_ratio`) + cap sul re-raise →
   niente più guerre all-in con coppia. Disciplina OOP (`OOP_POSITIONS`). Non
   togliere questi guardrail.
4. **Web replay driver** (`web_api.py`): la `Table` è bloccante; il web rigioca la
   mano da capo in modo deterministico (stesso seed) finché serve input umano
   (`NeedInput`). Costoso ma corretto. Se rendi la Table interrompibile/coroutine
   si può eliminare il replay.
5. **Posizioni vision**: `main_poker_vision_gto.py` ordina `p_infos` per angolo
   (riga ~1327) → già seat-order. Non è un bug (audit iniziale sbagliato).
6. **Vercel CLI** rifiuta `git connect` per il nome repo con maiuscole → auto-deploy
   va fatto da dashboard Vercel (Import Git Repository).
7. **Chip conservation**: test `test_session_conserves_chips` garantisce che la
   Table non crei/distrugga chip (side-pot corretti). Mantienilo verde.

---

## 5. Stato distribuzione

- **Web app live**: https://pokercoach-alpha.vercel.app (PWA installabile, offline,
  ~208ms/mano vs 3 bot engine).
- **Desktop macOS**: `make_mac_apps.py` → `apps/Virtual Poker.app` (gioco) +
  `apps/Poker Coach Live.app` (coach su schermo reale). Bundle con path assoluti →
  `apps/` è gitignored (solo macchina dell'autore). Amici = web.
- **CI** verde su GitHub Actions.

---

## 6. Backlog (cosa manca / prossimi step)

### Alta priorità prodotto
- **W2** Web: scelta n° mani / modalità torneo + **classifica amici** (serve un
  backend leggero o un servizio di storage condiviso — es. Supabase, già MCP
  disponibile — perché il web ora è 100% client-side).
- **W3** Coach web più didattico: mostra **outs / draw / equity breakdown**, non
  solo azione+equity.
- **W6** App desktop **autonoma per amici** (PyInstaller .app/.exe ~100MB, senza
  venv, offline). Il gioco non richiede torch → bundle leggero fattibile. La vision
  sì (torch) → bundle pesante, valutare.

### Motore (qualità strategica)
- **N3+** usare `range_model.equity_vs_ranges` DENTRO il motore quando si fronteggia
  aggressione (oggi c'è solo la penalità euristica). Più accurato multiway.
- Bilanciamento: `arena.tune_engine` fa grid search VALUE_THRESHOLD×BLUFF_FREQ;
  estendere a più parametri e auto-applicare i migliori.
- Postflop: sizing multipli, board texture, blocker reali, ICM-aware preflop nei
  tornei (oggi ICM è solo nel report finale, non nelle decisioni).

### Vision (stack B)
- Unificare meglio `live_coach` (oggi stima `to_call`/stack in modo grezzo dalla
  OCR rumorosa). Migliorare rilevamento azioni avversari e stack effettivi.
- Ridurre il god-file `main_poker_vision_gto.py` (2074 righe, una classe fa tutto):
  separare capture / vision / state / decision / io.

### Infra / pulizia
- **W5** auto-deploy Vercel↔GitHub via dashboard (CLI bloccata).
- `pyproject.toml` + `pip install -e .` per installazione pulita del pacchetto.
- Ridurre tempo CI (equity Monte Carlo) con iterazioni minori nei test marcati slow.
- `node_modules` della vecchia dashboard React (`poker_gto_dashboard/`, 265M) è
  scollegata dal gioco attuale: decidere se rimuoverla.

---

## 7. Come verificare che tutto funzioni (smoke)

```bash
venv312/bin/python -m pytest tests/ -q          # deve dare "30 passed"
venv312/bin/python play.py tourney --lineup engine,adaptive,tag,station --prize 100
venv312/bin/python -c "from poker.arena import round_robin; \
  print(round_robin(['engine','tag','station','rock','lag','adaptive'], hands=2000).ranking[:3])"
python build_web.py            # ricopia il motore in web/py/
```
Atteso: 30 test verdi; nei round-robin/sim lunghi `engine`/`adaptive` in cima.

---

## 8. Prompt suggerito per Codex

> Continui il progetto Poker_recognition_analysis (vedi HANDOFF.md). Repo su
> main, CI verde, 30 test. C'è un motore poker pure-python (`poker/`), una CLI
> (`play.py`), GUI PyQt6 (`poker_gui.py`), una web app Pyodide (`web/`, live su
> Vercel) e app desktop macOS (`make_mac_apps.py`). Rispetta i gotcha della
> sezione 4 (specie: store/arena import opzionali per Pyodide, USE_FAST_EQUITY
> default False per test deterministici, guardrail anti-leak del motore).
> Obiettivo: [scegliere da backlog sez. 6, es. W2 torneo+classifica o W3 coach
> didattico]. Aggiungi test per ogni nuova feature e tieni la CI verde.
```
```
