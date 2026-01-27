#!/usr/bin/env python3
"""
Training Script Semplificato per Massive Auto-Labeling
=======================================================
Training YOLOv8n per 100 epoche sul dataset Versione 1
"""

import os
import sys
from pathlib import Path

def main():
    print("=" * 70)
    print("🎴 TRAINING YOLOV8N - MODELLO SEME")
    print("=" * 70)
    
    # Import
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
        print(f"   ⚠️  Solo CPU disponibile")
    
    print(f"   Device selezionato: {device}")
    
    # Parametri
    MODEL = "yolov8n.pt"
    DATA_YAML = "data.yaml"
    EPOCHS = 100
    IMGSZ = 640
    
    print("\n" + "=" * 70)
    print("🚀 TRAINING CONFIGURATION")
    print("=" * 70)
    print(f"   Modello: {MODEL}")
    print(f"   Dataset: {DATA_YAML}")
    print(f"   Epochs: {EPOCHS}")
    print(f"   Image Size: {IMGSZ}")
    print(f"   Device: {device}")
    
    # Carica modello
    print("\n📥 Caricamento modello...")
    model = YOLO(MODEL)
    
    # Training
    print("\n🏋️  AVVIO TRAINING...\n")
    print("-" * 70)
    
    results = model.train(
        data=DATA_YAML,
        epochs=EPOCHS,
        imgsz=IMGSZ,
        device=device,
        plots=True,
        save=True,
        project="runs/detect",
        name="train",
        exist_ok=True,
        verbose=True,
        patience=20,
        batch=16,
        workers=4,
    )
    
    # Risultati
    print("\n" + "=" * 70)
    print("✅ TRAINING COMPLETATO!")
    print("=" * 70)
    
    best_path = Path("runs/detect/train/weights/best.pt")
    last_path = Path("runs/detect/train/weights/last.pt")
    
    print(f"\n📁 Modelli salvati:")
    print(f"   Best: {best_path}")
    print(f"   Last: {last_path}")
    
    if best_path.exists():
        print(f"\n✅ File best.pt generato con successo!")
        print(f"   Dimensione: {best_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    print("\n" + "=" * 70)
    print("🎉 PRONTO PER AUTO-LABELING!")
    print("=" * 70)

if __name__ == "__main__":
    main()
