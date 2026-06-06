# Overplay Poker Vision - Roadmap Esecutiva

## Obiettivo progetto
Costruire un sistema overplay in tempo reale per tornei demo: riconoscimento stato tavolo, suggerimento strategico GTO-like, overlay sopra la finestra di gioco e modulo storico basato su hand history.

## Stato attuale (diagnosi sintetica)
- Runtime live compilabile senza warning bloccanti sui moduli principali.
- Detection Hero/Board stabilizzata con filtri temporali multi-frame (anti-flicker).
- Pipeline asincrona completa e profiler p95 attivi; benchmark guidato pronto per validazione sul campo.
- Il motore decisionale e' preflop semplificato (non solver completo).
- Non esiste ancora un modulo ingest/upload per hand history PokerStars.

## Classificazione priorita'

### P0 - Critico (blocca il funzionamento)
- Fix sintassi/runtime del bot live.
- Fix bug logici su detection stato giocatori.
- Correzione payload WebSocket (hero cards/pot coerente).
- Verifica compilazione end-to-end dei moduli live.

### P1 - Alta importanza (stabilita' e affidabilita')
- Lock robusto della finestra target e gestione fallback.
- Stabilizzazione riconoscimento hero/board con filtri multi-frame.
- Riduzione latenza (pipeline asincrona + OCR throttling).
- Overlay stabile ancorato al tavolo.

### P2 - Media importanza (qualita' strategica e prodotto)
- Evoluzione motore decisionale (stack depth, action sequence, postflop light).
- Dashboard live con reason/confidence/action history.
- Logging strutturato e metriche operative (latency, confidence, fps).

### P3 - Evolutivo (coaching a 360)
- Upload e parsing hand history / tournament summary.
- Storage analitico (SQLite o DuckDB).
- Report coaching: leak per posizione, trend, spot costosi.

## Workstream tecnici

### 1) Runtime live e stabilita' core
- File principali: `main_poker_vision_gto.py`, `websocket_server.py`, `window_capture.py`.
- Deliverable: processo avviabile senza crash e con output coerente.

### 2) Vision pipeline
- Rilevazione carte Hero/Board robusta.
- Classificazione scena (`NO_TABLE`, `TABLE_IDLE`, `HAND_ACTIVE`, `SHOWDOWN`).
- Tracking temporale per ridurre flicker e false positive.

### 3) Decision engine
- Da tabella ABC a motore parametrico GTO-like.
- Input minimi: posizione, stack effettivo, sequenza azioni, street.
- Output: action, sizing, confidence, short reason.

### 4) UI overplay e dashboard
- Overlay trasparente sopra tavolo con coordinate affidabili.
- Pannello compatto: suggerimento + stato rilevamento.
- Dashboard separata per debug e revisione sessione.

### 5) Modulo documenti (hand history)
- Ingest file multipli.
- Parser PokerStars con deduplica.
- Panoramiche sessione/torneo e report automatici.

## KPI di accettazione
- Avvio runtime live: 10/10 sessioni senza crash all'avvio.
- Accuratezza hero cards >= 97% su set demo validato.
- Riconoscimento board count >= 99%.
- Latenza suggerimento p95 <= 350ms.
- Stabilita' sessione demo >= 2 ore senza stop.

## Piano operativo (ordine reale)

### Sprint 1 - Kickoff tecnico (P0)
- [x] Fix errori bloccanti in runtime live.
- [x] Correggere payload WebSocket e variabili non definite.
- [x] Eseguire check compilazione moduli principali.

### Sprint 2 - Stabilizzazione tavolo (P1)
- [x] Hard lock finestra target.
- [x] Migliorare detection Hero/Board con filtri temporali multi-frame.
- [x] Correggere mapping coordinate overlay.

### Sprint 3 - Prestazioni (P1)
- [x] OCR throttling e cache incrementale.
- [x] Pipeline asincrona capture/inference/state/overlay.
- [x] Profilazione p95 latenza.

### Sprint 4 - Strategia (P2)
- [ ] Refactor motore decisionale in layer separato.
- [ ] Introduzione parametri stack depth e sequence-aware.
- [ ] API output standard action/sizing/confidence/reason.

### Sprint 5 - Storico e coaching (P3)
- [ ] Parser hand history PokerStars.
- [ ] Storage e metriche aggregate.
- [ ] Report leak e review periodica.

### Sprint 6 - Benchmark guidato e hardening (P1)
- [x] Definire benchmark guidato con target p95/p99.
- [x] Riduzione rumore runtime (wait-log throttle e summary solo in active mode).
- [x] Ottimizzazioni essenziali anti-rallentamento (OCR dinamico, salvataggio DB throttled, broadcast WS throttled).

## Avvio primi step (esecuzione immediata)
- Step A: roadmap creata in questo documento.
- Step B: fix P0 avviati e applicati su runtime live e websocket.
- Step C: validazione tecnica eseguita con compilazione moduli.

## Log avanzamento
- 2026-02-09: completato kickoff tecnico P0 (sintassi/runtime, payload websocket, compilazione moduli live).
- 2026-02-09: avviati step P1 consigliati (window lock robusto, mapping overlay, OCR throttling).
- 2026-02-09: completata fase successiva prestazioni (pipeline async 4-stage + profiler p95 end-to-end).
- 2026-02-09: chiuso Sprint 2 con filtri temporali Hero/Board multi-frame (anti-flicker + isteresi).
- 2026-02-09: creato benchmark guidato p95/p99 in `BENCHMARK_GUIDATO_P95.md`.
- 2026-02-09: applicato hardening anti-rallentamento (OCR dinamico, throttling I/O DB e WebSocket, log waiting ridotti).
