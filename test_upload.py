#!/usr/bin/env python3
"""
Quick Test - Upload Script
===========================
Test rapido per verificare import credenziali e setup.
"""

import sys

def test_credential_import():
    """Test import credenziali da train.py"""
    print("🧪 Test 1: Import Credenziali da train.py")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("train", "train.py")
        if spec is None or spec.loader is None:
            print("   ❌ train.py non trovato")
            return False
        
        train_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(train_module)
        
        api_key = getattr(train_module, 'ROBOFLOW_API_KEY', None)
        workspace = getattr(train_module, 'WORKSPACE', None)
        project = getattr(train_module, 'PROJECT', None)
        
        if not all([api_key, workspace, project]):
            print("   ❌ Costanti mancanti")
            return False
        
        print(f"   ✅ API Key: {api_key[:10]}...")
        print(f"   ✅ Workspace: {workspace}")
        print(f"   ✅ Project: {project}")
        return True
    
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False

def test_upload_script_syntax():
    """Test syntax upload script"""
    print("\n🧪 Test 2: Upload Script Syntax")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "upload_to_roboflow",
            "upload_to_roboflow.py"
        )
        if spec is None or spec.loader is None:
            print("   ❌ upload_to_roboflow.py non trovato")
            return False
        
        module = importlib.util.module_from_spec(spec)
        sys.modules["upload_to_roboflow"] = module
        spec.loader.exec_module(module)
        
        # Verifica classi esistono
        assert hasattr(module, 'RoboflowUploader')
        assert hasattr(module, 'UploadStats')
        
        print("   ✅ Script caricato senza errori")
        print("   ✅ RoboflowUploader class OK")
        print("   ✅ UploadStats class OK")
        return True
    
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False

def main():
    print("=" * 70)
    print("🔬 Upload Script - Quick Test")
    print("=" * 70 + "\n")
    
    tests = [
        test_credential_import,
        test_upload_script_syntax
    ]
    
    results = [test() for test in tests]
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"📊 Risultati: {passed}/{total} test passati")
    
    if passed == total:
        print("\n✅ Upload script è pronto!")
        print("\n📝 Prossimi passi:")
        print("   1. Test dry-run:")
        print("      python upload_to_roboflow.py dataset/raw/session_*/ --dry-run")
        print("   2. Upload reale quando hai sessioni:")
        print("      python upload_to_roboflow.py dataset/raw/session_20260117_*/")
    else:
        print(f"\n⚠️  {total - passed} test falliti")
    
    print("=" * 70)
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
