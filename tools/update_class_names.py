#!/usr/bin/env python3
"""
Update Roboflow Class Names
============================
Maps numeric class IDs to actual card names
"""

import requests
import json

# Class names from data.yaml (in order 0-55)
CLASS_NAMES = [
    '2c', '2d', '2h', '2s', '3c', '3d', '3h', '3s', '4c', '4d',
    '4h', '4s', '5c', '5d', '5h', '5s', '6c', '6d', '6h', '6s',
    '7c', '7d', '7h', '7s', '8c', '8d', '8h', '8s', '9c', '9d',
    '9h', '9s', 'Ac', 'Ad', 'Ah', 'As', 'Jc', 'Jd', 'Jh', 'Js',
    'Kc', 'Kd', 'Kh', 'Ks', 'Qc', 'Qd', 'Qh', 'Qs', 'Tc', 'Td',
    'Th', 'Ts', 'board_info', 'rivals_card', 'player_info', 'table_info'
]

def update_class_names_via_api(api_key, workspace, project):
    """
    Update class names using Roboflow REST API
    """
    print("=" * 70)
    print("🏷️  UPDATING ROBOFLOW CLASS NAMES")
    print("=" * 70)
    
    print(f"\n📊 Configuration:")
    print(f"   Workspace: {workspace}")
    print(f"   Project: {project}")
    print(f"   Total classes: {len(CLASS_NAMES)}")
    
    # API endpoint for updating classes
    base_url = f"https://api.roboflow.com/{workspace}/{project}"
    
    print(f"\n🔄 Updating class names...")
    
    # Prepare class mapping
    class_mapping = {}
    for idx, name in enumerate(CLASS_NAMES):
        class_mapping[str(idx)] = name
    
    # Display mapping
    print(f"\n📋 Class Mapping (first 10):")
    for idx in range(min(10, len(CLASS_NAMES))):
        print(f"   {idx}: {CLASS_NAMES[idx]}")
    print(f"   ...")
    print(f"   {len(CLASS_NAMES)-1}: {CLASS_NAMES[-1]}")
    
    # Update via API (this endpoint may vary - Roboflow API documentation needed)
    # Alternative: update via dataset settings
    
    update_url = f"{base_url}/classes"
    headers = {
        "Content-Type": "application/json"
    }
    params = {
        "api_key": api_key
    }
    
    payload = {
        "classes": class_mapping
    }
    
    try:
        response = requests.post(update_url, params=params, headers=headers, json=payload)
        
        if response.status_code == 200:
            print(f"\n✅ Successfully updated class names!")
            return True
        else:
            print(f"\n⚠️  API Response: {response.status_code}")
            print(f"   {response.text[:200]}")
            
            # Alternative approach: print instructions for manual update
            print(f"\n📝 Manual Update Required:")
            print(f"   1. Go to Roboflow dashboard")
            print(f"   2. Navigate to Project Settings > Classes")
            print(f"   3. Update each class name according to mapping above")
            
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"\n📝 Class names to update manually:")
        for idx, name in enumerate(CLASS_NAMES):
            print(f"   Class {idx}: {name}")
        return False

def main():
    # API credentials
    API_KEY = "CtDu9vml1KIKbDsLHMYU"
    WORKSPACE = "pokergtobot"  
    PROJECT = "poker-gto-production"
    
    # Attempt to update
    success = update_class_names_via_api(API_KEY, WORKSPACE, PROJECT)
    
    if success:
        print("\n" + "=" * 70)
        print("✅ CLASS NAMES UPDATED!")
        print("=" * 70)
        print("\nGo to Roboflow > Classes & Tags to verify changes")
    else:
        print("\n" + "=" * 70)
        print("⚠️  MANUAL UPDATE NEEDED")
        print("=" * 70)
        
        # Save mapping to file for easy reference
        with open('class_mapping.json', 'w') as f:
            mapping = {str(i): name for i, name in enumerate(CLASS_NAMES)}
            json.dump(mapping, f, indent=2)
        
        print(f"\n📁 Class mapping saved to: class_mapping.json")
        print(f"   Use this file to manually update class names on Roboflow")

if __name__ == "__main__":
    main()
