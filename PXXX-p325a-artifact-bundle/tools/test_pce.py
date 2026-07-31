#!/usr/bin/env python3
"""
🧪 PCE (Pairwise Consensus Ensemble) Optimizer
Goal: Find consensus on PAIRS across multiple models.
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

class PCEOptimizer(BigLotto3BetOptimizer):
    def predict_3bets_pce(self, history, rules, use_kill=True):
        # 1. Get predictions from all methods
        methods = [
            'frequency_predict', 'bayesian_predict', 'markov_predict', 
            'deviation_predict', 'statistical_predict', 'trend_predict',
            'zone_balance_predict'
        ]
        
        all_preds = []
        for m_name in methods:
            try:
                res = getattr(self.engine, m_name)(history, rules)
                all_preds.append(res['numbers'])
            except: continue
            
        # 2. Build Consensus Matrix (of predictions)
        pair_votes = Counter()
        num_votes = Counter()
        for p in all_preds:
            for n in p: num_votes[n] += 1
            for a, b in combinations(sorted(p), 2):
                pair_votes[(a, b)] += 1
        
        # 3. P1 Kill
        kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
        kill_set = set(kill_nums)
        
        # 4. Greedy selection based on consensus
        # Start with the top consensus pairs
        sorted_pairs = sorted(pair_votes.items(), key=lambda x: x[1], reverse=True)
        
        bets = []
        for pair, votes in sorted_pairs:
            if pair[0] in kill_set or pair[1] in kill_set: continue
            
            # Form a bet around this pair
            bet = set(pair)
            
            # Fill with numbers that have high individual consensus AND are not killed
            remaining = sorted(num_votes.items(), key=lambda x: x[1], reverse=True)
            for n, v in remaining:
                if n not in bet and n not in kill_set:
                    bet.add(n)
                if len(bet) >= 6: break
            
            if len(bet) == 6:
                b_sorted = sorted(list(bet))
                if b_sorted not in bets:
                    bets.append(b_sorted)
            
            if len(bets) >= 3: break
            
        return {
            'bets': [{'numbers': b} for b in bets],
            'candidates': []
        }

def test_pce(test_periods=100):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = PCEOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing PCE (Pairwise Consensus Ensemble) over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_pce(history, rules)
            
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
    print(f"📊 PCE Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_pce(100)
