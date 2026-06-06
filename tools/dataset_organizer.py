#!/usr/bin/env python3
"""
Dataset Organizer & Auto-Labeling - Professional Workflow
==========================================================
Automatizza l'intero processo di preparazione dataset per training YOLO:
1. Inference con best.pt su immagini grezze
2. Generazione labels in formato YOLO
3. Organizzazione per confidence (ready/review/no_labels)
4. Report dettagliato per ottimizzazione upload Roboflow

WORKFLOW:
    input_images/           → Immagini grezze da processare
    ├─ ready_for_upload/   → Alta confidenza (>0.6) - pronte per Roboflow
    ├─ review_needed/      → Media confidenza (0.3-0.6) - revisione manuale
    └─ no_labels_found/    → Nessuna detection - annotazione manuale

USO:
    python dataset_organizer.py --input input_images/ --model best.pt
    python dataset_organizer.py --input new_training_images/ --confidence-high 0.7
"""

import argparse
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from ultralytics import YOLO
import shutil
from datetime import datetime
from collections import defaultdict
import json

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# Confidence thresholds
DEFAULT_HIGH_CONFIDENCE = 0.6   # Ready for upload
DEFAULT_LOW_CONFIDENCE = 0.3    # Below this = no labels

# Device
DEFAULT_DEVICE = "mps"  # Apple Silicon


class DatasetOrganizer:
    """
    Professional dataset organizer con auto-labeling e confidence filtering.
    """
    
    def __init__(
        self,
        model_path: str,
        high_confidence_threshold: float = DEFAULT_HIGH_CONFIDENCE,
        low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE,
        device: str = DEFAULT_DEVICE
    ):
        """
        Inizializza organizer.
        
        Args:
            model_path: Path a best.pt
            high_confidence_threshold: Soglia per ready_for_upload
            low_confidence_threshold: Soglia minima per generare labels
            device: Device per inference (mps, cuda, cpu)
        """
        self.model_path = Path(model_path)
        self.high_threshold = high_confidence_threshold
        self.low_threshold = low_confidence_threshold
        self.device = device
        
        # Verifica model exists
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        # Load model
        print(f"📦 Loading model: {model_path}")
        self.model = YOLO(str(model_path))
        print(f"✅ Model loaded successfully")
        print(f"   Device: {device}")
        print(f"   High confidence threshold: {high_confidence_threshold:.1%}")
        print(f"   Low confidence threshold: {low_confidence_threshold:.1%}")
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "ready_for_upload": 0,
            "review_needed": 0,
            "no_labels_found": 0,
            "total_labels_generated": 0,
            "errors": 0,
            "card_distribution": defaultdict(int)  # Track per-card detections
        }
    
    def process_image(
        self,
        image_path: Path
    ) -> Tuple[List[str], float, str]:
        """
        Processa singola immagine con inferenza e genera labels.
        
        Args:
            image_path: Path all'immagine
        
        Returns:
            Tuple di (label_lines, avg_confidence, category)
            - label_lines: Lista di stringhe formato YOLO
            - avg_confidence: Confidenza media delle detections
            - category: 'ready', 'review', o 'no_labels'
        """
        try:
            # Read image
            img = cv2.imread(str(image_path))
            if img is None:
                raise ValueError(f"Cannot read image: {image_path}")
            
            h, w = img.shape[:2]
            
            # Run inference
            results = self.model.predict(
                source=img,
                conf=self.low_threshold,  # Use minimum threshold
                device=self.device,
                verbose=False
            )
            
            # Extract detections
            label_lines = []
            confidences = []
            
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    
                    # Track confidence
                    confidences.append(conf)
                    
                    # Track card distribution
                    self.stats["card_distribution"][cls_id] += 1
                    
                    # Get bbox (xyxy format)
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    
                    # Convert to YOLO format (normalized center coordinates)
                    x_center = ((x1 + x2) / 2) / w
                    y_center = ((y1 + y2) / 2) / h
                    bbox_width = (x2 - x1) / w
                    bbox_height = (y2 - y1) / h
                    
                    # YOLO line: class x_center y_center width height
                    label_line = f"{cls_id} {x_center:.6f} {y_center:.6f} {bbox_width:.6f} {bbox_height:.6f}"
                    label_lines.append(label_line)
            
            # Calculate average confidence
            if confidences:
                avg_conf = sum(confidences) / len(confidences)
            else:
                avg_conf = 0.0
            
            # Determine category
            if not label_lines:
                category = "no_labels"
            elif avg_conf >= self.high_threshold:
                category = "ready"
            else:
                category = "review"
            
            return label_lines, avg_conf, category
        
        except Exception as e:
            print(f"  ❌ Error processing {image_path.name}: {str(e)}")
            self.stats["errors"] += 1
            return [], 0.0, "error"
    
    def organize_dataset(
        self,
        input_dir: Path,
        output_base_dir: Path
    ) -> Dict[str, int]:
        """
        Processa e organizza l'intero dataset.
        
        Args:
            input_dir: Cartella con immagini grezze
            output_base_dir: Cartella base output
        
        Returns:
            Statistics dictionary
        """
        input_dir = Path(input_dir)
        output_base_dir = Path(output_base_dir)
        
        # Create output folders
        ready_dir = output_base_dir / "ready_for_upload"
        review_dir = output_base_dir / "review_needed"
        no_labels_dir = output_base_dir / "no_labels_found"
        
        # Each folder needs images/ and labels/ subfolders
        for base_dir in [ready_dir, review_dir]:
            (base_dir / "images").mkdir(parents=True, exist_ok=True)
            (base_dir / "labels").mkdir(parents=True, exist_ok=True)
        
        no_labels_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all images
        image_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG", "*.JPEG"]:
            image_files.extend(input_dir.glob(ext))
        
        total = len(image_files)
        if total == 0:
            print(f"⚠️  No images found in {input_dir}")
            return self.stats
        
        self.stats["total_processed"] = total
        
        print(f"\n{'='*70}")
        print(f"🚀 DATASET ORGANIZER - Processing {total} images")
        print(f"{'='*70}\n")
        
        # Process each image
        for idx, img_path in enumerate(image_files, 1):
            # Progress indicator
            progress = (idx / total) * 100
            print(f"[{idx}/{total} - {progress:.1f}%] {img_path.name:40s} ", end="", flush=True)
            
            # Process
            labels, avg_conf, category = self.process_image(img_path)
            
            # Organize based on category
            if category == "ready":
                # High confidence - ready for upload
                dest_img = ready_dir / "images" / img_path.name
                dest_lbl = ready_dir / "labels" / f"{img_path.stem}.txt"
                
                shutil.copy2(img_path, dest_img)
                with open(dest_lbl, 'w') as f:
                    f.write("\n".join(labels))
                
                self.stats["ready_for_upload"] += 1
                self.stats["total_labels_generated"] += len(labels)
                print(f"✅ Ready ({len(labels)} labels, conf: {avg_conf:.2%})")
            
            elif category == "review":
                # Medium confidence - needs review
                dest_img = review_dir / "images" / img_path.name
                dest_lbl = review_dir / "labels" / f"{img_path.stem}.txt"
                
                shutil.copy2(img_path, dest_img)
                with open(dest_lbl, 'w') as f:
                    f.write("\n".join(labels))
                
                self.stats["review_needed"] += 1
                self.stats["total_labels_generated"] += len(labels)
                print(f"⚠️  Review ({len(labels)} labels, conf: {avg_conf:.2%})")
            
            elif category == "no_labels":
                # No detections - manual annotation needed
                dest_img = no_labels_dir / img_path.name
                shutil.copy2(img_path, dest_img)
                
                self.stats["no_labels_found"] += 1
                print(f"❌ No labels (manual annotation required)")
            
            else:  # error
                print(f"⚠️  Skipped (error)")
        
        return self.stats
    
    def print_summary_report(self, output_dir: Path):
        """
        Stampa report riepilogativo dettagliato.
        
        Args:
            output_dir: Directory output per salvataggio report
        """
        print(f"\n{'='*70}")
        print("📊 SUMMARY REPORT - Dataset Organization")
        print(f"{'='*70}\n")
        
        total = self.stats["total_processed"]
        ready = self.stats["ready_for_upload"]
        review = self.stats["review_needed"]
        no_labels = self.stats["no_labels_found"]
        errors = self.stats["errors"]
        
        print(f"📈 Processing Statistics:")
        print(f"   Total images processed: {total}")
        print(f"   ✅ Ready for upload: {ready} ({ready/total*100:.1f}%)")
        print(f"   ⚠️  Needs review: {review} ({review/total*100:.1f}%)")
        print(f"   ❌ No labels found: {no_labels} ({no_labels/total*100:.1f}%)")
        if errors > 0:
            print(f"   ⚠️  Errors: {errors}")
        
        print(f"\n🏷️  Labeling Statistics:")
        print(f"   Total labels generated: {self.stats['total_labels_generated']}")
        if ready + review > 0:
            avg_labels = self.stats['total_labels_generated'] / (ready + review)
            print(f"   Average labels per image: {avg_labels:.1f}")
        
        # Card distribution analysis
        if self.stats["card_distribution"]:
            print(f"\n🃏 Card Distribution (top 10):")
            sorted_cards = sorted(
                self.stats["card_distribution"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            for cls_id, count in sorted_cards:
                print(f"   Class {cls_id}: {count} detections")
        
        print(f"\n📁 Output Organization:")
        print(f"   Ready for upload: {output_dir}/ready_for_upload/")
        print(f"     ├─ images/ ({ready} files)")
        print(f"     └─ labels/ ({ready} files)")
        print(f"   Needs review: {output_dir}/review_needed/")
        print(f"     ├─ images/ ({review} files)")
        print(f"     └─ labels/ ({review} files)")
        print(f"   No labels: {output_dir}/no_labels_found/ ({no_labels} files)")
        
        print(f"\n💡 Recommendations:")
        
        # Upload recommendation
        upload_rate = ready / total * 100 if total > 0 else 0
        if upload_rate >= 70:
            print(f"   ✅ Excellent! {upload_rate:.0f}% ready for immediate upload")
        elif upload_rate >= 50:
            print(f"   ⚠️  Good start. {upload_rate:.0f}% ready, review {review} before full upload")
        else:
            print(f"   ❌ Low confidence rate ({upload_rate:.0f}%). Consider:")
            print(f"      - Improving model training (current mAP ~27%)")
            print(f"      - Manual review of {review} medium-confidence images")
        
        # Review recommendation
        if review > 0:
            print(f"   📝 Review {review} images in review_needed/ before upload")
            print(f"      Use LabelImg or Roboflow to correct/validate")
        
        # No labels recommendation
        if no_labels > 0:
            no_labels_rate = no_labels / total * 100
            if no_labels_rate > 20:
                print(f"   ⚠️  High no-detection rate ({no_labels_rate:.0f}%)")
                print(f"      - Check if images are valid poker screenshots")
                print(f"      - Consider lowering confidence threshold")
            else:
                print(f"   📌 {no_labels} images need manual annotation")
        
        print(f"\n{'='*70}")
        
        # Save JSON report
        report_path = output_dir / "organization_report.json"
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "statistics": dict(self.stats),
            "thresholds": {
                "high_confidence": self.high_threshold,
                "low_confidence": self.low_threshold
            },
            "recommendations": {
                "upload_rate": upload_rate,
                "immediate_upload": ready,
                "needs_review": review,
                "manual_annotation": no_labels
            }
        }
        
        # Convert defaultdict to regular dict for JSON
        report_data["statistics"]["card_distribution"] = dict(
            self.stats["card_distribution"]
        )
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"📄 Detailed report saved: {report_path}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Professional dataset organizer with auto-labeling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard usage
  %(prog)s --input input_images/ --model best.pt
  
  # Custom confidence thresholds
  %(prog)s --input new_data/ --confidence-high 0.7 --confidence-low 0.4
  
  # CPU mode
  %(prog)s --input images/ --device cpu
        """
    )
    
    parser.add_argument("--input", "-i", required=True,
                       help="Input folder with raw images")
    parser.add_argument("--output", "-o", default="organized_dataset",
                       help="Output base folder (default: organized_dataset)")
    parser.add_argument("--model", "-m", default="runs/poker_cards/train/weights/best.pt",
                       help="Path to YOLO model (default: best.pt)")
    parser.add_argument("--confidence-high", type=float, default=DEFAULT_HIGH_CONFIDENCE,
                       help=f"High confidence threshold for ready_for_upload (default: {DEFAULT_HIGH_CONFIDENCE})")
    parser.add_argument("--confidence-low", type=float, default=DEFAULT_LOW_CONFIDENCE,
                       help=f"Low confidence threshold (default: {DEFAULT_LOW_CONFIDENCE})")
    parser.add_argument("--device", "-d", default=DEFAULT_DEVICE,
                       choices=["mps", "cuda", "cpu"],
                       help=f"Inference device (default: {DEFAULT_DEVICE})")
    
    args = parser.parse_args()
    
    # Validation
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Input folder not found: {input_path}")
        return 1
    
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"❌ Model not found: {model_path}")
        print(f"   Train a model first with: python train.py")
        return 1
    
    # Create organizer
    try:
        organizer = DatasetOrganizer(
            model_path=args.model,
            high_confidence_threshold=args.confidence_high,
            low_confidence_threshold=args.confidence_low,
            device=args.device
        )
    except Exception as e:
        print(f"❌ Failed to initialize organizer: {e}")
        return 1
    
    # Process dataset
    output_path = Path(args.output)
    organizer.organize_dataset(
        input_dir=input_path,
        output_base_dir=output_path
    )
    
    # Print summary
    organizer.print_summary_report(output_path)
    
    # Next steps
    print("🚀 Next Steps:")
    print(f"   1. Review images in: {output_path}/review_needed/")
    print(f"   2. Upload to Roboflow:")
    print(f"      - Drag & drop {output_path}/ready_for_upload/ (images + labels)")
    print(f"      - After review, upload review_needed/ folder")
    print(f"   3. Manually annotate: {output_path}/no_labels_found/")
    print(f"   4. Re-train with improved dataset")
    
    return 0


if __name__ == "__main__":
    exit(main())
