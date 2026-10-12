#!/usr/bin/env python3
"""
Power Lotto Association Rule (Apriori) Auditor
==============================================
Logic:
1. Find pairs of numbers that frequently appear together in the last 200 draws.
2. Rank pairs by 'Lift' or 'Support'.
3. Select numbers that form the strongest 'Cliques'.
"""
import os
import sys
import numpy as np
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

def apriori_predict(history, n_bets=2, window=200):
    max_num = 38
    h_slice = history[-window:]
    
    # Calculate support for pairs
    pair_counts = {}
    for d in h_slice:
        nums = sorted(d['numbers'])
        for pair in combinations(nums, 2):
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
            
    # Sort pairs by frequency
    sorted_pairs = sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Select numbers based on top pairs
    all_num_scores = np.zeros(max_num + 1)
    for pair, count in sorted_pairs[:50]: # Top 50 associations
        all_num_scores[pair[0]] += count
        all_num_scores[pair[1]] += count
        
    all_indices = np.arange(1, max_num + 1)
    sorted_indices = all_indices[np.argsort(all_num_scores[1:])[::-1]]
    
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
    parser.add_argument('--lottery', default='POWER_LOTTO')
    parser.add_argument('--n', type=int, default=500)
    args = parser.parse_args()
    
    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type=args.lottery)
    
    def audit_bridge(history, num_bets=2):
        return apriori_predict(history, n_bets=num_bets, window=200)
        
    auditor.audit(audit_bridge, n=args.n, num_bets=2)
