#!/usr/bin/env python3
"""
🧪 4-Bet DCB Backtest (Full Pool Coverage)
"""
import sys
import os
import io
from collections import Counter, defaultdict
from itertools import combinations
import contextlib

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from tools.test_dcb import DCBOptimizer

class DCB4BetOptimizer(DCBOptimizer):
    def predict_4bets_dcb(self, history, rules, use_kill=True):
        res = self.predict_3bets_dcb(history, rules, use_kill=use_kill)
        top_18 = res['candidates']
        
        # New 4-bet slicing: 0-5, 4-9, 8-13, 12-17
        SLICES = [(0, 6), (4, 10), (8, 14), (12, 18)]
        bets = [sorted(top_18[s:e]) for s, e in SLICES]
        
        return {
            'bets': [{'numbers': b} for b in bets],
            'candidates': top_18
        }

def test_4bet_dcb(test_periods=200):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = DCB4BetOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing 4-Bet DCB (Full Pool Coverage) over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            # We skip redirection to avoid "closed file" issues
            res = optimizer.predict_4bets_dcb(history, rules)
            
            best_match = 0
            for b_data in res['bets']:
                m = len(set(b_data['numbers']) & actual)
                if m > best_match: best_match = m
            
            if best_match >= 3: 
                match_3_plus += 1
            match_dist[best_match] += 1
            total += 1
            
            if (i+1) % 20 == 0:
                print(f"進度: {i+1}/{test_periods} | M-3+: {match_3_plus/total*100:.2f}%")
        except Exception as e:
            # print(f"Error: {e}")
            continue
        
    print("\n" + "=" * 60)
    print(f"📊 4-Bet DCB Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_4bet_dcb(200)
