#!/usr/bin/env python3
import sys
import os
import json
import logging
from typing import List, Dict

# 設置路徑
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from common import get_lottery_rules

# 禁用詳細日誌以加快速度
logging.getLogger().setLevel(logging.ERROR)

def calculate_matches(predicted: List[int], actual: List[int]) -> int:
    return len(set(predicted) & set(actual))

def main():
    lottery_type = 'POWER_LOTTO'
    engine = UnifiedPredictionEngine()
    lottery_rules = get_lottery_rules(lottery_type)
    
    # Fix database path
    # db_manager defaults to "data/lottery_v2.db", but relative to root it should be "lottery_api/data/lottery_v2.db"
    # or absolute path.
    import os
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    if os.path.exists(db_path):
        db_manager.db_path = db_path
        print(f"DEBUG: Updated DB path to {db_path}")
    else:
        print(f"DEBUG: Could not find DB at {db_path}, keeping default {db_manager.db_path}")

    # 獲取所有數據
    all_draws = db_manager.get_all_draws(lottery_type)
    print(f"DEBUG: Loaded {len(all_draws)} draws for {lottery_type}")
    if len(all_draws) > 0:
        print(f"DEBUG: Sample draw: {all_draws[0]}")
    
    # 篩選 2025 年的期號
    draws_2025 = [d for d in all_draws if '2025' in str(d.get('date', ''))]
    draws_2025 = sorted(draws_2025, key=lambda x: x['draw'])
    
    # [MODIFIED] Only test last 30 draws to be faster and meaningful for "current" status
    if len(draws_2025) > 30:
        print(f"DEBUG: Truncating {len(draws_2025)} draws to last 30 for speed.")
        draws_2025 = draws_2025[-5:]

    if not draws_2025:
        print("❌ 未找到 2025 年數據")
        return

    print("=" * 100)
    print(f"📊 POWER_LOTTO ROLLING BACKTEST: 2025 YEAR SIMULATION")
    print(f"Total draws to test: {len(draws_2025)}")
    print("=" * 100)
    print(f"{'Draw':<12} | {'Actual (M+S)':<25} | {'Predicted (M+S)':<25} | {'Match':<5} | {'S'}")
    print("-" * 100)

    total_matches = 0
    total_special_hits = 0
    match_counts = {i: 0 for i in range(7)} # 0-6 matches
    
    from models.optimized_ensemble import OptimizedEnsemblePredictor
    ensemble = OptimizedEnsemblePredictor(engine)
    
    window_size = 500 # 使用較大的固定窗口以保證穩定性

    for target_draw in draws_2025:
        draw_id = target_draw['draw']
        
        target_idx = -1
        for i, d in enumerate(all_draws):
            if d['draw'] == draw_id:
                target_idx = i
                break
        
        if target_idx == -1 or target_idx + 1 >= len(all_draws):
            continue
            
        # 使用全部可用歷史數據
        history = all_draws[target_idx + 1 :]
        
        # 執行最新集成預測 (包含 SOTA, GWO 和全局過濾)
        try:
            # 這裡我們使用旗艦級集成預測 (使用 15 期回測權重以加快速度)
            ensemble_res = ensemble.predict(history, lottery_rules, backtest_periods=3)
            
            # 測試第一注
            bet1 = ensemble_res['bet1']
            predicted_numbers = bet1['numbers']
            predicted_special = bet1['special']
            
            actual_numbers = target_draw['numbers']
            actual_special = target_draw['special']
            
            # 計算命中
            m = calculate_matches(predicted_numbers, actual_numbers)
            s_hit = 1 if int(predicted_special) == int(actual_special) else 0
            
            match_counts[m] += 1
            if s_hit: total_special_hits += 1
            
            # 打印進度
            actual_str = f"{actual_numbers}+{actual_special}"
            pred_str = f"{predicted_numbers}+{predicted_special}"
            s_mark = "★" if s_hit else " "
            print(f"{draw_id:<12} | {str(actual_str):<25} | {str(pred_str):<25} | {m:<5} | {s_mark}")
            
        except Exception as e:
            # print(f"Error predicting {draw_id}: {e}")
            continue

    print("-" * 100)
    print(f"📈 BACKTEST SUMMARY (2025)")
    print("-" * 100)
    total_tested = sum(match_counts.values())
    for m, count in match_counts.items():
        rate = (count / total_tested) * 100 if total_tested > 0 else 0
        print(f"Match {m}: {count:2d} draws ({rate:5.1f}%)")
    
    s_rate = (total_special_hits / total_tested) * 100 if total_tested > 0 else 0
    print(f"Special: {total_special_hits:2d} draws ({s_rate:5.1f}%)")
    print("=" * 100)

if __name__ == '__main__':
    main()
