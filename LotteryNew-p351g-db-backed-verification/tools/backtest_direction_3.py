#!/usr/bin/env python3
"""
Direction 3: Stabilize BIG_LOTTO P0+P1 Gray Zone
===============================================
Compare:
1. Triple Strike (Fourier, Cold, Tail Balance) - Current Champ
2. Stabilized P0+P1 (Fourier, Cold, Gray Gap) - Proposed Champ
Result: 150/500/1500 Backtest with 5.49% baseline.
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

BASELINE_3BET = 5.49

def load_history():
    db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT draw, date, numbers, special FROM draws WHERE lottery_type=? ORDER BY date ASC",
        ('BIG_LOTTO',)
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

# ========== Strategies ==========

def fourier_rhythm_bet(history, window=500):
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    max_num = 49
    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= max_num: bitstreams[n][idx] = 1
    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        bh = bitstreams[n]
        if sum(bh) < 2: continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        if len(idx_pos[0]) == 0: continue
        pos_yf = np.abs(yf[idx_pos])
        if len(pos_yf) == 0: continue
        peak_idx = np.argmax(pos_yf)
        freq_val = xf[idx_pos][peak_idx]
        if freq_val == 0: continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit_idx = np.where(bh == 1)[0]
            if len(last_hit_idx) > 0:
                last_hit = last_hit_idx[-1]
                gap = (w - 1) - last_hit
                dist_to_peak = abs(gap - period)
                scores[n] = 1.0 / (dist_to_peak + 1.0)
    sorted_idx = np.argsort(scores[1:])[::-1] + 1
    return sorted(sorted_idx[:6].tolist())

def cold_numbers_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:]
    freq = Counter([n for d in recent for n in d['numbers']])
    candidates = [n for n in range(1, 50) if n not in exclude]
    candidates.sort(key=lambda x: freq.get(x, 0))
    return sorted(candidates[:6])

def tail_balance_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:]
    freq = Counter([n for d in recent for n in d['numbers']])
    tail_groups = {i: [] for i in range(10)}
    for n in range(1, 50):
        if n not in exclude:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for t in tail_groups: tail_groups[t].sort(key=lambda x: x[1], reverse=True)
    selected = []
    tails = sorted(range(10), key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0, reverse=True)
    while len(selected) < 6:
        for t in tails:
            if len(selected) >= 6: break
            if tail_groups[t]:
                n, _ = tail_groups[t].pop(0)
                selected.append(n)
    return sorted(selected)

def gray_gap_bet(history, window=50, exclude=None):
    exclude = exclude or set()
    recent = history[-window:]
    expected = window * 6 / 49
    freq = Counter([n for d in recent for n in d['numbers']])
    candidates = []
    for n in range(1, 50):
        if n in exclude: continue
        dev = freq.get(n, 0) - expected
        if -1.5 <= dev <= 1.5:
            gap = 0
            for j in range(len(history)-1, -1, -1):
                if n in history[j]['numbers']:
                    gap = len(history)-1-j; break
                gap = len(history)-j
            candidates.append((n, gap))
    candidates.sort(key=lambda x: x[1], reverse=True)
    return sorted([n for n, _ in candidates[:6]])

# ========== Strategy Ensembles ==========

def triple_strike_predict(history):
    b1 = fourier_rhythm_bet(history)
    b2 = cold_numbers_bet(history, exclude=set(b1))
    b3 = tail_balance_bet(history, exclude=set(b1)|set(b2))
    return [b1, b2, b3]

def stabilized_p0p1_predict(history):
    b1 = fourier_rhythm_bet(history) # Stabilized P0
    b2 = cold_numbers_bet(history, exclude=set(b1))
    b3 = gray_gap_bet(history, exclude=set(b1)|set(b2)) # Stabilized P1
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
        
        # Triple Strike
        b_triple = triple_strike_predict(hist)
        if max(len(set(b) & actual) for b in b_triple) >= 3: triple_hits += 1
        
        # Stabilized P0+P1
        b_stable = stabilized_p0p1_predict(hist)
        if max(len(set(b) & actual) for b in b_stable) >= 3: stable_hits += 1
        
        total += 1
        if total % 500 == 0:
            print(f"  Progress: {total}/{test_periods} draws...")
            
    print(f"\n📊 Comparison Results (N={total} draws)")
    print(f"  {'Strategy':<25} {'M3+ Rate':>10} {'Edge vs 5.49%':>15}")
    print("-" * 60)
    print(f"  {'Triple Strike':<25} {triple_hits/total*100:>10.2f}% {triple_hits/total*100-5.49:>+14.2f}%")
    print(f"  {'Stabilized P0+P1':<25} {stable_hits/total*100:>10.2f}% {stable_hits/total*100-5.49:>+14.2f}%")

if __name__ == "__main__":
    for p in [150, 500, 1500]:
        print(f"\nTesting window: {p} draws")
        run_compare(p)
