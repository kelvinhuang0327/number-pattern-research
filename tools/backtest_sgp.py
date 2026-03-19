#!/usr/bin/env python3
import sys
import os
import json
import logging
import numpy as np
from typing import List, Dict
from collections import Counter

# 設置路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from models.unified_predictor import UnifiedPredictionEngine
from common import get_lottery_rules

# 禁用詳細日誌以加快速度
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

def calculate_matches(predicted: List[int], actual: List[int]) -> int:
    return len(set(predicted) & set(actual))

def main():
    lottery_type = 'POWER_LOTTO'
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    engine = UnifiedPredictionEngine()
    lottery_rules = get_lottery_rules(lottery_type)
    
    # 獲取所有數據
    all_draws = sorted(db.get_all_draws(lottery_type), key=lambda x: (x['date'], x['draw']))
    
    # 設置回測參數
    test_count = 100 # Default
    if len(sys.argv) > 1:
        test_count = int(sys.argv[1])
        
    if len(all_draws) < test_count + 300:
        test_count = len(all_draws) - 300
        
    draws_to_test = all_draws[-test_count:]
    
    show_progress = test_count <= 100 # 只有小樣本才打印每一期
    
    if show_progress:
        print("=" * 100)
        print(f"📊 SGP STRATEGY BACKTEST: LAST {test_count} DRAWS SIMULATION")
        print("-" * 100)
        print(f"{'Draw':<12} | {'Actual':<20} | {'S'} | {'Predicted':<20} | {'pS'} | {'Hit'} | {'S'}")
        print("-" * 100)
    else:
        print(f"Running batch backtest for {test_count} periods...")

    match_counts = {i: 0 for i in range(7)}
    special_hits = 0
    total_samples = 0
    
    # 用於計算 Edge
    # 威力彩 38 選 6 的命中概率 (近似)
    # 0: 31.0%, 1: 43.0%, 2: 21.0%, 3: 4.4%, 4: 0.3%, 5: 0.006%, 6: 0.00003%
    theoretical_prob = {
        0: 0.3129, 1: 0.4371, 2: 0.2081, 3: 0.0385, 4: 0.0033, 5: 0.0001, 6: 0.00000003
    }
    theoretical_s_prob = 0.125 # 1/8
    
    for i in range(len(all_draws) - test_count, len(all_draws)):
        target_draw = all_draws[i]
        history = list(reversed(all_draws[:i])) # Predictors expect newest first
        
        try:
            # 執行 SGP 預測
            res = engine.sgp_predict(history, lottery_rules)
            
            predicted_nums = res['numbers']
            predicted_special = res.get('special')
            
            actual_nums = target_draw['numbers']
            actual_special = target_draw['special']
            
            # 安全檢查
            if actual_special is None: continue
            
            m = calculate_matches(predicted_nums, actual_nums)
            s_hit = 1 if int(predicted_special) == int(actual_special) else 0
            
            match_counts[m] += 1
            if s_hit: special_hits += 1
            total_samples += 1
            
            # 打印進度 (每 10 期顯示一條，或是有 3+ 命中時顯示)
            if show_progress and (total_samples % 10 == 0 or m >= 3):
                act_str = ",".join(f"{n:02d}" for n in actual_nums)
                pre_str = ",".join(f"{n:02d}" for n in predicted_nums)
                s_mark = "★" if s_hit else " "
                print(f"{target_draw['draw']:<12} | {act_str:<20} | {actual_special} | {pre_str:<20} | {predicted_special}  | {m:<3} | {s_mark}")
                
        except Exception as e:
            # logger.error(f"Error at draw {target_draw['draw']}: {e}")
            continue

    print("-" * 100)
    print(f"📈 SGP BACKTEST SUMMARY (N={total_samples})")
    print("-" * 100)
    
    for m in range(7):
        count = match_counts[m]
        actual_p = count / total_samples if total_samples > 0 else 0
        theo_p = theoretical_prob.get(m, 0)
        edge = (actual_p / theo_p - 1) * 100 if theo_p > 0 else 0
        print(f"Match {m}: {count:2d} draws ({actual_p*100:5.2f}%) | Theo: {theo_p*100:5.2f}% | Edge: {edge:+6.1f}%")

    s_rate = (special_hits / total_samples) * 100 if total_samples > 0 else 0
    s_edge = (s_rate / (theoretical_s_prob * 100) - 1) * 100
    print(f"Special: {special_hits:2d} hits  ({s_rate:5.2f}%) | Theo: {theoretical_s_prob*100:5.2f}% | Edge: {s_edge:+6.1f}%")
    
    # 綜合評價
    m3plus = sum(match_counts[m] for m in range(3, 7))
    m3plus_rate = m3plus / total_samples if total_samples > 0 else 0
    theo_m3plus = sum(theoretical_prob[m] for m in range(3, 7))
    m3plus_edge = (m3plus_rate / theo_m3plus - 1) * 100 if theo_m3plus > 0 else 0
    
    print("-" * 100)
    print(f"M3+ (3+ Numbers Hit): {m3plus:2d} draws ({m3plus_rate*100:5.2f}%) | Edge: {m3plus_edge:+6.1f}%")
    
    if m3plus_edge > 10:
        print("RESULT: ✅ SGP Strategy shows ALPHA (Significant Edge Detection).")
    elif m3plus_edge > -10:
        print("RESULT: ⚠️ SGP Strategy is NEUTRAL (Random-like performance).")
    else:
        print("RESULT: ❌ SGP Strategy shows NEGATIVE EDGE (Needs calibration).")
    print("=" * 100)

if __name__ == "__main__":
    main()
