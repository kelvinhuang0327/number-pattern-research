
import os, sys
import numpy as np
from collections import Counter

# Add necessary paths
project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import (
    _539_acb_bet, _539_markov_bet, _539_fourier_scores, 
    _539_midfreq_bet, _539_lag_echo_bet, _539_cold_burst_bet, 
    _539_lift_pair_bet
)

def run_evaluation():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    # Use DESC -> ASC
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    # Target numbers for 115000062
    actual_nums = {11, 12, 14, 17, 32}
    
    # Target draw: 115000062
    target_idx = -1
    for i, d in enumerate(history):
        if d['draw'] == '115000062':
            target_idx = i
            break
    
    if target_idx == -1:
        print("Draw 115000062 not found in DB! Using current history as base (last draw: {})".format(history[-1]['draw']))
        hist_for_pred = history
    else:
        hist_for_pred = history[:target_idx]
        actual_nums = set(history[target_idx]['numbers'])
    
    methods = {
        'ACB': lambda h: _539_acb_bet(h),
        'Markov (w30)': lambda h: _539_markov_bet(h, window=30),
        'MidFreq (w100)': lambda h: _539_midfreq_bet(h, window=100),
        'Fourier (w500)': lambda h: None, # special handling
        'Lag-k Echo (w/ 1:0.5, 2:2.0, 3:1.0)': lambda h: _539_lag_echo_bet(h),
        'Cold Burst (gap>=15)': lambda h: _539_cold_burst_bet(h, threshold_gap=15),
        'Lift Pair (w500)': lambda h: _539_lift_pair_bet(h, window=500),
    }

    # Fourier handling
    sc = _539_fourier_scores(hist_for_pred, window=500)
    methods['Fourier (w500)'] = lambda h: sorted(sc, key=lambda x: -sc[x])[:5]

    print(f"Target Numbers (115000062): {sorted(list(actual_nums))}")
    print("-" * 50)

    for name, func in methods.items():
        try:
            pred = func(hist_for_pred)
            if pred is None: continue
            hits = set(pred) & actual_nums
            print(f"{name:30}: {pred} | Hits: {sorted(list(hits))} ({len(hits)} hits)")
        except Exception as e:
            print(f"{name:30}: ERROR - {e}")

run_evaluation()
