#!/usr/bin/env python3
"""
🧪 Big Lotto 5-Bet Optimization Benchmark
Goal: Compare "4+1" vs "5ME" in deterministic environment (Seed 42).
"""
import sys
import os
import io
import random
import numpy as np
from collections import Counter
import contextlib

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer
from tools.test_tme import TMEOptimizer

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)

class FiveBetOptimizer(BigLotto3BetOptimizer):
    def predict_5me(self, history, rules):
        """5-Method Ensemble: Stat, Dev, Mark, HotCold, Trend"""
        methods = ['statistical_predict', 'deviation_predict', 'markov_predict', 'hot_cold_mix_predict', 'trend_predict']
        bets = []
        for m in methods:
            try:
                res = getattr(self.engine, m)(history, rules)
                bets.append(sorted(res['numbers']))
            except: pass
        return {'bets': [{'numbers': b} for b in bets]}

    def predict_4p1_tme_skew(self, history, rules):
        """TME 4-bet (Slicing Top 20) + 1 Skewed Bet"""
        # 1. Get Pool (Top 20)
        candidates = Counter()
        methods = [('deviation', 1.5), ('markov', 1.5), ('statistical', 2.0)]
        for m, w in methods:
            try:
                r = getattr(self.engine, m+'_predict')(history, rules)
                for n in r['numbers']: candidates[n] += w
            except: pass
        
        kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
        for n in kill_nums: candidates[n] = -9999
        top_20 = [num for num, _ in candidates.most_common(20)]
        
        # 4-bet slicing: 0-5, 4-9, 8-13, 12-17
        SLICES = [(0, 6), (4, 10), (8, 14), (12, 18)]
        bets = [sorted(top_20[s:e]) for s, e in SLICES]
        
        # 1 Skewed bet (Target coldest zone)
        z_scores = Counter()
        for d in history[-50:]:
            for n in d['numbers']:
                if 1 <= n <= 16: z_scores['low'] += 1
                elif 17 <= n <= 32: z_scores['mid'] += 1
                else: z_scores['high'] += 1
        
        coldest = min(z_scores, key=z_scores.get)
        if coldest == 'low': z_range = (1, 16)
        elif coldest == 'mid': z_range = (17, 32)
        else: z_range = (33, 49)
        
        zone_nums = [n for n in range(z_range[0], z_range[1]+1) if n not in kill_nums]
        secure_nums = [n for n in top_20 if z_range[0] <= n <= z_range[1]]
        
        skew_bet = secure_nums[:3] + zone_nums[:3]
        while len(set(skew_bet)) < 6:
            skew_bet.append(random.choice(zone_nums))
        
        bets.append(sorted(list(set(skew_bet))))
        return {'bets': [{'numbers': b} for b in bets]}

def run_benchmark(name, func, history_full, rules, periods=200):
    set_seed(42)
    total = 0
    match_3_plus = 0
    for i in range(periods):
        idx = len(history_full) - periods + i
        if idx <= 0: continue
        target = history_full[idx]
        hist = history_full[:idx]
        actual = set(target['numbers'])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = func(hist, rules)
            hits = [len(set(b['numbers']) & actual) for b in res['bets']]
            if max(hits) >= 3: match_3_plus += 1
            total += 1
        except: continue
    return match_3_plus / total * 100

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    opt = FiveBetOptimizer()
    
    print("="*60)
    print("🔬 Big Lotto 5-Bet Optimization (Seed: 42)")
    print("="*60)
    
    for p in [150, 200]:
        print(f"\n📊 testing {p} Periods:")
        print("-" * 40)
        rate_5me = run_benchmark("5-Method Ensemble", opt.predict_5me, all_draws, rules, p)
        print(f"5-Method Ensemble:  {rate_5me:.2f}%")
        
        rate_4p1 = run_benchmark("TME 4+1 Skewed", opt.predict_4p1_tme_skew, all_draws, rules, p)
        print(f"TME 4+1 Skewed:      {rate_4p1:.2f}%")
    
    def predict_5bet_dense(h, r):
        # Dense Slicing: (0,6), (3,9), (6,12), (9,15), (12,18)
        # Using the core U3E weighted pool
        candidates = Counter()
        methods = [('deviation', 1.5), ('markov', 1.5), ('statistical', 2.0)]
        for m, w in methods:
            try:
                r_res = opt.engine.predict_ranked_numbers(h, r, m, 18)
                for n in r_res: candidates[n] += w
            except: 
                # Fallback to direct method result if ranked helper fails
                try:
                    res = getattr(opt.engine, m+'_predict')(h, r)
                    for n in res['numbers']: candidates[n] += w
                except: pass
        
        kill_nums = opt.selector.predict_kill_numbers(count=10, history=h)
        for n in kill_nums: candidates[n] = -9999
        top_18 = [num for num, _ in candidates.most_common(18)]
        
        while len(top_18) < 18: top_18.append(random.randint(1,49))
        
        slices = [top_18[0:6], top_18[3:9], top_18[6:12], top_18[9:15], top_18[12:18]]
        return {'bets': [{'numbers': b} for b in slices]}

    rate_dense = run_benchmark("Dense Slicing 5-Bet", predict_5bet_dense, all_draws, rules)
    print(f"Dense Slicing 5-Bet: {rate_dense:.2f}%")

if __name__ == '__main__':
    main()
