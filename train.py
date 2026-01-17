"""
Training Script per YOLOv8 - Poker Card Recognition
=====================================================
Scarica il dataset da Roboflow e addestra YOLOv8 con accelerazione Metal (MPS).

IMPORTANTE: Esegui con Python 3.12 venv:
    source venv312/bin/activate && python train.py
"""

import os
import sys

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# Roboflow API
ROBOFLOW_API_KEY = "CUhu9vmliKIKhDxLNMVU"
WORKSPACE = "pokergtobot"
PROJECT = "poker-gto"
VERSION = 4

# Training Parameters
MODEL = "yolov8n.pt"  # nano model (veloce)
EPOCHS = 100
IMAGE_SIZE = 640
BATCH_SIZE = 16  # Riduci a 8 se hai problemi di memoria
DEVICE = "mps"  # Apple Silicon Metal

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("🎴 POKER CARD RECOGNITION - YOLOV8 TRAINING")
    print("=" * 70)
    
    # Import
    from roboflow import Roboflow
    from ultralytics import YOLO
    import torch
    
    # Verifica device
    print(f"\n📊 Verifica Hardware:")
    print(f"   Python: {sys.version}")
    print(f"   PyTorch: {torch.__version__}")
    
    if torch.backends.mps.is_available():
        device = "mps"
        print(f"   ✅ Apple Silicon Metal (MPS) disponibile!")
    elif torch.cuda.is_available():
        device = "cuda"
        print(f"   ✅ NVIDIA GPU (CUDA) disponibile!")
    else:
        device = "cpu"
        print(f"   ⚠️  Solo CPU disponibile (training più lento)")
    
    print(f"   Device selezionato: {device}")
    
    # =========================================================================
    # 1. DOWNLOAD DATASET
    # =========================================================================
    print("\n" + "=" * 70)
    print("📥 FASE 1: Download Dataset da Roboflow")
    print("=" * 70)
    
    rf = Roboflow(api_key=ROBOFLOW_API_KEY)
    project = rf.workspace(WORKSPACE).project(PROJECT)
    version = project.version(VERSION)
    
    print(f"\n   Workspace: {WORKSPACE}")
    print(f"   Project: {PROJECT}")
    print(f"   Version: {VERSION}")
    
    dataset = version.download("yolov8")
    
    data_yaml_path = os.path.join(dataset.location, "data.yaml")
    print(f"\n✅ Dataset scaricato in: {dataset.location}")
    print(f"   Config file: {data_yaml_path}")
    
    # =========================================================================
    # 2. TRAINING
    # =========================================================================
    print("\n" + "=" * 70)
    print("🚀 FASE 2: Training YOLOv8")
    print("=" * 70)
    
    print(f"\n   Modello base: {MODEL}")
    print(f"   Epochs: {EPOCHS}")
    print(f"   Image size: {IMAGE_SIZE}")
    print(f"   Batch size: {BATCH_SIZE}")
    print(f"   Device: {device}")
    
    # Carica il modello
    model = YOLO(MODEL)
    
    # Avvia il training
    print("\n🏋️ Avvio training... (potrebbe richiedere tempo)\n")
    
    results = model.train(
        data=data_yaml_path,
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        device=device,
        project="runs/poker_cards",
        name="train",
        exist_ok=True,
        verbose=True,
        plots=True,  # Grafici dei progressi
        # Ottimizzazioni per Apple Silicon
        workers=4,
        patience=20,  # Early stopping
        save=True,
        save_period=10,  # Salva checkpoint ogni 10 epochs
    )
    
    # =========================================================================
    # 3. RISULTATI
    # =========================================================================
    print("\n" + "=" * 70)
    print("✅ TRAINING COMPLETATO!")
    print("=" * 70)
    
    # Path al modello migliore
    best_model_path = "runs/poker_cards/train/weights/best.pt"
    last_model_path = "runs/poker_cards/train/weights/last.pt"
    
    print(f"\n📁 Modelli salvati:")
    print(f"   Best: {best_model_path}")
    print(f"   Last: {last_model_path}")
    
    # Copia il modello migliore nella cartella principale
    if os.path.exists(best_model_path):
        import shutil
        shutil.copy(best_model_path, "best.pt")
        print(f"\n✅ Modello copiato in: best.pt")
        print("\n📝 Per usare il modello, modifica main.py:")
        print('   YOLO_MODEL_PATH = "best.pt"')
    
    print("\n" + "=" * 70)
    print("🎉 FATTO! Puoi ora usare il modello per riconoscere le carte.")
    print("=" * 70)


if __name__ == "__main__":
    main()
