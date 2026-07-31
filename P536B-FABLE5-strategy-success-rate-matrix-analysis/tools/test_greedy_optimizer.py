#!/usr/bin/env python3
"""
🧪 Greedy-Constraint Optimizer (Experimental)
Goal: Scan C(18, 6) combinations in the Top 18 pool and pick the best 3.
"""
import sys
import os
import io
from collections import Counter, defaultdict
from itertools import combinations
import numpy as np

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class GreedyConstraintOptimizer(BigLotto3BetOptimizer):
    def _calculate_combo_score(self, numbers, num_scores, matrix, rules):
        # 1. Base Score (Sum of individual scores)
        score = sum(num_scores.get(n, 0) for n in numbers)
        
        # 2. Co-occurrence Score
        pair_score = 0
        for a, b in combinations(sorted(numbers), 2):
            pair_score += matrix[a][b]
        score += pair_score * 0.1 # Weight co-occurrence
        
        # 3. Global Constraints (AC, Sum, Odd/Even)
        min_num, max_num = rules.get('minNumber', 1), rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        # Sum constraint
        s = sum(numbers)
        ideal_sum = (min_num + max_num) * pick_count / 2
        sum_penalty = abs(s - ideal_sum) / 50
        score -= sum_penalty
        
        # AC constraint
        diffs = set()
        sorted_nums = sorted(numbers)
        for i in range(len(sorted_nums)):
            for j in range(i + 1, len(sorted_nums)):
                diffs.add(sorted_nums[j] - sorted_nums[i])
        ac = len(diffs) - (pick_count - 1)
        if ac < 6: score -= 5 # AC too low is bad
        
        # Odd/Even balance
        odd = sum(1 for n in numbers if n % 2 == 1)
        if odd < 2 or odd > 4: score -= 10 # Prefer 3:3 or 2:4/4:2
        
        return score

    def predict_3bets_greedy(self, history, rules, use_kill=True):
        # 1. Get Pool (Top 18)
        # Use our DCB-like logic for better pool quality
        methods = [
            ('deviation', 'deviation_predict', 1.5),
            ('markov', 'markov_predict', 1.5),
            ('statistical', 'statistical_predict', 2.0)
        ]
        
        num_scores = Counter()
        for _, func_name, weight in methods:
            try:
                res = getattr(self.engine, func_name)(history, rules)
                for num in res['numbers']:
                    num_scores[num] += weight
            except: continue
            
        kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
        for n in kill_nums: num_scores[n] = -999
        
        top_18 = [num for num, _ in num_scores.most_common(18)]
        
        # 2. Matrix
        matrix = defaultdict(Counter)
        for d in history[-200:]:
            nums = d['numbers']
            for a, b in combinations(sorted(nums), 2):
                matrix[a][b] += 1
                matrix[b][a] += 1
        
        # 3. Brute force all combos in Top 18
        # We can't actually brute force all 18,564 in the loop easily without it being slow
        # but let's try a prioritized search or a subset
        
        # Let's try picking the top 1000 combos based on sum of scores first
        all_combos = list(combinations(top_18, 6))
        # Pre-filter: only keep combos with at least 2 of the Top 5
        top_5 = set(top_18[:5])
        
        scored_combos = []
        for combo in all_combos:
            if len(set(combo) & top_5) < 1: continue # Must have at least 1 of top 5
            
            score = self._calculate_combo_score(combo, num_scores, matrix, rules)
            scored_combos.append((combo, score))
            
        scored_combos.sort(key=lambda x: x[1], reverse=True)
        
        # 4. Diversity-Greedy Pick Best 3
        selected = []
        for combo, score in scored_combos:
            if not selected:
                selected.append(combo)
            else:
                # Maximize coverage of top_18
                max_overlap = 3
                if all(len(set(combo) & set(s)) <= max_overlap for s in selected):
                    selected.append(combo)
            
            if len(selected) >= 3: break
            
        return {
            'bets': [{'numbers': sorted(list(s))} for s in selected],
            'candidates': top_18
        }

def test_greedy(test_periods=100):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = GreedyConstraintOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing Greedy-Constraint Optimizer over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            res = optimizer.predict_3bets_greedy(history, rules)
            
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
    print(f"📊 Greedy-Constraint Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_greedy(150)
