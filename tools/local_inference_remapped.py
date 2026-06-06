#!/usr/bin/env python3
"""
🏷️ Local Auto-Labeling with Class Remapping
==============================================
Esegue inferenza locale su 1,345 immagini usando best.pt
e corregge la mappatura delle classi per allinearsi a Roboflow.

PROBLEMA RILEVATO:
- Tc (Ten of clubs) è all'indice 55 invece che tra le carte (0-51)
- UI elements sono shiftati di 1 posizione

RIMAPPATURA:
- Indici 0-47: NO CHANGE (carte 2c-Kh)
- Indice 48 (Td): NO CHANGE  
- Indice 49 (Th): NO CHANGE
- Indice 50 (Ts): NO CHANGE
- Indice 51 (dealer_btn): → 52
- Indice 52 (player_bar): → 53
- Indice 53 (player_info): → 54
- Indice 54 (rivals_card): → 55
- Indice 55 (tc): → 48 (inserire tra Th e Ts)
"""

import os
from pathlib import Path
from ultralytics import YOLO
from tqdm import tqdm

# Class remapping dictionary
REMAP = {
    # UI elements shift +1
    51: 52,  # dealer_btn: 51 → 52
    52: 53,  # player_bar: 52 → 53
    53: 54,  # player_info: 53 → 54
    54: 55,  # rivals_card: 54 → 55
    # Tc va inserita al posto giusto
    55: 48   # tc: 55 → 48 (tra Th e Ts)
}

def remap_class_id(original_id):
    """Rimappa gli ID delle classi per allinearsi a Roboflow"""
    return REMAP.get(original_id, original_id)

def main():
    print("=" * 70)
    print("🏷️  LOCAL AUTO-LABELING - Best.pt with Class Remapping")
    print("=" * 70)
    
    # Configuration
    MODEL_PATH = "runs/detect/train/weights/best.pt"
    IMAGES_DIR = "UPLOAD_ROBOFLOW_FINALE/images"
    OUTPUT_DIR = "labels_v3_ready"
    CONFIDENCE = 0.50
    
    print(f"\n📊 Configuration:")
    print(f"   Model: {MODEL_PATH}")
    print(f"   Images: {IMAGES_DIR}")
    print(f"   Output: {OUTPUT_DIR}")
    print(f"   Confidence: {CONFIDENCE * 100}%")
    print(f"   Device: MPS (Mac M2)")
    
    print(f"\n🔧 Class Remapping:")
    print(f"   51 (dealer_btn) → 52")
    print(f"   52 (player_bar) → 53")
    print(f"   53 (player_info) → 54")
    print(f"   54 (rivals_card) → 55")
    print(f"   55 (tc) → 48")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load model
    print(f"\n📥 Loading YOLOv8 model...")
    model = YOLO(MODEL_PATH)
    print(f"✅ Model loaded! Classes: {len(model.names)}")
    
    # Get images
    images = sorted([
        f for f in os.listdir(IMAGES_DIR)
        if f.lower().endswith(('.jpg', '.png', '.jpeg'))
    ])
    total = len(images)
    
    print(f"\n📁 Found {total} images to process")
    print(f"\n🔄 Starting inference...\n")
    
    processed = 0
    with_detections = 0
    without_detections = 0
    total_detections = 0
    remapped_count = 0
    
    for img_name in tqdm(images, desc="Processing", unit="img"):
        img_path = os.path.join(IMAGES_DIR, img_name)
        
        # Run inference
        results = model.predict(
            source=img_path,
            conf=CONFIDENCE,
            device='mps',
            verbose=False
        )
        
        result = results[0]
        boxes = result.boxes
        
        if len(boxes) > 0:
            with_detections += 1
            
            # Create label file
            label_name = Path(img_name).with_suffix('.txt').name
            label_path = os.path.join(OUTPUT_DIR, label_name)
            
            with open(label_path, 'w') as f:
                for box in boxes:
                    # Get class ID and coordinates (normalized)
                    original_class_id = int(box.cls[0])
                    
                    # Remap class ID
                    class_id = remap_class_id(original_class_id)
                    if class_id != original_class_id:
                        remapped_count += 1
                    
                    # Get YOLO format coordinates (x_center, y_center, width, height)
                    # box.xywhn returns normalized coordinates
                    x_center, y_center, width, height = box.xywhn[0].tolist()
                    
                    # Write YOLO format line
                    f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
                    total_detections += 1
        else:
            without_detections += 1
        
        processed += 1
        
        # Progress report after first 10
        if processed == 10:
            print(f"\n📊 First 10 images:")
            print(f"   With detections: {with_detections}/10")
            print(f"   Total detections: {total_detections}")
            print(f"   Classes remapped: {remapped_count}")
            print(f"\n✅ Check first 10 .txt files in {OUTPUT_DIR}/\n")
    
    # Final report
    print("\n" + "=" * 70)
    print("✅ LOCAL INFERENCE COMPLETED!")
    print("=" * 70)
    print(f"\n📊 Statistics:")
    print(f"   Images processed: {processed}/{total}")
    print(f"   Images with detections: {with_detections} ({with_detections/total*100:.1f}%)")
    print(f"   Images without detections: {without_detections}")
    print(f"   Total detections: {total_detections}")
    print(f"   Average detections/image: {total_detections/with_detections:.1f}")
    print(f"   Classes remapped: {remapped_count}")
    print(f"\n📁 Labels saved to: {OUTPUT_DIR}/")
    print(f"   Total label files: {with_detections}")
    
    print(f"\n✅ READY FOR UPLOAD - Mappatura corretta applicata!")
    print("=" * 70)

if __name__ == "__main__":
    main()
