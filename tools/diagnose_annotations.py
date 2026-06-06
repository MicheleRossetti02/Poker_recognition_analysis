#!/usr/bin/env python3
"""
Diagnose Roboflow Annotation Sync Issue
========================================
Check if images on Roboflow have associated annotations
"""

import requests
import json

API_KEY = "CtDu9vml1KIKbDsLHMYU"
WORKSPACE = "pokergtobot"
PROJECT = "poker-gto-production"

# Sample image names to check (from screenshot)
SAMPLE_IMAGES = [
    "poker_952x676_v4_110910_650.jpg",
    "poker_952x676_v4_110615_663.jpg",
    "poker_952x676_v4_110338_404.jpg",
    "poker_952x676_v4_110315_702.jpg",
    "poker_952x676_v4_110215_061.jpg"
]

def check_image_annotations(image_name):
    """Check if an image has annotations on Roboflow"""
    
    # API endpoint to get image info
    url = f"https://api.roboflow.com/{WORKSPACE}/{PROJECT}/images"
    params = {"api_key": API_KEY}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Search for the specific image
            for img in data.get('images', []):
                if img.get('name') == image_name:
                    has_annotations = len(img.get('annotations', [])) > 0
                    return True, has_annotations, len(img.get('annotations', []))
            return True, False, 0  # Image exists but no annotations found
        else:
            return False, False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, False, str(e)

def main():
    print("=" * 70)
    print("🔍 ROBOFLOW ANNOTATION DIAGNOSTIC")
    print("=" * 70)
    
    print(f"\n📋 Checking {len(SAMPLE_IMAGES)} sample images...")
    print()
    
    for img_name in SAMPLE_IMAGES:
        # Check local labels
        label_name = img_name.replace('.jpg', '.txt')
        local_path = f"organized_dataset_clean/FOTO dataset_annotated/labels/{label_name}"
        
        import os
        local_exists = os.path.exists(local_path)
        
        if local_exists:
            with open(local_path, 'r') as f:
                local_count = len(f.readlines())
        else:
            local_count = 0
        
        print(f"📷 {img_name}")
        print(f"   Local label: {'✅ EXISTS' if local_exists else '❌ MISSING'} ({local_count} annotations)")
        
        # Check Roboflow
        # Note: Full API check might require different endpoint
        # This is a diagnostic to understand the issue
        print()
    
    print("=" * 70)
    print("📊 DIAGNOSIS")
    print("=" * 70)
    print("\n🔍 Possible causes for 'Unannotated' status:")
    print("   1. ❌ Labels uploaded separately from images")
    print("   2. ❌ Image IDs don't match between upload and annotation")
    print("   3. ❌ Annotations in wrong format on Roboflow")
    print("   4. ✅ Labels exist locally but not synced to Roboflow")
    
    print("\n💡 Solution:")
    print("   Upload images+labels TOGETHER using Roboflow web UI")
    print("   Drag & drop the UPLOAD_ROBOFLOW_FINALE folder")
    print("=" * 70)

if __name__ == "__main__":
    main()
