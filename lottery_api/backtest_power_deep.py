import os
import sys
import random
import numpy as np
import logging
import argparse
from typing import List, Dict

# 加入項目根目錄與 lottery_api 到 path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from database import db_manager
from common import get_lottery_rules

# 禁用詳細日誌以加速輸出
logging.basicConfig(level=logging.ERROR)

def calculate_matches(predicted, actual):
    return len(set(predicted) & set(actual))

def main():
    parser = argparse.ArgumentParser(description='Power Lotto Deep Historical Backtest')
    parser.add_argument('--periods', type=int, default=150, help='Number of periods to test')
    parser.add_argument('--bets', type=int, default=4, help='Number of bets per draw')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    args = parser.parse_args()

    # 初始化隨機種子
    random.seed(args.seed)
    np.random.seed(args.seed)
    try:
        import torch
        torch.manual_seed(args.seed)
    except: pass

    lottery_type = 'POWER_LOTTO'
    
    # Fix database path
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    if os.path.exists(db_path):
        db_manager.db_path = db_path
    elif os.path.exists('lottery_api/data/lottery_v2.db'):
        db_manager.db_path = 'lottery_api/data/lottery_v2.db'
    
    engine = UnifiedPredictionEngine()
    ensemble = OptimizedEnsemblePredictor(engine)
    lottery_rules = get_lottery_rules(lottery_type)
    
    # 獲取所有數據
    all_draws = sorted(db_manager.get_all_draws(lottery_type), key=lambda x: x['draw'])
    
    if len(all_draws) < args.periods + 150: # 150 for training window
        print(f"⚠️ 數據總量不足 ({len(all_draws)} < {args.periods + 150})")
        # 調整回測期數
        test_draws = all_draws[-args.periods:] if len(all_draws) > args.periods else all_draws[150:]
    else:
        test_draws = all_draws[-args.periods:]

    total_periods = len(test_draws)
    print("=" * 100)
    print(f"🛸 DEEP HISTORICAL BACKTEST: {total_periods} PERIODS")
    print(f"Config: Seed={args.seed}, Bets={args.bets}")
    print("=" * 100)

    win_count = 0
    special_hits = 0
    match_counts = {i: 0 for i in range(8)}
    
    # 指標記錄
    results_log = []

    for idx, target_draw in enumerate(test_draws):
        draw_id = target_draw['draw']
        actual_main = set(target_draw['numbers'])
        actual_special = target_draw.get('special')
        
        # 準備歷史數據 (嚴格不包含當前期)
        # 在 all_draws 中找到 target_draw 的位置
        target_pos = next(i for i, d in enumerate(all_draws) if d['draw'] == draw_id)
        history = list(reversed(all_draws[:target_pos]))
        
        # 預測
        try:
            # 使用 num_bets 獲取多組預測
            ensemble_res = ensemble.predict(history, lottery_rules, backtest_periods=15, num_bets=args.bets)
            
            # 支援 'bets' 列表或是 'bet1', 'bet2' 字典格式
            predictions = []
            if 'bets' in ensemble_res:
                predictions = ensemble_res['bets']
            else:
                for b_idx in range(1, args.bets + 1):
                    bet_key = f'bet{b_idx}'
                    if bet_key in ensemble_res:
                        predictions.append(ensemble_res[bet_key])
            
            if not predictions:
                # 至少取一個主預測
                predictions = [{'numbers': ensemble_res.get('numbers', []), 'special': ensemble_res.get('special')}]
        except Exception as e:
            # print(f"Error at {draw_id}: {e}")
            continue

        best_m = 0
        s_hit = False
        
        for bet in predictions:
            m = calculate_matches(bet['numbers'], actual_main)
            s = (bet['special'] == actual_special)
            if m > best_m: best_m = m
            if s: s_hit = True
            
        if s_hit: special_hits += 1
        # 嚴格定義：命中獎項 (普獎或更高) 
        # 普獎條件：命中特別號 OR 命中 3 個主號
        if s_hit or best_m >= 3: win_count += 1
        match_counts[best_m] += 1
        
        # 每 10 期輸出一次進度
        if (idx + 1) % 10 == 0 or (idx + 1) == total_periods:
            progress = (idx + 1) / total_periods * 100
            curr_sr = (special_hits / (idx + 1)) * 100
            print(f"[{idx+1}/{total_periods}] {progress:5.1f}% | Special Hit Rate: {curr_sr:5.2f}% | Win Rate: {(win_count/(idx+1))*100:5.2f}%")

    print("\n" + "-" * 100)
    print(f"🏆 FINAL SUMMARY ({total_periods} PERIODS)")
    print("-" * 100)
    print(f"Overall Prize Hit Rate: {(win_count / total_periods)*100:.2f}%")
    print(f"Special Number Hits: {special_hits} draws ({(special_hits / total_periods)*100:.2f}%)")
    print("\nMatch Distribution (Best per Draw):")
    for m in range(7):
        count = match_counts[m]
        print(f"  Match {m}: {count:4} draws ({count/total_periods*100:5.2f}%)")
    print("=" * 100)

if __name__ == "__main__":
    main()
