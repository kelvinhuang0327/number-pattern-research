#!/usr/bin/env python3
import torch
import torch.nn as nn
import json
import os
import sys
import numpy as np
import random
from collections import Counter
import contextlib
import io

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
sys.path.insert(0, os.path.join(project_root, 'ai_lab'))

from database import DatabaseManager
from common import get_lottery_rules
from models.ensemble_predictor import EnsemblePredictor, patch_ai_adapter

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

def run_benchmark(predict_func, all_draws, rules, ai_weight, periods=200):
    set_seed(42)
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = predict_func(history, rules, ai_weight=ai_weight)
            m = len(set(res['numbers']) & actual)
            if m >= 3: match_3_plus += 1
            match_dist[m] += 1
            total += 1
        except Exception as e:
            continue
    rate = match_3_plus / total * 100 if total > 0 else 0
    return rate, match_3_plus, total, match_dist

def main():
    patch_ai_adapter() # Enable raw probs
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    ensemble = EnsemblePredictor()
    
    print("=" * 80)
    print("🔬 Phase 11: Universal Consensus Weight Sensitivity Audit (Big Lotto)")
    print("=" * 80)
    print(f"{'AI Weight':<12} | {'Success Rate':<14} | {'M3+ Counts':<12} | {'M4 Hits':<8}")
    print("-" * 80)
    
    best_rate = -1
    best_weight = 0
    
    # Test weights from 0.0 to 1.0
    for w in np.arange(0.0, 1.1, 0.1):
        rate, count, total, dist = run_benchmark(ensemble.predict_ensemble, all_draws, rules, ai_weight=w, periods=200)
        print(f"{w:12.1f} | {rate:13.2f}% | {count:2d}/{total:3d}        | {dist[4]:<8}")
        
        if rate > best_rate:
            best_rate = rate
            best_weight = w
        elif rate == best_rate and dist[4] > dist.get(best_weight_m4, 0): # Tie break with M4
            best_weight = w
            
    print("-" * 80)
    print(f"✅ Optimal Universal Consensus Weight: AI={best_weight:.1f}, Stat={1.0-best_weight:.1f}")
    print(f"🚀 Peak Success Rate: {best_rate:.2f}%")
    print("=" * 80)

if __name__ == "__main__":
    main()
