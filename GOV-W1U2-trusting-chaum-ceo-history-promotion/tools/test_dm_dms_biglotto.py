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

def run_dm_dms_benchmark(history_full, rules, periods=200, audit_window=15):
    set_seed(42)
    engine = UnifiedPredictionEngine()
    total = 0
    match_3_plus = 0
    
    methods = {
        'hot_cold_mix': engine.hot_cold_mix_predict,
        'markov': engine.markov_predict,
        'deviation': engine.deviation_predict,
        'trend': engine.trend_predict,
        'statistical': engine.statistical_predict
    }

    for i in range(periods):
        target_idx = len(history_full) - periods + i
        if target_idx <= 0: continue
        
        target_draw = history_full[target_idx]
        current_history = history_full[:target_idx]
        actual = set(target_draw['numbers'])
        
        # 1. Rolling Audit for Top 2
        method_perf = []
        for m_name, m_func in methods.items():
            m_hits = 0
            for j in range(audit_window):
                a_idx = len(current_history) - audit_window + j
                if a_idx <= 0: continue
                a_target = set(current_history[a_idx]['numbers'])
                a_hist = current_history[:a_idx]
                try:
                    # We use a very fast check here
                    with contextlib.redirect_stdout(io.StringIO()):
                        a_res = m_func(a_hist, rules)
                    if len(set(a_res['numbers']) & a_target) >= 3:
                        m_hits += 1
                except: continue
            method_perf.append((m_name, m_hits))
        
        # Sort by hits descending
        method_perf.sort(key=lambda x: x[1], reverse=True)
        top_2_methods = [method_perf[0][0], method_perf[1][0]]
        
        # 2. Final Predictions
        bets = []
        for m_name in top_2_methods:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    res = methods[m_name](current_history, rules)
                bets.append(set(res['numbers']))
            except: continue
            
        if any(len(b & actual) >= 3 for b in bets):
            match_3_plus += 1
        total += 1
            
    rate = match_3_plus / total * 100 if total > 0 else 0
    return rate, match_3_plus, total

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    print("=" * 60)
    print("🔬 Big Lotto DM-DMS (2-Bet Dynamic) Audit")
    print("=" * 60)
    
    rate, count, total = run_dm_dms_benchmark(all_draws, rules, 200)
    
    print(f"Final Success Rate (2-Bet): {rate:5.2f}% ({count}/{total})")
    print("=" * 60)

if __name__ == '__main__':
    main()
