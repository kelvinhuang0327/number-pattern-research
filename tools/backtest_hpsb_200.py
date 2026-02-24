#!/usr/bin/env python3
"""
🧪 HPSB Verification Benchmark (Big Lotto)
Compare HPSB Optimizer against Standard Single Bet Benchmarks.
"""
import sys
import os
import io
import random
import numpy as np
from collections import Counter
import contextlib

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.hpsb_optimizer import HPSBOptimizer

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)

def run_1bet_benchmark(name, predict_func, history_full, rules, periods=200):
    set_seed(42)
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    print(f"DEBUG: Total draws in DB: {len(history_full)}")
    
    for i in range(periods):
        target_idx = len(history_full) - periods + i
        if target_idx <= 0: continue
        
        target_draw = history_full[target_idx]
        history = history_full[:target_idx]
        actual = set(target_draw['numbers'])
        
        # For 1-bet, we wrap the result if it's not already in 'bets' format
        with contextlib.redirect_stdout(io.StringIO()):
            res = predict_func(history, rules)
        
        # Normalize response to list of numbers
        if 'bets' in res:
            bet_nums = res['bets'][0]['numbers']
        else:
            bet_nums = res['numbers']
            
        m = len(set(bet_nums) & actual)
        if m >= 3: 
            match_3_plus += 1
        match_dist[m] += 1
        total += 1
            
    rate = match_3_plus / total * 100 if total > 0 else 0
    return rate, match_3_plus, total, match_dist

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    engine = UnifiedPredictionEngine()
    hpsb = HPSBOptimizer(engine)
    
    print("=" * 65)
    print("🔬 HPSB Optimizer Verification (200 Periods, Single Bet)")
    print("=" * 65)
    
    # 1. Baseline: Statistical (Top 6 by Freq)
    rate_stat, count_stat, total_stat, dist_stat = run_1bet_benchmark(
        "Standard Statistical", engine.statistical_predict, all_draws, rules, 200
    )
    print(f"Standard (Statistical): {rate_stat:.2f}% ({count_stat}/{total_stat})")

    # 2. Baseline: Repeat Booster alone
    rate_rb, count_rb, total_rb, dist_rb = run_1bet_benchmark(
        "Repeat Booster Only", engine.repeat_booster_predict, all_draws, rules, 200
    )
    print(f"Repeat Booster Only:   {rate_rb:.2f}% ({count_rb}/{total_rb})")

    # 3. Target: HPSB
    rate_hpsb, count_hpsb, total_hpsb, dist_hpsb = run_1bet_benchmark(
        "HPSB Optimizer", hpsb.predict_hpsb, all_draws, rules, 200
    )
    print(f"HPSB (Optimized):      {rate_hpsb:.2f}% ({count_hpsb}/{total_hpsb}) 🔥")
    
    print("-" * 65)
    print(f"Match Distribution (HPSB):")
    for m in range(7):
        print(f"  Match {m}: {dist_hpsb[m]:2d} draws")
    print("=" * 65)

if __name__ == '__main__':
    main()
