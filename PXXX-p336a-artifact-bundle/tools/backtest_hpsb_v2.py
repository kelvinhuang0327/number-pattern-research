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
from models.hpsb_optimizer import HPSBOptimizer

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)

def run_1bet_benchmark(name, func, history_full, rules, periods=200):
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
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    engine = UnifiedPredictionEngine()
    hpsb = HPSBOptimizer(engine)
    
    print("=" * 60)
    print("🔬 Big Lotto U-HPE (V2) Strategy Verification")
    print("=" * 60)
    
    strategies = [
        ("Markov (Baseline)", engine.markov_predict),
        ("HPSB V1 (Original)", hpsb.predict_hpsb),
        ("HPSB V2 (U-HPE)", hpsb.predict_hpsb_v2)
    ]
    
    for name, func in strategies:
        rate, count, total, dist = run_1bet_benchmark(name, func, all_draws, rules, 200)
        print(f"{name:20}: {rate:5.2f}% ({count:2d}/{total}) | M3:{dist[3]} M4:{dist[4]} M0:{dist[0]}")
    
    print("=" * 60)

if __name__ == '__main__':
    main()
