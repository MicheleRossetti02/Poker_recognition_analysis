#!/usr/bin/env python3
"""
📦 Prepare Upload Package for Roboflow
=======================================
Crea una struttura ZIP pronta per l'upload manuale su Roboflow
con matching perfetto image-label usando convenzione naming.
"""

import os
import shutil
from pathlib import Path
from tqdm import tqdm

def main():
    print("=" * 70)
    print("📦 PREPARE UPLOAD PACKAGE - Roboflow Compatible")
    print("=" * 70)
    
    # Paths
    IMAGES_DIR = "UPLOAD_ROBOFLOW_FINALE/images"
    LABELS_DIR = "labels_v3_ready"
    OUTPUT_DIR = "roboflow_package_v3_final"
    
    # Create package structure
    pkg_images = os.path.join(OUTPUT_DIR, "train", "images")
    pkg_labels = os.path.join(OUTPUT_DIR, "train", "labels")
    
    print(f"\n📁 Creating package structure...")
    os.makedirs(pkg_images, exist_ok=True)
    os.makedirs(pkg_labels, exist_ok=True)
    
    # Get images
    images = sorted([
        f for f in os.listdir(IMAGES_DIR)
        if f.lower().endswith(('.jpg', '.png', '.jpeg'))
    ])
    
    print(f"\n📊 Found {len(images)} images")
    
    # Copy matched pairs
    matched = 0
    unmatched = 0
    
    print(f"\n🔄 Copying image-label pairs...")
    
    for img_name in tqdm(images, desc="Copying"):
        # Image path
        img_src = os.path.join(IMAGES_DIR, img_name)
        
        # Label path
        label_name = Path(img_name).with_suffix('.txt').name
        label_src = os.path.join(LABELS_DIR, label_name)
        
        if os.path.exists(label_src):
            # Copy both files
            img_dst = os.path.join(pkg_images, img_name)
            label_dst = os.path.join(pkg_labels, label_name)
            
            shutil.copy2(img_src, img_dst)
            shutil.copy2(label_src, label_dst)
            matched += 1
        else:
            unmatched += 1
    
    print(f"\n✅ Package created!")
    print(f"   Matched pairs: {matched}")
    print(f"   Unmatched: {unmatched}")
    
    # Create data.yaml for reference
    yaml_content = f"""# Roboflow Upload Package V3 Final
# Generated: 2026-01-27
# Images with corrected class mapping

train: train/images
val: ''
test: ''

nc: 56  # number of classes
names:
  # Classes 0-51: Cards (52 total)
  # Class 52: dealer_btn
  # Class 53: player_bar
  # Class 54: player_info
  # Class 55: rivals_card
"""
    
    with open(os.path.join(OUTPUT_DIR, "data.yaml"), 'w') as f:
        f.write(yaml_content)
    
    # Create README
    readme = f"""# Roboflow Upload Package V3 Final

## Contents
- **Images**: {matched} files in `train/images/`
- **Labels**: {matched} files in `train/labels/` (YOLO format)
- **Class mapping**: Corrected (UI elements: 52-55, Tc: 48)

## Upload Instructions

### Option 1: Drag & Drop
1. Go to Roboflow Dashboard
2. Open project: poker-gto-production
3. Click "Upload"
4. Select format: "YOLO v8"
5. Drag the entire `train` folder
6. Batch name: "V3_FINAL_CORRECTED"

### Option 2: ZIP Upload
1. Compress the `train` folder
2. Upload the ZIP file to Roboflow
3. Roboflow will auto-detect YOLO format

## Generated: {matched} image-label pairs
## Date: 2026-01-27 20:46
"""
    
    with open(os.path.join(OUTPUT_DIR, "README.md"), 'w') as f:
        f.write(readme)
    
    print(f"\n📦 Package location: {OUTPUT_DIR}/")
    print(f"   Structure: train/images/ + train/labels/")
    print(f"   Includes: data.yaml + README.md")
    
    print(f"\n💡 Next steps:")
    print(f"   1. Open Finder and navigate to: {os.path.abspath(OUTPUT_DIR)}")
    print(f"   2. ZIP the 'train' folder")
    print(f"   3. Upload to Roboflow as 'YOLO v8' format")
    print(f"   OR")
    print(f"   4. Drag & drop the 'train' folder directly to Roboflow")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
