#!/usr/bin/env python3
"""
Power Lotto Companion Analysis (球號關聯分析)
目標：找出經常「成對出現」的號碼，用於修正選號組合。
"""
import os
import sys
from collections import Counter
import itertools

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

class CompanionAnalyzer:
    def __init__(self):
        self.db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.draws = self.db.get_all_draws('POWER_LOTTO')
        
    def find_top_pairs(self, window=200):
        print(f"\n👯 Companion Analysis (Top Pairs, Window={window})")
        print("-" * 50)
        
        recent = self.draws[-window:]
        pairs = Counter()
        for d in recent:
            nums = sorted(d['numbers'])
            for pair in itertools.combinations(nums, 2):
                pairs[pair] += 1
                
        # Get Top 10 pairs
        top_10 = pairs.most_common(10)
        print(f"{'Pair':<12} | {'Count':<6} | {'Status'}")
        for (a, b), count in top_10:
            print(f"({a:02d}, {b:02d})      | {count:<6} | 🔥 High Correlation")
            
        return top_10

if __name__ == "__main__":
    ca = CompanionAnalyzer()
    ca.find_top_pairs(window=200)
    ca.find_top_pairs(window=50)
