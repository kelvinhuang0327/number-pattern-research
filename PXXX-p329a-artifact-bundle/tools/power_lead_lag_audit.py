#!/usr/bin/env python3
"""
Power Lotto Temporal Lead-Lag Auditor
=====================================
Logic:
1. Matrix(X, Y) = Frequency that Number Y appears in Draw T given X appeared in T-1.
2. Predict Draw T based on the top associations from Draw T-1.
3. This captures 'Number Sequencing' patterns.
"""
import os
import sys
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

def lead_lag_predict(history, n_bets=2, window=500):
    max_num = 38
    h_slice = history[-window:]
    
    # 1. Build Transition Matrix
    matrix = np.zeros((max_num + 1, max_num + 1))
    for i in range(len(h_slice) - 1):
        prev_nums = h_slice[i]['numbers']
        curr_nums = h_slice[i+1]['numbers']
        for p in prev_nums:
            for c in curr_nums:
                matrix[p][c] += 1
                
    # 2. Use Last Draw to predict Next
    last_nums = history[-1]['numbers']
    next_scores = np.zeros(max_num + 1)
    for p in last_nums:
        next_scores += matrix[p]
        
    all_indices = np.arange(1, max_num + 1)
    sorted_indices = all_indices[np.argsort(next_scores[1:])[::-1]]
    
    bets = []
    for i in range(n_bets):
        # Bet 1: Top 6 association leaders
        # Bet 2: Next 6
        start = i * 6
        end = (i + 1) * 6
        bets.append(sorted(sorted_indices[start:end].tolist()))
        
    return bets

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=500)
    args = parser.parse_args()
    
    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type='POWER_LOTTO')
    
    def audit_bridge(history, num_bets=2):
        return lead_lag_predict(history, n_bets=num_bets)
        
    auditor.audit(audit_bridge, n=args.n, num_bets=2)
