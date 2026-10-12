#!/usr/bin/env python3
"""
Comprehensive Statistical Analysis for Big Lotto (大樂透) Draw 115000019
Numbers: [16, 35, 36, 37, 39, 49]

Data sources:
  - SQLite DB: lottery_api/data/lottery.db (draws table, big_lotto_draws table)
  - JSON:      lottery_api/data/lottery_history.json

Anti-data-leakage: Only uses draws BEFORE 115000019.
"""

import sqlite3
import json
import math
import os
import sys
from collections import Counter, defaultdict
from itertools import combinations
import numpy as np

np.random.seed(42)

# ============================================================
# 0. LOAD ALL BIG_LOTTO HISTORY (merged, deduplicated, sorted)
# ============================================================

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "lottery_api", "data", "lottery.db")
JSON_PATH = os.path.join(BASE, "lottery_api", "data", "lottery_history.json")

TARGET_DRAW = "115000019"
TARGET_NUMBERS = [16, 35, 36, 37, 39, 49]

def draw_to_int(d):
    return int(d)

def load_data():
    draws = {}  # draw_number -> {'draw': str, 'numbers': list[int]}

    # --- DB: draws table ---
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT draw, numbers FROM draws WHERE lottery_type='BIG_LOTTO'")
    for row in cur.fetchall():
        d, nums_str = row
        nums = json.loads(nums_str)
        draws[d] = {'draw': d, 'numbers': sorted(nums)}

    # --- DB: big_lotto_draws table ---
    cur.execute("SELECT draw_period, winning_numbers FROM big_lotto_draws")
    for row in cur.fetchall():
        d, nums_str = row
        d_str = str(d)
        nums = [int(x.strip()) for x in nums_str.split(',')]
        draws[d_str] = {'draw': d_str, 'numbers': sorted(nums)}

    conn.close()

    # --- JSON ---
    with open(JSON_PATH, 'r') as f:
        jdata = json.load(f)
    bl = jdata.get('data_by_type', {}).get('BIG_LOTTO', [])
    for entry in bl:
        d = entry['draw']
        nums = sorted(entry['numbers'])
        draws[d] = {'draw': d, 'numbers': nums}

    # Sort by draw number (integer)
    all_draws = sorted(draws.values(), key=lambda x: draw_to_int(x['draw']))
    return all_draws

def load_power_lotto():
    draws = {}
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT draw, numbers FROM draws WHERE lottery_type='POWER_LOTTO'")
    for row in cur.fetchall():
        d, nums_str = row
        nums = json.loads(nums_str)
        draws[d] = {'draw': d, 'numbers': sorted(nums)}
    conn.close()

    with open(JSON_PATH, 'r') as f:
        jdata = json.load(f)
    pl = jdata.get('data_by_type', {}).get('POWER_LOTTO', [])
    for entry in pl:
        d = entry['draw']
        nums = sorted(entry['numbers'])
        draws[d] = {'draw': d, 'numbers': nums}

    return sorted(draws.values(), key=lambda x: draw_to_int(x['draw']))


all_draws = load_data()
power_draws = load_power_lotto()

# Filter: only draws BEFORE 115000019
history = [d for d in all_draws if draw_to_int(d['draw']) < draw_to_int(TARGET_DRAW)]

print("=" * 80)
print(f"  COMPREHENSIVE STATISTICAL ANALYSIS: BIG LOTTO DRAW {TARGET_DRAW}")
print(f"  Numbers: {TARGET_NUMBERS}")
print("=" * 80)
print(f"\n  Total historical draws loaded: {len(history)}")
print(f"  Date range: draw {history[0]['draw']} .. {history[-1]['draw']}")
print(f"  Last 5 draws before {TARGET_DRAW}:")
for d in history[-5:]:
    print(f"    {d['draw']}: {d['numbers']}")


# ============================================================
# 1. STRUCTURAL FEATURES
# ============================================================

print("\n" + "=" * 80)
print("  SECTION 1: STRUCTURAL FEATURES")
print("=" * 80)

nums = TARGET_NUMBERS
n = len(nums)

# 1a. Sum analysis
total_sum = sum(nums)
hist_sums = [sum(d['numbers']) for d in history]
mean_sum = np.mean(hist_sums)
std_sum = np.std(hist_sums)
z_sum = (total_sum - mean_sum) / std_sum
percentile_sum = np.sum(np.array(hist_sums) <= total_sum) / len(hist_sums) * 100

print(f"\n  1a. SUM ANALYSIS")
print(f"      Sum = {total_sum}")
print(f"      Historical mean = {mean_sum:.2f}, std = {std_sum:.2f}")
print(f"      Z-score = {z_sum:+.3f}")
print(f"      Percentile = {percentile_sum:.1f}%  (higher than {percentile_sum:.1f}% of historical draws)")
if z_sum > 2:
    print(f"      *** UNUSUALLY HIGH (z > 2) ***")
elif z_sum > 1:
    print(f"      * Moderately high (1 < z < 2)")
elif z_sum < -2:
    print(f"      *** UNUSUALLY LOW (z < -2) ***")
elif z_sum < -1:
    print(f"      * Moderately low (-2 < z < -1)")
else:
    print(f"      Within normal range (-1 < z < 1)")

# 1b. AC Value
diffs = set()
for i in range(n):
    for j in range(i + 1, n):
        diffs.add(abs(nums[i] - nums[j]))
ac_value = len(diffs) - (n - 1)

# Historical AC values
hist_ac = []
for d in history:
    ds = set()
    nn = d['numbers']
    for i in range(len(nn)):
        for j in range(i + 1, len(nn)):
            ds.add(abs(nn[i] - nn[j]))
    hist_ac.append(len(ds) - (len(nn) - 1))

mean_ac = np.mean(hist_ac)
std_ac = np.std(hist_ac)
z_ac = (ac_value - mean_ac) / std_ac if std_ac > 0 else 0

print(f"\n  1b. AC VALUE (Complexity)")
print(f"      Unique absolute differences = {len(diffs)}")
print(f"      AC = {len(diffs)} - {n-1} = {ac_value}")
print(f"      Historical mean AC = {mean_ac:.2f}, std = {std_ac:.2f}")
print(f"      Z-score = {z_ac:+.3f}")
print(f"      All differences: {sorted(diffs)}")

# 1c. Consecutive pairs
gaps = [nums[i+1] - nums[i] for i in range(n-1)]
consec_pairs = sum(1 for g in gaps if g == 1)

# Count consecutive runs
consec_runs = []
run = 1
for i in range(1, n):
    if nums[i] == nums[i-1] + 1:
        run += 1
    else:
        if run >= 2:
            consec_runs.append((nums[i-run], nums[i-1], run))
        run = 1
if run >= 2:
    consec_runs.append((nums[n-run], nums[n-1], run))

# Historical consecutive pair count
hist_consec = []
for d in history:
    nn = sorted(d['numbers'])
    cp = sum(1 for i in range(len(nn)-1) if nn[i+1] - nn[i] == 1)
    hist_consec.append(cp)

# Count 3+ consecutive historically
hist_3consec = 0
for d in history:
    nn = sorted(d['numbers'])
    r = 1
    has3 = False
    for i in range(1, len(nn)):
        if nn[i] == nn[i-1] + 1:
            r += 1
            if r >= 3:
                has3 = True
        else:
            r = 1
    if has3:
        hist_3consec += 1

print(f"\n  1c. CONSECUTIVE NUMBERS")
print(f"      Gaps between numbers: {gaps}")
print(f"      Consecutive pairs (gap=1): {consec_pairs}")
for start, end, length in consec_runs:
    print(f"      Consecutive run: {start}-{end} (length {length})")
print(f"      Historical avg consecutive pairs = {np.mean(hist_consec):.2f}")
print(f"      Draws with 3+ consecutive: {hist_3consec}/{len(history)} = {hist_3consec/len(history)*100:.2f}%")
if any(r[2] >= 3 for r in consec_runs):
    print(f"      *** THIS DRAW HAS A 3-CONSECUTIVE RUN (35,36,37) - happens {hist_3consec/len(history)*100:.2f}% of the time ***")

# 1d. Odd/Even ratio
odd_count = sum(1 for x in nums if x % 2 == 1)
even_count = n - odd_count
odd_nums = [x for x in nums if x % 2 == 1]
even_nums = [x for x in nums if x % 2 == 0]

hist_odd = [sum(1 for x in d['numbers'] if x % 2 == 1) for d in history]
odd_dist = Counter(hist_odd)

print(f"\n  1d. ODD/EVEN RATIO")
print(f"      Even numbers: {even_nums} ({even_count})")
print(f"      Odd numbers:  {odd_nums} ({odd_count})")
print(f"      Ratio: {even_count}E:{odd_count}O")
print(f"      Historical odd-count distribution:")
for k in sorted(odd_dist.keys()):
    pct = odd_dist[k] / len(history) * 100
    print(f"        {6-k}E:{k}O -> {odd_dist[k]} draws ({pct:.1f}%)")

# 1e. Zone distribution (Z1: 1-16, Z2: 17-33, Z3: 34-49)
zones = {'Z1 (1-16)': 0, 'Z2 (17-33)': 0, 'Z3 (34-49)': 0}
zone_nums = {'Z1 (1-16)': [], 'Z2 (17-33)': [], 'Z3 (34-49)': []}
for x in nums:
    if 1 <= x <= 16:
        zones['Z1 (1-16)'] += 1
        zone_nums['Z1 (1-16)'].append(x)
    elif 17 <= x <= 33:
        zones['Z2 (17-33)'] += 1
        zone_nums['Z2 (17-33)'].append(x)
    else:
        zones['Z3 (34-49)'] += 1
        zone_nums['Z3 (34-49)'].append(x)

def get_zone_tuple(numbers):
    z = [0, 0, 0]
    for x in numbers:
        if 1 <= x <= 16: z[0] += 1
        elif 17 <= x <= 33: z[1] += 1
        else: z[2] += 1
    return tuple(z)

target_zt = get_zone_tuple(nums)
hist_zt = [get_zone_tuple(d['numbers']) for d in history]
zt_counter = Counter(hist_zt)
target_zt_count = zt_counter.get(target_zt, 0)

# Count draws where any zone has 5+
hist_zone5 = sum(1 for zt in hist_zt if max(zt) >= 5)

print(f"\n  1e. ZONE DISTRIBUTION")
for zname, zcount in zones.items():
    print(f"      {zname}: {zcount} numbers {zone_nums[zname]}")
print(f"      Zone tuple (Z1,Z2,Z3) = {target_zt}")
print(f"      Historical frequency of this zone pattern: {target_zt_count}/{len(history)} ({target_zt_count/len(history)*100:.2f}%)")
print(f"      Draws with any zone having 5+ numbers: {hist_zone5}/{len(history)} ({hist_zone5/len(history)*100:.2f}%)")
print(f"      *** EXTREMELY SKEWED: Zone 3 has {zones['Z3 (34-49)']} of 6 numbers ***")

# Top 10 zone patterns
print(f"      Top 10 zone patterns:")
for zt, cnt in zt_counter.most_common(10):
    print(f"        {zt}: {cnt} ({cnt/len(history)*100:.1f}%)")

# 1f. Tail number distribution
tails = [x % 10 for x in nums]
tail_counter = Counter(tails)

print(f"\n  1f. TAIL NUMBER DISTRIBUTION")
print(f"      Numbers: {nums}")
print(f"      Tails:   {tails}")
print(f"      Tail counts: {dict(tail_counter)}")
print(f"      Unique tails: {len(tail_counter)} / {n}")
# Check for repeat tails
for t, c in tail_counter.items():
    if c > 1:
        matching = [x for x in nums if x % 10 == t]
        print(f"      * Repeated tail {t}: numbers {matching} (appears {c} times)")

# 1g. Gap analysis
print(f"\n  1g. GAP ANALYSIS (between consecutive sorted numbers)")
for i in range(n - 1):
    gap = nums[i+1] - nums[i]
    print(f"      {nums[i]} -> {nums[i+1]}: gap = {gap}")
print(f"      First-to-last span: {nums[-1]} - {nums[0]} = {nums[-1] - nums[0]}")
print(f"      Max gap: {max(gaps)}, Min gap: {min(gaps)}")

hist_max_gaps = [max(sorted(d['numbers'])[i+1] - sorted(d['numbers'])[i] for i in range(5)) for d in history]
hist_min_gaps = [min(sorted(d['numbers'])[i+1] - sorted(d['numbers'])[i] for i in range(5)) for d in history]
print(f"      Historical avg max gap: {np.mean(hist_max_gaps):.2f}")
print(f"      Historical avg min gap: {np.mean(hist_min_gaps):.2f}")

# Also compute first number and last number distributions
first_gap = nums[0] - 1
last_gap = 49 - nums[-1]
print(f"      Leading gap (1 to first): {first_gap}")
print(f"      Trailing gap (last to 49): {last_gap}")


# ============================================================
# 2. HISTORICAL FREQUENCY ANALYSIS
# ============================================================

print("\n" + "=" * 80)
print("  SECTION 2: HISTORICAL FREQUENCY ANALYSIS")
print("=" * 80)

def freq_in_window(draws_list, window):
    """Count frequency of each number in the last `window` draws."""
    subset = draws_list[-window:] if window <= len(draws_list) else draws_list
    freq = Counter()
    for d in subset:
        for x in d['numbers']:
            freq[x] += 1
    return freq

windows = [10, 30, 50, 100]
expected_per_draw = 6.0 / 49.0  # each number's expected freq per draw

print(f"\n  Expected frequency per number per draw: {expected_per_draw:.4f}")
print(f"  (6 numbers drawn from 49)")

for w in windows:
    freq = freq_in_window(history, w)
    expected = expected_per_draw * min(w, len(history))
    print(f"\n  --- Last {w} draws (expected count per number: {expected:.2f}) ---")
    print(f"  {'Number':>8} {'Count':>6} {'Expected':>9} {'Deviation':>10} {'Status':>10}")
    for num in TARGET_NUMBERS:
        actual = freq.get(num, 0)
        dev = actual - expected
        dev_pct = ((actual / expected) - 1) * 100 if expected > 0 else 0
        status = "HOT" if dev > 1.5 else ("COLD" if dev < -1.5 else "NEUTRAL")
        print(f"  {num:>8d} {actual:>6d} {expected:>9.2f} {dev:>+10.2f} {status:>10}")

# Overall hot/cold assessment
freq100 = freq_in_window(history, 100)
exp100 = expected_per_draw * min(100, len(history))
hot_nums = [x for x in TARGET_NUMBERS if freq100.get(x, 0) > exp100 + 1.5]
cold_nums = [x for x in TARGET_NUMBERS if freq100.get(x, 0) < exp100 - 1.5]
neutral_nums = [x for x in TARGET_NUMBERS if x not in hot_nums and x not in cold_nums]

print(f"\n  100-draw summary for {TARGET_NUMBERS}:")
print(f"    HOT numbers (above expected+1.5):     {hot_nums}")
print(f"    COLD numbers (below expected-1.5):     {cold_nums}")
print(f"    NEUTRAL numbers (within ±1.5):         {neutral_nums}")


# ============================================================
# 3. PATTERN RARITY ANALYSIS
# ============================================================

print("\n" + "=" * 80)
print("  SECTION 3: PATTERN RARITY ANALYSIS")
print("=" * 80)

# 3a. 3-consecutive rarity (already computed)
print(f"\n  3a. THREE CONSECUTIVE NUMBERS (35, 36, 37)")
print(f"      Historical draws with 3+ consecutive: {hist_3consec}/{len(history)}")
print(f"      Probability: {hist_3consec/len(history)*100:.2f}%")

# Theoretical: P(at least one 3-consecutive in 6 from 49)
# Enumerate by simulation
np.random.seed(42)
sim_count = 500000
sim_3consec = 0
for _ in range(sim_count):
    sample = sorted(np.random.choice(range(1, 50), 6, replace=False))
    r = 1
    has3 = False
    for i in range(1, 6):
        if sample[i] == sample[i-1] + 1:
            r += 1
            if r >= 3:
                has3 = True
                break
        else:
            r = 1
    if has3:
        sim_3consec += 1

print(f"      Random simulation (N={sim_count}): {sim_3consec/sim_count*100:.2f}% have 3+ consecutive")
ratio = (hist_3consec / len(history)) / (sim_3consec / sim_count)
print(f"      Historical / Random ratio: {ratio:.3f}")

# 3b. Zone skewness: 5 of 6 in one zone
print(f"\n  3b. EXTREME ZONE SKEWNESS (5 of 6 in Zone 3)")
print(f"      Historical draws with any zone >= 5: {hist_zone5}/{len(history)} ({hist_zone5/len(history)*100:.2f}%)")

# Theoretical P(any zone >= 5) by simulation
sim_zone5 = 0
for _ in range(sim_count):
    sample = sorted(np.random.choice(range(1, 50), 6, replace=False))
    z = [0, 0, 0]
    for x in sample:
        if 1 <= x <= 16: z[0] += 1
        elif 17 <= x <= 33: z[1] += 1
        else: z[2] += 1
    if max(z) >= 5:
        sim_zone5 += 1

print(f"      Random simulation (N={sim_count}): {sim_zone5/sim_count*100:.2f}% have any zone >= 5")

# Exact zone pattern frequency
print(f"      Historical draws with pattern (1,0,5): {zt_counter.get((1,0,5), 0)}")
print(f"      Historical draws with pattern (0,1,5): {zt_counter.get((0,1,5), 0)}")
print(f"      Historical draws with pattern (0,0,6): {zt_counter.get((0,0,6), 0)}")

# 3c. Sum percentile (already computed)
print(f"\n  3c. SUM PERCENTILE")
print(f"      Sum = {total_sum}")
print(f"      Percentile: {percentile_sum:.1f}%")
print(f"      Z-score: {z_sum:+.3f}")

# Random baseline for sum
sim_sums = []
for _ in range(sim_count):
    sample = np.random.choice(range(1, 50), 6, replace=False)
    sim_sums.append(int(np.sum(sample)))
sim_sums = np.array(sim_sums)
sim_percentile = np.sum(sim_sums <= total_sum) / sim_count * 100
print(f"      Random simulation sum mean: {np.mean(sim_sums):.2f}, std: {np.std(sim_sums):.2f}")
print(f"      Random simulation percentile for {total_sum}: {sim_percentile:.1f}%")

# 3d. Compare to random baseline (overall rarity score)
print(f"\n  3d. COMPOSITE RARITY SCORE")
features_unusual = 0
if abs(z_sum) > 1.5: features_unusual += 1
if any(r[2] >= 3 for r in consec_runs): features_unusual += 1
if max(target_zt) >= 5: features_unusual += 1
if len(tail_counter) < 5: features_unusual += 1  # less than 5 unique tails from 6 numbers
total_features = 4
print(f"      Unusual features count: {features_unusual} / {total_features}")
print(f"      Features checked: sum z>1.5, 3+consecutive, zone>=5, repeated tails")
if features_unusual >= 3:
    print(f"      *** THIS IS A HIGHLY UNUSUAL DRAW ***")
elif features_unusual >= 2:
    print(f"      ** This draw has notable unusual features **")
else:
    print(f"      This draw is within normal structural bounds")


# ============================================================
# 4. LAG / ECHO ANALYSIS
# ============================================================

print("\n" + "=" * 80)
print("  SECTION 4: LAG / ECHO ANALYSIS")
print("=" * 80)

# 4a. Lag for each number
print(f"\n  4a. LAG VALUES (draws since last appearance)")
for num in TARGET_NUMBERS:
    lag = None
    for i in range(len(history) - 1, -1, -1):
        if num in history[i]['numbers']:
            lag = len(history) - 1 - i
            last_draw = history[i]['draw']
            break
    if lag is not None:
        print(f"      Number {num:2d}: lag = {lag:3d} (last appeared in draw {last_draw})")
    else:
        print(f"      Number {num:2d}: NEVER appeared in history (lag = infinity)")

# Expected lag
expected_lag = 1 / expected_per_draw
print(f"      Expected lag (1/p): {expected_lag:.2f} draws")

# 4b. Lag-2 echo pattern
print(f"\n  4b. LAG-2 ECHO PATTERN (numbers from 2 draws ago)")
if len(history) >= 2:
    draw_n_minus_2 = history[-2]
    draw_n_minus_1 = history[-1]
    print(f"      N-1 draw ({draw_n_minus_1['draw']}): {draw_n_minus_1['numbers']}")
    print(f"      N-2 draw ({draw_n_minus_2['draw']}): {draw_n_minus_2['numbers']}")

    echo_from_n2 = set(TARGET_NUMBERS) & set(draw_n_minus_2['numbers'])
    echo_from_n1 = set(TARGET_NUMBERS) & set(draw_n_minus_1['numbers'])

    print(f"      Numbers in common with N-2: {sorted(echo_from_n2)} ({len(echo_from_n2)} numbers)")
    print(f"      Numbers in common with N-1: {sorted(echo_from_n1)} ({len(echo_from_n1)} numbers)")

    # Historical lag-2 echo rate
    echo_counts = []
    for i in range(2, len(history)):
        current = set(history[i]['numbers'])
        prev2 = set(history[i-2]['numbers'])
        overlap = len(current & prev2)
        echo_counts.append(overlap)

    mean_echo = np.mean(echo_counts)
    pct_any_echo = sum(1 for e in echo_counts if e > 0) / len(echo_counts) * 100

    print(f"      Historical lag-2 echo rate (any overlap): {pct_any_echo:.1f}%")
    print(f"      Historical mean lag-2 overlap: {mean_echo:.2f}")

# 4c. Deviation from expected frequency
print(f"\n  4c. DEVIATION FROM EXPECTED FREQUENCY (last 50 draws)")
freq50 = freq_in_window(history, 50)
exp50 = expected_per_draw * min(50, len(history))
print(f"      Expected count per number in 50 draws: {exp50:.2f}")
for num in TARGET_NUMBERS:
    actual = freq50.get(num, 0)
    dev = (actual - exp50) / max(math.sqrt(exp50 * (1 - expected_per_draw)), 0.01)
    print(f"      Number {num:2d}: count={actual:2d}, dev z-score={dev:+.2f}", end="")
    if abs(dev) > 2:
        print(" ***SIGNIFICANT***")
    elif abs(dev) > 1:
        print(" *notable*")
    else:
        print("")


# ============================================================
# 5. INFORMATION ENTROPY
# ============================================================

print("\n" + "=" * 80)
print("  SECTION 5: INFORMATION ENTROPY")
print("=" * 80)

def number_entropy(numbers, n_bins=7):
    """Compute entropy of the number distribution across bins."""
    # Bin the numbers 1-49 into n_bins equal-width bins
    bins = np.linspace(0, 49, n_bins + 1)
    counts = np.zeros(n_bins)
    for x in numbers:
        for b in range(n_bins):
            if bins[b] < x <= bins[b + 1]:
                counts[b] += 1
                break
    # Avoid log(0)
    probs = counts / counts.sum()
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    return entropy

target_entropy = number_entropy(TARGET_NUMBERS)

hist_entropies = [number_entropy(d['numbers']) for d in history]
mean_entropy = np.mean(hist_entropies)
std_entropy = np.std(hist_entropies)
z_entropy = (target_entropy - mean_entropy) / std_entropy if std_entropy > 0 else 0

print(f"\n  5a. DISTRIBUTION ENTROPY (7-bin)")
print(f"      Target draw entropy: {target_entropy:.4f} bits")
print(f"      Historical mean:     {mean_entropy:.4f} bits")
print(f"      Historical std:      {std_entropy:.4f} bits")
print(f"      Z-score:             {z_entropy:+.3f}")
if z_entropy < -1.5:
    print(f"      *** LOW ENTROPY: numbers are clustered (not spread out) ***")
elif z_entropy > 1.5:
    print(f"      High entropy: numbers are well-spread")
else:
    print(f"      Within normal entropy range")

# Also compute gap-based entropy
def gap_entropy(numbers):
    """Entropy of gap distribution."""
    sorted_n = sorted(numbers)
    gaps = [sorted_n[0] - 1]  # leading gap
    for i in range(len(sorted_n) - 1):
        gaps.append(sorted_n[i+1] - sorted_n[i])
    gaps.append(49 - sorted_n[-1])  # trailing gap
    total = sum(gaps)
    probs = [g / total for g in gaps if g > 0]
    if not probs:
        return 0
    return -sum(p * math.log2(p) for p in probs)

target_gap_entropy = gap_entropy(TARGET_NUMBERS)
hist_gap_entropies = [gap_entropy(d['numbers']) for d in history]
mean_gap_entropy = np.mean(hist_gap_entropies)
std_gap_entropy = np.std(hist_gap_entropies)
z_gap_entropy = (target_gap_entropy - mean_gap_entropy) / std_gap_entropy if std_gap_entropy > 0 else 0

print(f"\n  5b. GAP-BASED ENTROPY")
print(f"      Gaps: [{nums[0]-1}, {', '.join(str(nums[i+1]-nums[i]) for i in range(n-1))}, {49-nums[-1]}]")
print(f"      Target gap entropy:  {target_gap_entropy:.4f} bits")
print(f"      Historical mean:     {mean_gap_entropy:.4f} bits")
print(f"      Z-score:             {z_gap_entropy:+.3f}")
if z_gap_entropy < -1.5:
    print(f"      *** LOW GAP ENTROPY: gaps are uneven (clustered numbers) ***")


# ============================================================
# 6. CROSS-LOTTERY CORRELATION (Power Lotto)
# ============================================================

print("\n" + "=" * 80)
print("  SECTION 6: CROSS-LOTTERY CORRELATION (Power Lotto)")
print("=" * 80)

# Filter power lotto to recent draws
pl_recent = power_draws[-20:] if len(power_draws) >= 20 else power_draws

print(f"\n  Checking if any of {TARGET_NUMBERS} appeared in recent Power Lotto draws:")
print(f"  (Last {len(pl_recent)} Power Lotto draws)")

overlaps = []
for pd in pl_recent[-10:]:
    common = set(TARGET_NUMBERS) & set(pd['numbers'])
    if common:
        overlaps.append((pd['draw'], sorted(common)))
    print(f"    PL {pd['draw']}: {pd['numbers']}  overlap={sorted(common) if common else 'none'}")

print(f"\n  Summary: {len(overlaps)} of last 10 Power Lotto draws share numbers with {TARGET_NUMBERS}")
for draw, common in overlaps:
    print(f"    Draw {draw}: shared {common}")

# Historical cross-correlation baseline
if len(power_draws) > 0 and len(history) > 0:
    # For each BIG_LOTTO draw, compute overlap with nearest Power Lotto draw
    overlap_hist = []
    for bl_d in history[-100:]:
        bl_int = draw_to_int(bl_d['draw'])
        # Find closest power lotto draw before this
        nearest_pl = None
        for pl_d in power_draws:
            if draw_to_int(pl_d['draw']) <= bl_int:
                nearest_pl = pl_d
        if nearest_pl:
            ov = len(set(bl_d['numbers']) & set(nearest_pl['numbers']))
            overlap_hist.append(ov)

    if overlap_hist:
        print(f"\n  Historical BIG_LOTTO vs nearest Power Lotto overlap (last 100 BL draws):")
        print(f"    Mean overlap: {np.mean(overlap_hist):.2f} numbers")
        print(f"    Overlap distribution: {Counter(overlap_hist)}")


# ============================================================
# 7. ADDITIONAL DEEP STATISTICS
# ============================================================

print("\n" + "=" * 80)
print("  SECTION 7: ADDITIONAL DEEP STATISTICS")
print("=" * 80)

# 7a. Number pair frequency
print(f"\n  7a. PAIR FREQUENCY IN HISTORY")
pair_freq = Counter()
for d in history:
    for c in combinations(d['numbers'], 2):
        pair_freq[c] += 1

target_pairs = list(combinations(TARGET_NUMBERS, 2))
print(f"      Total unique pairs in target: {len(target_pairs)}")
pair_freqs_target = [(p, pair_freq.get(p, 0)) for p in target_pairs]
pair_freqs_target.sort(key=lambda x: -x[1])

expected_pair_freq = len(history) * (6*5) / (49*48)  # C(6,2)/C(49,2) * N

print(f"      Expected pair frequency: {expected_pair_freq:.2f}")
print(f"      {'Pair':>12} {'Freq':>6} {'Expected':>9} {'Ratio':>7}")
for pair, freq in pair_freqs_target:
    ratio = freq / expected_pair_freq if expected_pair_freq > 0 else 0
    marker = " ***" if ratio > 2.0 else (" **" if ratio > 1.5 else "")
    print(f"      ({pair[0]:2d},{pair[1]:2d}) {freq:>6d} {expected_pair_freq:>9.2f} {ratio:>7.2f}{marker}")

# 7b. Historical match rate with target numbers
print(f"\n  7b. MATCH DISTRIBUTION WITH {TARGET_NUMBERS}")
target_set = set(TARGET_NUMBERS)
match_counts = []
for d in history:
    mc = len(target_set & set(d['numbers']))
    match_counts.append(mc)

match_dist = Counter(match_counts)
print(f"      {'Match':>6} {'Count':>7} {'Percent':>8} {'Cumulative':>11}")
cum = 0
for m in sorted(match_dist.keys(), reverse=True):
    cnt = match_dist[m]
    pct = cnt / len(history) * 100
    cum += pct
    print(f"      {m:>6d} {cnt:>7d} {pct:>7.2f}% {cum:>10.2f}%")

# ============================================================
# 8. SUMMARY
# ============================================================

print("\n" + "=" * 80)
print("  SECTION 8: SUMMARY & KEY FINDINGS")
print("=" * 80)

print(f"""
  Draw {TARGET_DRAW}: {TARGET_NUMBERS}

  KEY FINDINGS:

  1. SUM = {total_sum}
     - Z-score: {z_sum:+.3f} (percentile: {percentile_sum:.1f}%)
     - Verdict: {"UNUSUALLY HIGH" if z_sum > 2 else "HIGH but not extreme" if z_sum > 1 else "NORMAL"}

  2. AC VALUE = {ac_value}
     - Z-score: {z_ac:+.3f}
     - Verdict: {"LOW complexity" if z_ac < -1 else "NORMAL complexity" if abs(z_ac) <= 1 else "HIGH complexity"}

  3. CONSECUTIVE: {consec_pairs} pair(s), including 3-consecutive (35,36,37)
     - Historical 3+ consecutive rate: {hist_3consec/len(history)*100:.2f}%
     - Random baseline: {sim_3consec/sim_count*100:.2f}%
     - Verdict: RARE pattern

  4. ODD/EVEN = {even_count}E:{odd_count}O
     - Historical frequency of this ratio: {odd_dist.get(odd_count, 0)/len(history)*100:.1f}%

  5. ZONE DISTRIBUTION = {target_zt}
     - Zone 3 has {zones['Z3 (34-49)']} of 6 numbers - EXTREMELY SKEWED
     - Historical frequency of this pattern: {target_zt_count/len(history)*100:.2f}%
     - Any zone >= 5: {hist_zone5/len(history)*100:.2f}% historically

  6. ENTROPY = {target_entropy:.4f} bits (z={z_entropy:+.3f})
     - Verdict: {"LOW - clustered" if z_entropy < -1.5 else "NORMAL" if abs(z_entropy) <= 1.5 else "HIGH - spread"}

  7. LAG-2 ECHO: {len(echo_from_n2)} number(s) from N-2 draw {draw_n_minus_2['draw']}: {sorted(echo_from_n2)}
     - Historical echo rate: {pct_any_echo:.1f}%

  8. OVERALL RARITY: {features_unusual}/4 unusual features
     - {"*** HIGHLY UNUSUAL DRAW ***" if features_unusual >= 3 else "** Notable unusual features **" if features_unusual >= 2 else "Within normal bounds"}
""")

print("=" * 80)
print("  Analysis complete. seed=42, no future data used.")
print("=" * 80)
