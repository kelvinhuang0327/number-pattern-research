#!/usr/bin/env python3
"""
Power Lotto Lag Reversion Model
===============================
Logic: 
1. Calculate the 'Median Interval' for each number over 500 draws.
2. Calculate the 'Current Lag' (draws since last appearance).
3. Score = Current Lag / Median Interval.
4. Higher score = Number is 'Overdue' based on its own unique rhythm.
"""
import os
import sys
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

def lag_reversion_predict(history, n_bets=2, window=500):
    max_num = 38
    scores = np.zeros(max_num + 1)
    
    # 1. Calculate historical intervals for each number
    last_seen = {i: -1 for i in range(1, max_num + 1)}
    intervals = {i: [] for i in range(1, max_num + 1)}
    
    # Use window for interval calculation
    h_slice = history[-window:]
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if last_seen[n] != -1:
                intervals[n].append(idx - last_seen[n])
            last_seen[n] = idx
            
    # 2. Calculate Median Interval and Current Lag
    current_idx = len(h_slice)
    for n in range(1, max_num + 1):
        if not intervals[n]:
            # fallback for rare numbers: use global mean (38/6 = 6.33)
            median_int = 38 / 6.0
        else:
            median_int = np.median(intervals[n])
            
        current_lag = current_idx - last_seen[n]
        
        # Scoring: Reversion probability increases as lag exceeds median
        scores[n] = current_lag / (median_int + 0.1)
        
    all_indices = np.arange(1, max_num + 1)
    sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
    
    bets = []
    for i in range(n_bets):
        # Pick top overdue numbers, but ensure we don't just pick the oldest (mix with diversity)
        # We'll use a simple block selection for this baseline
        start = i * 6
        end = (i + 1) * 6
        bets.append(sorted(sorted_indices[start:end].tolist()))
        
    return bets

if __name__ == "__main__":
    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type='POWER_LOTTO')
    
    def audit_bridge(history, num_bets=2):
        return lag_reversion_predict(history, n_bets=num_bets, window=500)
        
    auditor.audit(audit_bridge, n=500, num_bets=2)
