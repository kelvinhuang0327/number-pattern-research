#!/usr/bin/env python3
import sys
import os
import logging
import torch

sys.path.insert(0, os.getcwd())
from database import db_manager
from models.sota_predictor import PatternAwareTransformerPredictor
from common import get_lottery_rules

logging.basicConfig(level=logging.INFO)

def main():
    lottery_type = 'POWER_LOTTO'
    lottery_rules = get_lottery_rules(lottery_type)
    
    # 初始化增強版 SOTA
    predictor = PatternAwareTransformerPredictor(lottery_rules)
    
    # 獲取近期數據
    history = db_manager.get_all_draws(lottery_type)[:100]
    
    if not history:
        print("No history found.")
        return

    print("=" * 60)
    print("🧪 TESTING ENHANCED SOTA TRANSFORMER (DUAL-HEAD)")
    print("=" * 60)
    
    # 1. 測試在線訓練
    print("\n1. Testing Online Fine-tuning...")
    predictor.train_on_history(history, epochs=3)
    
    # 2. 測試預測輸出
    print("\n2. Testing Dual-Head Prediction...")
    res = predictor.predict(history)
    
    if res:
        print(f"   Method          : {res['method']}")
        print(f"   Main Numbers    : {res['numbers']}")
        print(f"   Special Number  : {res['special']}")
        print(f"   Confidence      : {res['confidence']:.4f}")
        print(f"   S2 Probabilities: {res['s2_probabilities']}")
        
        # 驗證二區輸出範圍
        assert 1 <= res['special'] <= 8, f"Invalid special number: {res['special']}"
        print("\n✅ Verification SUCCESS: Dual-head outputs are valid.")
    else:
        print("\n❌ Verification FAILED: No prediction result.")

if __name__ == '__main__':
    main()
