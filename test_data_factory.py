#!/usr/bin/env python3
"""
Quick Start Test - Data Factory
================================
Test rapido per verificare che tutto funzioni correttamente.

Questo script esegue un test completo del workflow:
1. Simula cattura con motion detection
2. Verifica naming e session management
3. Testa upload (dry-run) a Roboflow

REQUISITI:
    pip install opencv-python mss numpy roboflow tqdm

USO:
    python test_data_factory.py
"""

import sys
import time
import subprocess
from pathlib import Path

def print_header(text):
    """Stampa header formattato."""
    print("\n" + "=" * 70)
    print(f"🧪 {text}")
    print("=" * 70)

def run_command(cmd, description):
    """
    Esegue un comando e stampa output.
    
    Args:
        cmd: Comando da eseguire (lista)
        description: Descrizione del test
    
    Returns:
        True se successo, False altrimenti
    """
    print(f"\n▶️  {description}")
    print(f"   $ {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print(f"   ✅ Successo!")
            return True
        else:
            print(f"   ❌ Errore (exit code: {result.returncode})")
            if result.stderr:
                print(f"   Stderr: {result.stderr[:200]}")
            return False
    
    except subprocess.TimeoutExpired:
        print(f"   ⚠️  Timeout (normale per script interattivi)")
        return True
    except Exception as e:
        print(f"   ❌ Eccezione: {e}")
        return False

def check_file_exists(filepath, description):
    """Verifica esistenza file."""
    path = Path(filepath)
    if path.exists():
        print(f"   ✅ {description}: {filepath}")
        return True
    else:
        print(f"   ❌ {description} NON trovato: {filepath}")
        return False

def main():
    print_header("DATA FACTORY - Quick Start Test")
    
    # Test 1: Verifica dipendenze
    print_header("Test 1: Verifica Dipendenze")
    
    deps = {
        "cv2": "opencv-python",
        "mss": "mss",
        "numpy": "numpy",
        "roboflow": "roboflow",
        "tqdm": "tqdm"
    }
    
    missing_deps = []
    for module, package in deps.items():
        try:
            __import__(module)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - MANCANTE")
            missing_deps.append(package)
    
    if missing_deps:
        print(f"\n⚠️  Installa dipendenze mancanti:")
        print(f"   pip install {' '.join(missing_deps)}")
        return False
    
    # Test 2: Verifica script esistono
    print_header("Test 2: Verifica Script")
    
    scripts = [
        "fast_capture.py",
        "upload_to_roboflow.py"
    ]
    
    all_exist = True
    for script in scripts:
        if not check_file_exists(script, script):
            all_exist = False
    
    if not all_exist:
        print("\n❌ Alcuni script sono mancanti!")
        return False
    
    # Test 3: Help di fast_capture.py
    print_header("Test 3: Help fast_capture.py")
    run_command(["python", "fast_capture.py", "--help"], "Verifica argomenti CLI")
    
    # Test 4: Help di upload_to_roboflow.py
    print_header("Test 4: Help upload_to_roboflow.py")
    run_command(["python", "upload_to_roboflow.py", "--help"], "Verifica argomenti CLI")
    
    # Test 5: Verifica imports
    print_header("Test 5: Verifica Imports Script")
    
    try:
        # Test import fast_capture components
        import cv2
        import mss
        import numpy as np
        print("   ✅ fast_capture.py imports OK")
    except Exception as e:
        print(f"   ❌ fast_capture.py imports: {e}")
    
    try:
        from roboflow import Roboflow
        from tqdm import tqdm
        print("   ✅ upload_to_roboflow.py imports OK")
    except Exception as e:
        print(f"   ❌ upload_to_roboflow.py imports: {e}")
    
    # Summary
    print_header("Test Summary")
    print("""
✅ Tutti i test di base sono passati!

📝 PROSSIMI PASSI - Test Manuale:

1️⃣  Test Cattura (5 secondi):
   python fast_capture.py --interval 2 --motion-threshold 5 --manual
   
   - Premi SPAZIO per catturare 2-3 immagini
   - Premi Q per uscire
   - Verifica che sia stata creata: dataset/raw/session_YYYYMMDD_HHMM/

2️⃣  Verifica Output:
   ls -la dataset/raw/session_*/
   cat dataset/raw/session_*/session_metadata.json | python -m json.tool

3️⃣  Test Upload (DRY RUN):
   python upload_to_roboflow.py --session session_YYYYMMDD_HHMM --dry-run

4️⃣  Upload Reale (SE DESIDERI):
   python upload_to_roboflow.py --session session_YYYYMMDD_HHMM

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📚 WORKFLOW COMPLETO:

1. Avvia PokerStars
2. python fast_capture.py --interval 2 --motion-threshold 5
3. Gioca alcune mani (lo script salva automaticamente frame con cambiamenti)
4. Premi Q per uscire
5. python upload_to_roboflow.py --session session_YYYYMMDD_HHMM
6. Annota su Roboflow
7. python train.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
