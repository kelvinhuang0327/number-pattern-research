#!/usr/bin/env python3
import sys
import os
import json
import numpy as np
from typing import List, Dict

# 設置路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from models.sgp_strategy import SGPStrategy
from common import get_lottery_rules

def calculate_matches(predicted_sets: List[List[int]], actual: List[int]) -> Dict:
    """計算多注組合的覆蓋率指標"""
    actual_set = set(actual)
    
    # 1. 最高單注命中 (Max Single Hit)
    max_hit = 0
    for bet in predicted_sets:
       max_hit = max(max_hit, len(set(bet) & actual_set))
    
    # 2. 聯集命中 (Union Hit / Coverage)
    union_set = set()
    for bet in predicted_sets:
        union_set.update(bet)
    union_hit = len(union_set & actual_set)
    
    return {
        'max_hit': max_hit,
        'union_hit': union_hit,
        'pool_size': len(union_set)
    }

def main():
    lottery_type = 'POWER_LOTTO'
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    sgp = SGPStrategy()
    lottery_rules = get_lottery_rules(lottery_type)
    
    # 獲取回測數據
    all_draws = sorted(db.get_all_draws(lottery_type), key=lambda x: (x['date'], x['draw']))
    test_count = 100
    draws_to_test = all_draws[-test_count:]
    
    print("=" * 100)
    print(f"📊 SGP 3-BET COVERAGE BACKTEST (N={test_count})")
    print(f"Goal: Evaluate 3-Bet ensemble's ability to catch all 6 numbers in union set.")
    print("-" * 100)
    print(f"{'Draw':<12} | {'Actual':<18} | {'Max Hit':<7} | {'Union Hit':<10} | {'Coverage%'}")
    print("-" * 100)

    stats = {
        'max_hits': {i: 0 for i in range(7)},
        'union_hits': {i: 0 for i in range(7)},
        'total_union_hits': 0,
    }

    for i in range(len(all_draws) - test_count, len(all_draws)):
        target_draw = all_draws[i]
        history = list(reversed(all_draws[:i]))
        actual_nums = target_draw['numbers']
        
        try:
            # 生成 3 注預測
            bets = sgp.generate_bets(history, n_bets=3, lottery_type=lottery_type)
            
            # 計算命中
            res = calculate_matches(bets, actual_nums)
            
            stats['max_hits'][res['max_hit']] += 1
            stats['union_hits'][res['union_hit']] += 1
            stats['total_union_hits'] += res['union_hit']
            
            # 打印顯著結果 (Union Hit >= 4)
            if res['union_hit'] >= 4 or (i+1) % 20 == 0:
                act_str = ",".join(f"{n:02d}" for n in actual_nums)
                cov_pct = (res['union_hit'] / 6) * 100
                print(f"{target_draw['draw']:<12} | {act_str:<18} | {res['max_hit']:<7} | {res['union_hit']:<10} | {cov_pct:5.1f}%")
                
        except Exception as e:
            continue

    print("-" * 100)
    print(f"📈 3-BET SUMMARY (N={test_count})")
    print("-" * 100)
    
    print("1. Highest Single Bet Performance:")
    for m in range(7):
        count = stats['max_hits'][m]
        print(f"  Predict {m} correct: {count:2d} draws ({count/test_count*100:5.1f}%)")
        
    print("\n2. Union Coverage (Systematic Defense):")
    for m in range(7):
        count = stats['union_hits'][m]
        print(f"  Union has {m} correct: {count:2d} draws ({count/test_count*100:5.1f}%)")

    # 理論隨機 18 號覆蓋率: 18/38 ~= 47.3% -> 6 * 0.473 ~= 2.83 顆
    avg_union = stats['total_union_hits'] / test_count
    theoretical_avg = 6 * (18/38)
    edge = (avg_union / theoretical_avg - 1) * 100
    
    print("-" * 100)
    print(f"Avg Union Hit: {avg_union:.2f} (Theoretical Random: {theoretical_avg:.2f})")
    print(f"Systematic Edge: {edge:+6.1f}%")
    
    # 結論
    full_hit_rate = (stats['union_hits'][5] + stats['union_hits'][6]) / test_count * 100
    print(f"Heavy Hit Probability (5+ in Union): {full_hit_rate:5.1f}%")
    print("=" * 100)

if __name__ == "__main__":
    main()
