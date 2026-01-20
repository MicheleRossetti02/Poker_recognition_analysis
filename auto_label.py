#!/usr/bin/env python3
"""
Auto-Labeling Script - YOLO Poker Cards
========================================
Processa batch di immagini non annotate usando il modello YOLO best.pt
e genera automaticamente file .txt in formato YOLO.

FEATURES:
- Confidence filtering (high/medium/low)
- Batch processing con progress bar
- Generated labels in YOLO format
- Uncertain images flagged for manual review

USO:
    python auto_label.py --input new_training_images/ --output auto_labeled/ --confidence 0.90
    
WORKFLOW:
    1. Load best.pt model
    2. Process all .jpg/.png in input folder
    3. Generate .txt labels for high-confidence detections
    4. Flag low-confidence images for manual review
"""

import argparse
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict
from ultralytics import YOLO
import shutil
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

# Confidence thresholds
HIGH_CONFIDENCE = 0.90  # Auto-label without review
MEDIUM_CONFIDENCE = 0.70  # Auto-label but flag for spot-check
LOW_CONFIDENCE = 0.50  # Skip or manual review required

# Card class mapping (52 cards + button)
CARD_CLASSES = [
    # Cuori (Hearts - h)
    "Ah", "2h", "3h", "4h", "5h", "6h", "7h", "8h", "9h", "Th", "Jh", "Qh", "Kh",
    # Quadri (Diamonds - d)
    "Ad", "2d", "3d", "4d", "5d", "6d", "7d", "8d", "9d", "Td", "Jd", "Qd", "Kd",
    # Fiori (Clubs - c)
    "Ac", "2c", "3c", "4c", "5c", "6c", "7c", "8c", "9c", "Tc", "Jc", "Qc", "Kc",
    # Picche (Spades - s)
    "As", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s", "Ts", "Js", "Qs", "Ks",
    # Button
    "button"
]


class AutoLabeler:
    """
    Auto-labeling engine for poker cards using pre-trained YOLO model.
    """
    
    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = HIGH_CONFIDENCE,
        device: str = "mps"
    ):
        """
        Initialize auto-labeler.
        
        Args:
            model_path: Path to best.pt model
            confidence_threshold: Minimum confidence for auto-labeling
            device: Device for inference ('mps', 'cuda', 'cpu')
        """
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self.device = device
        
        # Load model
        print(f"Loading model: {model_path}")
        self.model = YOLO(str(model_path))
        
        # Stats
        self.stats = {
            "total_images": 0,
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
            "no_detections": 0,
            "total_labels": 0
        }
    
    def process_image(
        self,
        image_path: Path
    ) -> Tuple[List[str], str]:
        """
        Process single image and generate YOLO label lines.
        
        Args:
            image_path: Path to image file
        
        Returns:
            Tuple of (label_lines, confidence_category)
            - label_lines: List of YOLO format strings
            - confidence_category: 'high', 'medium', 'low', or 'none'
        """
        # Read image
        img = cv2.imread(str(image_path))
        if img is None:
            return [], "none"
        
        h, w = img.shape[:2]
        
        # Run inference
        results = self.model.predict(
            source=img,
            conf=LOW_CONFIDENCE,  # Use min threshold to catch all
            device=self.device,
            verbose=False
        )
        
        # Extract detections
        label_lines = []
        max_confidence = 0.0
        
        for result in results:
            boxes = result.boxes
            
            if len(boxes) == 0:
                return [], "none"
            
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                max_confidence = max(max_confidence, conf)
                
                # Get bbox (xyxy format)
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # Convert to YOLO format (normalized x_center, y_center, width, height)
                x_center = ((x1 + x2) / 2) / w
                y_center = ((y1 + y2) / 2) / h
                bbox_width = (x2 - x1) / w
                bbox_height = (y2 - y1) / h
                
                # YOLO format: class x_center y_center width height
                label_line = f"{cls_id} {x_center:.6f} {y_center:.6f} {bbox_width:.6f} {bbox_height:.6f}"
                label_lines.append((label_line, conf))
        
        # Determine confidence category based on max confidence
        if max_confidence >= HIGH_CONFIDENCE:
            category = "high"
        elif max_confidence >= MEDIUM_CONFIDENCE:
            category = "medium"
        elif max_confidence >= self.confidence_threshold:
            category = "low"
        else:
            category = "none"
        
        # Filter labels by threshold
        filtered_labels = [
            line for line, conf in label_lines 
            if conf >= self.confidence_threshold
        ]
        
        return filtered_labels, category
    
    def process_folder(
        self,
        input_dir: Path,
        output_dir: Path,
        copy_images: bool = True
    ) -> Dict[str, int]:
        """
        Batch process all images in folder.
        
        Args:
            input_dir: Folder containing raw images
            output_dir: Output folder for labeled images
            copy_images: If True, copy images to output (for YOLO datasets)
        
        Returns:
            Statistics dictionary
        """
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        
        # Create output structure
        images_dir = output_dir / "images"
        labels_dir = output_dir / "labels"
        review_dir = output_dir / "_review_required"
        
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        review_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all images
        image_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG"]:
            image_files.extend(input_dir.glob(ext))
        
        total = len(image_files)
        self.stats["total_images"] = total
        
        print(f"\n{'='*60}")
        print(f"AUTO-LABELING: {total} images")
        print(f"Confidence threshold: {self.confidence_threshold:.0%}")
        print(f"{'='*60}\n")
        
        # Process each image
        for idx, img_path in enumerate(image_files, 1):
            # Progress
            print(f"[{idx}/{total}] {img_path.name}... ", end="", flush=True)
            
            # Process
            labels, category = self.process_image(img_path)
            
            # Update stats
            if category == "high":
                self.stats["high_confidence"] += 1
            elif category == "medium":
                self.stats["medium_confidence"] += 1
            elif category == "low":
                self.stats["low_confidence"] += 1
            else:
                self.stats["no_detections"] += 1
            
            self.stats["total_labels"] += len(labels)
            
            # Save labels if any
            if labels:
                # Copy image
                if copy_images:
                    dest_img = images_dir / img_path.name
                    shutil.copy2(img_path, dest_img)
                
                # Write label file
                label_path = labels_dir / f"{img_path.stem}.txt"
                with open(label_path, 'w') as f:
                    f.write("\n".join(labels))
                
                print(f"✓ {len(labels)} labels ({category})")
                
                # Flag for review if medium confidence
                if category == "medium":
                    review_marker = review_dir / f"{img_path.stem}_CHECK.txt"
                    review_marker.write_text(
                        f"Medium confidence - spot-check recommended\n"
                        f"Labels: {len(labels)}\n"
                    )
            
            else:
                print(f"⚠ No detections (skipped)")
                # Flag for manual annotation
                review_marker = review_dir / f"{img_path.stem}_MANUAL.txt"
                review_marker.write_text(
                    f"No detections or low confidence - manual annotation required\n"
                )
                
                # Optionally copy image to review folder
                if copy_images:
                    dest_img = review_dir / img_path.name
                    shutil.copy2(img_path, dest_img)
        
        return self.stats
    
    def print_summary(self):
        """Print summary statistics."""
        print(f"\n{'='*60}")
        print("AUTO-LABELING SUMMARY")
        print(f"{'='*60}")
        print(f"Total images processed: {self.stats['total_images']}")
        print(f"  ✓ High confidence (≥{HIGH_CONFIDENCE:.0%}): {self.stats['high_confidence']}")
        print(f"  • Medium confidence (≥{MEDIUM_CONFIDENCE:.0%}): {self.stats['medium_confidence']}")
        print(f"  ⚠ Low confidence (≥{self.confidence_threshold:.0%}): {self.stats['low_confidence']}")
        print(f"  ✗ No detections: {self.stats['no_detections']}")
        print(f"\nTotal labels generated: {self.stats['total_labels']}")
        
        auto_labeled = self.stats['high_confidence'] + self.stats['medium_confidence']
        if self.stats['total_images'] > 0:
            rate = (auto_labeled / self.stats['total_images']) * 100
            print(f"Auto-label rate: {rate:.1f}%")
        
        review_count = self.stats['medium_confidence'] + self.stats['no_detections']
        if review_count > 0:
            print(f"\n⚠️  {review_count} images flagged for review (see _review_required folder)")
        
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Auto-label poker card images using YOLO model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input new_training_images/ --output auto_labeled/
  %(prog)s --input raw/ --output labeled/ --confidence 0.85
  %(prog)s --model runs/poker_cards/train/weights/best.pt --confidence 0.95
        """
    )
    
    parser.add_argument("--input", "-i", required=True,
                       help="Input folder with raw images")
    parser.add_argument("--output", "-o", required=True,
                       help="Output folder for labeled dataset")
    parser.add_argument("--model", "-m", default="runs/poker_cards/train/weights/best.pt",
                       help="Path to YOLO model (default: best.pt)")
    parser.add_argument("--confidence", "-c", type=float, default=HIGH_CONFIDENCE,
                       help=f"Minimum confidence threshold (default: {HIGH_CONFIDENCE})")
    parser.add_argument("--device", "-d", default="mps",
                       choices=["mps", "cuda", "cpu"],
                       help="Device for inference (default: mps for Apple Silicon)")
    parser.add_argument("--no-copy-images", action="store_true",
                       help="Don't copy images to output (labels only)")
    
    args = parser.parse_args()
    
    # Validate paths
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Input folder not found: {input_path}")
        return 1
    
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"❌ Model not found: {model_path}")
        return 1
    
    # Create auto-labeler
    labeler = AutoLabeler(
        model_path=args.model,
        confidence_threshold=args.confidence,
        device=args.device
    )
    
    # Process
    output_path = Path(args.output)
    labeler.process_folder(
        input_dir=input_path,
        output_dir=output_path,
        copy_images=not args.no_copy_images
    )
    
    # Summary
    labeler.print_summary()
    
    # Save metadata
    metadata_path = output_path / "auto_label_metadata.txt"
    with open(metadata_path, 'w') as f:
        f.write(f"Auto-Labeling Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n")
        f.write(f"Model: {model_path}\n")
        f.write(f"Input: {input_path}\n")
        f.write(f"Confidence threshold: {args.confidence:.2%}\n")
        f.write(f"\nStatistics:\n")
        for key, value in labeler.stats.items():
            f.write(f"  {key}: {value}\n")
    
    print(f"📄 Metadata saved: {metadata_path}")
    
    print("\n📝 Next steps:")
    print(f"  1. Review images in: {output_path}/_review_required/")
    print(f"  2. Verify labels in: {output_path}/labels/")
    print(f"  3. Merge with existing dataset or train directly")
    
    return 0


if __name__ == "__main__":
    exit(main())
