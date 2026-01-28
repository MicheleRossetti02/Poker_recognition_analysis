#!/usr/bin/env python3
"""
Fix Roboflow Class Names - Direct API Method
=============================================
Rename class IDs 52-55 to proper names
"""

import requests
import json

# Configuration
API_KEY = "CtDu9vml1KIKbDsLHMYU"
WORKSPACE = "pokergtobot"
PROJECT = "poker-gto-production"

# Class name mapping from data.yaml
CLASS_MAPPING = {
    0: '2c', 1: '2d', 2: '2h', 3: '2s', 4: '3c', 5: '3d', 6: '3h', 7: '3s',
    8: '4c', 9: '4d', 10: '4h', 11: '4s', 12: '5c', 13: '5d', 14: '5h', 15: '5s',
    16: '6c', 17: '6d', 18: '6h', 19: '6s', 20: '7c', 21: '7d', 22: '7h', 23: '7s',
    24: '8c', 25: '8d', 26: '8h', 27: '8s', 28: '9c', 29: '9d', 30: '9h', 31: '9s',
    32: 'Ac', 33: 'Ad', 34: 'Ah', 35: 'As', 36: 'Jc', 37: 'Jd', 38: 'Jh', 39: 'Js',
    40: 'Kc', 41: 'Kd', 42: 'Kh', 43: 'Ks', 44: 'Qc', 45: 'Qd', 46: 'Qh', 47: 'Qs',
    48: 'Td', 49: 'Th', 50: 'Ts', 51: 'dealer_btn', 52: 'player_bar', 
    53: 'player_info', 54: 'rivals_card', 55: 'tc'
}

def main():
    print("=" * 70)
    print("🔧 FIXING ROBOFLOW CLASS NAMES - PRIORITY FIX")
    print("=" * 70)
    
    print(f"\n🎯 Critical Classes to Fix:")
    print(f"   51: dealer_btn")
    print(f"   52: player_bar")
    print(f"   53: player_info")
    print(f"   54: rivals_card")
    print(f"   55: tc (card)")
    
    # Method 1: Try updating via dataset classes endpoint
    print(f"\n📡 Attempting API update...")
    
    base_url = f"https://api.roboflow.com/{WORKSPACE}/{PROJECT}"
    
    # Create class mapping payload
    classes_payload = {}
    for class_id, class_name in CLASS_MAPPING.items():
        classes_payload[str(class_id)] = class_name
    
    # Try updating via API
    update_url = f"{base_url}/classes"
    params = {"api_key": API_KEY}
    
    try:
        response = requests.put(
            update_url,
            params=params,
            json={"classes": classes_payload},
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   Response: {response.status_code}")
        if response.status_code in [200, 201]:
            print(f"   ✅ Classes updated successfully!")
        else:
            print(f"   Response body: {response.text[:300]}")
    except Exception as e:
        print(f"   ❌ API Error: {e}")
    
    # Save mapping to JSON for manual update if needed
    with open('roboflow_class_mapping.json', 'w') as f:
        json.dump(CLASS_MAPPING, f, indent=2)
    
    print(f"\n📁 Class mapping saved to: roboflow_class_mapping.json")
    
    print("\n" + "=" * 70)
    print("⚠️  MANUAL UPDATE REQUIRED IF API FAILED:")
    print("=" * 70)
    print("\n1. Go to: https://app.roboflow.com/pokergtobot/poker-gto-production/classes")
    print("2. For each class ID, click Edit and update name:")
    print(f"   - Class 51: dealer_btn")
    print(f"   - Class 52: player_bar")
    print(f"   - Class 53: player_info")
    print(f"   - Class 54: rivals_card")
    print(f"   - Class 55: tc")
    print("\n" + "=" * 70)
    
    print("\n✅ Done! Refresh Roboflow dashboard to see changes.")

if __name__ == "__main__":
    main()
