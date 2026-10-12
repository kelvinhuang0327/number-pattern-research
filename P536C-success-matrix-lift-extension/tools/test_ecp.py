#!/usr/bin/env python3
"""
🧪 ECP (Elite Consensus Pool) Optimizer
Goal: Use the frequency of 'Statistical' outputs to build a high-precision pool.
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

class ECPOptimizer(BigLotto3BetOptimizer):
    def predict_3bets_ecp(self, history, rules, use_kill=True):
        # 1. Generate Elite Consensus via Statistical Sampling
        consensus = Counter()
        for _ in range(50): # 50 samples
            try:
                res = self.engine.statistical_predict(history, rules)
                for n in res['numbers']:
                    consensus[n] += 1
            except: continue
        
        # 2. Blend with Markov and Deviation for stability
        try:
            m_res = self.engine.markov_predict(history, rules)
            for n in m_res['numbers']: consensus[n] += 5 # Markov boost
        except: pass
        
        try:
            d_res = self.engine.deviation_predict(history, rules)
            for n in d_res['numbers']: consensus[n] += 5 # Deviation boost
        except: pass
        
        # 3. P1 Kill
        kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
        for n in kill_nums: consensus[n] = -9999
        
        # 4. Top 18
        top_18 = [num for num, _ in consensus.most_common(18)]
        
        # 5. Slicing
        bets = self._generate_bets(top_18)
        
        return {
            'bets': [{'numbers': b} for b in bets],
            'candidates': top_18
        }

def test_ecp(test_periods=100):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = ECPOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing ECP (Elite Consensus Pool) over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_ecp(history, rules)
            
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
    print(f"📊 ECP Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_ecp(100)
