#!/usr/bin/env python3
import json
import sqlite3
import os
import numpy as np
import math
from collections import Counter
from scipy import stats

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

def analyze_echo_spectrum(draws):
    N = len(draws)
    print(f"Analyzing {N} draws for Echo Spectrum...")
    
    # Theoretical probability of AT LEAST 1 repeat
    # P(0 repeats) = C(34, 5) / C(39, 5)
    p0_theoretical = math.comb(34, 5) / math.comb(39, 5)
    p_atleast1_theoretical = 1 - p0_theoretical
    
    # Theoretical mean overlap
    # E[overlap] = PICK * PICK / POOL = 25 / 39 = 0.641
    e_overlap_theoretical = PICK * PICK / POOL

    lags = range(1, 11)
    results = {}

    for lag in lags:
        overlaps = []
        echo_indices = []
        for i in range(lag, N):
            overlap = set(draws[i-lag]['numbers']) & set(draws[i]['numbers'])
            overlaps.append(len(overlap))
            echo_indices.append(1 if len(overlap) >= 1 else 0)
        
        actual_rate = np.mean(echo_indices)
        actual_mean_overlap = np.mean(overlaps)
        
        # T-test for mean overlap
        t_stat, p_val_overlap = stats.ttest_1samp(overlaps, e_overlap_theoretical)
        
        # Binomial test for hit rate
        try:
            p_val_rate = stats.binomtest(sum(echo_indices), len(echo_indices), p_atleast1_theoretical, alternative='greater').pvalue
        except AttributeError:
            p_val_rate = stats.binom_test(sum(echo_indices), len(echo_indices), p_atleast1_theoretical, alternative='greater')
        
        results[lag] = {
            'rate': actual_rate,
            'p_rate': p_val_rate,
            'mean_overlap': actual_mean_overlap,
            'p_overlap': p_val_overlap,
            'edge_rate': actual_rate - p_atleast1_theoretical
        }
        
    print(f"{'Lag':<5} {'Rate':<10} {'Edge':<10} {'p-value(Rate)':<15} {'Mean Overlap':<15} {'p-value(Overlap)':<15}")
    for lag in lags:
        res = results[lag]
        print(f"{lag:<5} {res['rate']*100:6.2f}% {res['edge_rate']*100:+7.2f}% {res['p_rate']:15.6f} {res['mean_overlap']:15.4f} {res['p_overlap']:15.6f}")

    return results

def analyze_echo_stability_by_number(draws, lag=2):
    N = len(draws)
    num_echo_counts = Counter()
    num_total_presence_at_lag = Counter()
    
    for i in range(lag, N):
        prev_nums = draws[i-lag]['numbers']
        curr_nums = draws[i]['numbers']
        for n in prev_nums:
            num_total_presence_at_lag[n] += 1
            if n in curr_nums:
                num_echo_counts[n] += 1
                
    # Theoretical p per number: 5/39
    p_theoretical = PICK / POOL
    
    number_signals = []
    for n in range(1, POOL + 1):
        obs = num_echo_counts[n]
        total = num_total_presence_at_lag[n]
        rate = obs / total if total > 0 else 0
        # Binomial test
        try:
            p_val = stats.binomtest(obs, total, p_theoretical, alternative='greater').pvalue
        except AttributeError:
            p_val = stats.binom_test(obs, total, p_theoretical, alternative='greater')
        number_signals.append((n, obs, total, rate, p_val))
        
    number_signals.sort(key=lambda x: x[4]) # Sort by p-value
    print(f"\nLag-{lag} Echo by Number (Top 5):")
    for n, obs, total, rate, p_val in number_signals[:5]:
        print(f"  #{n:2}: {obs}/{total} ({rate*100:5.2f}%) p={p_val:.6f}")
    
    return number_signals

def main():
    draws = load_draws()
    echo_res = analyze_echo_spectrum(draws)
    
    # Analyze if Lag-2 + Lag-3 are correlated
    # (i.e. if it echoes from 2nd ago, is it more/less likely to echo from 3rd ago?)
    print("\nAnalyzing Cross-Lag Dependencies (Lag 2 & Lag 3)...")
    lag2_hits = []
    lag3_hits = []
    for i in range(3, len(draws)):
        l2 = 1 if len(set(draws[i-2]['numbers']) & set(draws[i]['numbers'])) >= 1 else 0
        l3 = 1 if len(set(draws[i-3]['numbers']) & set(draws[i]['numbers'])) >= 1 else 0
        lag2_hits.append(l2)
        lag3_hits.append(l3)
        
    contingency = Counter(zip(lag2_hits, lag3_hits))
    print(f"Lag2\tLag3\tCount")
    for (l2, l3), count in sorted(contingency.items()):
        print(f"{l2}\t{l3}\t{count}")
        
    # Chi-square independence test
    obs = [[contingency[(0,0)], contingency[(0,1)]], [contingency[(1,0)], contingency[(1,1)]]]
    chi2, p, dof, ex = stats.chi2_contingency(obs)
    print(f"Chi-square independence: chi2={chi2:.4f}, p={p:.6f}")
    if p < 0.05:
        print("Signal: Lag-2 and Lag-3 echoes are NOT independent!")
    else:
        print("No interaction between Lag-2 and Lag-3 echoes.")

    # Number specific stability
    analyze_echo_stability_by_number(draws, lag=2)
    analyze_echo_stability_by_number(draws, lag=3)

if __name__ == "__main__":
    main()
