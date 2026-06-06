#!/usr/bin/env python3
"""
Script to verify and display the exact class mapping mismatch
between local data.yaml and Roboflow project
"""

# Roboflow classes from screenshot (exact order, 56 classes total)
roboflow_classes = [
    '2c', '2d', '2h', '2s',  # 0-3
    '3c', '3d', '3h', '3s',  # 4-7
    '4c', '4d', '4h', '4s',  # 8-11
    '5c', '5d', '5h', '5s',  # 12-15
    '6c', '6d', '6h', '6s',  # 16-19
    '7c', '7d', '7h', '7s',  # 20-23
    '8c', '8d', '8h', '8s',  # 24-27
    '9c', '9d', '9h', '9s',  # 28-31
    'Ac', 'Ad', 'Ah', 'As',  # 32-35
    'Jc', 'Jd', 'Jh', 'Js',  # 36-39
    'Kc', 'Kd', 'Kh', 'Ks',  # 40-43
    'Qc', 'Qd', 'Qh', 'Qs',  # 44-47
    'Td', 'Th', 'Ts',        # 48-50 (NOTE: Missing Tc here!)
    'dealer_btn',            # 51
    'player_bar',            # 52
    'player_info',           # 53
    'rivals_card',           # 54
    'tc'                     # 55 (10 of clubs - LOWERCASE!)
]

# Local data.yaml classes
local_classes = ['2c', '2d', '2h', '2s', '3c', '3d', '3h', '3s', '4c', '4d', '4h', '4s', 
                 '5c', '5d', '5h', '5s', '6c', '6d', '6h', '6s', '7c', '7d', '7h', '7s', 
                 '8c', '8d', '8h', '8s', '9c', '9d', '9h', '9s', 'Ac', 'Ad', 'Ah', 'As', 
                 'Jc', 'Jd', 'Jh', 'Js', 'Kc', 'Kd', 'Kh', 'Ks', 'Qc', 'Qd', 'Qh', 'Qs', 
                 'Td', 'Th', 'Ts', 'dealer_btn', 'player_bar', 'player_info', 'rivals_card', 'tc']

print("=== CLASS MAPPING ANALYSIS ===\n")
print(f"Roboflow classes: {len(roboflow_classes)}")
print(f"Local classes: {len(local_classes)}")
print()

print("=== MISMATCHES FOUND ===\n")
mismatches = []
for i, (rf_class, local_class) in enumerate(zip(roboflow_classes, local_classes)):
    if rf_class != local_class:
        print(f"Position {i}: Roboflow='{rf_class}' vs Local='{local_class}' ❌")
        mismatches.append((i, rf_class, local_class))
    else:
        if i < 10 or i in [48, 49, 50, 51, 52, 53, 54, 55]:  # Show key positions
            print(f"Position {i}: '{rf_class}' ✓")

if not mismatches:
    print("\n✓ All classes match perfectly!")
else:
    print(f"\n⚠️ Found {len(mismatches)} mismatches")
    print("\n=== REQUIRED CORRECTIONS ===")
    for pos, rf, local in mismatches:
        print(f"  Position {pos}: Change'{local}' → '{rf}'")

# Create the correct mapping
print("\n=== CORRECT ROBOFLOW CLASS LIST ===")
print("names:", roboflow_classes)
