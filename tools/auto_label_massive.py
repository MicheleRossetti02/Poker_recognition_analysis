#!/usr/bin/env python3
"""
Auto-Labeling Script per Massive Dataset
==========================================
Utilizza il modello best.pt per annotare automaticamente
le 1.415 immagini del dataset FOTO con confidenza 40%
"""

import os
import sys
from pathlib import Path
from tqdm import tqdm

def main():
    print("=" * 70)
    print("🏷️  AUTO-LABELING MASSIVE DATASET")
    print("=" * 70)
    
    # Configurazione
    MODEL_PATH = "runs/detect/train/weights/best.pt"
    IMAGES_DIR = "organized_dataset_clean/FOTO dataset"
    OUTPUT_DIR = "organized_dataset_clean/FOTO dataset_annotated"
    CONFIDENCE_THRESHOLD = 0.40  # 40%
    
    # Import
    from ultralytics import YOLO
    import cv2
    
    # Verifica modello
    print(f"\n📊 Configurazione:")
    print(f"   Modello: {MODEL_PATH}")
    print(f"   Directory Immagini: {IMAGES_DIR}")
    print(f"   Output: {OUTPUT_DIR}")
    print(f"   Confidence Threshold: {CONFIDENCE_THRESHOLD * 100}%")
    
    if not os.path.exists(MODEL_PATH):
        print(f"\n❌ ERRORE: Modello {MODEL_PATH} non trovato!")
        print("   Assicurati che il training sia completato.")
        sys.exit(1)
    
    # Crea directory output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    labels_dir = os.path.join(OUTPUT_DIR, "labels")
    images_dir = os.path.join(OUTPUT_DIR, "images")
    os.makedirs(labels_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    
    # Carica modello
    print(f"\n📥 Caricamento modello...")
    model = YOLO(MODEL_PATH)
    print(f"✅ Modello caricato!")
    
    # Trova tutte le immagini
    image_extensions = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']
    images_path = Path(IMAGES_DIR)
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(list(images_path.glob(f'*{ext}')))
    
    total_images = len(image_files)
    print(f"\n📁 Trovate {total_images} immagini")
    
    if total_images == 0:
        print(f"❌ ERRORE: Nessuna immagine trovata in {IMAGES_DIR}")
        sys.exit(1)
    
    # Processa ogni immagine
    print(f"\n🔄 Inizio auto-labeling...\n")
    
    processed = 0
    annotated = 0
    
    for img_path in tqdm(image_files, desc="Auto-labeling", unit="img"):
        try:
            # Predizione
            results = model.predict(
                source=str(img_path),
                conf=CONFIDENCE_THRESHOLD,
                verbose=False,
                save=False
            )
            
            # Estrai bounding boxes
            result = results[0]
            boxes = result.boxes
            
            if len(boxes) > 0:
                # Prepara file label YOLO format
                img_stem = img_path.stem
                label_file = os.path.join(labels_dir, f"{img_stem}.txt")
                
                # Ottieni dimensioni immagine
                img_height, img_width = result.orig_shape
                
                # Scrivi labels
                with open(label_file, 'w') as f:
                    for box in boxes:
                        # YOLO format: class_id x_center y_center width height (normalized)
                        cls_id = int(box.cls[0])
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        
                        # Converti in formato YOLO (normalized)
                        x_center = ((x1 + x2) / 2) / img_width
                        y_center = ((y1 + y2) / 2) / img_height
                        width = (x2 - x1) / img_width
                        height = (y2 - y1) / img_height
                        
                        # Scrivi linea
                        f.write(f"{cls_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
                
                # Copia immagine nella cartella output
                import shutil
                dest_img = os.path.join(images_dir, img_path.name)
                shutil.copy2(img_path, dest_img)
                
                annotated += 1
            
            processed += 1
            
        except Exception as e:
            print(f"\n⚠️  Errore su {img_path.name}: {e}")
            continue
    
    # Risultati
    print("\n" + "=" * 70)
    print("✅ AUTO-LABELING COMPLETATO!")
    print("=" * 70)
    print(f"\n📊 Statistiche:")
    print(f"   Immagini processate: {processed}/{total_images}")
    print(f"   Immagini annotate: {annotated}")
    print(f"   Immagini senza detection: {processed - annotated}")
    print(f"   Percentuale annotata: {(annotated/processed*100):.1f}%")
    
    print(f"\n📁 Output salvato in:")
    print(f"   Immagini: {images_dir}")
    print(f"   Labels: {labels_dir}")
    
    print("\n" + "=" * 70)
    print("🎉 PRONTO PER UPLOAD SU ROBOFLOW!")
    print("=" * 70)
    
    return annotated, processed

if __name__ == "__main__":
    main()
