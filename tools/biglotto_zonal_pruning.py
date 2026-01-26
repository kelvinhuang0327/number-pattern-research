#!/usr/bin/env python3
"""
Big Lotto Zonal Dispersion Optimizer
====================================
Logic:
1. Divide 1-49 into 7 zones (1-7, 8-14, ..., 43-49).
2. Analyze historical distribution: How many zones are typically covered?
3. Use this as a final pruning filter for Cluster Pivot candidates.
"""
import os
import sys
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

def get_zone(n):
    return (n - 1) // 7

def analyze_zones(history, n=500):
    h_slice = history[-n:]
    coverage_counts = Counter()
    for d in h_slice:
        zones = set(get_zone(n) for n in d['numbers'])
        coverage_counts[len(zones)] += 1
        
    print(f"📊 Zonal Coverage Analysis (N={n})")
    for count, freq in coverage_counts.most_common():
        print(f"   - {count} Zones covered: {freq/n*100:5.2f}%")
        
    # Typical coverage is the key signal
    typical_coverage = coverage_counts.most_common(2) 
    return set(c[0] for c in typical_coverage)

def zonal_pruned_predict(history, n_bets=4, window=150):
    lb = StrategyLeaderboard(lottery_type='BIG_LOTTO')
    
    # Get base candidates from Cluster Pivot (over-generate to allow pruning)
    base_bets = lb.strat_cluster_pivot(history, n_bets=n_bets*3, window=window)
    
    typical_zones = analyze_zones(history, n=200)
    
    pruned_bets = []
    for bet in base_bets:
        zones = set(get_zone(n) for n in bet)
        if len(zones) in typical_zones:
            pruned_bets.append(bet)
            if len(pruned_bets) >= n_bets:
                break
                
    # Fallback if pruning is too aggressive
    if not pruned_bets:
        return base_bets[:n_bets]
        
    return pruned_bets

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='BIG_LOTTO')
    parser.add_argument('--n', type=int, default=500)
    parser.add_argument('--bets', type=int, default=4)
    args = parser.parse_args()
    
    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type=args.lottery)
    
    def audit_bridge(history, num_bets=4):
        return zonal_pruned_predict(history, n_bets=args.bets)
        
    auditor.audit(audit_bridge, n=args.n, num_bets=args.bets)
