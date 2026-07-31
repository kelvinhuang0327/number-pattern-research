#!/usr/bin/env python3
import sys
import os
import io
import random
import numpy as np
from collections import Counter
import contextlib

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)

def run_benchmark(name, func, history_full, rules, periods=200):
    set_seed(42)
    total = 0
    match_3_plus = 0
    
    for i in range(periods):
        target_idx = len(history_full) - periods + i
        if target_idx <= 0: continue
        
        target_draw = history_full[target_idx]
        history = history_full[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = func(history, rules)
            
            # Extract bets
            if 'bets' in res:
                bets = [set(b['numbers']) for b in res['bets']]
            else:
                bets = [set(res['numbers'])]
                
            hits = [len(b & actual) for b in bets]
            if max(hits) >= 3: 
                match_3_plus += 1
            total += 1
        except: continue
            
    return match_3_plus / total * 100 if total > 0 else 0

def predict_2bet_markov_dev(engine, history, rules):
    m = engine.markov_predict(history, rules)['numbers']
    d = engine.deviation_predict(history, rules)['numbers']
    return {'bets': [{'numbers': m}, {'numbers': d}]}

def predict_2bet_slice(engine, history, rules):
    # Weighted Pool
    pool = Counter()
    methods = [('markov', 1.0), ('deviation', 1.0), ('statistical', 1.0)]
    for m, w in methods:
        try:
            r = getattr(engine, m+'_predict')(history, rules)
            for n in r['numbers']: pool[n] += w
        except: pass
    top_12 = [n for n, _ in pool.most_common(12)]
    return {'bets': [{'numbers': sorted(top_12[:6])}, {'numbers': sorted(top_12[6:12])}]}

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()
    
    print("=" * 60)
    print("🔬 Big Lotto Feasibility Audit (200 Periods, Seed: 42)")
    print("=" * 60)
    
    # 1-Bet Baselines
    print("\n--- 1-Bet Strategies ---")
    methods = [
        ("Markov", engine.markov_predict),
        ("Deviation", engine.deviation_predict),
        ("Statistical", engine.statistical_predict),
        ("Bayesian", engine.bayesian_predict)
    ]
    for name, func in methods:
        rate = run_benchmark(name, func, all_draws, rules)
        print(f"{name:15}: {rate:5.2f}%")
        
    # 2-Bet Baselines
    print("\n--- 2-Bet Strategies ---")
    rates_2b = [
        ("Markov + Deviation", lambda h, r: predict_2bet_markov_dev(engine, h, r)),
        ("Top 12 Slicing", lambda h, r: predict_2bet_slice(engine, h, r))
    ]
    for name, func in rates_2b:
        rate = run_benchmark(name, func, all_draws, rules)
        print(f"{name:20}: {rate:5.2f}%")
        
    print("=" * 60)

if __name__ == '__main__':
    main()
