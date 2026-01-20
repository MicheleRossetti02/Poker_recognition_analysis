# Setup Instructions - Data Factory

## ✅ Quick Setup

### 1. Activate Virtual Environment
```bash
cd /Users/michelerossetti/Documents/Apps/Poker_recognition_analysis
source venv312/bin/activate
```

### 2. Install Core Dependencies
```bash
# Dependencies for fast_capture.py (CORE - REQUIRED)
pip install opencv-python mss numpy

# Dependencies for upload (OPTIONAL - can install later) 
pip install roboflow tqdm chardet requests-toolbelt
```

### 3. Test Installation
```bash
# Test that fast_capture works
python fast_capture.py --help

# Should show all CLI options
```

---

## 🚀 Quick Start Workflow

### Step 1: Capture Images (READY NOW)
```bash
# Manual mode for testing
python fast_capture.py --manual

# Press SPACE to capture 2-3 test images
# Press Q to exit
```

**This creates:**
```
dataset/raw/session_YYYYMMDD_HHMM/
├── session_metadata.json
├── poker_952x676_v1_20260117_1400_0001.jpg
└── ...
```

### Step 2: Verify Output
```bash
# Check images were captured
ls -la dataset/raw/session_*/

# View metadata
cat dataset/raw/session_*/session_metadata.json | python -m json.tool
```

### Step 3: Production Capture
```bash
# Automatic capture with motion detection
python fast_capture.py --interval 2 --motion-threshold 5

# Play poker for 30-60 minutes
# Press Q when done
```

---

## 📤 Upload to Roboflow (Optional)

> **NOTE**: Il modulo roboflow ha alcune dipendenze complesse. 
> Se riscontri problemi con l'upload, puoi:
> 1. Caricare manualmente su https://app.roboflow.com
> 2. Usare questo script dopo aver risolto le dipendenze

### If Upload Works:
```bash
python upload_to_roboflow.py --session session_YYYYMMDD_HHMM
```

### Alternative - Manual Upload:
1. Go to https://app.roboflow.com
2. Login → Workspace: `pokergtobot` → Project: `poker-gto`
3. Click "Upload"
4. Drag & drop folder: `dataset/raw/session_YYYYMMDD_HHMM/`
5. Annotate and version dataset

---

##🎯 Core Features (WORKING NOW)

✅ **fast_capture.py** - Fully operational
- Motion detection with `cv2.absdiff()`
- Smart naming: `poker_952x676_v1_session_0001.jpg`
- Session management with JSON metadata
- Real-time statistics
- CLI arguments: `--interval`, `--motion-threshold`, `--manual`

✅ **Session Metadata** - Auto-generated
- Total frames analyzed
- Motion detection count
- Save rate percentage
- Complete session stats

✅ **Documentation** - Complete
- [DATA_FACTORY_GUIDE.md](file:///Users/michelerossetti/Documents/Apps/Poker_recognition_analysis/DATA_FACTORY_GUIDE.md)
- [test_data_factory.py](file:///Users/michelerossetti/Documents/Apps/Poker_recognition_analysis/test_data_factory.py)

---

## 🔧 Troubleshooting Roboflow

If you see `ModuleNotFoundError: No module named 'roboflow'`:

```bash
#Option 1: Fresh install in new terminal
source venv312/bin/activate
pip install --upgrade pip
pip install roboflow tqdm

# Option 2: Use manual upload (see above)

# Option 3: Create new venv (if persistent issues)
python3.12 -m venv venv_new
source venv_new/bin/activate
pip install opencv-python mss numpy roboflow tqdm ultralytics
```

---

## ✨ You're Ready!

**Start collecting data now:**
```bash
python fast_capture.py --interval 2 --motion-threshold 5
```

**The core system is fully operational!** 🎉
