# Benchmark guidato latenza (target p95)

## Obiettivo
Misurare in modo ripetibile la latenza end-to-end della pipeline async (`capture -> inference -> state -> overlay`) e verificare il rispetto del target:
- `p95 end-to-end <= 350ms` (target principale)
- `p99 end-to-end <= 500ms` (target stabilita')
- `mean inference <= 220ms`
- `mean state <= 45ms`
- `mean emit <= 20ms`

## Prerequisiti
- Poker client demo aperto e tavolo target visibile.
- Nessun training/script pesante in parallelo.
- Dashboard WebSocket opzionale (test separato).

## Comando di run benchmark
```bash
python3 main_poker_vision_gto.py 2>&1 | tee benchmark_runtime.log
```

Il runtime stampa periodicamente righe del tipo:
`LATENCY p50=... p95=... p99=... | mean(c/i/s/e)=...`

### Smoke benchmark (ambiente senza GUI/dashboard)
Solo per test tecnico della pipeline:
```bash
POKER_DISABLE_HUD=1 POKER_DISABLE_WS=1 python3 -u main_poker_vision_gto.py 2>&1 | tee benchmark_runtime_smoke.log
```

## Scenario test (ordine consigliato)
1. **Idle lock** (3 minuti): tavolo aperto ma mano non attiva.
2. **Hand attiva** (8 minuti): preflop/flop/turn/river normali.
3. **Stress azioni** (6 minuti): tavolo rapido con molte azioni consecutive.
4. **Con dashboard connessa** (5 minuti): websocket attivo con client dashboard.

## Raccolta risultati
Estrarre le finestre latency:
```bash
rg "LATENCY p50" benchmark_runtime.log > latency_windows.log
```

Estrarre i valori `p95` e `p99`:
```bash
sed -E 's/.*p95=([0-9.]+)ms.*p99=([0-9.]+)ms.*/\1 \2/' latency_windows.log > p95_p99_values.txt
```

Valori peggiori (worst-case su finestre):
```bash
awk '{print $1}' p95_p99_values.txt | sort -n | tail -n 1
awk '{print $2}' p95_p99_values.txt | sort -n | tail -n 1
```

Ultime 5 finestre (stato finale):
```bash
tail -n 5 latency_windows.log
```

## Criterio PASS/FAIL
- PASS se i peggiori valori su finestra rispettano:
  - `p95 <= 350ms`
  - `p99 <= 500ms`
- FAIL se uno dei due target e' superato.

## Playbook tuning rapido (se FAIL)
1. Aumentare OCR idle (`ocr_interval_frames_idle`) per ridurre costo OCR.
2. Aumentare `capture_thread_sleep_idle` se CPU in saturazione.
3. Ridurre log verbose (`debug_cards=False`, `verbose_runtime=False`).
4. Tenere una sola dashboard client durante il benchmark.
5. Ripetere benchmark con stesso scenario e confrontare `latency_windows.log`.
