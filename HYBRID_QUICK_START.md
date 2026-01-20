# Data Factory Hybrid - Quick Start Guide

## 🎯 Novità Versione Hybrid

**Data Factory Hybrid** combina due metodi di motion detection:

| Metodo | Algoritmo | Migliore Per | Soglia Default |
|--------|-----------|--------------|----------------|
| **percent** ⭐ | cv2.absdiff + threshold | Generale, robusto | 5.0% |
| **mse** | Mean Squared Error | Cambiamenti drastici (carte distribuite) | 15.0 |

---

## ⚡ Quick Start

### Test Rapido (Percent Method - Default)
```bash
python fast_capture.py --threshold 5.0 --interval 2
```

### Test MSE Method
```bash
python fast_capture.py --motion-method mse --threshold 15 --interval 2
```

### Modalità Manuale
```bash
python fast_capture.py --manual
```

---

## 🔧 Argomenti CLI Completi

```bash
python fast_capture.py [OPZIONI]

OPZIONI:
  --motion-method [percent|mse]  # Metodo rilevamento (default: percent)
  --threshold N                  # Soglia movimento (auto-detect se omesso)
  --interval N                   # Intervallo secondi (default: 2)
  --output DIR                   # Directory output (default: dataset/raw)
  --version N                    # Versione dataset (default: 4)
  --manual                       # Modalità manuale (solo SPAZIO)
```

---

## 📊 Confronto Metodi

### Percent Method (Raccomandato ⭐)

**Come Funziona:**
1. `cv2.absdiff()` calcola differenza pixel tra frame
2. Binary threshold a 25 identifica pixel "cambiati"
3. Conta % pixel cambiati
4. Salva se % >= soglia

**Pro:**
- ✅ Robusto a illuminazione
- ✅ Sensibile a piccoli cambiamenti (carte che si spostano)
- ✅ Calibrazione intuitiva (5% = 1 pixel su 20 cambia)

**Contro:**
- ❌ Può essere sensibile a animazioni UI

**Best Practice:**
- Soglia 3-5% per catturare micro-movimenti
- Soglia 7-10% per solo grandi cambiamenti

### MSE Method

**Come Funziona:**
1. Calcola errore quadratico medio tra frame
2. MSE = Σ(pixel_current - pixel_prev)² / totale_pixel
3. Salva se MSE >= soglia

**Pro:**
- ✅ Molto sensibile a cambiamenti drastici
- ✅ Meno false positive da animazioni sottili

**Contro:**
- ❌ Meno intuitivo da calibrare
- ❌ Dipendente dalla risoluzione

**Best Practice:**
- Soglia 10-15 per carte distribuite
- Soglia 20+ per solo nuove mani

---

## 🎨 UI Preview - Cosa Significa

Durante la cattura, vedi:

```
🔴 REC (2s)              ← Status (Recording/Pausa/Manuale)
Salvate: 42 (18.5%)      ← Immagini salvate (save rate)
Change: 7.3% ✓           ← Motion metric corrente + detección
Method: PERCENT          ← Metodo attivo
Next: 1.2s              ← Countdown prossima cattura
```

**Interpretazione Motion Metric:**

- **Percent Method:**
  - `Change: 2.1% ✗` - Nessun movimento significativo
  - `Change: 6.8% ✓` - Movimento rilevato! (verde)
  
- **MSE Method:**
  - `MSE: 8.2 ✗` - Sotto soglia
  - `MSE: 21.5 ✓` - Sopra soglia! (verde)

---

## 📁 Output

### Struttura Sessione
```
dataset/raw/
└── session_20260117_133527/
    ├── session_info.json          ← Metadata completi
    ├── poker_952x676_v4_133530_234.jpg
    ├── poker_952x676_v4_133545_891.jpg
    └── ...
```

### session_info.json
```json
{
  "session_id": "20260117_133527",
  "start_time": "2026-01-17T13:35:27",
  "end_time": "2026-01-17T14:20:15",
  "duration_seconds": 2688,
  "frames_analyzed": 1344,
  "motion_detected_count": 324,
  "images_saved": 248,
  "save_rate_percent": 18.45,
  "dataset_version": 4,
  "motion_detection": {
    "method": "percent",
    "threshold": 5.0,
    "resize_optimization": "200x150"
  },
  "resolution": "952x676"
}
```

---

## 🧪 Come Calibrare la Soglia

### Step 1: Run Test (30 secondi)
```bash
python fast_capture.py --threshold 5.0 --interval 2
```

### Step 2: Osserva Metric nella UI
- Guarda il valore quando distribuiscono carte → dovrebbe essere >10%
- Guarda il valore quando nulla cambia → dovrebbe essere <3%

### Step 3: Aggiusta Soglia

**Se salva TROPPO (save rate >40%):**
```bash
# Aumenta soglia
python fast_capture.py --threshold 8.0
```

**Se salva TROPPO POCO (save rate <10%):**
```bash
# Diminuisci soglia
python fast_capture.py --threshold 3.0
```

### Step 4: Target Save Rate

**Ideale: 15-25%**
- Significa che 1 frame su 4-6 è rilevante
- Buon bilanciamento varietà/efficienza

---

## 🎮 Controlli Durante Cattura

| Tasto | Azione |
|-------|--------|
| **SPAZIO** | Cattura manuale (ignora motion, salva subito) |
| **P** | Pausa/Riprendi auto-capture |
| **Q** | Esci e salva statistiche |

---

## 💡 Scenario d'Uso

### Scenario 1: Raccolta Dati Generale
```bash
# Percent method con soglia standard
python fast_capture.py --threshold 5.0 --interval 2

# Gioca 30-60 minuti normalmente
# Target: 200-400 immagini varie
```

### Scenario 2: Solo Nuove Mani
```bash
# MSE method con soglia alta
python fast_capture.py --motion-method mse --threshold 20 --interval 3

# Salva solo quando distribuiscono nuove carte
# Target: 50-100 immagini (solo inizio mani)
```

### Scenario 3: Micro-Movimenti (Button Position)
```bash
# Percent con soglia bassa
python fast_capture.py --threshold 3.0 --interval 1.5

# Cattura anche cambiamenti sottili (button che si sposta)
# Target: 300+ immagini ad alta varietà
```

### Scenario 4: Controllo Totale
```bash
# Modalità manuale
python fast_capture.py --manual

# Tu decidi quando premere SPAZIO
# Perfetto per situazioni specifiche
```

---

## 🔍 Troubleshooting

### "Salva tutto, anche scene identiche"
→ **Soglia troppo bassa**, aumenta:
```bash
--threshold 8.0  # per percent
--threshold 25   # per mse
```

### "Non salva mai nulla"
→ **Soglia troppo alta**, diminuisci:
```bash
--threshold 3.0  # per percent
--threshold 10   # per mse
```

### "MSE values sembrano strani"
→ MSE dipende da risoluzione/illuminazione. Usa **percent method** per risultati più prevedibili.

### "Voglio il vecchio comportamento"
→ Usa modalità manuale o soglia molto bassa:
```bash
python fast_capture.py --threshold 0.1  # salva quasi tutto
```

---

## 📈 Metriche di Successo

**Buona Sessione:**
- ✅ Save rate: 15-25%
- ✅ Motion detected: 20-35% dei frame
- ✅ Durata: 30+ minuti
- ✅ Immagini: 200-500

**Verifica Qualità:**
```bash
# Controlla immagini
ls dataset/raw/session_*/

# Vedi metadata
cat dataset/raw/session_*/session_info.json | python -m json.tool

# Conta immagini
find dataset/raw/session_*/ -name "*.jpg" | wc -l
```

---

## 🎯 Best Practice Finale

1. **Inizia con percent method** - Più intuitivo
2. **Calibra con test 30s** - Osserva metric nella UI
3. **Target save rate 15-25%** - Bilanciamento ottimale
4. **Sessioni multiple** - Meglio 3x30min che 1x90min
5. **Verifica metadata** - Controlla session_info.json

**Sei pronto per raccogliere dati di qualità con motion detection intelligente!** 🎴📊
