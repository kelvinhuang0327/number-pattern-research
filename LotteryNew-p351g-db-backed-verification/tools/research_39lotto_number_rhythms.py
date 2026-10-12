#!/usr/bin/env python3
import json
import sqlite3
import os
import numpy as np
from scipy import stats
from collections import Counter

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'lottery_v2.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_v2.db')

POOL = 39
PICK = 5

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'DAILY_539'
        ORDER BY date ASC, draw ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums)})
    return draws

def find_best_lag_per_number(draws):
    N = len(draws)
    max_lag = 15
    p_theoretical = PICK / POOL
    
    number_best_lags = {}
    
    print(f"Finding best lag (1-{max_lag}) for each number...")
    
    for n in range(1, POOL + 1):
        lags_p = []
        for lag in range(1, max_lag + 1):
            obs = 0
            total = 0
            for i in range(lag, N):
                if n in draws[i-lag]['numbers']:
                    total += 1
                    if n in draws[i]['numbers']:
                        obs += 1
            if total > 50: # Minimum sample size
                try:
                    p = stats.binomtest(obs, total, p_theoretical, alternative='greater').pvalue
                except AttributeError:
                    p = stats.binom_test(obs, total, p_theoretical, alternative='greater')
                lags_p.append((lag, p, obs/total))
        
        if lags_p:
            lags_p.sort(key=lambda x: x[1])
            number_best_lags[n] = lags_p[0]
            
    # Sort numbers by how significant their best lag is
    sorted_nums = sorted(number_best_lags.items(), key=lambda x: x[1][1])
    
    print(f"{'Num':<5} {'Lag':<5} {'p-value':<15} {'Rate':<10} {'Edge':<10}")
    for n, (lag, p, rate) in sorted_nums[:15]:
        edge = rate - p_theoretical
        print(f"{n:<5} {lag:<5} {p:15.6f} {rate*100:6.2f}% {edge*100:+7.2f}%")
        
    return number_best_lags

def analyze_fourier_stability(draws, num):
    N = len(draws)
    series = np.array([1 if num in d['numbers'] else 0 for d in draws], dtype=float)
    
    # Split into 3 segments
    segment_size = N // 3
    print(f"\nFourier Stability for Number {num}:")
    for i in range(3):
        seg = series[i*segment_size : (i+1)*segment_size]
        fft_vals = np.fft.rfft(seg - seg.mean())
        power = np.abs(fft_vals) ** 2
        # Find dominant period > 2
        valid_indices = range(1, len(power)) 
        if not valid_indices: continue
        dominant_idx = np.argmax(power[1:]) + 1
        period = len(seg) / dominant_idx
        print(f"  Segment {i+1}: Dominant Period = {period:.2f} draws")

def main():
    draws = load_draws()
    best_lags = find_best_lag_per_number(draws)
    
    # Analyze Number 12 and 18 specifically
    analyze_fourier_stability(draws, 12)
    analyze_fourier_stability(draws, 18)

if __name__ == "__main__":
    main()
