#!/usr/bin/env python3
"""
Power Lotto Marginal Edge Analysis
==================================
Testing individual modules to find a STABLE 3-bet or 4-bet for Power Lotto.
1. Fourier (Existing)
2. Gray Zone Gap (Promising)
3. Lag-2 Echo (New)
4. Cold Numbers (Existing)
"""
import os
import sys
import sqlite3
import json
import numpy as np
from collections import Counter
from pathlib import Path
from scipy.fft import fft, fftfreq

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Baseline for N bets in Power Lotto (38 balls)
# P(1) = 3.87%, P(2) = 7.59%, P(3) = 11.17%, P(4) = 14.60%
BASELINES = {1: 3.87, 2: 7.59, 3: 11.17, 4: 14.60}

def load_draws():
    db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'
    if not db_path.exists(): db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT numbers FROM draws WHERE lottery_type='POWER_LOTTO' ORDER BY date ASC")
    rows = cursor.fetchall()
    conn.close()
    return [{'numbers': json.loads(r[0])} for r in rows]

def get_fourier(history):
    # Same as predict_power_quad_strike.fourier_rhythm_bet
    window = 500
    h_slice = history[-window:]
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, 39)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= 38: bitstreams[n][idx] = 1
    scores = np.zeros(39)
    for n in range(1, 39):
        bh = bitstreams[n]
        if sum(bh) < 2: continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0: continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores)[::-1] # Full rank

def get_gray_gap(history, exclude=None):
    # Same as predict_power_quad_strike.gray_zone_gap_bet
    exclude = exclude or set()
    recent = history[-50:]
    expected = 50 * 6 / 38
    freq = Counter([n for d in recent for n in d['numbers']])
    candidates = []
    for n in range(1, 39):
        if n in exclude: continue
        dev = freq.get(n, 0) - expected
        if -1.2 <= dev <= 1.2:
            gap = 0
            for j in range(len(history)-1, -1, -1):
                if n in history[j]['numbers']:
                    gap = len(history)-1-j; break
                gap = len(history)-j
            candidates.append((n, gap))
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [n for n, _ in candidates]

def get_echo(history, exclude=None):
    # Lag-2 Echo logic
    exclude = exclude or set()
    if len(history) < 2: return []
    lag2 = set(history[-2]['numbers'])
    return [n for n in range(1, 39) if n in lag2 and n not in exclude]

# ========== Backtest Comparison ==========

def run_marginal_test(periods=1384):
    all_draws = load_draws()
    total = 0
    hits_f2 = 0 # Fourier Top 12 (2 bets)
    hits_f2_g1 = 0 # Fourier Top 12 + Gray Gap 1 (3 bets)
    hits_f2_e1 = 0 # Fourier Top 12 + Echo 1 (多樣化)
    
    print(f"🔬 Testing Marginal Contribution (N={periods})...")
    
    for i in range(len(all_draws) - periods, len(all_draws)):
        hist = all_draws[:i]
        if len(hist) < 500: continue
        actual = set(all_draws[i]['numbers'])
        
        # 1. Fourier 2-bet
        f_rank = get_fourier(hist)
        b1 = sorted(f_rank[:6].tolist())
        b2 = sorted(f_rank[6:12].tolist())
        f2_bets = [set(b1), set(b2)]
        if any(len(b & actual) >= 3 for b in f2_bets): hits_f2 += 1
        
        # 2. Fourier 2-bet + Gray Gap 1 (3-bet)
        exclude = set(b1) | set(b2)
        gray_rank = get_gray_gap(hist, exclude=exclude)
        b3_gray = set(gray_rank[:6])
        if any(len(b & actual) >= 3 for b in f2_bets + [b3_gray]): hits_f2_g1 += 1
        
        # 3. Fourier 2-bet + Echo 1 (3-bet)
        echo_nums = get_echo(hist, exclude=exclude)
        # Combine echo with cold or gap to fill 6? Just take top 6 from (Echo + Cold)
        recent = hist[-100:]
        freq = Counter([n for d in recent for n in d['numbers']])
        remaining = [n for n in range(1, 39) if n not in exclude and n not in echo_nums]
        remaining.sort(key=lambda x: freq.get(x, 0)) # Cold
        b3_echo = set((echo_nums + remaining)[:6])
        if any(len(b & actual) >= 3 for b in f2_bets + [b3_echo]): hits_f2_e1 += 1
        
        total += 1
        if total % 500 == 0: print(f"  Progress {total}/{periods}...")

    print("-" * 70)
    print(f"📊 Results (N={total})")
    print(f"  {'Strategy':<25} {'M3+ Rate':>10} {'Edge vs Random':>15}")
    print("-" * 70)
    print(f"  {'Fourier 2-bet':<25} {hits_f2/total*100:>10.2f}% {hits_f2/total*100-BASELINES[2]:>+14.2f}%")
    print(f"  {'F2 + Gray Gap (3注)':<25} {hits_f2_g1/total*100:>10.2f}% {hits_f2_g1/total*100-BASELINES[3]:>+14.2f}%")
    print(f"  {'F2 + Echo/Cold (3注)':<25} {hits_f2_e1/total*100:>10.2f}% {hits_f2_e1/total*100-BASELINES[3]:>+14.2f}%")
    
    # Marginal Analysis
    f2_rate = hits_f2/total*100
    gray_rate = hits_f2_g1/total*100
    echo_rate = hits_f2_e1/total*100
    
    print("\n💡 Marginal Edge Analysis (Contribution of 3rd bet):")
    print(f"  Gray Gap 3rd bet: {gray_rate - f2_rate - (BASELINES[3]-BASELINES[2]):>+7.2f}%")
    print(f"  Echo/Cold 3rd bet: {echo_rate - f2_rate - (BASELINES[3]-BASELINES[2]):>+7.2f}%")

if __name__ == "__main__":
    run_marginal_test(1384)
