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

def run_dms_benchmark(history_full, rules, periods=200, audit_window=50):
    set_seed(42)
    engine = UnifiedPredictionEngine()
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    methods = {
        'hot_cold_mix': engine.hot_cold_mix_predict,
        'markov': engine.markov_predict,
        'deviation': engine.deviation_predict,
        'trend': engine.trend_predict,
        'statistical': engine.statistical_predict
    }

    # For reporting method usage
    method_usage = Counter()

    for i in range(periods):
        target_idx = len(history_full) - periods + i
        if target_idx <= 0: continue
        
        target_draw = history_full[target_idx]
        current_history = history_full[:target_idx]
        actual = set(target_draw['numbers'])
        
        # 1. Rolling Audit: Pick the best method based on last X periods
        best_method = 'hot_cold_mix' # Default
        if len(current_history) > audit_window:
            best_rate = -1
            audit_start = len(current_history) - audit_window
            
            # Sub-audit for each method
            for m_name, m_func in methods.items():
                m_hits = 0
                # We can't re-run 50 backtests per draw (too slow), 
                # instead let's use a 10-period "Fast Audit"
                fast_audit_p = min(15, audit_window)
                for j in range(fast_audit_p):
                    a_idx = len(current_history) - fast_audit_p + j
                    if a_idx <= 0: continue
                    a_target = set(current_history[a_idx]['numbers'])
                    a_hist = current_history[:a_idx]
                    try:
                        with contextlib.redirect_stdout(io.StringIO()):
                            a_res = m_func(a_hist, rules)
                        if len(set(a_res['numbers']) & a_target) >= 3:
                            m_hits += 1
                    except: continue
                
                if m_hits > best_rate:
                    best_rate = m_hits
                    best_method = m_name
                elif m_hits == best_rate:
                    # Tie-breaker: prioritize hot_cold or markov
                    if m_name == 'hot_cold_mix': best_method = m_name
        
        # 2. Final Prediction using the 'best' method
        method_usage[best_method] += 1
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = methods[best_method](current_history, rules)
            m = len(set(res['numbers']) & actual)
            if m >= 3: 
                match_3_plus += 1
            match_dist[m] += 1
            total += 1
        except: continue
            
    rate = match_3_plus / total * 100 if total > 0 else 0
    return rate, match_3_plus, total, match_dist, method_usage

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    print("=" * 70)
    print("🔬 Big Lotto DMS (Dynamic Method Selection) Audit")
    print("=" * 70)
    
    rate, count, total, dist, usage = run_dms_benchmark(all_draws, rules, 200)
    
    print(f"Final Success Rate: {rate:5.2f}% ({count}/{total})")
    print(f"Match Dist: M3:{dist[3]} M4:{dist[4]} M0:{dist[0]}")
    print("\nMethod Usage Statistics:")
    for m, c in usage.most_common():
        print(f" - {m:15}: {c} times")
    print("=" * 70)

if __name__ == '__main__':
    main()
