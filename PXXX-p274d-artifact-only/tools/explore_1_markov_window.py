#!/usr/bin/env python3
"""
探索 #1: Markov 窗口參數掃描
==============================
測試 TS3 + Markov(w=?) 的最優窗口長度。

固定條件:
  - TS3 前 3 注不變 (Fourier + Cold + Tail)
  - 第 4 注: Markov Order-1, 窗口長度變動
  - 4 注基準: 7.23%
  - 1500 期嚴格時序回測
  - Seed: 42
"""
import os
import sys
import time
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

from lottery_api.database import DatabaseManager

# Import exact TS3 logic
from tools.predict_biglotto_triple_strike import (
    fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet
)
# Import exact Markov logic
from tools.backtest_biglotto_markov_4bet import markov_orthogonal_bet

MAX_NUM = 49
PICK = 6
P_SINGLE = 0.0186
BASELINE_4BET = (1 - (1 - P_SINGLE) ** 4) * 100  # 7.23%
MIN_HISTORY = 200
SEED = 42

MARKOV_WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200, 300]


def run_markov_window_test(draws, markov_w, n_periods=1500):
    """回測 TS3 + Markov(w) 4注組合"""
    np.random.seed(SEED)
    
    start_idx = max(MIN_HISTORY, len(draws) - n_periods)
    test_draws = draws[start_idx:]
    
    hits = 0
    total = 0
    
    for target_draw in test_draws:
        target_idx = draws.index(target_draw)
        if target_idx < MIN_HISTORY:
            continue
        
        history = draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        # TS3 前 3 注
        bet1 = fourier_rhythm_bet(history)
        bet2 = cold_numbers_bet(history, exclude=set(bet1))
        bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
        
        # 第 4 注: Markov with variable window
        used = set(bet1) | set(bet2) | set(bet3)
        bet4 = markov_orthogonal_bet(history, exclude=used, markov_window=markov_w)
        
        # Check M3+
        won = False
        for b in [bet1, bet2, bet3, bet4]:
            if len(set(b) & actual) >= 3:
                won = True
                break
        
        if won:
            hits += 1
        total += 1
    
    rate = (hits / total * 100) if total > 0 else 0
    edge = rate - BASELINE_4BET
    return hits, total, rate, edge


def main():
    print("=" * 70)
    print("🔬 探索 #1: Markov 窗口參數掃描 (TS3 + Markov 4注)")
    print(f"   4注基準: {BASELINE_4BET:.2f}% | 測試窗口: {MARKOV_WINDOWS}")
    print("=" * 70)
    
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'),
                   key=lambda x: (x.get('date', ''), x.get('draw', 0)))
    
    print(f"  Total draws: {len(draws)}\n")
    
    results = []
    
    for w in MARKOV_WINDOWS:
        t0 = time.time()
        hits, total, rate, edge = run_markov_window_test(draws, w, 1500)
        elapsed = time.time() - t0
        
        verdict = "✅" if edge > 0 else "❌"
        print(f"  Markov w={w:>3d} | Rate: {rate:5.2f}% | Edge: {edge:+5.2f}% | "
              f"Hits: {hits:>3}/{total} | {verdict} ({elapsed:.1f}s)")
        
        results.append({'w': w, 'hits': hits, 'total': total, 'rate': rate, 'edge': edge})
    
    # Find best
    best = max(results, key=lambda x: x['edge'])
    worst = min(results, key=lambda x: x['edge'])
    
    print(f"\n{'='*70}")
    print(f"  🥇 Best:  w={best['w']:>3d} | Edge: {best['edge']:+.2f}% ({best['hits']}/{best['total']})")
    print(f"  🥉 Worst: w={worst['w']:>3d} | Edge: {worst['edge']:+.2f}% ({worst['hits']}/{worst['total']})")
    print(f"  📊 Range: {worst['edge']:+.2f}% ~ {best['edge']:+.2f}% (Δ={best['edge']-worst['edge']:.2f}%)")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
