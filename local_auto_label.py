#!/usr/bin/env python3
"""
Local Auto-Labeling Script
===========================
Uses trained best.pt model to generate YOLO labels locally on Mac M2
Bypasses Roboflow credit limits
"""

import os
import sys
from pathlib import Path
from tqdm import tqdm

def main():
    print("=" * 70)
    print("🏷️  LOCAL AUTO-LABELING (Mac M2)")
    print("=" * 70)
    
    # Configuration
    MODEL_PATH = "runs/detect/train/weights/best.pt"
    IMAGES_DIR = "UPLOAD_ROBOFLOW_FINALE/images"
    OUTPUT_DIR = "generated_labels"
    CONFIDENCE = 0.5  # 50% confidence threshold
    
    print(f"\n📊 Configuration:")
    print(f"   Model: {MODEL_PATH}")
    print(f"   Images: {IMAGES_DIR}")
    print(f"   Output: {OUTPUT_DIR}")
    print(f"   Confidence: {CONFIDENCE * 100}%")
    print(f"   Device: MPS (Mac M2)")
    
    # Verify model exists
    if not os.path.exists(MODEL_PATH):
        print(f"\n❌ ERROR: Model not found at {MODEL_PATH}")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Import YOLO
    from ultralytics import YOLO
    
    # Load model
    print(f"\n📥 Loading model...")
    model = YOLO(MODEL_PATH)
    print(f"✅ Model loaded successfully!")
    print(f"   Classes: {len(model.names)}")
    
    # Find all images
    images_path = Path(IMAGES_DIR)
    if not images_path.exists():
        print(f"\n❌ ERROR: Images directory not found: {IMAGES_DIR}")
        sys.exit(1)
    
    image_files = list(images_path.glob("*.jpg"))
    total = len(image_files)
    
    print(f"\n📁 Found {total} images to process")
    
    if total == 0:
        print("No images found!")
        return
    
    print(f"\n🔄 Starting inference...\n")
    
    processed = 0
    annotated = 0
    
    for img_path in tqdm(image_files, desc="Processing", unit="img"):
        try:
            # Run inference
            results = model.predict(
                source=str(img_path),
                conf=CONFIDENCE,
                device='mps',  # Mac M2 GPU acceleration
                verbose=False,
                save=False
            )
            
            # Extract predictions
            result = results[0]
            boxes = result.boxes
            
            if len(boxes) > 0:
                # Create label file
                label_file = os.path.join(OUTPUT_DIR, f"{img_path.stem}.txt")
                
                # Get image dimensions
                img_height, img_width = result.orig_shape
                
                # Write YOLO format labels
                with open(label_file, 'w') as f:
                    for box in boxes:
                        # Extract box data
                        cls_id = int(box.cls[0])
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        
                        # Convert to YOLO normalized format
                        x_center = ((x1 + x2) / 2) / img_width
                        y_center = ((y1 + y2) / 2) / img_height
                        width = (x2 - x1) / img_width
                        height = (y2 - y1) / img_height
                        
                        # Write to file
                        f.write(f"{cls_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
                
                annotated += 1
            
            processed += 1
            
        except Exception as e:
            print(f"\n⚠️  Error processing {img_path.name}: {e}")
            continue
    
    # Final report
    print("\n" + "=" * 70)
    print("✅ LOCAL AUTO-LABELING COMPLETED!")
    print("=" * 70)
    print(f"\n📊 Statistics:")
    print(f"   Images processed: {processed}/{total}")
    print(f"   Images with detections: {annotated}")
    print(f"   Images without detections: {processed - annotated}")
    print(f"   Detection rate: {(annotated/processed*100):.1f}%")
    
    print(f"\n📁 Labels saved to: {OUTPUT_DIR}/")
    print(f"   Total label files: {len(os.listdir(OUTPUT_DIR))}")
    
    print("\n💡 Next steps:")
    print("   1. Review generated labels in visual_test.py")
    print("   2. Upload to Roboflow manually if needed")
    print("=" * 70)

if __name__ == "__main__":
    main()
