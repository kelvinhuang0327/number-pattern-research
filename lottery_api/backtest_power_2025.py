#!/usr/bin/env python3
import sys
import os
import json
import logging
from typing import List, Dict
from collections import defaultdict

# 設置路徑
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from common import get_lottery_rules

# 禁用詳細日誌以加快速度
logging.getLogger().setLevel(logging.WARNING)

def calculate_matches(predicted: List[int], actual: List[int]) -> int:
    return len(set(predicted) & set(actual))


import argparse

def main():
    parser = argparse.ArgumentParser(description='Power Lotto Backtest 2025')
    parser.add_argument('--periods', type=int, default=30, help='Number of periods to test')
    parser.add_argument('--bets', type=int, default=4, help='Number of bets per draw (1, 4, or 6)')
    parser.add_argument('--full', action='store_true', help='Test all 2025 draws')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility')
    args = parser.parse_args()

    # Initialize random seeds
    import random
    import numpy as np
    random.seed(args.seed)
    np.random.seed(args.seed)
    try:
        import torch
        torch.manual_seed(args.seed)
    except ImportError:
        pass

    lottery_type = 'POWER_LOTTO'
    engine = UnifiedPredictionEngine()
    lottery_rules = get_lottery_rules(lottery_type)
    
    # Fix database path
    import os
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    if os.path.exists(db_path):
        db_manager.db_path = db_path
    
    # 獲取所有數據
    all_draws = db_manager.get_all_draws(lottery_type)
    
    # 篩選 2025 年的期號
    draws_2025 = [d for d in all_draws if '2025' in str(d.get('date', ''))]
    draws_2025 = sorted(draws_2025, key=lambda x: x['draw'])
    
    if not args.full:
        if len(draws_2025) > args.periods:
            draws_2025 = draws_2025[-args.periods:]

    if not draws_2025:
        print("❌ 未找到 2025 年數據")
        return

    num_bets = args.bets
    print("=" * 100)
    print(f"📊 POWER_LOTTO ROLLING BACKTEST: 2025 YEAR SIMULATION")
    print(f"Total draws to test: {len(draws_2025)} | Bets per draw: {num_bets}")
    print("=" * 100)
    print(f"{'Draw':<10} | {'Actual (M+S)':<15} | {'Best Prediction':<18} | {'Best M':<6} | {'S'} | {'Result'}")
    print("-" * 100)

    any_hit_20_count = 0  # 至少中3個號碼的期數 (威力彩中3個即有獎)
    main_match_dist = defaultdict(int)
    special_hit_count = 0
    
    from models.optimized_ensemble import OptimizedEnsemblePredictor
    ensemble = OptimizedEnsemblePredictor(engine)

    for target_draw in draws_2025:
        draw_id = target_draw['draw']
        
        target_idx = -1
        for i, d in enumerate(all_draws):
            if d['draw'] == draw_id:
                target_idx = i
                break
        
        if target_idx == -1 or target_idx + 1 >= len(all_draws):
            continue
            
        history = all_draws[target_idx + 1 :]
        print(f"DEBUG: Predicting {draw_id}... ", end='', flush=True)
        
        try:
            ensemble_res = ensemble.predict(history, lottery_rules, backtest_periods=15, num_bets=num_bets)
            
            actual_numbers = set(target_draw['numbers'])
            actual_special = int(target_draw['special'])
            
            best_m = -1
            special_hit = False
            has_hit_any = False
            
            # 檢查多注
            for b_idx in range(1, num_bets + 1):
                bet_key = f'bet{b_idx}'
                if bet_key not in ensemble_res:
                    continue
                    
                bet = ensemble_res[bet_key]
                pred_nums = set(bet['numbers'])
                pred_special = int(bet['special'])
                
                m = len(pred_nums & actual_numbers)
                s = (pred_special == actual_special)
                
                if m > best_m:
                    best_m = m
                if s:
                    special_hit = True
                
                # 威力彩只要有獎就算 Hit
                # 普獎: 1區中3; 陸獎: 1區中3+2區中; ... 
                # 這裡 1區中3 或 1區中2+2區中 或 1區中1+2區中 或 直接2區中 都有獎
                # 但 20% 目標通常指「有獎」的機率
                if m >= 3 or (m >= 1 and s) or s:
                    has_hit_any = True

            if has_hit_any:
                any_hit_20_count += 1
                
            main_match_dist[best_m] += 1
            if special_hit:
                special_hit_count += 1
            
            # Print row
            best_pred_str = f"M:{best_m}"
            s_mark = "★" if special_hit else " "
            status = "WIN" if has_hit_any else "---"
            
            actual_str = f"{sorted(list(actual_numbers))}+{actual_special}"
            
            print(f"\r{draw_id:<10} | {str(actual_str):<15} | {best_pred_str:<18} | {best_m:<6} | {s_mark} | {status}")
            
        except Exception as e:
            continue

    print("-" * 100)
    print(f"📈 BACKTEST SUMMARY (2025) - {num_bets} BETS CONFIG")
    print("-" * 100)
    total_tested = len(draws_2025)
    
    hit_rate = (any_hit_20_count / total_tested) * 100 if total_tested > 0 else 0
    print(f"Total Periods: {total_tested}")
    print(f"Winning Periods: {any_hit_20_count}")
    print(f"Overall Hit Rate: {hit_rate:.2f}% (Target: 20%+)")
    print("-" * 100)
    print("Best Match Distribution (Per Draw):")
    for m in range(7):
        count = main_match_dist[m]
        rate = (count / total_tested) * 100 if total_tested > 0 else 0
        print(f"  Max Match {m}: {count:2d} draws ({rate:5.1f}%)")
    
    s_rate = (special_hit_count / total_tested) * 100 if total_tested > 0 else 0
    print(f"Special Number Hits: {special_hit_count:2d} draws ({s_rate:5.1f}%)")
    print("=" * 100)


if __name__ == '__main__':
    main()
