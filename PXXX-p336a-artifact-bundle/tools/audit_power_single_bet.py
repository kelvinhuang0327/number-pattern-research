#!/usr/bin/env python3
import sys
import os
import io
import random
import numpy as np
from collections import Counter
import contextlib

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.hpsb_optimizer import HPSBOptimizer

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)

def run_pure_1bet(name, func, history_full, rules, periods=200):
    set_seed(42)
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    for i in range(periods):
        target_idx = len(history_full) - periods + i
        if target_idx <= 0: continue
        
        target_draw = history_full[target_idx]
        history = history_full[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = func(history, rules)
            
            nums = res['numbers']
            m = len(set(nums) & actual)
            if m >= 3: 
                match_3_plus += 1
            match_dist[m] += 1
            total += 1
        except:
            continue
            
    rate = match_3_plus / total * 100 if total > 0 else 0
    return rate, match_3_plus, total, match_dist

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    engine = UnifiedPredictionEngine()
    hpsb = HPSBOptimizer(engine)
    
    methods = [
        ("Markov (Recommended)", engine.markov_predict),
        ("Statistical (Contested)", engine.statistical_predict),
        ("Bayesian", engine.bayesian_predict),
        ("Repeat Booster", engine.repeat_booster_predict),
        ("Deviation", engine.deviation_predict),
        ("HPSB (Optimized)", hpsb.predict_hpsb)
    ]
    
    print("=" * 70)
    print("🔬 Power Lotto Single Bet Comprehensive Audit (200 Periods, Seed: 42)")
    print("=" * 70)
    
    for name, func in methods:
        rate, count, total, dist = run_pure_1bet(name, func, all_draws, rules, 200)
        print(f"{name:25}: {rate:5.2f}% ({count:2d}/{total})  | M3:{dist[3]:2d} M4:{dist[4]:d}")
    
    print("=" * 70)

if __name__ == '__main__':
    main()
