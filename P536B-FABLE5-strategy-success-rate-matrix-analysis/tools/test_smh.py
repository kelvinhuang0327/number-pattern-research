#!/usr/bin/env python3
"""
🧪 SMH (Statistical Multi-Head) Optimizer
Goal: Use 3 targeted Statistical predictors for different zone behaviors.
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

class SMHOptimizer(BigLotto3BetOptimizer):
    def predict_3bets_smh(self, history, rules, use_kill=True):
        # 1. P1 Kill
        kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
        
        # Define 3 Heads with modified rules
        heads = [
            {'sumRange': (100, 140), 'desc': 'Low Sum'},
            {'sumRange': (130, 170), 'desc': 'Mid Sum'},
            {'sumRange': (160, 210), 'desc': 'High Sum'}
        ]
        
        bets = []
        for h in heads:
            # We adapt the statistical_predict logic or use it with custom rules
            # For simplicity, we use the engine's internal sampler but try to guide it
            # (In a real implementation, we'd pass these constraints to statistical_predict)
            
            # Since we can't easily modify the engine's internal logic without touching the file,
            # let's simulate it by sampling 1000 combinations and picking the best fit for each head.
            # This is essentially what 'statistical_predict' does.
            
            best_combo = None
            max_hits = -1
            
            # Build a pool for sampling (using weighting)
            candidates = Counter()
            methods = [('deviation', 1.5), ('markov', 1.5), ('frequency', 1.5)]
            for m_name, w in methods:
                 try:
                     res = getattr(self.engine, m_name+'_predict')(history, rules)
                     for n in res['numbers']: candidates[n] += w
                 except: pass
            
            import random
            pool = []
            for n, w in candidates.items():
                if n not in kill_nums:
                    pool.extend([n] * int(w * 5))
            
            for _ in range(500):
                if len(pool) < 6: break
                combo = set(random.sample(pool, 6))
                s = sum(combo)
                if h['sumRange'][0] <= s <= h['sumRange'][1]:
                    best_combo = sorted(list(combo))
                    break
            
            if not best_combo:
                 # Fallback to simple random sample
                 best_combo = sorted(random.sample([n for n in range(1, 50) if n not in kill_nums], 6))
            
            bets.append(best_combo)
            
        return {
            'bets': [{'numbers': b} for b in bets]
        }

def test_smh(test_periods=100):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = SMHOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing SMH (Statistical Multi-Head) over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_smh(history, rules)
            
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
    print(f"📊 SMH Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_smh(150)
