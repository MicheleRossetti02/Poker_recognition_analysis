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

# Training Parameters - OPTIMIZED FOR PRODUCTION
MODEL = "yolov8s.pt"  # Upgrade to SMALL for better accuracy (still MPS-compatible)
EPOCHS = 200  # Increased for better convergence
IMAGE_SIZE = 640
BATCH_SIZE = 16  # Riduci a 8 se hai problemi di memoria con yolov8s
DEVICE = "mps"  # Apple Silicon Metal

# Hyperparameters Optimization
LR0 = 0.01  # Initial learning rate
LRF = 0.01  # Final learning rate (fraction of lr0)
WARMUP_EPOCHS = 3  # Learning rate warmup
PATIENCE = 30  # Early stopping patience (increased for larger model)

# Data Augmentation (for better generalization)
AUGMENT = True
MOSAIC = 1.0  # Mosaic augmentation probability
MIXUP = 0.1  # Mixup augmentation probability
HSV_H = 0.015  # Image HSV hue augmentation
HSV_S = 0.7  # Image HSV saturation augmentation
HSV_V = 0.4  # Image HSV value augmentation

# AGGRESSIVE AUGMENTATION for PokerStars Variance
# -------------------------------------------------
# Geometric transformations
DEGREES = 5.0        # Rotation augmentation (±5°) - cards slightly tilted
TRANSLATE = 0.1      # Translation (10% shift) - handle position variance
SCALE = 0.15         # Scale variance (±15%) - different zoom levels
SHEAR = 2.0          # Shear transformation - perspective changes
PERSPECTIVE = 0.0003 # Perspective distortion - viewing angles
FLIPUD = 0.0         # NO vertical flip (cards have orientation)
FLIPLR = 0.0         # NO horizontal flip (suits would be mirrored)

# Quality variance
BLUR = 0.01          # Motion blur probability (1%)

# Advanced augmentation
COPY_PASTE = 0.05    # 5% probability to paste cards from other images
CLOSE_MOSAIC = 0.3   # Use for 30% of epochs (better for small objects)

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
        # Core parameters
        data=data_yaml_path,
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        device=device,
        project="runs/poker_cards",
        name="train",
        exist_ok=True,
        verbose=True,
        plots=True,
        
        # Optimization
        workers=4,
        patience=PATIENCE,
        save=True,
        save_period=10,
        
        # Learning rate schedule
        lr0=LR0,
        lrf=LRF,
        warmup_epochs=WARMUP_EPOCHS,
        warmup_momentum=0.8,    # Start momentum at 0.8
        momentum=0.937,         # Final momentum  
        weight_decay=0.0005,    # L2 regularization
        
        # Standard augmentation
        augment=AUGMENT,
        mosaic=MOSAIC,
        mixup=MIXUP,
        hsv_h=HSV_H,
        hsv_s=HSV_S,
        hsv_v=HSV_V,
        
        # AGGRESSIVE augmentation (PokerStars variance)
        degrees=DEGREES,
        translate=TRANSLATE,
        scale=SCALE,
        shear=SHEAR,
        perspective=PERSPECTIVE,
        flipud=FLIPUD,
        fliplr=FLIPLR,
        blur=BLUR,
        copy_paste=COPY_PASTE,
        close_mosaic=CLOSE_MOSAIC,
        
        # Optimizer
        optimizer='AdamW',      # Better than SGD for card detection
        cos_lr=True,            # Cosine learning rate scheduling
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
