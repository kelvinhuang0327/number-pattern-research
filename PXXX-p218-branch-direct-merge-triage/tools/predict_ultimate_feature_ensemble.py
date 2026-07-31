#!/usr/bin/env python3
"""
Ultimate Feature Ensemble (UFE)
==============================
Synthesized from exhaustive sweep Phase 17-20.
Combines:
1. Spatial: Zonal Pruning (Big Lotto King)
2. Harmonic: FFT Rhythm (Power Lotto/Big Lotto Stable)
3. Statistical: Long-Term Frequency (Power Lotto King)
"""
import os
import sys
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from tools.power_fourier_rhythm import fourier_rhythm_predict

def ultimate_ensemble_predict(history, lottery_type='BIG_LOTTO', num_bets=2):
    """
    UFE V2: Dynamic Model Selector (MAB Lite)
    1. Backtests candidate features on the last 20 periods.
    2. Selects the one with the highest hit rate for the next draw.
    """
    # Candidate methods
    from tools.power_fourier_rhythm import fourier_rhythm_predict
    from tools.biglotto_zonal_pruning import zonal_pruned_predict
    from tools.power_wavelet_mra import wavelet_mra_predict
    
    def freq_300(h, num_bets=1):
        subset = h[-300:]
        counts = Counter([n for d in subset for n in d['numbers']])
        top = [n for n, c in counts.most_common(6*num_bets)]
        return [sorted(top[i*6:(i+1)*6]) for i in range(num_bets)]

    methods = {
        "FFT": lambda h, num_bets=1: fourier_rhythm_predict(h, n_bets=num_bets, window=500),
        "Zonal": lambda h, num_bets=1: zonal_pruned_predict(h, n_bets=num_bets),
        "Wavelet": lambda h, num_bets=1: wavelet_mra_predict(h, n_bets=num_bets),
        "Freq300": freq_300
    }

    # Dynamic Selection (Last 20 periods)
    if len(history) < 50: # Baseline
        return methods["Zonal"](history, num_bets)

    scores = Counter()
    audit_len = 20
    test_slice = history[-audit_len-1:] # Need history+1 for checking last
    
    # Simple walk-forward validation
    for name, func in methods.items():
        hits = 0
        for i in range(audit_len):
            idx = len(history) - audit_len + i
            h_past = history[:idx]
            target = set(history[idx]['numbers'])
            # We check if the method would have predicted Match-3+ in the past
            bets = func(h_past, num_bets=1) # Check single bet power
            if any(len(set(b) & target) >= 3 for b in bets):
                hits += 1
        scores[name] = hits

    best_method_name = scores.most_common(1)[0][0]
    print(f"📊 Market Regime: Picking best model '{best_method_name}' (Hits: {scores[best_method_name]}/{audit_len})")
    
    # For multiple bets, we take the best and the runner-up
    if num_bets == 1:
        return methods[best_method_name](history, 1)
    else:
        runner_up = scores.most_common(2)[1][0]
        bet1 = methods[best_method_name](history, 1)
        bet2 = methods[runner_up](history, 1)
        return [bet1[0], bet2[0]]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='BIG_LOTTO')
    parser.add_argument('--bets', type=int, default=2)
    args = parser.parse_args()
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(args.lottery)
    
    bets = ultimate_ensemble_predict(history, args.lottery, args.bets)
    
    print(f"\n🎯 【{args.lottery}】 ULTIMATE FEATURE ENSEMBLE")
    print("-" * 50)
    for i, b in enumerate(bets, 1):
        print(f"Bet {i}: {b}")
    print("-" * 50)
