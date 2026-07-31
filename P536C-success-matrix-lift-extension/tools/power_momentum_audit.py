#!/usr/bin/env python3
"""
Power Lotto Momentum Stacking Auditor
=====================================
Logic:
1. High-frequency 'Hot Hand' detection (Window=10-20).
2. Momentum = Current Frequency / Historical Average.
3. Goal: Capture trending numbers that are in an active cycle.
"""
import os
import sys
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

def momentum_predict(history, n_bets=2, short_window=15, long_window=500):
    max_num = 38
    h_short = history[-short_window:]
    h_long = history[-long_window:]
    
    # 1. Calculate Expected Frequency (Long term)
    long_freq = {}
    for d in h_long:
        for n in d['numbers']:
            long_freq[n] = long_freq.get(n, 0) + 1
    
    # 2. Calculate Recent Frequency (Short term)
    short_freq = {}
    for d in h_short:
        for n in d['numbers']:
            short_freq[n] = short_freq.get(n, 0) + 1
            
    # 3. Momentum Score: How much is recent freq exceeding long-term expected?
    scores = np.zeros(max_num + 1)
    avg_expected = (short_window * 6.0) / 38.0
    
    for n in range(1, max_num + 1):
        actual = short_freq.get(n, 0)
        # We look for 'Momentum Burst': recent freq > global avg
        scores[n] = actual / (avg_expected + 0.1)
        
    all_indices = np.arange(1, max_num + 1)
    sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
    
    bets = []
    for i in range(n_bets):
        start = i * 6
        end = (i + 1) * 6
        bets.append(sorted(sorted_indices[start:end].tolist()))
        
    return bets

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=1000)
    args = parser.parse_args()
    
    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type='POWER_LOTTO')
    
    def audit_bridge(history, num_bets=2):
        return momentum_predict(history, n_bets=num_bets)
        
    auditor.audit(audit_bridge, n=args.n, num_bets=2)
