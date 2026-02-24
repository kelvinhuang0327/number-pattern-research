#!/usr/bin/env python3
"""
🧪 Dynamic Correlation Boosting (DCB)
Goal: Boost co-occurring numbers to improve "Density" of hits in Top candidates.
"""
import sys
import os
import io
from collections import Counter, defaultdict
from itertools import combinations

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class DCBOptimizer(BigLotto3BetOptimizer):
    def predict_3bets_dcb(self, history, rules, use_kill=True):
        # 1. Base Weighted Scoring (Boosted Statistical)
        methods = [
            ('deviation', 'deviation_predict', 1.5),
            ('markov', 'markov_predict', 1.5),
            ('statistical', 'statistical_predict', 2.0),
            ('hot_cold_mix', 'hot_cold_mix_predict', 1.0)
        ]
        
        candidates = Counter()
        for _, func_name, weight in methods:
            try:
                res = getattr(self.engine, func_name)(history, rules)
                for num in res['numbers']:
                    candidates[num] += weight
            except: continue
            
        # 2. P1 Kill
        kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
        for n in kill_nums:
            candidates[n] = -9999
            
        # 3. Correlation Boosting
        matrix = defaultdict(Counter)
        for d in history[-200:]:
            nums = d['numbers']
            for a, b in combinations(sorted(nums), 2):
                matrix[a][b] += 1
                matrix[b][a] += 1
                
        # Boost numbers that co-occur with Top 5
        top_5 = [n for n, s in candidates.most_common(5)]
        boosted_candidates = Counter(candidates)
        for t5 in top_5:
            base_score = candidates[t5]
            for neighbor, count in matrix[t5].items():
                if neighbor in boosted_candidates and boosted_candidates[neighbor] > 0:
                    # Boost by 10% of anchor's score * co-occurrence frequency (normalized)
                    boosted_candidates[neighbor] += (base_score * 0.1) * (count / 10)

        # 4. Top 18 Selection
        top_18 = [num for num, _ in boosted_candidates.most_common(18)]
        
        # 5. Fixed Slicing (Restored because it's better than zero-overlap)
        bets = self._generate_bets(top_18)
        
        return {
            'bets': [{'numbers': b} for b in bets],
            'candidates': top_18
        }

def test_dcb(test_periods=150):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = DCBOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing DCB (Dynamic Correlation Boosting) over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_dcb(history, rules)
            
            best_match = 0
            for b in res['bets']:
                m = len(set(b['numbers']) & actual)
                if m > best_match: best_match = m
            
            if best_match >= 3: match_3_plus += 1
            match_dist[best_match] += 1
            total += 1
        except: continue
        
    print("\n" + "=" * 60)
    print(f"📊 DCB Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

import contextlib
if __name__ == '__main__':
    test_dcb(200)
