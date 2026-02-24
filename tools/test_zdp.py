#!/usr/bin/env python3
"""
🧪 ZDP (Zonal Density Protection) Optimizer
Goal: Force 3 distinct zonal distributions (Skewed Mode) into the 3 bets.
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

class ZDPOptimizer(BigLotto3BetOptimizer):
    def predict_3bets_zdp(self, history, rules, use_kill=True):
        # 1. Get Pool (Top 25 for more zonal diversity)
        res = self.predict_3bets_diversified(history, rules, use_kill=use_kill)
        # We need more candidates than just 18 to fill zones properly
        methods = [('deviation', 1.5), ('markov', 1.5), ('statistical', 2.0)]
        candidates = Counter()
        for m, w in methods:
            try:
                r = getattr(self.engine, m+'_predict')(history, rules)
                for n in r['numbers']: candidates[n] += w
            except: pass
            
        kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
        for n in kill_nums: candidates[n] = -9999
        
        top_30 = [num for num, _ in candidates.most_common(30)]
        
        # 2. Divide into Zones
        z_low = [n for n in top_30 if 1 <= n <= 16]
        z_mid = [n for n in top_30 if 17 <= n <= 32]
        z_high = [n for n in top_30 if 33 <= n <= 49]
        
        bets = []
        # Configuration: (Heavy Zone, Other Zones)
        configs = [
            (z_low, z_mid + z_high), # Low Heavy
            (z_mid, z_low + z_high), # Mid Heavy
            (z_high, z_low + z_mid)  # High Heavy
        ]
        
        for heavy, others in configs:
            import random
            random.seed(42) # Deterministic for test
            
            bet = []
            # Take 4 from heavy
            if len(heavy) >= 4: bet.extend(heavy[:4])
            else: bet.extend(heavy)
            
            # Fill with others
            idx = 0
            while len(bet) < 6 and idx < len(others):
                if others[idx] not in bet:
                    bet.append(others[idx])
                idx += 1
            
            # Final fallback
            while len(bet) < 6:
                bet.append(random.randint(1, 49))
                
            bets.append(sorted(bet))
            
        return {
            'bets': [{'numbers': b} for b in bets]
        }

def test_zdp(test_periods=100):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = ZDPOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing ZDP (Zonal Density Protection) over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_zdp(history, rules)
            
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
    print(f"📊 ZDP Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_zdp(150)
