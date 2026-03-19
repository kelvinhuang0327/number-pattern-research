#!/usr/bin/env python3
"""
ACF/PACF Analysis for BIG_LOTTO: Lag-13 Echo Investigation
===========================================================
Context: Draw 022 [12,13,17,27,41,48] and Draw 035 [5,12,13,38,47,48]
share numbers {12,13,48}. Is lag-13 echo statistically significant?

Method:
  1. Build binary time series for each of the 49 numbers
  2. Compute autocorrelation at lags 1-20 for all 49 numbers
  3. Check statistical significance using Bartlett's approximation
  4. Specifically examine numbers involved in the echo
  5. Analyze pair co-occurrence at lag 13 vs random expectation
"""

import sys
import math
import numpy as np
from collections import defaultdict

sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew')
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
from database import DatabaseManager

# --- 1. Load data ---
db = DatabaseManager(db_path='/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db')
history = sorted(
    db.get_all_draws(lottery_type='BIG_LOTTO'),
    key=lambda x: (x['date'], x['draw'])
)
N = len(history)
print(f"{'='*72}")
print(f"BIG_LOTTO ACF/PACF Analysis -- Lag-13 Echo Investigation")
print(f"{'='*72}")
print(f"Total draws loaded: {N}")
print(f"Period: {history[0]['date']} to {history[-1]['date']}")
print(f"Draw range: {history[0]['draw']} to {history[-1]['draw']}")
print()

# --- 2. Build binary time series for each number (1-49) ---
binary_series = {}
for num in range(1, 50):
    series = np.zeros(N, dtype=float)
    for i, draw in enumerate(history):
        if num in draw['numbers']:
            series[i] = 1.0
    binary_series[num] = series

# Verify base rates
print(f"--- Base Rate Check ---")
for num in [5, 12, 13, 38, 47, 48]:
    rate = binary_series[num].mean()
    expected = 6.0 / 49.0
    print(f"  Number {num:2d}: appears in {binary_series[num].sum():.0f}/{N} draws "
          f"({rate:.4f}), expected={expected:.4f}")
print()

# --- 3. Compute ACF function ---
def compute_acf(series, max_lag=20):
    """Compute autocorrelation at lags 1..max_lag."""
    n = len(series)
    mean = series.mean()
    var = np.sum((series - mean) ** 2) / n
    if var == 0:
        return np.zeros(max_lag)
    acf_values = np.zeros(max_lag)
    for lag in range(1, max_lag + 1):
        cov = np.sum((series[:n - lag] - mean) * (series[lag:] - mean)) / n
        acf_values[lag - 1] = cov / var
    return acf_values

# --- 4. Compute ACF for all 49 numbers ---
MAX_LAG = 20
all_acf = {}
for num in range(1, 50):
    all_acf[num] = compute_acf(binary_series[num], MAX_LAG)

# Significance threshold: 2/sqrt(N) (Bartlett approximation, ~95% CI)
sig_threshold = 2.0 / math.sqrt(N)
print(f"--- Significance Threshold ---")
print(f"  N = {N}, threshold = 2/sqrt({N}) = {sig_threshold:.6f}")
print(f"  Any |ACF| > {sig_threshold:.6f} is significant at ~95% level")
print()

# --- 5. Average ACF across all 49 numbers at each lag ---
print(f"--- Average ACF Across All 49 Numbers ---")
header = f"  {'Lag':>4s}  {'Mean ACF':>10s}  {'Std':>8s}  {'#Sig':>5s}  {'Significant?':>12s}"
print(header)
print(f"  {'----':>4s}  {'----------':>10s}  {'--------':>8s}  {'-----':>5s}  {'------------':>12s}")

key_lags = {2, 3, 5, 10, 13}
avg_acf_by_lag = np.zeros(MAX_LAG)
sig_count_by_lag = np.zeros(MAX_LAG, dtype=int)

for lag_idx in range(MAX_LAG):
    lag = lag_idx + 1
    values = np.array([all_acf[num][lag_idx] for num in range(1, 50)])
    avg = values.mean()
    std = values.std()
    avg_acf_by_lag[lag_idx] = avg
    n_sig = np.sum(np.abs(values) > sig_threshold)
    sig_count_by_lag[lag_idx] = n_sig
    is_sig = "*** YES ***" if abs(avg) > sig_threshold else "no"
    marker = " <-- KEY" if lag in key_lags else ""
    print(f"  {lag:4d}  {avg:10.6f}  {std:8.6f}  {n_sig:5d}  {is_sig:>12s}{marker}")

print()

# --- 6. Individual ACF for target numbers ---
target_numbers = [47, 48, 12, 13, 38, 5]
print(f"--- Individual ACF for Target Numbers (Draw 035 members) ---")
print(f"  {'Lag':>4s}", end="")
for num in target_numbers:
    print(f"  {'#'+str(num):>8s}", end="")
print()
print(f"  {'----':>4s}", end="")
for _ in target_numbers:
    print(f"  {'--------':>8s}", end="")
print()

for lag_idx in range(MAX_LAG):
    lag = lag_idx + 1
    marker = " <--" if lag in key_lags else ""
    print(f"  {lag:4d}", end="")
    for num in target_numbers:
        val = all_acf[num][lag_idx]
        sig_mark = "*" if abs(val) > sig_threshold else " "
        print(f"  {val:7.4f}{sig_mark}", end="")
    print(marker)

print(f"\n  (* = significant at 95% level, |ACF| > {sig_threshold:.4f})")
print()

# --- 7. Cross-correlation at lag 13: pair co-occurrence analysis ---
draw_035_numbers = [5, 12, 13, 38, 47, 48]
draw_022_numbers = [12, 13, 17, 27, 41, 48]
shared = set(draw_035_numbers) & set(draw_022_numbers)

print(f"--- Lag-13 Echo: Pair Co-occurrence Analysis ---")
print(f"  Draw 022 numbers: {draw_022_numbers}")
print(f"  Draw 035 numbers: {draw_035_numbers}")
print(f"  Shared numbers: {sorted(shared)}")
print()

def compute_cross_corr_at_lag(series_a, series_b, lag):
    """Cross-correlation: corr(A[t], B[t+lag])."""
    n = len(series_a)
    a = series_a[:n - lag]
    b = series_b[lag:]
    mean_a = series_a.mean()
    mean_b = series_b.mean()
    std_a = series_a.std()
    std_b = series_b.std()
    if std_a == 0 or std_b == 0:
        return 0.0
    return np.mean((a - mean_a) * (b - mean_b)) / (std_a * std_b)

print(f"  Lag-13 Auto-correlation for each number in draw 035:")
for num in draw_035_numbers:
    acf13 = all_acf[num][12]
    sig = "SIGNIFICANT" if abs(acf13) > sig_threshold else "not significant"
    print(f"    Number {num:2d}: ACF(13) = {acf13:+.6f}  [{sig}]")

print()
print(f"  Lag-13 Cross-correlation for pairs in draw 035:")
print(f"  (Does number A appearing at time t predict number B at time t+13?)")
print()

sig_pairs = 0
total_pairs = 0
print(f"  {'Pair':>12s}  {'XCorr(13)':>10s}  {'Significance':>14s}")
print(f"  {'------------':>12s}  {'----------':>10s}  {'--------------':>14s}")

for i in range(len(draw_035_numbers)):
    for j in range(i + 1, len(draw_035_numbers)):
        a, b = draw_035_numbers[i], draw_035_numbers[j]
        xcorr_ab = compute_cross_corr_at_lag(binary_series[a], binary_series[b], 13)
        xcorr_ba = compute_cross_corr_at_lag(binary_series[b], binary_series[a], 13)
        xcorr = max(abs(xcorr_ab), abs(xcorr_ba))
        xcorr_val = xcorr_ab if abs(xcorr_ab) >= abs(xcorr_ba) else xcorr_ba
        direction = f"{a}->{b}" if abs(xcorr_ab) >= abs(xcorr_ba) else f"{b}->{a}"
        sig = "SIGNIFICANT" if xcorr > sig_threshold else "not significant"
        if xcorr > sig_threshold:
            sig_pairs += 1
        total_pairs += 1
        print(f"  {direction:>12s}  {xcorr_val:+10.6f}  {sig:>14s}")

print()
print(f"  Significant pairs: {sig_pairs}/{total_pairs}")

# --- 8. Monte Carlo: expected number of shared numbers at lag 13 ---
print()
print(f"--- Monte Carlo: Expected Overlap at Lag 13 ---")

overlaps_lag13 = []
for t in range(N - 13):
    set_t = set(history[t]['numbers'])
    set_t13 = set(history[t + 13]['numbers'])
    overlaps_lag13.append(len(set_t & set_t13))

overlaps_lag13 = np.array(overlaps_lag13)
mean_overlap = overlaps_lag13.mean()
std_overlap = overlaps_lag13.std()

expected_random = 6.0 * 6.0 / 49.0

print(f"  Empirical mean overlap at lag 13: {mean_overlap:.4f} +/- {std_overlap:.4f}")
print(f"  Theoretical random expectation:   {expected_random:.4f}")
print(f"  Draw 022 vs 035 actual overlap:   {len(shared)}")

print(f"\n  Distribution of lag-13 overlaps:")
for k in range(7):
    count = np.sum(overlaps_lag13 == k)
    pct = count / len(overlaps_lag13) * 100
    bar = "#" * int(pct)
    marker = " <-- OBSERVED" if k == len(shared) else ""
    print(f"    {k} shared: {count:5d} ({pct:5.1f}%) {bar}{marker}")

z_score = (len(shared) - mean_overlap) / std_overlap
print(f"\n  Z-score of {len(shared)} shared numbers: {z_score:.4f}")
p_ge3 = np.sum(overlaps_lag13 >= len(shared)) / len(overlaps_lag13)
print(f"  P(>= {len(shared)} shared) at lag 13: {p_ge3:.4f} ({p_ge3*100:.1f}%)")

# --- 9. Compare lag-13 to other lags ---
print()
print(f"--- Overlap Distribution by Lag (1-20) ---")
print(f"  {'Lag':>4s}  {'Mean Overlap':>13s}  {'Std':>6s}  {'P(>=3)':>8s}  {'Sig?':>6s}")
print(f"  {'----':>4s}  {'-------------':>13s}  {'------':>6s}  {'--------':>8s}  {'------':>6s}")

for lag in range(1, 21):
    overlaps = []
    for t in range(N - lag):
        set_t = set(history[t]['numbers'])
        set_tL = set(history[t + lag]['numbers'])
        overlaps.append(len(set_t & set_tL))
    overlaps = np.array(overlaps)
    m = overlaps.mean()
    s = overlaps.std()
    p_ge3_lag = np.sum(overlaps >= 3) / len(overlaps)
    z = (m - expected_random) / (s / math.sqrt(len(overlaps)))
    sig = "YES" if abs(z) > 1.96 else "no"
    marker = " <-- LAG 13" if lag == 13 else ""
    print(f"  {lag:4d}  {m:13.4f}  {s:6.4f}  {p_ge3_lag:8.4f}  {sig:>6s}{marker}")

# --- 10. Summary ---
print()
print(f"{'='*72}")
print(f"SUMMARY")
print(f"{'='*72}")
print(f"""
  1. Significance threshold: |ACF| > {sig_threshold:.6f}

  2. Average ACF at lag 13 across all 49 numbers: {avg_acf_by_lag[12]:.6f}
     Numbers with significant ACF at lag 13: {sig_count_by_lag[12]}/49

  3. Specific numbers from draw 035:""")
for num in draw_035_numbers:
    acf13 = all_acf[num][12]
    sig = "SIG" if abs(acf13) > sig_threshold else "n.s."
    print(f"     #{num:2d}: ACF(13) = {acf13:+.6f} [{sig}]")

conclusion_echo = "The lag-13 echo shows NO special significance beyond chance." if p_ge3 > 0.05 and sig_count_by_lag[12] < 5 else "The lag-13 echo warrants further investigation."
conclusion_pval = "NOT statistically unusual (p > 0.05)." if p_ge3 > 0.05 else "statistically significant (p < 0.05)."

print(f"""
  4. Lag-13 pair co-occurrence: {sig_pairs}/{total_pairs} pairs significant

  5. Overlap at lag 13:
     - Mean empirical: {mean_overlap:.4f} (random expectation: {expected_random:.4f})
     - Observed (draw 022->035): {len(shared)} shared numbers
     - P(>= {len(shared)} shared) = {p_ge3:.4f}

  6. CONCLUSION: {conclusion_echo}
     The overlap of {len(shared)} numbers between draw 022 and 035 has a
     probability of {p_ge3:.1%} under random assumption, which is
     {conclusion_pval}
""")
