#!/usr/bin/env python3
"""
Null Hypothesis / Falsification Tests for Big Lotto Draw 115000019
Target draw: [16, 35, 36, 37, 39, 49]

Tests performed:
  1. Random baseline (100k Monte Carlo simulations)
  2. Historical pattern rarity (consecutive runs, zone skew, sum)
  3. Chi-square on last 50 draws (uniformity of number frequencies)
  4. Wald-Wolfowitz runs test on individual numbers (last 100 draws)
  5. Serial correlation (Ljung-Box on draw sums, lag 1-3)
  6. Kolmogorov-Smirnov (empirical vs Uniform[1,49])
"""

import sqlite3
import json
import numpy as np
from itertools import combinations
from collections import Counter
from scipy import stats
from scipy.stats import kstest, chi2_contingency, norm
import warnings
warnings.filterwarnings("ignore")

# ============================================================
# 0. Load all BIG_LOTTO history
# ============================================================
DB_PATH = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery.db"
TARGET = [16, 35, 36, 37, 39, 49]
TARGET_SET = set(TARGET)

def load_history():
    """Load all BIG_LOTTO draws from both tables, sorted chronologically."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    draws = []

    # Table 1: draws (older data, periods 100000001 .. 99000105 stored as text)
    cur.execute("""
        SELECT draw, date, numbers, special
        FROM draws
        WHERE lottery_type = 'BIG_LOTTO'
        ORDER BY date ASC, draw ASC
    """)
    for row in cur.fetchall():
        period, date, nums_str, special = row
        nums = json.loads(nums_str)
        draws.append({
            "period": period,
            "date": date,
            "numbers": sorted(nums),
            "special": special,
        })

    # Table 2: big_lotto_draws (newer 115xxx data)
    cur.execute("""
        SELECT draw_period, date, winning_numbers, special_number
        FROM big_lotto_draws
        ORDER BY draw_period ASC
    """)
    for row in cur.fetchall():
        period, date, nums_str, special = row
        nums = [int(x.strip()) for x in nums_str.split(",")]
        draws.append({
            "period": str(period),
            "date": date,
            "numbers": sorted(nums),
            "special": special,
        })

    conn.close()

    # Deduplicate by period
    seen = set()
    unique = []
    for d in draws:
        if d["period"] not in seen:
            seen.add(d["period"])
            unique.append(d)
    unique.sort(key=lambda d: d["date"])
    return unique


history = load_history()
print(f"Loaded {len(history)} BIG_LOTTO draws  (earliest: {history[0]['date']}, latest: {history[-1]['date']})")
print(f"Target draw 115000019: {TARGET}  (sum = {sum(TARGET)})")
print("=" * 80)


# ============================================================
# 1. Random Baseline Calculation (100k Monte Carlo)
# ============================================================
print("\n" + "=" * 80)
print("TEST 1: RANDOM BASELINE  (100,000 random 6-from-49 vs target)")
print("=" * 80)

np.random.seed(42)
N_SIM = 100_000
pool = np.arange(1, 50)  # 1..49
match_counts = np.zeros(7, dtype=int)  # index 0..6

for _ in range(N_SIM):
    combo = set(np.random.choice(pool, size=6, replace=False))
    m = len(combo & TARGET_SET)
    match_counts[m] += 1

# Also compute exact hypergeometric probabilities
from scipy.stats import hypergeom
print(f"\n{'Matches':>8}  {'Simulated':>12}  {'Sim %':>8}  {'Exact %':>10}")
print("-" * 50)
for k in range(7):
    # hypergeom: total=49, good=6, draws=6
    exact_p = hypergeom.pmf(k, 49, 6, 6) * 100
    sim_p = match_counts[k] / N_SIM * 100
    print(f"{k:>8d}  {match_counts[k]:>12,d}  {sim_p:>7.3f}%  {exact_p:>9.4f}%")

print(f"\nP(match >= 3) exact = {sum(hypergeom.pmf(k, 49, 6, 6) for k in range(3,7)) * 100:.4f}%")
print(f"P(match >= 4) exact = {sum(hypergeom.pmf(k, 49, 6, 6) for k in range(4,7)) * 100:.6f}%")
print(f"P(match >= 5) exact = {sum(hypergeom.pmf(k, 49, 6, 6) for k in range(5,7)) * 100:.6f}%")
print(f"P(match  = 6) exact = {hypergeom.pmf(6, 49, 6, 6) * 100:.10f}%")


# ============================================================
# 2. Historical Pattern Rarity Tests
# ============================================================
print("\n" + "=" * 80)
print("TEST 2: HISTORICAL PATTERN RARITY")
print("=" * 80)

# 2a. Consecutive number streaks
def max_consecutive(nums):
    """Return length of longest consecutive run in sorted nums."""
    s = sorted(nums)
    max_run = 1
    run = 1
    for i in range(1, len(s)):
        if s[i] == s[i-1] + 1:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    return max_run

target_consec = max_consecutive(TARGET)
print(f"\n--- 2a. Consecutive numbers ---")
print(f"Target {TARGET} has a consecutive run of length {target_consec} (35,36,37)")

consec_hist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
for d in history:
    mc = max_consecutive(d["numbers"])
    consec_hist[mc] = consec_hist.get(mc, 0) + 1

print(f"\nHistorical distribution of max consecutive run:")
print(f"{'Run length':>12}  {'Count':>8}  {'%':>8}")
print("-" * 35)
total = len(history)
for k in sorted(consec_hist.keys()):
    pct = consec_hist[k] / total * 100
    print(f"{k:>12d}  {consec_hist[k]:>8d}  {pct:>7.2f}%")

draws_with_3plus = sum(v for k, v in consec_hist.items() if k >= 3)
print(f"\nDraws with 3+ consecutive: {draws_with_3plus}/{total} = {draws_with_3plus/total*100:.2f}%")
print(f"This pattern is {'COMMON' if draws_with_3plus/total > 0.05 else 'UNCOMMON' if draws_with_3plus/total > 0.01 else 'RARE'}")


# 2b. Zone distribution skewness
print(f"\n--- 2b. Zone distribution skew ---")

def zone_dist(nums, n_zones=3, max_num=49):
    """Compute zone distribution for 3 equal zones [1-16], [17-33], [34-49]."""
    boundaries = [16, 33, 49]
    zones = [0, 0, 0]
    for n in nums:
        if n <= boundaries[0]:
            zones[0] += 1
        elif n <= boundaries[1]:
            zones[1] += 1
        else:
            zones[2] += 1
    return tuple(zones)

target_zone = zone_dist(TARGET)
target_max_zone = max(target_zone)
print(f"Target zone distribution: {target_zone}  (zones: [1-16], [17-33], [34-49])")
print(f"Maximum numbers in any single zone: {target_max_zone}")

zone_max_hist = Counter()
draws_with_5plus = 0
for d in history:
    zd = zone_dist(d["numbers"])
    mx = max(zd)
    zone_max_hist[mx] += 1
    if mx >= 5:
        draws_with_5plus += 1

print(f"\nHistorical distribution of max zone concentration:")
print(f"{'Max in zone':>12}  {'Count':>8}  {'%':>8}")
print("-" * 35)
for k in sorted(zone_max_hist.keys()):
    pct = zone_max_hist[k] / total * 100
    print(f"{k:>12d}  {zone_max_hist[k]:>8d}  {pct:>7.2f}%")

print(f"\nDraws with 5+ in one zone: {draws_with_5plus}/{total} = {draws_with_5plus/total*100:.2f}%")
print(f"This zone skew is {'COMMON' if draws_with_5plus/total > 0.05 else 'UNCOMMON' if draws_with_5plus/total > 0.01 else 'RARE'}")


# 2c. Sum test
print(f"\n--- 2c. Sum of drawn numbers ---")
target_sum = sum(TARGET)
sums = [sum(d["numbers"]) for d in history]
mean_sum = np.mean(sums)
std_sum = np.std(sums)
z_score_sum = (target_sum - mean_sum) / std_sum

draws_with_sum_gte = sum(1 for s in sums if s >= target_sum)
expected_sum = 6 * 50 / 2  # E[sum of 6 from Uniform(1,49)] = 6*25 = 150

print(f"Target sum: {target_sum}")
print(f"Theoretical expected sum (6 from 1-49): {expected_sum:.0f}")
print(f"Historical mean sum: {mean_sum:.2f} (std = {std_sum:.2f})")
print(f"Z-score of target sum: {z_score_sum:+.3f}")
print(f"P(sum >= {target_sum}) from history: {draws_with_sum_gte}/{total} = {draws_with_sum_gte/total*100:.2f}%")
print(f"P(sum >= {target_sum}) from normal approx: {(1 - norm.cdf(z_score_sum)) * 100:.2f}%")
print(f"This sum is {'NORMAL' if abs(z_score_sum) < 2 else 'UNUSUAL' if abs(z_score_sum) < 3 else 'EXTREME'}")


# ============================================================
# 3. Chi-Square Test: Last 50 Draws Number Frequencies vs Uniform
# ============================================================
print("\n" + "=" * 80)
print("TEST 3: CHI-SQUARE TEST ON LAST 50 DRAWS (uniformity of ball frequencies)")
print("=" * 80)

last_50 = history[-50:]
freq_50 = Counter()
for d in last_50:
    for n in d["numbers"]:
        freq_50[n] += 1

# Expected under uniform: each of 49 numbers drawn 50*6/49 times
total_balls_50 = 50 * 6
expected_freq = total_balls_50 / 49

observed = np.array([freq_50.get(i, 0) for i in range(1, 50)])
expected = np.full(49, expected_freq)

chi2_stat = np.sum((observed - expected) ** 2 / expected)
df = 49 - 1  # 48 degrees of freedom
p_value_chi2 = 1 - stats.chi2.cdf(chi2_stat, df)

print(f"\nLast 50 draws: {total_balls_50} total ball appearances across 49 possible numbers")
print(f"Expected frequency per number (uniform): {expected_freq:.4f}")
print(f"Observed frequency range: min={observed.min()}, max={observed.max()}")
print(f"\nMost frequent numbers (last 50 draws):")
for num, cnt in sorted(freq_50.items(), key=lambda x: -x[1])[:10]:
    dev = (cnt - expected_freq) / np.sqrt(expected_freq)
    print(f"  Number {num:2d}: appeared {cnt:2d} times  (z = {dev:+.2f})")

print(f"\nLeast frequent numbers (last 50 draws):")
for num, cnt in sorted(freq_50.items(), key=lambda x: x[1])[:10]:
    dev = (cnt - expected_freq) / np.sqrt(expected_freq)
    print(f"  Number {num:2d}: appeared {cnt:2d} times  (z = {dev:+.2f})")

# Check which target numbers are hot/cold
print(f"\nTarget numbers in last 50 draws:")
for n in TARGET:
    cnt = freq_50.get(n, 0)
    dev = (cnt - expected_freq) / np.sqrt(expected_freq)
    label = "HOT" if dev > 1 else "COLD" if dev < -1 else "NEUTRAL"
    print(f"  Number {n:2d}: appeared {cnt:2d} times  (z = {dev:+.2f})  [{label}]")

print(f"\nChi-square statistic: {chi2_stat:.4f}")
print(f"Degrees of freedom: {df}")
print(f"P-value: {p_value_chi2:.6f}")
alpha = 0.05
if p_value_chi2 < alpha:
    print(f"RESULT: REJECT uniformity at alpha={alpha} (p={p_value_chi2:.6f} < {alpha})")
    print("  => Last 50 draws show SIGNIFICANT deviation from uniform distribution.")
else:
    print(f"RESULT: FAIL TO REJECT uniformity at alpha={alpha} (p={p_value_chi2:.6f} >= {alpha})")
    print("  => No significant evidence that last 50 draws deviate from uniform distribution.")


# ============================================================
# 4. Wald-Wolfowitz Runs Test on Individual Numbers
# ============================================================
print("\n" + "=" * 80)
print("TEST 4: WALD-WOLFOWITZ RUNS TEST (appearance pattern in last 100 draws)")
print("=" * 80)

last_100 = history[-100:]

def runs_test(binary_seq):
    """
    Wald-Wolfowitz runs test for randomness.
    binary_seq: list of 0/1 values.
    Returns (n_runs, z_stat, p_value_two_sided).
    """
    n = len(binary_seq)
    n1 = sum(binary_seq)           # count of 1s
    n0 = n - n1                     # count of 0s

    if n1 == 0 or n0 == 0:
        return (None, None, None)

    # Count runs
    runs = 1
    for i in range(1, n):
        if binary_seq[i] != binary_seq[i-1]:
            runs += 1

    # Expected runs and variance under H0
    E_R = 1 + (2 * n0 * n1) / n
    Var_R = (2 * n0 * n1 * (2 * n0 * n1 - n)) / (n**2 * (n - 1))

    if Var_R <= 0:
        return (runs, None, None)

    z = (runs - E_R) / np.sqrt(Var_R)
    p = 2 * (1 - norm.cdf(abs(z)))
    return (runs, z, p)

print(f"\nFor each target number, check if its appearance/absence in the last 100 draws")
print(f"follows a random pattern (H0: random sequence of hits/misses).")
print(f"\n{'Number':>8}  {'Appeared':>9}  {'Runs':>6}  {'E[Runs]':>8}  {'z-stat':>8}  {'p-value':>8}  {'Verdict':>20}")
print("-" * 85)

for num in TARGET:
    # Build binary sequence: 1 if number appeared in that draw, 0 otherwise
    seq = [1 if num in d["numbers"] else 0 for d in last_100]
    n1 = sum(seq)
    n0 = 100 - n1
    runs, z, p = runs_test(seq)

    E_R = 1 + (2 * n0 * n1) / 100 if n1 > 0 and n0 > 0 else float('nan')

    if z is not None:
        verdict = "RANDOM" if p >= 0.05 else "NON-RANDOM (clumped)" if z < 0 else "NON-RANDOM (alternating)"
        print(f"{num:>8d}  {n1:>5d}/100  {runs:>6d}  {E_R:>8.2f}  {z:>+8.3f}  {p:>8.4f}  {verdict:>20}")
    else:
        print(f"{num:>8d}  {n1:>5d}/100  {'N/A':>6}  {'N/A':>8}  {'N/A':>8}  {'N/A':>8}  INSUFFICIENT DATA")

print(f"\nInterpretation:")
print(f"  z < 0 => fewer runs than expected  => CLUSTERING (hot/cold streaks)")
print(f"  z > 0 => more runs than expected   => ALTERNATING (mean-reversion)")
print(f"  |z| < 1.96 and p > 0.05 => consistent with randomness")


# ============================================================
# 5. Serial Correlation Test (Ljung-Box on draw sums)
# ============================================================
print("\n" + "=" * 80)
print("TEST 5: SERIAL CORRELATION TEST (Ljung-Box on consecutive draw sums)")
print("=" * 80)

# Use statsmodels for Ljung-Box if available, otherwise manual
try:
    from statsmodels.stats.diagnostic import acorr_ljungbox
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

all_sums = np.array([sum(d["numbers"]) for d in history])

# Compute autocorrelations at lag 1, 2, 3
n_total = len(all_sums)
mean_s = np.mean(all_sums)
var_s = np.var(all_sums)

print(f"\nDraw sums: n={n_total}, mean={mean_s:.2f}, std={np.sqrt(var_s):.2f}")
print(f"\nSample autocorrelations:")
print(f"{'Lag':>6}  {'r(lag)':>10}  {'95% CI bound':>14}")
print("-" * 35)

ci_bound = 1.96 / np.sqrt(n_total)
acfs = []
for lag in [1, 2, 3]:
    if lag < n_total:
        r = np.corrcoef(all_sums[:-lag], all_sums[lag:])[0, 1]
        acfs.append(r)
        sig = "*" if abs(r) > ci_bound else ""
        print(f"{lag:>6d}  {r:>+10.6f}  +/-{ci_bound:.6f}  {sig}")

if HAS_STATSMODELS:
    # Ljung-Box test on the sum series
    lb_result = acorr_ljungbox(all_sums, lags=[1, 2, 3], return_df=True)
    print(f"\nLjung-Box test results:")
    print(f"{'Lag':>6}  {'LB stat':>10}  {'p-value':>10}  {'Verdict':>20}")
    print("-" * 55)
    for idx, row in lb_result.iterrows():
        lag = idx
        lb_stat = row['lb_stat']
        lb_p = row['lb_pvalue']
        verdict = "REJECT H0 (correlated)" if lb_p < 0.05 else "FAIL TO REJECT H0"
        print(f"{lag:>6}  {lb_stat:>10.4f}  {lb_p:>10.6f}  {verdict:>20}")
else:
    # Manual Ljung-Box: Q = n(n+2) * sum(r_k^2 / (n-k)) for k=1..m
    print(f"\n(statsmodels not available; computing Ljung-Box manually)")
    for max_lag in [1, 2, 3]:
        Q = 0
        for k in range(max_lag):
            Q += n_total * (n_total + 2) * (acfs[k]**2) / (n_total - (k+1))
        p_lb = 1 - stats.chi2.cdf(Q, max_lag)
        verdict = "REJECT H0 (correlated)" if p_lb < 0.05 else "FAIL TO REJECT H0"
        print(f"  Lag 1..{max_lag}: Q={Q:.4f}, df={max_lag}, p={p_lb:.6f}  => {verdict}")

print(f"\nInterpretation:")
print(f"  If p < 0.05: evidence of serial correlation in draw sums (non-random pattern)")
print(f"  If p >= 0.05: draw sums consistent with no serial correlation")


# ============================================================
# 6. Kolmogorov-Smirnov Test: Empirical vs Uniform[1,49]
# ============================================================
print("\n" + "=" * 80)
print("TEST 6: KOLMOGOROV-SMIRNOV TEST (all drawn numbers vs Uniform[1,49])")
print("=" * 80)

all_numbers = []
for d in history:
    all_numbers.extend(d["numbers"])

all_numbers = np.array(all_numbers)

# KS test against continuous uniform on [0.5, 49.5] (to properly bracket integers 1-49)
# We transform to [0,1] by (x - 0.5) / 49
transformed = (all_numbers - 0.5) / 49.0
ks_stat, ks_p = kstest(transformed, 'uniform')

print(f"\nTotal drawn numbers: {len(all_numbers)}")
print(f"Range: [{all_numbers.min()}, {all_numbers.max()}]")
print(f"Mean: {all_numbers.mean():.4f}  (expected: 25.00)")
print(f"Std:  {all_numbers.std():.4f}  (expected: {np.sqrt((49**2-1)/12):.4f} for Uniform(1,49))")

print(f"\nKS statistic: {ks_stat:.6f}")
print(f"KS p-value:   {ks_p:.6f}")

if ks_p < 0.05:
    print(f"RESULT: REJECT uniformity at alpha=0.05")
    print(f"  => The empirical distribution of drawn numbers significantly deviates from Uniform[1,49].")
else:
    print(f"RESULT: FAIL TO REJECT uniformity at alpha=0.05")
    print(f"  => Drawn numbers are consistent with Uniform[1,49].")

# Also report per-number frequency deviation
print(f"\nPer-number frequency analysis (all {len(history)} draws):")
freq_all = Counter(all_numbers)
expected_all = len(all_numbers) / 49

most_drawn = freq_all.most_common(5)
least_drawn = freq_all.most_common()[-5:]
print(f"Expected freq per number: {expected_all:.2f}")
print(f"Most drawn:  {[(n, c) for n, c in most_drawn]}")
print(f"Least drawn: {[(n, c) for n, c in least_drawn]}")

# KS test on just the last 200 draws for a more recent picture
last_200_nums = []
for d in history[-200:]:
    last_200_nums.extend(d["numbers"])
last_200_nums = np.array(last_200_nums)
transformed_200 = (last_200_nums - 0.5) / 49.0
ks_stat_200, ks_p_200 = kstest(transformed_200, 'uniform')
print(f"\nKS test on last 200 draws only:")
print(f"  KS statistic: {ks_stat_200:.6f}")
print(f"  KS p-value:   {ks_p_200:.6f}")
if ks_p_200 < 0.05:
    print(f"  RESULT: REJECT uniformity (recent draws show significant deviation)")
else:
    print(f"  RESULT: FAIL TO REJECT uniformity (recent draws consistent with Uniform)")


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 80)
print("SUMMARY OF FALSIFICATION TESTS FOR DRAW 115000019 [16,35,36,37,39,49]")
print("=" * 80)

print(f"""
+-------+-------------------------------------------+---------------------------+
| Test  | Description                               | Result                    |
+-------+-------------------------------------------+---------------------------+""")

# Test 1 summary
p_m3 = sum(hypergeom.pmf(k, 49, 6, 6) for k in range(3, 7)) * 100
print(f"| 1     | Random baseline P(match>=3)               | {p_m3:.4f}%                 |")

# Test 2a
pct_3consec = draws_with_3plus/total*100
print(f"| 2a    | 3+ consecutive in history                 | {pct_3consec:.2f}% of draws          |")

# Test 2b
pct_5zone = draws_with_5plus/total*100
print(f"| 2b    | 5+ in one zone in history                 | {pct_5zone:.2f}% of draws          |")

# Test 2c
print(f"| 2c    | Sum=212 z-score                           | z={z_score_sum:+.3f}                |")

# Test 3
chi2_verdict = "REJECT" if p_value_chi2 < 0.05 else "FAIL TO REJECT"
print(f"| 3     | Chi-square uniformity (last 50)            | p={p_value_chi2:.4f}, {chi2_verdict:14s} |")

# Test 4
n_nonrandom = sum(1 for num in TARGET
                   for _, z, p in [runs_test([1 if num in d["numbers"] else 0 for d in last_100])]
                   if p is not None and p < 0.05)
print(f"| 4     | Runs test (non-random numbers / 6)         | {n_nonrandom}/6 non-random         |")

# Test 5
if HAS_STATSMODELS:
    lb_p3 = lb_result.iloc[-1]['lb_pvalue']
else:
    Q = sum(n_total * (n_total + 2) * (acfs[k]**2) / (n_total - (k+1)) for k in range(3))
    lb_p3 = 1 - stats.chi2.cdf(Q, 3)
lb_verdict = "CORRELATED" if lb_p3 < 0.05 else "NO CORRELATION"
print(f"| 5     | Ljung-Box serial correlation (lag 1-3)     | p={lb_p3:.4f}, {lb_verdict:14s} |")

# Test 6
ks_verdict = "NON-UNIFORM" if ks_p < 0.05 else "UNIFORM"
print(f"| 6     | KS test (all draws vs Uniform)             | p={ks_p:.4f}, {ks_verdict:14s} |")

print(f"+-------+-------------------------------------------+---------------------------+")

print(f"""
INTERPRETATION:
  - Test 1:  The target draw matches are fully consistent with combinatorial probability.
             Any single random ticket has {p_m3:.2f}% chance of matching 3+ numbers.
  - Test 2:  3 consecutive numbers appears in ~{pct_3consec:.1f}% of draws (not extremely rare).
             Zone skew with 5+ in one zone occurs in ~{pct_5zone:.1f}% of draws.
             Sum of 212 has z={z_score_sum:+.2f} ({'within normal range' if abs(z_score_sum) < 2 else 'moderately unusual'}).
  - Test 3:  {'The last 50 draws show statistically significant frequency deviations.' if p_value_chi2 < 0.05 else 'No evidence of non-uniform frequency in the last 50 draws.'}
  - Test 4:  {n_nonrandom}/6 target numbers show non-random appearance patterns.
  - Test 5:  {'Serial correlation detected in draw sums.' if lb_p3 < 0.05 else 'No serial correlation in draw sums.'}
  - Test 6:  {'Overall number distribution deviates from uniform.' if ks_p < 0.05 else 'Overall number distribution is consistent with uniform.'}

CONCLUSION:
  These tests evaluate whether draw 115000019 or recent draws show patterns
  that falsify the null hypothesis of a fair, independent lottery.
""")
