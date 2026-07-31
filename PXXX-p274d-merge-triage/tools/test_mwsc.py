#!/usr/bin/env python3
"""
🧪 MWSC (Multi-Window Strategy Consensus) Optimizer
Goal: Build a pool using consensus across multiple window sizes.
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

class MWSCOptimizer(BigLotto3BetOptimizer):
    def predict_3bets_mwsc(self, history, rules, use_kill=True):
        windows = [10, 20, 50, 100]
        consensus = Counter()
        
        for w in windows:
            past = history[-w:]
            # We simulate's engine's logic but with different windows
            # Since the engine methods don't take window, we'd have to pass a sliced history
            # which is what history[-w:] is.
            
            methods = ['statistical_predict', 'deviation_predict', 'markov_predict']
            for m in methods:
                try:
                    res = getattr(self.engine, m)(past, rules)
                    for n in res['numbers']: consensus[n] += 1
                except: pass
        
        kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
        for n in kill_nums: consensus[n] = -9999
        
        top_18 = [num for num, _ in consensus.most_common(18)]
        bets = self._generate_bets(top_18)
        
        return {
            'bets': [{'numbers': b} for b in bets],
            'candidates': top_18
        }

def test_mwsc(test_periods=100):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = MWSCOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing MWSC (Multi-Window Strategy Consensus) over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_mwsc(history, rules)
            
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
    print(f"📊 MWSC Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_mwsc(100)
