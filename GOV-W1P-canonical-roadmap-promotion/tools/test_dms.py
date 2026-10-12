#!/usr/bin/env python3
"""
🧪 DMS (Dynamic Method Selection) Optimizer
Goal: Predict using the top 3 best-performing strategies in the recent window.
"""
import sys
import os
import io
from collections import Counter, defaultdict
import contextlib

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer

class DMSOptimizer(BigLotto3BetOptimizer):
    def predict_3bets_dms(self, history, rules, use_kill=True):
        # 1. Backtest strategies on the last 30 draws
        window = 30
        methods = {
            'frequency': self.engine.frequency_predict,
            'bayesian': self.engine.bayesian_predict,
            'markov': self.engine.markov_predict,
            'trend': self.engine.trend_predict,
            'deviation': self.engine.deviation_predict,
            'statistical': self.engine.statistical_predict,
            'zone_balance': self.engine.zone_balance_predict,
            'hot_cold_mix': self.engine.hot_cold_mix_predict
        }
        
        perf = Counter()
        # Due to speed, we'll only audit the last 20 draws to pick the method
        audit_history = history[-window:]
        for i in range(10, window): # Audit last 20 samples
            audit_target = history[-(window-i)]
            past = history[:-(window-i)]
            actual = set(audit_target['numbers'])
            
            for name, func in methods.items():
                try:
                    res = func(past, rules)
                    hits = len(set(res['numbers']) & actual)
                    perf[name] += hits # Use total hits as proxy for reliability
                except: continue
        
        # 2. Pick top 3 methods
        top_methods = [m for m, _ in perf.most_common(3)]
        
        # 3. Predict with them
        bets = []
        for m_name in top_methods:
            try:
                res = methods[m_name](history, rules)
                bets.append(sorted(res['numbers']))
            except: continue
            
        # Fallback if less than 3
        while len(bets) < 3:
            bets.append(sorted(self.engine.statistical_predict(history, rules)['numbers']))
            
        return {
            'bets': [{'numbers': b} for b in bets],
            'top_methods': top_methods
        }

def test_dms(test_periods=100):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = DMSOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing DMS (Dynamic Method Selection) over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_dms(history, rules)
            
            best_match = 0
            for b_data in res['bets']:
                m = len(set(b_data['numbers']) & actual)
                if m > best_match: best_match = m
            
            if best_match >= 3: match_3_plus += 1
            match_dist[best_match] += 1
            total += 1
            
            if (i+1) % 10 == 0:
                print(f"進度: {i+1}/{test_periods} | M-3+: {match_3_plus/total*100:.2f}%")
        except Exception as e:
            # print(f"Error: {e}")
            continue
        
    print("\n" + "=" * 60)
    print(f"📊 DMS Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_dms(100)
