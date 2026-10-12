#!/usr/bin/env python3
"""
🧪 CES (Constrained Elite Sampling) Optimizer
Goal: Filter the entire Top 20 pool combinations through strict lottery rules.
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

class CESOptimizer(BigLotto3BetOptimizer):
    def _is_valid(self, combo):
        # 1. Sum range (110 - 190)
        s = sum(combo)
        if not (110 <= s <= 190): return False
        
        # 2. AC Value (>= 6)
        diffs = set()
        for a, b in combinations(sorted(combo), 2):
            diffs.add(b - a)
        ac = len(diffs) - 5
        if ac < 6: return False
        
        # 3. Odd/Even (2:4, 3:3, 4:2)
        odd = sum(1 for n in combo if n % 2 == 1)
        if odd < 2 or odd > 4: return False
        
        # 4. Range (Spread > 25)
        if (max(combo) - min(combo)) < 25: return False
        
        return True

    def predict_3bets_ces(self, history, rules, use_kill=True):
        # 1. Create Pool (Top 20)
        # Using a balanced multi-model scoring
        candidates = Counter()
        methods = [
            ('deviation', 'deviation_predict', 1.5),
            ('markov', 'markov_predict', 1.5),
            ('statistical', 'statistical_predict', 2.0),
            ('hot_cold_mix', 'hot_cold_mix_predict', 1.0)
        ]
        for _, func_name, weight in methods:
            try:
                res = getattr(self.engine, func_name)(history, rules)
                for num in res['numbers']:
                    candidates[num] += weight
            except: continue
            
        kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
        for n in kill_nums: candidates[n] = -9999
        
        top_20 = [num for num, _ in candidates.most_common(20)]
        
        # 2. Generate and filter combinations
        valid_combos = []
        # C(20, 6) = 38,760 - manageable in Python
        for combo in combinations(top_20, 6):
            if self._is_valid(combo):
                # Calculate combo score
                score = sum(candidates[n] for n in combo)
                valid_combos.append((combo, score))
        
        # 3. Sort by score
        valid_combos.sort(key=lambda x: x[1], reverse=True)
        
        # 4. Pick best 3 with minimal overlap (safety constraint)
        selected = []
        for combo, score in valid_combos:
            if not selected:
                selected.append(combo)
            else:
                # Max overlap check
                if all(len(set(combo) & set(s)) <= 2 for s in selected):
                    selected.append(combo)
            
            if len(selected) >= 3: break
            
        # Fallback if valid combos < 3
        while len(selected) < 3 and valid_combos:
             selected.append(valid_combos[len(selected)][0])
             
        return {
            'bets': [{'numbers': sorted(list(s))} for s in selected],
            'candidates': top_20
        }

def test_ces(test_periods=100):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = CESOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing CES (Constrained Elite Sampling) over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_ces(history, rules)
            
            best_match = 0
            for b_data in res['bets']:
                m = len(set(b_data['numbers']) & actual)
                if m > best_match: best_match = m
            
            if best_match >= 3: match_3_plus += 1
            match_dist[best_match] += 1
            total += 1
            
            if (i+1) % 10 == 0:
                print(f"進度: {i+1}/{test_periods} | M-3+: {match_3_plus/total*100:.2f}%")
        except: continue
        
    print("\n" + "=" * 60)
    print(f"📊 CES Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_ces(100)
