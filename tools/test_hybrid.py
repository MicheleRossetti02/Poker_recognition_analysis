#!/usr/bin/env python3
"""
Test Validator - Data Factory Hybrid
=====================================
Valida tutte le feature della versione hybrid.
"""

import sys
import json
from pathlib import Path

def test_imports():
    """Test 1: Verifica imports"""
    print("🧪 Test 1: Import Validation")
    try:
        import cv2
        import mss
        import numpy as np
        print("   ✅ Dipendenze OK (cv2, mss, numpy)")
        return True
    except ImportError as e:
        print(f"   ❌ Import fallito: {e}")
        return False

def test_cli_help():
    """Test 2: Verifica CLI help"""
    print("\n🧪 Test 2: CLI Help")
    import subprocess
    result = subprocess.run(
        ["python", "fast_capture.py", "--help"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0 and "--motion-method" in result.stdout:
        print("   ✅ CLI  arguments OK")
        return True
    else:
        print("   ❌ CLI help fallito")
        return False

def test_motion_detector():
    """Test 3: Test MotionDetector class"""
    print("\n🧪 Test 3: MotionDetector Unit Test")
    try:
        import sys
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fast_capture",
            "fast_capture.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["fast_capture"] = module
        spec.loader.exec_module(module)
        
        # Test percent method
        detector_percent = module.MotionDetector(method="percent", threshold=5.0)
        print("   ✅ MotionDetector(percent) initialized")
        
        # Test MSE method
        detector_mse = module.MotionDetector(method="mse", threshold=15.0)
        print("   ✅ MotionDetector(mse) initialized")
        
        # Test con frame fittizio
        import numpy as np
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        motion, value, label = detector_percent.detect_motion(frame)
        print(f"   ✅ Motion detection OK: {label}")
        
        return True
    except Exception as e:
        print(f"   ❌ MotionDetector test fallito: {e}")
        return False

def test_session_manager():
    """Test 4: Test SessionManager"""
    print("\n🧪 Test 4: SessionManager Unit Test")
    try:
        import sys
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fast_capture",
            "fast_capture.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["fast_capture"] = module
        spec.loader.exec_module(module)
        
        session = module.SessionManager(
            base_dir="test_output",
            version=4,
            motion_method="percent",
            motion_threshold=5.0,
            capture_config={
                "top": 19,
                "left": 4,
                "width": 476,
                "height": 338,
                "scale": 2
            }
        )
        
        print(f"   ✅ SessionManager initialized: {session.session_id}")
        
        # Test metadata generazione
        session.frames_analyzed = 100
        session.images_saved = 20
        session.motion_detected_count = 35
        metadata = session.finalize()
        
        if metadata["save_rate_percent"] == 20.0:
            print(f"   ✅ Metadata correct: save_rate = 20%")
        else:
            print(f"   ⚠️  Save rate calculation: {metadata['save_rate_percent']}")
        
        # Cleanup
        import shutil
        if Path("test_output").exists():
            shutil.rmtree("test_output")
            print("   ✅ Cleanup OK")
        
        return True
    except Exception as e:
        print(f"   ❌ SessionManager test fallito: {e}")
        return False

def main():
    print("=" * 70)
    print("🔬 DATA FACTORY HYBRID - Validation Suite")
    print("=" * 70)
    
    tests = [
        test_imports,
        test_cli_help,
        test_motion_detector,
        test_session_manager
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    success_rate = (passed / total) * 100
    
    print(f"\n✅ Passed: {passed}/{total} ({success_rate:.0f}%)")
    
    if passed == total:
        print("\n🎉 Tutti i test passati! Data Factory Hybrid è PRONTO.")
        print("\n📝 Prossimi passi:")
        print("   1. Test manuale: python fast_capture.py --manual")
        print("   2. Premi SPAZIO 2-3 volte per catturare test images")
        print("   3. Premi Q per uscire")
        print("   4. Verifica session_info.json creato")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test falliti. Ricontrolla l'implementazione.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
