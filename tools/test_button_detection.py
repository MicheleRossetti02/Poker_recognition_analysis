#!/usr/bin/env python3
"""
Test - Button Recognition & Position Detection
===============================================
Valida le nuove funzionalità di button detection.
"""

import sys
import numpy as np

def test_module_imports():
    """Test 1: Verifica import modulo e nuove classi"""
    print("🧪 Test 1: Module Imports & New Classes")
    try:
        from card_recognizer import (
            PokerBrain, 
            ButtonDetection, 
            HeroPosition,
            BUTTON_CLASS_ID,
            BUTTON_CLASS_NAME
        )
        
        print(f"   ✅ ButtonDetection class imported")
        print(f"   ✅ HeroPosition enum imported")
        print(f"   ✅ BUTTON_CLASS_ID = {BUTTON_CLASS_ID}")
        print(f"   ✅ BUTTON_CLASS_NAME = '{BUTTON_CLASS_NAME}'")
        
        # Verifica HeroPosition positions
        positions = [pos.value for pos in HeroPosition]
        print(f"   ✅ HeroPosition values: {positions}")
        
        return True
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False

def test_hero_position_logic():
    """Test 2: Test logica get_hero_position con posizioni simulate"""
    print("\n🧪 Test 2: Hero Position Logic")
    try:
        from card_recognizer import PokerBrain, HeroPosition
        
        # Inizializza brain (usa yolov8n.pt generico per test)
        brain = PokerBrain(model_path="yolov8n.pt", verbose=False)
        
        # Frame size simulato (tipico PokerStars)
        frame_size = (952, 676)
        center_x = frame_size[0] // 2
        center_y = frame_size[1] // 2
        
        # Test posizioni simulate
        test_cases = [
            # (button_x, button_y, expected_position)
            (center_x, int(frame_size[1] * 0.7), "Button"),  # Basso center
            (int(frame_size[0] * 0.8), center_y, "Small Blind"),  # Destra
            (int(frame_size[0] * 0.8), int(frame_size[1] * 0.3), "Big Blind"),  # Alto-destra
            (int(frame_size[0] * 0.2), int(frame_size[1] * 0.3), "Under The Gun"),  # Alto-sinistra
            (int(frame_size[0] * 0.15), center_y, "Hijack"),  # Sinistra
            (int(frame_size[0] * 0.2), int(frame_size[1] * 0.65), "Cutoff"),  # Basso-sinistra
        ]
        
        passed = 0
        for button_pos, expected in test_cases:
            result = brain._get_hero_position(button_pos, frame_size)
            status = "✅" if result.value == expected else "❌"
            print(f"   {status} Button at {button_pos} → {result.value} (expected: {expected})")
            if result.value == expected:
                passed += 1
        
        print(f"\n   Results: {passed}/{len(test_cases)} correct")
        return passed == len(test_cases)
        
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_analyze_frame_structure():
    """Test 3: Verifica struttura risultato analyze_frame"""
    print("\n 🧪 Test 3: analyze_frame Result Structure")
    try:
        from card_recognizer import PokerBrain
        
        brain = PokerBrain(model_path="yolov8n.pt", verbose=False)
        
        # Frame fittizio
        frame = np.zeros((676, 952, 3), dtype=np.uint8)
        
        result = brain.analyze_frame(frame)
        
        # Verifica chiavi aggiunte
        required_keys = ["button_detected", "hero_position"]
        for key in required_keys:
            if key in result:
                print(f"   ✅ Key '{key}' present: {result[key]}")
            else:
                print(f"   ❌ Key '{key}' missing")
                return False
        
        # Verifica tipi
        if isinstance(result["button_detected"], bool):
            print(f"   ✅ button_detected is bool")
        else:
            print(f"   ❌ button_detected wrong type: {type(result['button_detected'])}")
            return False
        
        if isinstance(result["hero_position"], str):
            print(f"   ✅ hero_position is str")
        else:
            print(f"   ❌ hero_position wrong type: {type(result['hero_position'])}")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 70)
    print("🔬 Button Recognition & Position Detection - Test Suite")
    print("=" * 70 + "\n")
    
    tests = [
        test_module_imports,
        test_hero_position_logic,
        test_analyze_frame_structure
    ]
    
    results = [test() for test in tests]
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    success_rate = (passed / total) * 100
    
    print(f"📊 Test Results: {passed}/{total} passed ({success_rate:.0f}%)")
    
    if passed == total:
        print("\n✅ Tutti i test passati!")
        print("\n📝 Prossimi passi:")
        print("   1. Allenare modello YOLOv8 con classe 'button' (ID 52)")
        print("   2. Testare con immagini reali di PokerStars")
        print("   3. Validare posizioni rilevate durante il gioco")
        print("   4. Integrare nel main.py per GTO context-aware")
    else:
        print(f"\n⚠️  {total - passed} test falliti. Ricontrolla implementazione.")
    
    print("=" * 70)
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
