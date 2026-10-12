#!/usr/bin/env python3
"""
🧪 ASM (Anchor-Secondary Mixed) Optimizer
Goal: Mix high-confidence anchors into all bets while maintaining diversity.
"""
import sys
import os
import io
from collections import Counter
import contextlib

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer

class ASMOptimizer(BigLotto3BetOptimizer):
    def predict_3bets_asm(self, history, rules, use_kill=True):
        res = self.predict_3bets_diversified(history, rules, use_kill=use_kill)
        top_18 = res['candidates']
        
        # ASM Mapping:
        # Bet 1: [0, 1, 2, 3, 4, 5] (The Top Elite)
        # Bet 2: [0, 1, 6, 7, 8, 9] (Top Anchors + Mid-range)
        # Bet 3: [2, 3, 4, 10, 11, 12] (Secondary Anchors + Long-tail)
        
        idx_map = [
            [0, 1, 2, 3, 4, 5],
            [0, 1, 6, 7, 8, 9],
            [2, 3, 4, 10, 11, 12]
        ]
        
        bets = []
        for indices in idx_map:
            bets.append(sorted([top_18[i] for i in indices]))
            
        return {
            'bets': [{'numbers': b} for b in bets],
            'candidates': top_18
        }

def test_asm(test_periods=150):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = ASMOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing ASM (Anchor-Secondary Mixed) over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_asm(history, rules)
            
            best_match = 0
            for b_data in res['bets']:
                m = len(set(b_data['numbers']) & actual)
                if m > best_match: best_match = m
            
            if best_match >= 3: match_3_plus += 1
            match_dist[best_match] += 1
            total += 1
            
            if (i+1) % 20 == 0:
                print(f"進度: {i+1}/{test_periods} | M-3+: {match_3_plus/total*100:.2f}%")
        except: continue
        
    print("\n" + "=" * 60)
    print(f"📊 ASM Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_asm(150)
