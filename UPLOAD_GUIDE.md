# Upload Script - Quick Reference

## 🚀 Utilizzo Rapido

### Upload Sessione Singola
```bash
python upload_to_roboflow.py dataset/raw/session_20260117_133527/
```

### Upload Tutte le Sessioni (Ricorsivo)
```bash
python upload_to_roboflow.py dataset/raw/ --recursive
```

### Dry Run (Test Senza Upload)
```bash
python upload_to_roboflow.py dataset/raw/session_20260117_133527/ --dry-run
```

### Configurazione Avanzata
```bash
# 8 thread per massima performance
python upload_to_roboflow.py dataset/raw/ -r --workers 8

# Batch name custom
python upload_to_roboflow.py dataset/raw/custom/ --batch-name "test_batch_v1"
```

---

## 🔑 Features Principali

### 1. Import Credenziali Automatico
**Non serve hardcodare chiavi API!**

Lo script legge automaticamente da `train.py`:
```python
ROBOFLOW_API_KEY = 'CUhu9vmliKIKhDxLNMVU'
WORKSPACE = 'pokergtobot'
PROJECT = 'poker-gto'
```

### 2. Multi-Threading
- **Default: 4 thread** simultanei
- Configurable: `--workers 8` per massima velocità
- ThreadPoolExecutor per gestione robusta

**Performance:**
- Single thread: ~2 img/s
- 4 threads: ~7-8 img/s
- 8 threads: ~12-15 img/s (limitato da API rate)

### 3. Retry Logic Intelligente
- **3 tentativi** automatici per ogni fallimento
- **Exponential backoff**: 1s → 2s → 4s
- **Rate limit detection**: pausa automatica e retry
- **Duplicate detection**: skip senza errori

### 4. Batch Tagging Automatico
Organizzazione immagini su Roboflow per sessione:
- Auto-detect: estrae `session_YYYYMMDD_HHMMSS` dalla path
- Manual: `--batch-name "my_custom_batch"`
- Filtrabile su Roboflow dashboard

### 5. Logging Dettagliato
```
📤 Uploading 248 immagini (4 threads)...
   ✅ poker_952x676_v4_133530_234.jpg
   ✅ poker_952x676_v4_133545_891.jpg
   ⏭️  poker_952x676_v4_133602_123.jpg (duplicato)
   ❌ poker_952x676_v4_133620_456.jpg (fallito dopo 3 retry)
```

---

## 📊 Report Generato

Ogni upload crea `upload_report_YYYYMMDD_HHMMSS.json`:

```json
{
  "upload_timestamp": "2026-01-17T14:30:00",
  "directory": "dataset/raw/session_20260117_133527",
  "batch_name": "session_20260117_133527",
  "duration_seconds": 32.5,
  "throughput_img_per_sec": 7.6,
  "workers": 4,
  "total_files": 248,
  "successful": 245,
  "failed": 1,
  "skipped": 2,
  "success_rate": 98.8,
  "failed_files": ["poker_..._0142.jpg"]
}
```

---

## 🔧 Argomenti CLI

| Argomento | Short | Default | Descrizione |
|-----------|-------|---------|-------------|
| `directory` | - | Required | Directory con immagini |
| `--recursive` | `-r` | False | Scansiona subdirectory |
| `--batch-name` | `-b` | Auto | Nome batch/tag |
| `--workers` | `-w` | 4 | Thread pool size |
| `--dry-run` | - | False | Simula senza upload |
| `--verbose` | `-v` | True | Output dettagliato |

---

## 💡 Best Practices

### Performance Optimization
```bash
# Network veloce → più thread
python upload_to_roboflow.py dataset/raw/ -r --workers 8

# Network lenta → meno thread per evitare timeout
python upload_to_roboflow.py dataset/raw/ -r --workers 2
```

### Organizzazione Batch
```bash
# Sessioni separate = batch separati (raccomandato)
python upload_to_roboflow.py dataset/raw/session_20260117_1000/
python upload_to_roboflow.py dataset/raw/session_20260117_1500/

# Oppure batch custom per grouping logico
python upload_to_roboflow.py dataset/raw/day1/ --batch-name "training_day1"
```

### Error Recovery
Se upload si interrompe:
```bash
# Re-run stesso comando
python upload_to_roboflow.py dataset/raw/session_20260117_1000/

# Script skippa automaticamente duplicati già uploadati
# ⏭️ poker_..._0001.jpg (duplicato)
# ✅ poker_..._0142.jpg (nuovo)
```

---

## 🐛 Troubleshooting

### "train.py not found"
```bash
# Assicurati di essere nella directory progetto
cd /path/to/Poker_recognition_analysis
python upload_to_roboflow.py ...
```

### "ModuleNotFoundError: roboflow"
```bash
pip install roboflow tqdm
```

### "Rate Limit"
Lo script gestisce automaticamente, ma se persiste:
```bash
# Riduci workers
python upload_to_roboflow.py ... --workers 2

# Oppure attendi 5 minuti e riprova
```

### "Too many failures"
Controlla `upload_report_*.json` per vedere quali file:
```bash
cat upload_report_*.json | python -m json.tool
# Cerca "failed_files": [...]
```

---

## 📋 Checklist Pre-Upload

Prima di uploadare, verifica:

- [ ] `dataset/data.yaml` ha classe `52: button`
- [ ] Immagini nella directory sono `.jpg` di buona qualità
- [ ] `train.py` contiene credenziali corrette
- [ ] Roboflow account ha spazio disponibile

---

## 🎯 Workflow Completo

### 1. Cattura Dati
```bash
python fast_capture.py --threshold 5.0 --interval 2
# Gioca 30-60 min
# Premi Q per uscire
```

### 2. Verifica Output
```bash
ls dataset/raw/session_*/
# Dovresti vedere 100-500 immagini
```

### 3. Test Upload (Dry Run)
```bash
python upload_to_roboflow.py dataset/raw/session_20260117_*/ --dry-run
# Verifica che tutto funzioni
```

### 4. Upload Reale
```bash
python upload_to_roboflow.py dataset/raw/session_20260117_*/
```

### 5. Verifica su Roboflow
- Login: https://app.roboflow.com
- Workspace: `pokergtobot` → Project: `poker-gto`
- Filtra per batch: `session_20260117_133527`
- Verifica immagini caricate

### 6. Annotazione
- Usa `ANNOTATION_GUIDE.md` e `BUTTON_ANNOTATION_REFERENCE.md`
- Annota tutte le carte + button
- Verifica qualità con checklist

### 7. Versioning & Training
```bash
# Su Roboflow: crea versione (es. v5)
# Aggiorna train.py: VERSION = 5
python train.py
```

---

**Upload script pronto per uso production!** 📤✨
