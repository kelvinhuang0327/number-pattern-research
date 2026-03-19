#!/usr/bin/env python3
"""
Backtest script for Optimized 7-Bet "Hepta-Slice" Strategy
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
from tools.predict_biglotto_7bets_optimized import BigLotto7BetOptimizer

logging.basicConfig(level=logging.ERROR) 

def run_backtest():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO'))) 
    rules = get_lottery_rules('BIG_LOTTO')
    
    optimizer = BigLotto7BetOptimizer()
    
    test_periods = 100 
    start_idx = len(all_draws) - test_periods
    
    wins = Counter()
    
    print(f"🚀 開始 7-Bet Hepta-Slice 回測 (近 {test_periods} 期)...")
    print("-" * 60)
    
    for i in range(test_periods):
        curr_idx = start_idx + i
        target_draw = all_draws[curr_idx]
        history = all_draws[:curr_idx]
        actual = set(target_draw['numbers'])
        
        try:
            bets = optimizer.generate_7bets(history, rules)
        except Exception as e:
            continue
            
        period_best = 0
        for bet in bets:
            match = len(set(bet['numbers']) & actual)
            period_best = max(period_best, match)
                
        wins[period_best] += 1
        
        if (i+1) % 20 == 0:
            print(f"Draw {i+1}: Best Match {period_best}")
            
    print("-" * 60)
    print(f"🏆 7-Bet Hepta-Slice 最終結果 (100期):")
    total_match3_plus = sum(wins[k] for k in wins if k >= 3)
    print(f"  Match 3+ 期數: {total_match3_plus} / {test_periods} ({total_match3_plus/test_periods*100:.1f}%)")
    print("  詳細分佈 (每期最佳):")
    for k in sorted(wins.keys(), reverse=True):
        print(f"    Match {k}: {wins[k]}")

if __name__ == '__main__':
    run_backtest()
