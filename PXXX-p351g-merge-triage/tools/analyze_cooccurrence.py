#!/usr/bin/env python3
"""
Big Lotto Co-occurrence Analyzer
================================
Identifies 'Impossible Pairs' (Zero occurrences in N=1000 history).
Used to prune high-entropy candidates from the Cluster Pivot model.
"""
import os
import sys
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

def analyze(n=1000):
    lb = StrategyLeaderboard(lottery_type='BIG_LOTTO')
    history = lb.draws[-n:]
    max_num = 49
    
    # Adjacency matrix for co-occurrence
    matrix = np.zeros((max_num + 1, max_num + 1), dtype=int)
    
    for d in history:
        nums = d['numbers']
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                n1, n2 = nums[i], nums[j]
                matrix[n1][n2] += 1
                matrix[n2][n1] += 1
                
    # Identify pairs with 0 or near-zero occurrences
    impossible_pairs = []
    for i in range(1, max_num + 1):
        for j in range(i + 1, max_num + 1):
            if matrix[i][j] == 0:
                impossible_pairs.append((i, j))
                
    print(f"📊 Big Lotto Co-occurrence Analysis (N={n})")
    print(f"   - Found {len(impossible_pairs)} 'Impossible Pairs' (Zero shared draws).")
    
    # Save to data/cooccurrence_biglotto.json
    output = {
        "n": n,
        "impossible_pairs": impossible_pairs,
        "description": "Pairs that never appeared together in the last 1000 draws."
    }
    
    data_dir = os.path.join(project_root, 'tools', 'data')
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, 'cooccurrence_biglotto.json'), 'w') as f:
        import json
        json.dump(output, f)

if __name__ == "__main__":
    analyze()
