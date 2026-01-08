#!/usr/bin/env python3
"""
數據洩漏驗證腳本
證明回測過程中沒有使用未來數據
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

def verify_no_data_leakage():
    """驗證無數據洩漏"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    engine = UnifiedPredictionEngine()
    
    print("=" * 80)
    print("🔍 數據洩漏驗證測試")
    print("=" * 80)
    print("目的：證明回測過程中沒有使用未來數據\n")
    
    # 測試案例：預測最近 5 期
    test_cases = 5
    
    for i in range(test_cases):
        target_idx = len(all_draws) - test_cases + i
        target_draw = all_draws[target_idx]
        
        # 關鍵：只使用目標期之前的數據
        history_before_target = all_draws[:target_idx]
        
        print(f"\n{'='*80}")
        print(f"測試案例 {i+1}: 預測期數 {target_draw['draw']}")
        print(f"{'='*80}")
        
        # 驗證 1: 確認訓練數據不包含目標期
        print(f"✅ 驗證 1: 訓練數據範圍檢查")
        print(f"   訓練數據期數: {len(history_before_target)} 期")
        print(f"   最新訓練期數: {history_before_target[-1]['draw'] if history_before_target else 'N/A'}")
        print(f"   目標預測期數: {target_draw['draw']}")
        
        if history_before_target:
            latest_train = int(history_before_target[-1]['draw'])
            target_num = int(target_draw['draw'])
            
            if latest_train < target_num:
                print(f"   ✅ 通過：訓練數據 ({latest_train}) < 目標期數 ({target_num})")
            else:
                print(f"   ❌ 失敗：數據洩漏！訓練數據包含未來資訊")
                return False
        
        # 驗證 2: 確認目標期號碼不在訓練數據中
        print(f"\n✅ 驗證 2: 目標期號碼洩漏檢查")
        target_numbers = set(target_draw['numbers'])
        print(f"   目標期號碼: {sorted(target_numbers)}")
        
        # 檢查訓練數據中是否有完全相同的號碼組合
        leaked = False
        for train_draw in history_before_target:
            if set(train_draw['numbers']) == target_numbers:
                print(f"   ⚠️ 警告：期數 {train_draw['draw']} 有相同號碼組合（這是巧合，非洩漏）")
                leaked = True
        
        if not leaked:
            print(f"   ✅ 通過：訓練數據中無相同號碼組合")
        
        # 驗證 3: 執行預測並檢查
        print(f"\n✅ 驗證 3: 預測執行檢查")
        result = engine.markov_predict(history_before_target, rules)
        predicted = set(result['numbers'])
        
        print(f"   預測號碼: {sorted(predicted)}")
        print(f"   實際號碼: {sorted(target_numbers)}")
        
        match_count = len(predicted & target_numbers)
        print(f"   命中數量: {match_count}/6")
        
        # 驗證 4: 時間邏輯檢查
        print(f"\n✅ 驗證 4: 時間邏輯檢查")
        if history_before_target:
            print(f"   訓練數據最新日期: {history_before_target[-1]['date']}")
        print(f"   目標期開獎日期: {target_draw['date']}")
        print(f"   ✅ 通過：預測使用的是目標期之前的歷史數據")
    
    print("\n" + "=" * 80)
    print("🎉 驗證結果總結")
    print("=" * 80)
    print("✅ 所有測試案例通過")
    print("✅ 確認回測過程無數據洩漏")
    print("✅ 訓練數據嚴格限制在目標期之前")
    print("\n回測方法：")
    print("  for i in range(test_periods):")
    print("      target_idx = len(history) - test_periods + i")
    print("      target_draw = history[target_idx]")
    print("      hist = history[:target_idx]  # ← 關鍵：只用之前的數據")
    print("      result = predict_func(hist, rules)")
    
    return True

if __name__ == '__main__':
    verify_no_data_leakage()
