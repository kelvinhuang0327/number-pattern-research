#!/usr/bin/env python3
"""
Backtest script for Optimized 6-Bet "Hexa-Core" Strategy
"""
import sys
import os
import logging
from collections import Counter
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from tools.predict_biglotto_6bets_optimized import BigLotto6BetOptimizer

logging.basicConfig(level=logging.ERROR) # Mute info logs during backtest loop

def run_backtest():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO'))) # Old to New
    rules = get_lottery_rules('BIG_LOTTO')
    
    optimizer = BigLotto6BetOptimizer()
    
    test_periods = 100 # Test last 100 draws
    start_idx = len(all_draws) - test_periods
    
    wins = Counter()
    total_cost = 0
    total_prize = 0
    
    print(f"🚀 開始 6-Bet Hexa-Core 回測 (近 {test_periods} 期)...")
    print("-" * 60)
    
    for i in range(test_periods):
        curr_idx = start_idx + i
        target_draw = all_draws[curr_idx]
        history = all_draws[:curr_idx]
        actual = set(target_draw['numbers'])
        
        try:
            # Generate bets
            # Redirect stdout to suppress print noise
            # sys.stdout = open(os.devnull, 'w')
            bets = optimizer.generate_6bets(history, rules)
            # sys.stdout = sys.__stdout__
        except Exception as e:
            print(f"⚠️ Error at draw {target_draw['draw']}: {e}")
            continue
            
        period_best = 0
        hit_details = []
        
        for bet in bets:
            match = len(set(bet['numbers']) & actual)
            period_best = max(period_best, match)
            if match >= 3:
                hit_details.append(f"{bet['strategy']}({match})")
                
        wins[period_best] += 1
        total_cost += len(bets) * 50
        
        # Simple Prize Calculation (Approx)
        if 3 in wins: total_prize += 400 * wins[3] # 普獎
        # ... logic for detailed prize calculation omitted for brevity, focusing on Match Rates
        
        if (i+1) % 20 == 0:
            print(f"Draw {i+1}: Best Match {period_best}")
            
    print("-" * 60)
    print(f"🏆 6-Bet Hexa-Core 最終結果 (100期):")
    total_match3_plus = sum(wins[k] for k in wins if k >= 3)
    print(f"  Match 3+ 期數: {total_match3_plus} / {test_periods} ({total_match3_plus/test_periods*100:.1f}%)")
    print("  詳細分佈 (每期最佳):")
    for k in sorted(wins.keys(), reverse=True):
        print(f"    Match {k}: {wins[k]}")

if __name__ == '__main__':
    run_backtest()
