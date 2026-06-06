#!/usr/bin/env python3
"""
Visual Test for Bounding Boxes
===============================
Draws bounding boxes on 3 sample images to verify correctness
"""

import cv2
import os
from pathlib import Path

def draw_boxes_on_image(image_path, label_path, output_path):
    """Draw bounding boxes from YOLO label file onto image"""
    
    # Read image
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"ERROR: Could not read {image_path}")
        return False
    
    height, width = img.shape[:2]
    
    # Read labels
    if not os.path.exists(label_path):
        print(f"WARNING: No label file for {image_path.name}")
        return False
    
    with open(label_path, 'r') as f:
        lines = f.readlines()
    
    # Draw each bounding box
    colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
    
    for idx, line in enumerate(lines):
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        
        try:
            class_id = int(parts[0])
            x_center = float(parts[1])
            y_center = float(parts[2])
            box_width = float(parts[3])
            box_height = float(parts[4])
            
            # Convert from YOLO format to pixel coordinates
            x1 = int((x_center - box_width/2) * width)
            y1 = int((y_center - box_height/2) * height)
            x2 = int((x_center + box_width/2) * width)
            y2 = int((y_center + box_height/2) * height)
            
            # Draw rectangle
            color = colors[idx % len(colors)]
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            
            # Draw class label
            cv2.putText(img, f"cls:{class_id}", (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
        except ValueError as e:
            print(f"ERROR parsing line: {line.strip()}")
            print(f"  Error: {e}")
            return False
    
    # Save result
    cv2.imwrite(str(output_path), img)
    print(f"✅ Saved: {output_path}")
    return True

def main():
    print("=" * 70)
    print("🎨 VISUAL TEST - Bounding Box Verification")
    print("=" * 70)
    
    images_dir = Path("organized_dataset_clean/FOTO dataset_annotated/images")
    labels_dir = Path("organized_dataset_clean/FOTO dataset_annotated/labels")
    output_dir = Path("visual_test_results")
    
    output_dir.mkdir(exist_ok=True)
    
    # Get 3 sample images
    image_files = list(images_dir.glob("*.jpg"))[:3]
    
    print(f"\n📁 Testing {len(image_files)} sample images...")
    print()
    
    success_count = 0
    for img_path in image_files:
        label_path = labels_dir / f"{img_path.stem}.txt"
        output_path = output_dir / f"{img_path.stem}_boxes.jpg"
        
        print(f"Processing: {img_path.name}")
        if draw_boxes_on_image(img_path, label_path, output_path):
            success_count += 1
        print()
    
    print("=" * 70)
    print(f"✅ Visual Test Complete: {success_count}/{len(image_files)} succeeded")
    print("=" * 70)
    print(f"\n📁 Results saved in: {output_dir}/")
    print("\nPlease review the images to verify boxes are correctly placed on cards!")
    
if __name__ == "__main__":
    main()
