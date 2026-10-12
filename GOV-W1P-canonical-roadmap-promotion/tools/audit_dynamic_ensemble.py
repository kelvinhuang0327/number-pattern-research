#!/usr/bin/env python3
"""
Power Lotto Dynamic Ensemble Auditor
====================================
Logic:
1. For each draw T, scan windows (20, 50, 100, 150, 200) to see which would have worked best on Draws [T-151...T-1].
2. Use that 'Best' window to predict Draw T.
"""
import os
import sys
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

def dynamic_ensemble_predict(history, num_bets=2):
    lb = StrategyLeaderboard(lottery_type='POWER_LOTTO')
    
    # 1. Dynamic Window Tuning (Scanning recent history)
    windows = [20, 50, 100, 150, 200]
    best_window = 100
    max_rate = -1
    
    # Crucially, the tuner should only see history[:len(history)]
    # which is already isolation-safe in the Auditor bridge.
    for w in windows:
        # Mini backtest on the PAST of this history slice
        # We check the performance on the last 50 draws of the current slice
        if len(history) < w + 50: continue
        
        hits = 0
        test_range = 50
        for i in range(test_range):
            t_idx = len(history) - test_range + i
            t_target = history[t_idx]['numbers']
            t_hist = history[:t_idx]
            
            # Predict using window w
            t_recent = t_hist[-w:]
            t_all_n = [n for d in t_recent for n in d['numbers']]
            t_f = Counter(t_all_n)
            t_sorted = sorted(range(1, 39), key=lambda x: t_f.get(x, 0))
            
            # Check if top 6 from window w hit
            if sum(1 for n in t_sorted[:12] if n in t_target) >= 3:
                hits += 1
        
        rate = hits / test_range
        if rate > max_rate:
            max_rate = rate
            best_window = w
            
    # 2. Final Prediction using the 'Discovered' best window
    recent = history[-best_window:]
    all_nums = [n for d in recent for n in d['numbers']]
    f = Counter(all_nums)
    sorted_cold = sorted(range(1, 39), key=lambda x: f.get(x, 0))
    
    return [sorted(sorted_cold[:6]), sorted(sorted_cold[6:12])]

if __name__ == "__main__":
    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type='POWER_LOTTO')
    
    # This is a meta-prediction (it tunes itself during each step)
    auditor.audit(dynamic_ensemble_predict, n=500, num_bets=2)
