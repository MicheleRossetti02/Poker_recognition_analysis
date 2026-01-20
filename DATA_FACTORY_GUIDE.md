# Data Factory - Quick Start Guide

## 🎯 Panoramica

Il **Data Factory** è un sistema professionale per raccogliere migliaia di immagini di alta qualità per il training del modello YOLOv8. Include:

- ✅ **Motion Detection** - Salva solo frame con cambiamenti significativi
- ✅ **Smart Naming** - Naming automatico con risoluzione e metadata
- ✅ **Session Management** - Organizzazione automatica in cartelle per sessione
- ✅ **Roboflow Upload** - Upload batch automatico con retry logic

---

## 📦 Installazione Dipendenze

```bash
# Attiva virtual environment
source venv312/bin/activate

# Installa dipendenze (se non già fatto)
pip install opencv-python mss numpy roboflow tqdm
```

---

## 🚀 Quick Start

### 1. Test Rapido Sistema

```bash
# Verifica che tutto sia installato correttamente
python test_data_factory.py
```

### 2. Prima Cattura (Manuale)

```bash
# Modalità manuale per test
python fast_capture.py --manual

# Premi SPAZIO per catturare 3-5 immagini
# Premi Q per uscire
```

**Output atteso:**
```
📁 Sessione creata: dataset/raw/session_20260117_1400/
📸 [1] poker_952x676_v1_20260117_1400_0001.jpg
📸 [2] poker_952x676_v1_20260117_1400_0002.jpg
...
```

### 3. Verifica Output

```bash
# Controlla immagini salvate
ls -la dataset/raw/session_*/

# Visualizza metadata sessione
cat dataset/raw/session_*/session_metadata.json | python -m json.tool
```

### 4. Upload a Roboflow (Dry Run)

```bash
# Test upload senza caricare (simulazione)
python upload_to_roboflow.py --session session_20260117_1400 --dry-run
```

### 5. Upload Reale

```bash
# Upload effettivo a Roboflow
python upload_to_roboflow.py --session session_20260117_1400
```

---

## 📖 Comandi Dettagliati

### `fast_capture.py` - Cattura Immagini

**Uso Base:**
```bash
# Cattura automatica ogni 2 secondi con motion detection
python fast_capture.py --interval 2 --motion-threshold 5
```

**Opzioni Avanzate:**
```bash
# Intervallo personalizzato (1.5s)
python fast_capture.py --interval 1.5

# Soglia motion più sensibile (3% invece di 5%)
python fast_capture.py --motion-threshold 3

# Modalità manuale (solo SPAZIO)
python fast_capture.py --manual

# Output directory personalizzata
python fast_capture.py --output my_dataset/raw

# Versione dataset (per tracking)
python fast_capture.py --version 2

# Visualizza differenza frame
python fast_capture.py --show-diff
```

**Controlli Durante Cattura:**
- `SPAZIO` - Cattura manuale (ignora motion detection)
- `P` - Pausa/Riprendi auto-capture
- `D` - Toggle visualizzazione differenza frame
- `Q` - Esci e salva statistiche

**Output:**
```
📁 Sessione: dataset/raw/session_20260117_1400/
   ├── poker_952x676_v1_20260117_1400_0001.jpg
   ├── poker_952x676_v1_20260117_1400_0002.jpg
   ├── ...
   └── session_metadata.json
```

**Metadata Sessione (`session_metadata.json`):**
```json
{
  "session_id": "20260117_1400",
  "start_time": "2026-01-17T14:00:00",
  "end_time": "2026-01-17T14:35:23",
  "duration_seconds": 2123,
  "total_frames_analyzed": 1845,
  "motion_detected_count": 456,
  "images_saved": 342,
  "save_rate_percent": 18.5,
  "motion_threshold_percent": 5.0,
  "dataset_version": 1,
  "resolution": "952x676"
}
```

---

### `upload_to_roboflow.py` - Upload Automatico

**Uso Base:**
```bash
# Upload sessione specifica
python upload_to_roboflow.py --session session_20260117_1400

# Upload directory specifica
python upload_to_roboflow.py --directory dataset/raw/session_20260117_1400/

# Upload TUTTE le sessioni
python upload_to_roboflow.py --all
```

**Opzioni:**
```bash
# Dry run (test senza upload)
python upload_to_roboflow.py --session session_20260117_1400 --dry-run

# Directory base personalizzata
python upload_to_roboflow.py --all --base-dir my_dataset/raw

# Verbose output
python upload_to_roboflow.py --session session_20260117_1400 --verbose
```

**Features:**
- ✅ Progress bar in tempo reale
- ✅ Retry automatico (max 3 tentativi)
- ✅ Skip duplicati automatico
- ✅ Report JSON dettagliato
- ✅ Gestione rate limits

**Upload Report (`upload_report_YYYYMMDD_HHMMSS.json`):**
```json
{
  "upload_timestamp": "2026-01-17T15:00:00",
  "session_uploaded": "session_20260117_1400",
  "total_images": 342,
  "successful_uploads": 340,
  "failed_uploads": 2,
  "skipped_duplicates": 0,
  "success_rate_percent": 99.4,
  "duration_seconds": 156,
  "failed_files": ["poker_..._0123.jpg"]
}
```

---

## 🔧 Parametri di Tuning

### Motion Threshold

Controlla la sensibilità del rilevamento movimento:

- **`--motion-threshold 3`** - Molto sensibile (salva più immagini)
  - Usa quando: Cambiamenti sottili (animazioni, contatori)
  - Save rate atteso: 25-35%

- **`--motion-threshold 5`** ⭐ **RACCOMANDATO**
  - Usa quando: Gaming normale
  - Save rate atteso: 15-25%

- **`--motion-threshold 10`** - Poco sensibile (salva meno immagini)
  - Usa quando: Solo grandi cambiamenti (nuove carte distribuite)
  - Save rate atteso: 5-15%

### Intervallo di Cattura

- **`--interval 1`** - Molto frequente (per azioni rapide)
- **`--interval 2`** ⭐ **RACCOMANDATO**
- **`--interval 3`** - Meno frequente (risparmia risorse)

**Regola d'oro:**
```
Intervallo basso + Threshold alto = Cattura solo grandi cambiamenti frequenti
Intervallo alto + Threshold basso = Cattura cambiamenti sottili meno frequenti
```

---

## 📋 Workflow Completo

### Scenario: Raccogliere 1000+ Immagini

**Step 1: Setup**
```bash
source venv312/bin/activate
python test_data_factory.py  # Verifica installazione
```

**Step 2: Cattura Durante Gioco (30-60 min)**
```bash
# Avvia PokerStars
# Poi:
python fast_capture.py --interval 2 --motion-threshold 5

# Gioca normalmente per 30-60 minuti
# Premi Q quando hai finito
```

**Step 3: Verifica Dati**
```bash
# Conta immagini
find dataset/raw/session_*/ -name "*.jpg" | wc -l

# Visualizza stats
cat dataset/raw/session_$(ls -t dataset/raw/ | head -1)/session_metadata.json | python -m json.tool
```

**Step 4: Upload a Roboflow**
```bash
# Test dry-run
python upload_to_roboflow.py --all --dry-run

# Upload reale
python upload_to_roboflow.py --all
```

**Step 5: Annotazione**
- Vai su https://app.roboflow.com
- Login → Workspace `pokergtobot` → Project `poker-gto`
- Annota le nuove immagini
- Versiona il dataset (es. v5)

**Step 6: Training**
```bash
# Aggiorna VERSION in train.py
# VERSION = 5

# Training
python train.py
```

---

## ❓ FAQ

**Q: Quante immagini servono?**
A: Per un modello robusto:
- Minimo: 500 immagini (accuratezza base)
- Raccomandato: 1000-2000 immagini (buona accuratezza)
- Ottimale: 3000+ immagini (eccellente accuratezza)

**Q: Come evito duplicati?**
A: Il motion detector filtra automaticamente. Verifica che `save_rate_percent` sia 10-30%. Se è 90%+, aumenta `--motion-threshold`.

**Q: Upload fallito con "Rate Limit"?**
A: Lo script ri-prova automaticamente. Se persiste, attendi 5 minuti e riprova.

**Q: Posso raccogliere dati da più tavoli contemporaneamente?**
A: Sì, ma usa sessioni separate. Modifica `CAPTURE_TOP/LEFT` tra sessioni o usa `calibrate_screen.py`.

**Q: Come verifico la qualità delle immagini?**
A: Apri alcune immagini da `dataset/raw/session_*/`. Verifica che le carte siano nitide e leggibili.

---

## 🐛 Troubleshooting

### Errore: "No module named 'roboflow'"
```bash
pip install roboflow tqdm
```

### Errore: "MSS: Screen capture permission denied"
```bash
# macOS: Abilita Screen Recording per Terminal
# Impostazioni → Privacy → Registrazione Schermo → Terminal
```

### Warning: "Motion always detected (100%)"
```bash
# Aumenta la soglia
python fast_capture.py --motion-threshold 10
```

### Errore Upload: "Invalid API Key"
```bash
# Verifica in train.py:
# ROBOFLOW_API_KEY = "..."
```

---

## 📊 Metriche di Successo

**Buona Sessione di Cattura:**
- ✅ Save rate: 10-30%
- ✅ Motion detected: 20-40% dei frame
- ✅ Immagini nitide e varie
- ✅ Diversi game states (preflop, flop, turn, river)

**Upload Riuscito:**
- ✅ Success rate: >95%
- ✅ Nessun duplicato eccessivo
- ✅ Report senza errori critici

---

## 🎓 Best Practices

1. **Varietà**: Cattura diverse situazioni di gioco
   - Carte diverse
   - Pot sizes diversi
   - Posizioni diverse del dealer button

2. **Qualità > Quantità**: 500 immagini varie > 2000 immagini simili

3. **Sessioni Multiple**: Meglio 5 sessioni da 200 immagini che 1 da 1000

4. **Backup**: Le sessioni sono in `dataset/raw/` - fai backup regolare

5. **Versioning**: Usa `--version` per tracciare evoluzioni del dataset

---

**🎉 Congratulazioni! Sei pronto a raccogliere dati di qualità per il tuo modello YOLO.**
