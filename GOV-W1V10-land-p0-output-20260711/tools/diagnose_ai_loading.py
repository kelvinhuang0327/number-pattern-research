#!/usr/bin/env python3
import os
import sys
import traceback
import json

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

def diagnose():
    print("🔍 Diagnosing AI Adapter Prediction Flow...")
    
    # 1. Check Dependencies
    try:
        import torch
        import numpy as np
        print(f"✅ PyTorch ({torch.__version__}) and NumPy ({np.__version__}) available.")
    except ImportError as e:
        print(f"❌ Dependency Missing: {e}")
        return

    # 2. Check Files
    model_path = os.path.join(project_root, 'ai_lab', 'ai_models', 'v3_deep_resonance.pth')
    data_path = os.path.join(project_root, 'ai_lab', 'data', 'real_biglotto.json')
    
    if os.path.exists(model_path):
        print(f"✅ Model File Found: {model_path}")
    else:
        print(f"❌ Model File Missing: {model_path}")
        
    if os.path.exists(data_path):
        print(f"✅ Data File Found: {data_path}")
    else:
        print(f"❌ Data File Missing: {data_path}")
        # Note: If this is missing, the adapter will fail at line 36
        
    # 3. Import Adapter
    try:
        from ai_lab.adapter import AIAdapter
        print("✅ AIAdapter Imported")
    except Exception as e:
        print(f"❌ Failed to Import AIAdapter: {e}")
        traceback.print_exc()
        return

    # 4. Simulate Prediction
    try:
        # Dummy history (15 draws of 6 numbers)
        dummy_history = [{'numbers': [1, 2, 3, 4, 5, 6]} for _ in range(20)]
        dummy_rules = {'pickCount': 6}
        
        print("⏳ Calling get_ai_prediction('transformer_v3')...")
        res = AIAdapter.get_ai_prediction('transformer_v3', dummy_history, dummy_rules)
        
        if res:
            print("✅ AI Prediction SUCCESS")
            print(f"   Confidence: {res.get('confidence')}")
            print(f"   Numbers: {res.get('numbers')}")
        else:
            print("❌ AI Prediction Returned None (Fallback Triggered)")
            # To find out WHY, we might need to peek at logs or temporarily modify the adapter
            # But usually it's one of the files above.
            
    except Exception as e:
        print(f"❌ Crash during Prediction Call: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    diagnose()
