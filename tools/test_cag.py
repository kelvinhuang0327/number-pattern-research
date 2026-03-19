#!/usr/bin/env python3
"""
🧪 CAG (Co-occurrence Anchor Grouping) Optimizer
Goal: Group the Top 18 around the Top 3 Anchors using Co-occurrence.
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
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer

class CAGOptimizer(BigLotto3BetOptimizer):
    def predict_3bets_cag(self, history, rules, use_kill=True):
        # 1. Get Pool (Top 18)
        # Using the same proven weighted logic
        res = self.predict_3bets_diversified(history, rules, use_kill=use_kill)
        top_18 = res['candidates']
        
        # 2. Build Matrix
        matrix = defaultdict(Counter)
        for d in history[-200:]:
            nums = d['numbers']
            for a, b in combinations(sorted(nums), 2):
                matrix[a][b] += 1
                matrix[b][a] += 1
        
        # 3. Create 3 bets centered on the Top 3 Anchors
        anchors = top_18[:3]
        pool = set(top_18)
        bets = []
        
        for a in anchors:
            bet = [a]
            # Find 5 companions from the entire pool (excluding self)
            companions = []
            for candidate in pool:
                if candidate == a: continue
                co_score = matrix[a][candidate]
                companions.append((candidate, co_score))
            
            # Sort by co-occurrence score, then by individual rank in top_18
            # (Higher rank in top_18 is better for ties)
            companions.sort(key=lambda x: (x[1], -top_18.index(x[0])), reverse=True)
            
            for i in range(5):
                bet.append(companions[i][0])
            bets.append(sorted(bet))
            
        return {
            'bets': [{'numbers': b} for b in bets],
            'candidates': top_18
        }

def test_cag(test_periods=150):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = CAGOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing CAG (Co-occurrence Anchor Grouping) over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_cag(history, rules)
            
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
    print(f"📊 CAG Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_cag(150)
