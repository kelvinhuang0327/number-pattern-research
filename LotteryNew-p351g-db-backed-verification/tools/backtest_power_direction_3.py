#!/usr/bin/env python3
"""
Direction 3: Stabilize POWER_LOTTO P0+P1
=======================================
Compare:
1. Power Triple Strike (Fourier, Cold, Tail Balance) - Existing
2. Stabilized P0+P1 Power (Fourier, Cold, Gray Gap) - Proposed
Result: 150/500/1500 Backtest with 11.17% baseline.
"""
import sqlite3
import json
import sys
import os
import numpy as np
from pathlib import Path
from collections import Counter
from scipy.fft import fft, fftfreq

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))

from tools.predict_power_quad_strike import (
    fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet, gray_zone_gap_bet
)

BASELINE_3BET = 11.17

def load_history():
    db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'
    if not db_path.exists():
        db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery.db'
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT draw, date, numbers, special FROM draws WHERE lottery_type=? ORDER BY date ASC",
        ('POWER_LOTTO',)
    )
    draws = []
    for row in cursor.fetchall():
        nums = json.loads(row[2]) if row[2] else []
        draws.append({
            'draw': row[0], 'date': row[1],
            'numbers': nums, 'special': row[3] or 0
        })
    conn.close()
    return draws

# ========== Strategy Ensembles ==========

def power_triple_strike_predict(history):
    b1 = fourier_rhythm_bet(history) # Power version in predict_power_quad_strike
    b2 = cold_numbers_bet(history, exclude=set(b1))
    b3 = tail_balance_bet(history, exclude=set(b1)|set(b2))
    return [b1, b2, b3]

def stabilized_p0p1_power_predict(history):
    b1 = fourier_rhythm_bet(history) 
    b2 = cold_numbers_bet(history, exclude=set(b1))
    b3 = gray_zone_gap_bet(history, exclude=set(b1)|set(b2)) 
    return [b1, b2, b3]

# ========== Backtest Engine ==========

def run_compare(test_periods=1500):
    all_draws = load_history()
    test_periods = min(test_periods, len(all_draws) - 500)
    
    triple_hits = 0
    stable_hits = 0
    total = 0
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 500: continue
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        # Power Triple Strike
        b_triple = power_triple_strike_predict(hist)
        if max(len(set(b) & actual) for b in b_triple) >= 3: triple_hits += 1
        
        # Stabilized P0+P1 Power
        b_stable = stabilized_p0p1_power_predict(hist)
        if max(len(set(b) & actual) for b in b_stable) >= 3: stable_hits += 1
        
        total += 1
        if total % 500 == 0:
            print(f"  Progress: {total}/{test_periods} draws...")
            
    print(f"\n📊 Comparison Results (N={total} draws)")
    print(f"  {'Strategy':<25} {'M3+ Rate':>10} {'Edge vs 11.17%':>15}")
    print("-" * 65)
    print(f"  {'Power Triple Strike':<25} {triple_hits/total*100:>10.2f}% {triple_hits/total*100-11.17:>+14.2f}%")
    print(f"  {'Stabilized P0+P1 Power':<25} {stable_hits/total*100:>10.2f}% {stable_hits/total*100-11.17:>+14.2f}%")

if __name__ == "__main__":
    for p in [150, 500, 1500]:
        print(f"\nTesting window: {p} draws")
        run_compare(p)
