#!/usr/bin/env python3
"""
🧪 Standard Deterministic Benchmark for Big Lotto
Goal: Provide a reproducible test method with fixed seeds.
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
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    # Note: If there are torch models, we'd set torch seeds here too.

def run_benchmark(strategy_name, predict_func, history_full, rules, periods=150):
    set_seed(42) # Reset seed for every strategy to ensure fair comparison
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    # Use latest N periods
    for i in range(periods):
        target_idx = len(history_full) - periods + i
        if target_idx <= 0: continue
        
        target_draw = history_full[target_idx]
        history = history_full[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = predict_func(history, rules)
            
            best_match = 0
            for b_data in res['bets']:
                m = len(set(b_data['numbers']) & actual)
                if m > best_match: best_match = m
            
            if best_match >= 3: 
                match_3_plus += 1
            match_dist[best_match] += 1
            total += 1
        except:
            continue
            
    return {
        'rate': match_3_plus / total * 100 if total > 0 else 0,
        'count': match_3_plus,
        'total': total,
        'dist': match_dist
    }

from tools.test_dcb import DCBOptimizer
from tools.test_tme import TMEOptimizer

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    # Optimizers
    opt_smart = BigLotto3BetOptimizer()
    opt_dcb = DCBOptimizer()
    opt_tme = TMEOptimizer()
    
    print("=" * 60)
    print("🔬 Big Lotto Deterministic Benchmark (Seed: 42)")
    print("=" * 60)
    
    # 1. 150 Periods (Baseline)
    print(f"\n📊 testing 150 Periods:")
    print("-" * 40)
    
    res_smart = run_benchmark("Smart 3-Bet", opt_smart.predict_3bets_diversified, all_draws, rules, 150)
    print(f"Smart 3-Bet: {res_smart['rate']:.2f}% ({res_smart['count']}/150)")
    
    res_tme = run_benchmark("TME 3-Bet", opt_tme.predict_3bets_tme, all_draws, rules, 150)
    print(f"TME 3-Bet:   {res_tme['rate']:.2f}% ({res_tme['count']}/150)")
    
    res_dcb = run_benchmark("DCB 3-Bet", opt_dcb.predict_3bets_dcb, all_draws, rules, 150)
    print(f"DCB 3-Bet:   {res_dcb['rate']:.2f}% ({res_dcb['count']}/150)")

    # 2. 200 Periods
    print(f"\n📊 testing 200 Periods:")
    print("-" * 40)
    
    res_smart2 = run_benchmark("Smart 3-Bet", opt_smart.predict_3bets_diversified, all_draws, rules, 200)
    print(f"Smart 3-Bet: {res_smart2['rate']:.2f}% ({res_smart2['count']}/200)")
    
    res_tme2 = run_benchmark("TME 3-Bet", opt_tme.predict_3bets_tme, all_draws, rules, 200)
    print(f"TME 3-Bet:   {res_tme2['rate']:.2f}% ({res_tme2['count']}/200)")
    
    res_dcb2 = run_benchmark("DCB 3-Bet", opt_dcb.predict_3bets_dcb, all_draws, rules, 200)
    print(f"DCB 3-Bet:   {res_dcb2['rate']:.2f}% ({res_dcb2['count']}/200)")
    
    print("\n" + "=" * 60)
    print("💡 Method for Claude:")
    print("1. Set random.seed(42) and np.random.seed(42)")
    print("2. Run 150/200 periods backtest on Big Lotto")
    print("3. Compare results.")
    print("=" * 60)

if __name__ == '__main__':
    main()
