#!/usr/bin/env python3
"""
Power Lotto Zonal Dispersion Optimizer
====================================
Logic:
1. Divide 1-38 into 8 zones (1-5, 6-10, ..., 36-38).
2. Analyze historical distribution.
3. Prune candidates based on coverage.
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
    if n > 35: return 7
    return (n - 1) // 5

def analyze_zones(history, n=500):
    coverage_counts = Counter()
    for d in history[-n:]:
        zones = set(get_zone(n) for n in d['numbers'])
        coverage_counts[len(zones)] += 1
    typical_zones = set(c[0] for c in coverage_counts.most_common(2))
    return typical_zones

def scientific_power_predict(history, n_bets=2, window=150):
    # Strategy: Combine Cold/Lag with Zonal Pruning
    # 1. Base Strategy (Lag Reversion / Cold)
    max_num = 38
    freq = {}
    for d in history[-window:]:
        for n in d['numbers']:
            freq[n] = freq.get(n, 0) + 1
    sorted_nums = sorted(range(1, 38), key=lambda x: freq.get(x, 0))
    
    # Generate broad candidates
    candidates = []
    # Mix top cold and medium active numbers
    base_pool = sorted_nums[:18]
    import random
    random.seed(42)
    
    typical_zones = analyze_zones(history, n=200)
    
    bets = []
    for _ in range(50): # Try 50 random combos from pool
        sample = sorted(random.sample(base_pool, 6))
        zones = set(get_zone(n) for n in sample)
        if len(zones) in typical_zones:
            if sample not in bets:
                bets.append(sample)
                if len(bets) >= n_bets:
                    break
                    
    if not bets:
        return [sorted_nums[:6], sorted_nums[6:12]]
    return bets

if __name__ == "__main__":
    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type='POWER_LOTTO')
    
    def audit_bridge(history, num_bets=2):
        return scientific_power_predict(history, n_bets=num_bets)
        
    auditor.audit(audit_bridge, n=1000, num_bets=2)
