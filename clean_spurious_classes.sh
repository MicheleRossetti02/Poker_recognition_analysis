#!/bin/bash
# CORRECTED Post-Processing Script - Remove ONLY Class 32
# =========================================================
# EMERGENCY UPDATE: Classes 54-56 are ESSENTIAL and must NOT be removed
# 
# Only removing:
# - Class 32: A5 (error - invalid card notation)

set -e  # Exit on error

echo "======================================================================"
echo "🛡️  CORRECTED Post-Processing: Removing ONLY Class 32"
echo "======================================================================"
echo ""
echo "⚠️  CRITICAL: Classes 54, 55, 56 are PRESERVED (essential for app)"
echo ""

# Configuration
DATASET_DIR="organized_dataset_clean"
READY_LABELS_DIR="$DATASET_DIR/ready_for_upload/labels"
REVIEW_LABELS_DIR="$DATASET_DIR/review_needed/labels"

# Only class 32 to remove
REMOVE_CLASS=32

echo "📁 Target directories:"
echo "   - $READY_LABELS_DIR"
echo "   - $REVIEW_LABELS_DIR"
echo ""
echo "🗑️  Removing ONLY class: $REMOVE_CLASS (A5 error)"
echo ""

# Function to clean labels in a directory
clean_labels() {
    local dir=$1
    local label_count=$(ls -1 "$dir"/*.txt 2>/dev/null | wc -l | tr -d ' ')
    
    echo "Processing $label_count files in $dir..."
    
    # Count how many class 32 instances exist
    local before_count=$(grep -r "^$REMOVE_CLASS " "$dir" 2>/dev/null | wc -l | tr -d ' ')
    
    if [ "$before_count" -eq 0 ]; then
        echo "  ℹ️  No Class $REMOVE_CLASS instances found - skipping"
    else
        echo "  Found $before_count instances of Class $REMOVE_CLASS"
        
        # Remove lines starting with "32 " from all .txt files
        find "$dir" -name "*.txt" -type f -exec sed -i '' "/^$REMOVE_CLASS /d" {} \;
        
        # Verify removal
        local after_count=$(grep -r "^$REMOVE_CLASS " "$dir" 2>/dev/null | wc -l | tr -d ' ')
        echo "  ✅ Removed $(($before_count - $after_count)) instances"
    fi
    echo ""
}

# Clean ready_for_upload labels
if [ -d "$READY_LABELS_DIR" ]; then
    clean_labels "$READY_LABELS_DIR"
else
    echo "⚠️  Directory not found: $READY_LABELS_DIR"
    echo ""
fi

# Clean review_needed labels
if [ -d "$REVIEW_LABELS_DIR" ]; then
    clean_labels "$REVIEW_LABELS_DIR"
else
    echo "⚠️  Directory not found: $REVIEW_LABELS_DIR"
    echo ""
fi

echo "======================================================================"
echo "🔍 Verification"
echo "======================================================================"
echo ""

# Verify no class 32 remains
echo "Checking for remaining Class 32 instances..."
count=$(grep -r "^32 " "$DATASET_DIR" 2>/dev/null | wc -l | tr -d ' ')
if [ "$count" -eq 0 ]; then
    echo "  ✅ Class 32: 0 instances (successfully removed)"
else
    echo "  ⚠️  Class 32: $count instances still found!"
fi
echo ""

# Verify classes 54-56 are PRESERVED
echo "Verifying ESSENTIAL classes are preserved..."
for class_id in 54 55 56; do
    count=$(grep -r "^$class_id " "$DATASET_DIR" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" -gt 0 ]; then
        echo "  ✅ Class $class_id: $count instances (PRESERVED)"
    else
        echo "  ⚠️  Class $class_id: 0 instances (unexpected)"
    fi
done
echo ""

# Check for empty label files
echo "Checking for empty label files..."
empty_files=$(find "$DATASET_DIR" -name "*.txt" -type f -empty | wc -l | tr -d ' ')

if [ "$empty_files" -eq 0 ]; then
    echo "  ✅ No empty label files found"
else
    echo "  ⚠️  Found $empty_files empty label files"
    echo "  (These images had ONLY class 32 labels)"
fi
echo ""

echo "======================================================================"
echo "✅ POST-PROCESSING COMPLETE"
echo "======================================================================"
echo ""
echo "📊 Summary:"
echo "   - Removed class: 32 (A5 error only)"
echo "   - PRESERVED classes: 54, 55, 56 (essential for app)"
echo "   - Ready labels: $(ls -1 "$READY_LABELS_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')"
echo "   - Review labels: $(ls -1 "$REVIEW_LABELS_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')"
echo ""
echo "🚀 Next Steps:"
echo "   1. Upload to Roboflow:"
echo "      - Drag & drop: $DATASET_DIR/ready_for_upload/"
echo "      - Format: YOLOv8 with 57 classes"
echo "   2. Start training: python train.py"
echo ""
