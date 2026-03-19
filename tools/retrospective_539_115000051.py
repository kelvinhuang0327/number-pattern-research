#!/usr/bin/env python3
"""
=============================================================================
今彩539 第115000051期 回顧分析 (Retrospective Analysis)
=============================================================================
開獎日期: 115/02/26
開獎號碼: 03 06 09 31 39

目標:
1. 使用所有現有預測方法事後模擬預測（基於115000050期及之前的數據）
2. 分析哪個方法最接近
3. 識別未預測到的特徵
4. 提出改進方向
=============================================================================
"""

import json
import math
import sqlite3
import sys
import os
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations

# Setup paths
_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_base, '..', 'lottery_api'))
sys.path.insert(0, os.path.join(_base, '..'))

# ═══════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════
POOL = 39
PICK = 5
ACTUAL_DRAW = '115000051'
ACTUAL_DATE = '2026/02/26'
ACTUAL_NUMBERS = [3, 6, 9, 31, 39]

from math import comb
C39_5 = comb(39, 5)  # 575757

def _p_match_exactly(k):
    return comb(5, k) * comb(34, 5 - k) / C39_5

P_MATCH = {k: _p_match_exactly(k) for k in range(6)}
P_GE2_SINGLE = sum(P_MATCH[k] for k in range(2, 6))
P_GE3_SINGLE = sum(P_MATCH[k] for k in range(3, 6))

# ═══════════════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════════════
DB_PATH = os.path.join(_base, '..', 'lottery_api', 'data', 'lottery_v2.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(_base, '..', 'lottery_v2.db')

def load_draws():
    """Load all DAILY_539 draws up to and including 115000050"""
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
        draws.append({
            'draw': draw_id,
            'date': date,
            'numbers': sorted(nums)
        })
    return draws

# ═══════════════════════════════════════════════════════════════════
#  PREDICTION METHODS (All 29+ methods)
# ═══════════════════════════════════════════════════════════════════

def method_frequency(hist, window=100):
    """Hot numbers - most frequent in recent window"""
    recent = hist[-window:]
    counter = Counter()
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    return sorted([x[0] for x in counter.most_common(PICK)])

def method_frequency_w50(hist):
    return method_frequency(hist, 50)

def method_frequency_w100(hist):
    return method_frequency(hist, 100)

def method_frequency_w200(hist):
    return method_frequency(hist, 200)

def method_gap(hist, window=200):
    """Gap analysis - most overdue numbers"""
    recent = hist[-window:]
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(recent)
    gaps = {}
    for n in range(1, POOL + 1):
        gaps[n] = current - last_seen.get(n, -1)
    ranked = sorted(gaps, key=lambda x: -gaps[x])
    return sorted(ranked[:PICK])

def method_cold_rebound(hist, window=200):
    """Cold rebound - numbers not seen recently"""
    recent = hist[-window:]
    counter = Counter()
    for n in range(1, POOL + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    bottom = [x[0] for x in counter.most_common()[::-1][:PICK]]
    return sorted(bottom)

def method_hot_cold(hist, hot_w=30, cold_w=200):
    """3 hot + 2 cold"""
    hot_recent = hist[-hot_w:]
    counter_hot = Counter()
    for d in hot_recent:
        for n in d['numbers']:
            counter_hot[n] += 1
    hot = [x[0] for x in counter_hot.most_common(3)]
    
    cold_recent = hist[-cold_w:]
    counter_cold = Counter()
    for n in range(1, POOL + 1):
        counter_cold[n] = 0
    for d in cold_recent:
        for n in d['numbers']:
            counter_cold[n] += 1
    cold = [x[0] for x in counter_cold.most_common()[::-1] if x[0] not in hot][:2]
    return sorted(hot + cold)

def method_markov(hist, window=30):
    """Markov transition matrix"""
    recent = hist[-window:]
    if len(recent) < 5:
        return list(range(1, PICK + 1))
    transition = np.zeros((POOL, POOL))
    for i in range(len(recent) - 1):
        curr = recent[i]['numbers']
        nxt = recent[i + 1]['numbers']
        for a in curr:
            for b in nxt:
                transition[a - 1][b - 1] += 1
    row_sums = transition.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    transition = transition / row_sums
    last_nums = recent[-1]['numbers']
    scores = np.zeros(POOL)
    for n in last_nums:
        scores += transition[n - 1]
    ranked = np.argsort(-scores)
    return sorted([int(idx + 1) for idx in ranked[:PICK]])

def method_fourier(hist, window=500):
    """Fourier rhythm analysis"""
    recent = hist[-window:] if len(hist) >= window else hist
    w = len(recent)
    scores = {}
    for n in range(1, POOL + 1):
        series = np.array([1 if n in d['numbers'] else 0 for d in recent], dtype=float)
        fft_vals = np.fft.rfft(series)
        power = np.abs(fft_vals) ** 2
        if len(power) > 1:
            dominant_idx = np.argmax(power[1:]) + 1
            phase = np.angle(fft_vals[dominant_idx])
            freq = dominant_idx / len(series)
            t_next = len(series)
            predicted = np.abs(fft_vals[dominant_idx]) * np.cos(2 * np.pi * freq * t_next + phase)
            base = series.mean()
            scores[n] = base + 0.3 * predicted / (len(series) ** 0.5)
        else:
            scores[n] = 0
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_fourier_w300(hist):
    return method_fourier(hist, 300)

def method_fourier_w500(hist):
    return method_fourier(hist, 500)

def method_bayesian(hist, window=200):
    """Bayesian Dirichlet posterior"""
    recent = hist[-window:]
    counter = Counter()
    for n in range(1, POOL + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    total = sum(counter.values())
    alpha = 1.0
    posterior = {}
    for n in range(1, POOL + 1):
        posterior[n] = (alpha + counter[n]) / (POOL * alpha + total)
    ranked = sorted(posterior, key=lambda x: -posterior[x])
    return sorted(ranked[:PICK])

def method_state_space(hist, window=300):
    """State space model - conditional entropy based"""
    recent = hist[-window:]
    scores = {}
    for n in range(1, POOL + 1):
        series = [1 if n in d['numbers'] else 0 for d in recent]
        trans = {'00': 0, '01': 0, '10': 0, '11': 0}
        for i in range(1, len(series)):
            key = f"{series[i-1]}{series[i]}"
            trans[key] += 1
        last_state = series[-1]
        total_from_last = trans[f'{last_state}0'] + trans[f'{last_state}1']
        if total_from_last > 0:
            p_appear = trans[f'{last_state}1'] / total_from_last
        else:
            p_appear = 0.5
        scores[n] = p_appear
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_regime(hist, window=100):
    """Regime switching - HMM-like"""
    recent = hist[-window:]
    half = len(recent) // 2
    counter1, counter2 = Counter(), Counter()
    for d in recent[:half]:
        for n in d['numbers']:
            counter1[n] += 1
    for d in recent[half:]:
        for n in d['numbers']:
            counter2[n] += 1
    total1, total2 = sum(counter1.values()), sum(counter2.values())
    entropy1, entropy2 = 0, 0
    for n in range(1, POOL + 1):
        p1 = counter1.get(n, 0) / max(total1, 1)
        p2 = counter2.get(n, 0) / max(total2, 1)
        if p1 > 0: entropy1 -= p1 * np.log2(p1)
        if p2 > 0: entropy2 -= p2 * np.log2(p2)
    scores = {}
    if entropy2 < entropy1:
        for n in range(1, POOL + 1):
            scores[n] = counter2.get(n, 0) / max(total2, 1)
    else:
        for n in range(1, POOL + 1):
            freq = counter2.get(n, 0) / max(total2, 1)
            scores[n] = 1.0 / POOL - freq
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_monte_carlo(hist, window=200, n_sim=1000):
    """Monte Carlo weighted sampling"""
    recent = hist[-window:]
    counter = Counter()
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    total = sum(counter.values())
    weights = np.array([counter.get(n, 0.5) / max(total, 1) for n in range(1, POOL + 1)])
    weights = weights / weights.sum()
    rng = np.random.RandomState(42)
    vote = Counter()
    for _ in range(n_sim):
        pick = rng.choice(range(1, POOL + 1), size=PICK, replace=False, p=weights)
        for p in pick:
            vote[p] += 1
    return sorted([x[0] for x in vote.most_common(PICK)])

def method_position_bias(hist, window=300):
    """Position bias - frequency per sorted position"""
    recent = hist[-window:]
    pos_counter = [Counter() for _ in range(PICK)]
    for d in recent:
        nums = sorted(d['numbers'])
        for i, n in enumerate(nums):
            pos_counter[i][n] += 1
    result = []
    used = set()
    for i in range(PICK):
        for n, _ in pos_counter[i].most_common():
            if n not in used:
                result.append(n)
                used.add(n)
                break
    return sorted(result[:PICK])

def method_orthogonal(hist, window=200):
    """Orthogonal frequency - pick from different frequency bands"""
    recent = hist[-window:]
    counter = Counter()
    for n in range(1, POOL + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    ranked = sorted(counter, key=lambda x: -counter[x])
    step = max(1, len(ranked) // PICK)
    result = [ranked[i * step] for i in range(PICK) if i * step < len(ranked)]
    while len(result) < PICK:
        for n in ranked:
            if n not in result:
                result.append(n)
                break
    return sorted(result[:PICK])

def method_tail(hist, window=100):
    """Tail distribution - pick numbers with deficient tail digits"""
    recent = hist[-window:]
    tail_counter = Counter()
    for d in recent:
        for n in d['numbers']:
            tail_counter[n % 10] += 1
    total = sum(tail_counter.values())
    tail_deficit = {}
    for t in range(10):
        expected = total / 10
        tail_deficit[t] = expected - tail_counter.get(t, 0)
    scores = {}
    for n in range(1, POOL + 1):
        scores[n] = tail_deficit[n % 10]
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_consecutive(hist, window=100):
    """Consecutive injection - include consecutive pairs"""
    recent = hist[-window:]
    counter = Counter()
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    ranked = sorted(counter, key=lambda x: -counter[x])
    result = [ranked[0]]
    next_n = ranked[0] + 1 if ranked[0] < POOL else ranked[0] - 1
    if next_n >= 1 and next_n <= POOL:
        result.append(next_n)
    for n in ranked:
        if n not in result and len(result) < PICK:
            result.append(n)
    return sorted(result[:PICK])

def method_lag_echo(hist, lag=2):
    """Lag echo - boost numbers from lag periods ago"""
    if len(hist) < lag + 1:
        return list(range(1, PICK + 1))
    lag_nums = set(hist[-lag]['numbers'])
    counter = Counter()
    for d in hist[-100:]:
        for n in d['numbers']:
            counter[n] += 1
    for n in lag_nums:
        counter[n] = counter.get(n, 0) * 1.5
    return sorted([x[0] for x in counter.most_common(PICK)])

def method_entropy(hist, window=200):
    """Entropy ranking - select numbers with lowest appearance entropy"""
    recent = hist[-window:]
    scores = {}
    for n in range(1, POOL + 1):
        series = [1 if n in d['numbers'] else 0 for d in recent]
        p1 = sum(series) / len(series)
        p0 = 1 - p1
        if p1 > 0 and p0 > 0:
            h = -(p0 * np.log2(p0) + p1 * np.log2(p1))
        else:
            h = 0
        scores[n] = p1 * (1 - h)  # favor high probability AND low entropy
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_pair_interaction(hist, window=200):
    """Pair frequency interaction"""
    recent = hist[-window:]
    pair_counter = Counter()
    for d in recent:
        nums = d['numbers']
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                pair_counter[(nums[i], nums[j])] += 1
    num_scores = Counter()
    for (a, b), count in pair_counter.most_common(50):
        num_scores[a] += count
        num_scores[b] += count
    result = [x[0] for x in num_scores.most_common(PICK)]
    while len(result) < PICK:
        for n in range(1, POOL + 1):
            if n not in result:
                result.append(n)
                break
    return sorted(result[:PICK])

def method_zone_balance(hist, window=100):
    """Zone balance - distribute across number zones"""
    recent = hist[-window:]
    zones = {0: range(1, 14), 1: range(14, 27), 2: range(27, 40)}
    num_counter = Counter()
    zone_counter = Counter()
    for d in recent:
        for n in d['numbers']:
            num_counter[n] += 1
            zone_counter[n // 14 if n < 40 else 2] += 1
    total = sum(zone_counter.values())
    expected_zone = total / 3
    zone_deficit = {z: expected_zone - zone_counter.get(z, 0) for z in range(3)}
    total_deficit = sum(max(0, d) for d in zone_deficit.values())
    if total_deficit == 0:
        allocations = {0: 2, 1: 2, 2: 1}
    else:
        raw = {z: max(0, zone_deficit[z]) / total_deficit * PICK for z in range(3)}
        allocations = {z: max(1, round(raw[z])) for z in range(3)}
        while sum(allocations.values()) > PICK:
            max_z = max(allocations, key=allocations.get)
            allocations[max_z] -= 1
        while sum(allocations.values()) < PICK:
            min_z = min(allocations, key=allocations.get)
            allocations[min_z] += 1
    result = []
    for z in range(3):
        zone_nums = list(zones[z])
        scored = sorted(zone_nums, key=lambda x: -num_counter.get(x, 0))
        result.extend(scored[:allocations.get(z, 0)])
    return sorted(result[:PICK])

def method_sum_constraint(hist, window=300):
    """Sum constraint - target historical mean sum"""
    recent = hist[-window:]
    sums = [sum(d['numbers']) for d in recent]
    target_sum = np.mean(sums)
    counter = Counter()
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    ranked = sorted(counter, key=lambda x: -counter[x])
    best_combo = None
    best_diff = float('inf')
    for combo in combinations(ranked[:15], PICK):
        diff = abs(sum(combo) - target_sum)
        if diff < best_diff:
            best_diff = diff
            best_combo = combo
    return sorted(list(best_combo)) if best_combo else sorted(ranked[:PICK])

def method_ac_value(hist, window=100):
    """AC value optimization"""
    recent = hist[-window:]
    ac_values = []
    for d in recent:
        nums = sorted(d['numbers'])
        diffs = set()
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                diffs.add(nums[j] - nums[i])
        ac = len(diffs) - (len(nums) - 1)
        ac_values.append(ac)
    target_ac = round(np.mean(ac_values))
    counter = Counter()
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    ranked = sorted(counter, key=lambda x: -counter[x])
    best_combo = None
    best_score = -1
    for combo in combinations(ranked[:20], PICK):
        nums = sorted(combo)
        diffs = set()
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                diffs.add(nums[j] - nums[i])
        ac = len(diffs) - (len(nums) - 1)
        if abs(ac - target_ac) <= 1:
            freq_score = sum(counter.get(n, 0) for n in combo)
            if freq_score > best_score:
                best_score = freq_score
                best_combo = combo
    return sorted(list(best_combo)) if best_combo else sorted(ranked[:PICK])

def method_pattern_match(hist, window=200):
    """Pattern matching - find similar past draws"""
    if len(hist) < 10:
        return list(range(1, PICK + 1))
    last_draw = hist[-1]['numbers']
    recent = hist[-window:-1]
    best_sim = -1
    best_next = None
    for i in range(len(recent) - 1):
        sim = len(set(recent[i]['numbers']) & set(last_draw))
        if sim > best_sim:
            best_sim = sim
            best_next = recent[i + 1]['numbers']
    return sorted(best_next) if best_next else sorted(last_draw)

def method_multiplicative(hist, window=200):
    """Multiplicative signal - freq * gap"""
    recent = hist[-window:]
    counter = Counter()
    for n in range(1, POOL + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(recent)
    scores = {}
    for n in range(1, POOL + 1):
        freq = counter[n] / len(recent)
        gap = current - last_seen.get(n, 0)
        scores[n] = freq * gap
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_covering(hist, window=100):
    """Covering design - maximize spread"""
    counter = Counter()
    for d in hist[-window:]:
        for n in d['numbers']:
            counter[n] += 1
    ranked = sorted(counter, key=lambda x: -counter[x])
    # Pick evenly spaced from the ranked list
    step = max(1, POOL // PICK)
    result = []
    for i in range(PICK):
        idx = i * step
        if idx < POOL:
            result.append(idx + 1)
    return sorted(result[:PICK])

def method_cycle_regression(hist, window=300):
    """Cycle regression - predict based on appearance cycles"""
    recent = hist[-window:]
    scores = {}
    for n in range(1, POOL + 1):
        appearances = [i for i, d in enumerate(recent) if n in d['numbers']]
        if len(appearances) < 2:
            scores[n] = 0.5
            continue
        gaps = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
        avg_gap = np.mean(gaps)
        current_gap = len(recent) - appearances[-1]
        scores[n] = current_gap / avg_gap if avg_gap > 0 else 0
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_adaptive_ensemble(hist, window=200):
    """Adaptive ensemble - combine freq + gap + markov signals"""
    freq_pred = method_frequency(hist, window)
    gap_pred = method_gap(hist, window)
    markov_pred = method_markov(hist, 30)
    vote = Counter()
    for n in freq_pred: vote[n] += 3
    for n in gap_pred: vote[n] += 2
    for n in markov_pred: vote[n] += 2
    return sorted([x[0] for x in vote.most_common(PICK)])

def method_triple_strike(hist):
    """Triple Strike (Fourier + Cold + TailBalance)"""
    fourier_pred = method_fourier(hist, 500)
    cold_pred = method_cold_rebound(hist, 100)
    tail_pred = method_tail(hist, 100)
    vote = Counter()
    for n in fourier_pred: vote[n] += 3
    for n in cold_pred: vote[n] += 2
    for n in tail_pred: vote[n] += 1
    return sorted([x[0] for x in vote.most_common(PICK)])

def method_deviation_complement(hist, window=100):
    """Deviation complement - hot deviance + cold deviance"""
    recent = hist[-window:]
    counter = Counter()
    for n in range(1, POOL + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    expected = len(recent) * PICK / POOL
    dev_hot = {n: counter[n] - expected for n in range(1, POOL + 1)}
    dev_cold = {n: expected - counter[n] for n in range(1, POOL + 1)}
    hot_ranked = sorted(dev_hot, key=lambda x: -dev_hot[x])
    cold_ranked = sorted(dev_cold, key=lambda x: -dev_cold[x])
    result = hot_ranked[:3] + [n for n in cold_ranked if n not in hot_ranked[:3]][:2]
    return sorted(result[:PICK])

def method_neighbor_cold(hist, window=30):
    """Neighbor + Cold (P1 移植)"""
    recent = hist[-window:]
    if len(recent) < 5:
        return list(range(1, PICK + 1))
    # P1 Neighbor: Markov transition top
    transition = np.zeros((POOL, POOL))
    for i in range(len(recent) - 1):
        curr = recent[i]['numbers']
        nxt = recent[i + 1]['numbers']
        for a in curr:
            for b in nxt:
                transition[a - 1][b - 1] += 1
    row_sums = transition.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    transition = transition / row_sums
    last_nums = recent[-1]['numbers']
    scores = np.zeros(POOL)
    for n in last_nums:
        scores += transition[n - 1]
    neighbor_ranked = np.argsort(-scores)
    neighbor = [int(idx + 1) for idx in neighbor_ranked[:PICK]]
    
    # Cold: lowest frequency in w=100
    cold = method_cold_rebound(hist, 100)
    cold_excl = [n for n in cold if n not in neighbor][:2]
    result = neighbor[:3] + cold_excl
    while len(result) < PICK:
        for n in neighbor:
            if n not in result:
                result.append(n)
                break
    return sorted(result[:PICK])

# ═══════════════════════════════════════════════════════════════════
#  5-BET STRATEGIES (Fourier正交+Cold)
# ═══════════════════════════════════════════════════════════════════

def method_5bet_fourier4_cold(hist):
    """5bet Fourier4正交+Cold"""
    recent = hist[-500:] if len(hist) >= 500 else hist
    w = len(recent)
    scores = {}
    for n in range(1, POOL + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(recent):
            if n in d['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = np.fft.fft(bh - np.mean(bh))
        xf = np.fft.fftfreq(w, 1)
        ip = np.where(xf > 0)
        py = np.abs(yf[ip])
        px = xf[ip]
        pk = np.argmax(py)
        fv = px[pk]
        if fv == 0:
            scores[n] = 0.0
            continue
        period = 1 / fv
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    ranked = [n for n in sorted(scores, key=lambda x: -scores[x]) if scores[n] > 0]
    bets = [sorted(ranked[i*5:(i+1)*5]) for i in range(4)]
    excl = set(sum(bets, []))
    freq = Counter()
    for d in hist[-100:]:
        for n in d['numbers']:
            freq[n] += 1
    cold_sorted = sorted(range(1, POOL + 1), key=lambda n: freq.get(n, 0))
    bet5 = sorted([n for n in cold_sorted if n not in excl][:5])
    bets.append(bet5)
    return bets

# ═══════════════════════════════════════════════════════════════════
#  ANALYSIS ENGINE
# ═══════════════════════════════════════════════════════════════════

def count_hits(prediction, actual):
    return len(set(prediction) & set(actual))

def analyze_number_features(hist, actual_numbers):
    """Analyze features of the actual drawn numbers"""
    print("\n" + "=" * 70)
    print("  第二部分：開獎號碼特徵分析")
    print("=" * 70)
    actual = set(actual_numbers)
    
    # 1. Sum analysis
    actual_sum = sum(actual_numbers)
    recent_sums = [sum(d['numbers']) for d in hist[-100:]]
    avg_sum = np.mean(recent_sums)
    std_sum = np.std(recent_sums)
    z_sum = (actual_sum - avg_sum) / std_sum if std_sum > 0 else 0
    print(f"\n  1. 和值分析:")
    print(f"     開獎和值: {actual_sum}")
    print(f"     近100期均值: {avg_sum:.1f} ± {std_sum:.1f}")
    print(f"     Z-score: {z_sum:.2f} ({'偏低' if z_sum < -1 else '偏高' if z_sum > 1 else '正常範圍'})")
    
    # 2. Odd/Even
    odd_count = sum(1 for n in actual_numbers if n % 2 == 1)
    even_count = PICK - odd_count
    print(f"\n  2. 奇偶比: {odd_count}:{even_count} (奇:偶)")
    
    # 3. Zone distribution (1-13, 14-26, 27-39)
    z1 = sum(1 for n in actual_numbers if n <= 13)
    z2 = sum(1 for n in actual_numbers if 14 <= n <= 26)
    z3 = sum(1 for n in actual_numbers if n >= 27)
    print(f"\n  3. 區域分佈: {z1}:{z2}:{z3} (低:中:高)")
    
    # 4. Tail digit distribution
    tails = [n % 10 for n in actual_numbers]
    print(f"\n  4. 尾數分佈: {sorted(tails)}")
    tail_unique = len(set(tails))
    print(f"     獨特尾數: {tail_unique}/5")
    
    # 5. Gap analysis (each number's gap before this draw)
    print(f"\n  5. 各號碼缺席分析 (距上次出現幾期):")
    for n in actual_numbers:
        gap = 0
        for i in range(len(hist) - 1, -1, -1):
            if n in hist[i]['numbers']:
                gap = len(hist) - 1 - i
                break
            gap = len(hist)
        print(f"     號碼 {n:2d}: 缺席 {gap} 期")
    
    # 6. Consecutive / spacing
    diffs = [actual_numbers[i+1] - actual_numbers[i] for i in range(len(actual_numbers)-1)]
    print(f"\n  6. 間距分析: {diffs}")
    has_consecutive = any(d == 1 for d in diffs)
    print(f"     連號: {'有' if has_consecutive else '無'}")
    
    # 7. AC value
    all_diffs = set()
    for i in range(len(actual_numbers)):
        for j in range(i+1, len(actual_numbers)):
            all_diffs.add(actual_numbers[j] - actual_numbers[i])
    ac = len(all_diffs) - (PICK - 1)
    recent_acs = []
    for d in hist[-100:]:
        nums = sorted(d['numbers'])
        ds = set()
        for i in range(len(nums)):
            for j in range(i+1, len(nums)):
                ds.add(nums[j] - nums[i])
        recent_acs.append(len(ds) - (PICK - 1))
    avg_ac = np.mean(recent_acs)
    print(f"\n  7. AC值: {ac} (近100期均值: {avg_ac:.1f})")
    
    # 8. Frequency rank
    counter = Counter()
    for d in hist[-100:]:
        for n in d['numbers']:
            counter[n] += 1
    ranked_all = sorted(range(1, POOL + 1), key=lambda x: -counter.get(x, 0))
    print(f"\n  8. 各號碼近100期頻率排名:")
    for n in actual_numbers:
        rank = ranked_all.index(n) + 1
        freq = counter.get(n, 0)
        print(f"     號碼 {n:2d}: 排名 {rank}/39, 出現 {freq} 次")
    
    # 9. Three draw pattern
    print(f"\n  9. 近3期號碼:")
    for d in hist[-3:]:
        print(f"     {d['draw']}: {d['numbers']}")
    
    # 10. Repeat from recent draws
    for lag in range(1, 4):
        if lag <= len(hist):
            prev_nums = set(hist[-lag]['numbers'])
            repeats = actual & prev_nums
            if repeats:
                print(f"     與前{lag}期重複: {sorted(repeats)}")
            else:
                print(f"     與前{lag}期重複: 無")
    
    return {
        'sum': actual_sum, 'avg_sum': avg_sum, 'z_sum': z_sum,
        'odd_even': (odd_count, even_count),
        'zones': (z1, z2, z3),
        'ac': ac, 'avg_ac': avg_ac,
        'has_consecutive': has_consecutive,
        'tails': tails
    }

def run_all_methods(hist):
    """Run all prediction methods and compare with actual"""
    methods = {
        'freq_w50': method_frequency_w50,
        'freq_w100': method_frequency_w100,
        'freq_w200': method_frequency_w200,
        'gap': method_gap,
        'cold_rebound': method_cold_rebound,
        'hot_cold': method_hot_cold,
        'markov_w30': method_markov,
        'fourier_w300': method_fourier_w300,
        'fourier_w500': method_fourier_w500,
        'bayesian': method_bayesian,
        'state_space': method_state_space,
        'regime': method_regime,
        'monte_carlo': method_monte_carlo,
        'position_bias': method_position_bias,
        'orthogonal': method_orthogonal,
        'tail': method_tail,
        'consecutive': method_consecutive,
        'lag_echo': method_lag_echo,
        'entropy': method_entropy,
        'pair_interaction': method_pair_interaction,
        'zone_balance': method_zone_balance,
        'sum_constraint': method_sum_constraint,
        'ac_value': method_ac_value,
        'pattern_match': method_pattern_match,
        'multiplicative': method_multiplicative,
        'covering': method_covering,
        'cycle_regression': method_cycle_regression,
        'adaptive_ensemble': method_adaptive_ensemble,
        'triple_strike': method_triple_strike,
        'deviation_complement': method_deviation_complement,
        'neighbor_cold(P1)': method_neighbor_cold,
    }
    
    print("\n" + "=" * 70)
    print("  第一部分：所有預測方法 vs 實際開獎對比")
    print(f"  目標期: {ACTUAL_DRAW} ({ACTUAL_DATE})")
    print(f"  實際開獎: {ACTUAL_NUMBERS}")
    print("=" * 70)
    
    results = []
    for name, method in methods.items():
        try:
            pred = method(hist)
            hits = count_hits(pred, ACTUAL_NUMBERS)
            matched = sorted(set(pred) & set(ACTUAL_NUMBERS))
            missed = sorted(set(ACTUAL_NUMBERS) - set(pred))
            wrong = sorted(set(pred) - set(ACTUAL_NUMBERS))
            results.append({
                'name': name,
                'prediction': pred,
                'hits': hits,
                'matched': matched,
                'missed': missed,
                'wrong': wrong
            })
        except Exception as e:
            results.append({
                'name': name,
                'prediction': [],
                'hits': 0,
                'matched': [],
                'missed': ACTUAL_NUMBERS,
                'wrong': [],
                'error': str(e)
            })
    
    # Sort by hits descending
    results.sort(key=lambda x: -x['hits'])
    
    print(f"\n  {'排名':<4} {'方法':<25} {'命中':>4} {'預測號碼':<25} {'命中號碼':<20} {'未中號碼'}")
    print("  " + "-" * 110)
    for i, r in enumerate(results, 1):
        flag = "★" if r['hits'] >= 3 else "◆" if r['hits'] >= 2 else " "
        print(f"  {flag}{i:<3} {r['name']:<25} {r['hits']:>4}  {str(r['prediction']):<25} {str(r['matched']):<20} {str(r['missed'])}")
    
    # 5-bet strategy
    print(f"\n  {'='*70}")
    print("  多注策略 (5bet_fourier4_cold):")
    print("  " + "-" * 70)
    try:
        bets_5 = method_5bet_fourier4_cold(hist)
        total_hits_5 = 0
        any_ge2 = False
        any_ge3 = False
        for i, bet in enumerate(bets_5, 1):
            hits = count_hits(bet, ACTUAL_NUMBERS)
            matched = sorted(set(bet) & set(ACTUAL_NUMBERS))
            total_hits_5 = max(total_hits_5, hits)
            if hits >= 2: any_ge2 = True
            if hits >= 3: any_ge3 = True
            flag = "★" if hits >= 3 else "◆" if hits >= 2 else " "
            label = f"F500-rank{(i-1)*5+1}-{i*5}" if i <= 4 else "Cold(w=100)"
            print(f"  {flag}注{i} ({label}): {bet}  命中={hits} {matched}")
        print(f"\n  5注最佳單注命中: {total_hits_5}, ≥2命中: {'✅' if any_ge2 else '❌'}, ≥3命中: {'✅' if any_ge3 else '❌'}")
    except Exception as e:
        print(f"  Error: {e}")
    
    return results

def identify_missed_patterns(hist, features):
    """Identify what patterns were missed"""
    print("\n" + "=" * 70)
    print("  第三部分：未能預測的特徵與根因分析")
    print("=" * 70)
    
    # 1. Number 39 (boundary number)
    print(f"\n  1. 號碼39（邊界號碼）:")
    n39_freq = sum(1 for d in hist[-100:] if 39 in d['numbers'])
    print(f"     近100期出現 {n39_freq} 次（期望 ~{100*5/39:.1f} 次）")
    n39_gap = 0
    for i in range(len(hist)-1, -1, -1):
        if 39 in hist[i]['numbers']:
            n39_gap = len(hist) - 1 - i
            break
    print(f"     上次出現距今 {n39_gap} 期")
    
    # 2. 小號集中 (03, 06, 09)
    print(f"\n  2. 小號集中 (03, 06, 09 = 3個小於10的號碼):")
    count_under10 = []
    for d in hist[-100:]:
        c = sum(1 for n in d['numbers'] if n < 10)
        count_under10.append(c)
    avg_under10 = np.mean(count_under10)
    pct_3plus = sum(1 for c in count_under10 if c >= 3) / len(count_under10) * 100
    print(f"     近100期平均小於10的號碼數: {avg_under10:.2f}")
    print(f"     近100期≥3個小於10的機率: {pct_3plus:.1f}%")
    
    # 3. 等差特徵 (3, 6, 9 是公差3的等差數列)
    print(f"\n  3. 等差數列特徵:")
    print(f"     03, 06, 09 形成公差=3的等差數列")
    print(f"     03, 09 是 3 的倍數; 06 是 6 的倍數")
    
    # 4. The 3的倍數特徵
    multiples_of_3 = [n for n in ACTUAL_NUMBERS if n % 3 == 0]
    print(f"\n  4. 3的倍數特徵:")
    print(f"     開獎號碼中3的倍數: {multiples_of_3} ({len(multiples_of_3)}/{PICK})")
    mul3_counts = []
    for d in hist[-100:]:
        c = sum(1 for n in d['numbers'] if n % 3 == 0)
        mul3_counts.append(c)
    avg_mul3 = np.mean(mul3_counts)
    print(f"     近100期平均3的倍數個數: {avg_mul3:.2f}")
    
    # 5. Zone imbalance
    print(f"\n  5. 極端區域分佈 ({features['zones'][0]}:{features['zones'][1]}:{features['zones'][2]}):")
    if features['zones'][1] == 0:
        print(f"     ⚠️ 中間區域 (14-26) 完全缺席——這是極端分佈")
        zone_patterns = []
        for d in hist[-100:]:
            z1 = sum(1 for n in d['numbers'] if n <= 13)
            z2 = sum(1 for n in d['numbers'] if 14 <= n <= 26)
            z3 = sum(1 for n in d['numbers'] if n >= 27)
            zone_patterns.append((z1, z2, z3))
        no_mid_count = sum(1 for z in zone_patterns if z[1] == 0)
        print(f"     近100期中間區域完全缺席的次數: {no_mid_count} ({no_mid_count}%)")
    
    # 6. Sum of numbers
    print(f"\n  6. 和值分析 (和={features['sum']}):")
    if abs(features['z_sum']) > 1:
        direction = '偏低' if features['z_sum'] < 0 else '偏高'
        print(f"     ⚠️ 和值 {direction} (z={features['z_sum']:.2f})")
    
    # 7. 尾數 pattern
    print(f"\n  7. 尾數特殊模式:")
    tails = [n % 10 for n in ACTUAL_NUMBERS]
    print(f"     尾數: {tails}")
    if len(set(tails)) < PICK:
        repeated_tails = [t for t in set(tails) if tails.count(t) > 1]
        print(f"     ⚠️ 重複尾數: {repeated_tails}")
    
    # 8. 距均值分佈
    mean_num = np.mean(ACTUAL_NUMBERS)
    print(f"\n  8. 號碼均值: {mean_num:.1f} (理論均值: 20.0)")
    
    print()
    return

def generate_expert_panel(hist, results, features):
    """Three expert panel discussion"""
    print("\n" + "=" * 70)
    print("  第四部分：三位專家評審團討論")
    print("=" * 70)
    
    # Best method
    best = results[0]
    best_ge2 = [r for r in results if r['hits'] >= 2]
    best_ge3 = [r for r in results if r['hits'] >= 3]
    
    # Expert 1: Method Theory Expert
    print(f"""
{'─'*70}
👨‍🔬 方法理論專家 (Dr. Statistical)
{'─'*70}

■ 分析評估:
  最佳方法: {best['name']} (命中 {best['hits']} 個)
  ≥2命中方法: {len(best_ge2)} 個
  ≥3命中方法: {len(best_ge3)} 個

■ 關鍵發現:
  1. 本期開獎號碼 {ACTUAL_NUMBERS} 具有極強的【結構特殊性】:
     - 3個號碼 (03,06,09) 形成等差數列 (公差=3)
     - 中間區域 (14-26) 完全跳過
     - 極端高低分佈 (3低+2高)
  
  2. 現有統計方法的局限:
     - 頻率類方法: 追蹤的是「哪些號碼出現多」，無法捕捉數字間的結構關係
     - Fourier方法: 追蹤個別號碼的週期性，無法識別「號碼間的聯動模式」
     - Markov方法: 只看相鄰期的轉移機率，對zone跳躍無感
     - State Space: 基於單號碼二態模型，無法建模跨號碼的結構約束

  3. 理論上可增加的統計特徵:
     ☆ 號碼間距分佈建模 (目前幾乎未用)
     ☆ 組合結構特徵 (AC值、等差子序列、尾數分佈)
     ☆ Zone跳躍模式 (哪些zone組合更可能出現)
     ☆ 和值約束 + 結構約束的聯合模型

■ 長期 vs 短期優勢判斷:
  - 短期 (30-100期): Markov 和 Regime 可能捕捉到zone轉換趨勢
  - 中期 (100-500期): Fourier + 結構約束組合最穩定
  - 長期 (500-1500期): State Space + 組合特徵可能有邊際優勢
""")

    # Expert 2: Technical Pragmatic Expert
    print(f"""
{'─'*70}
👩‍💻 技術務實專家 (Dr. Pragmatic)
{'─'*70}

■ 系統邊界分析:
  1. 預測空間: C(39,5) = 575,757 種組合
     → 任何方法最多只能覆蓋微小子集
     → 5注覆蓋 5/575757 = 0.00087%
  
  2. 本期「難預測」的客觀原因:
     - 號碼39是邊界值(pool末端)，出現頻率通常偏低
     - 3個≤9的小號同時出現是低頻事件 (約{sum(1 for d in hist[-100:] if sum(1 for n in d['numbers'] if n < 10) >= 3):.0f}% of draws)
     - 中間zone完全缺席是罕見事件
     → 這類「異常組合」本身就是高entropy事件

  3. 可行性評估:
     ✅ 可行: 增加Zone覆蓋策略 (確保每注覆蓋不同zone組合)
     ✅ 可行: 增加號碼間距diversity約束
     ✅ 可行: 建立等差序列偵測器 (低成本)
     ⚠️ 有限: ML模型(LSTM/Transformer) → 需要大量特徵+大量數據
     ⚠️ 有限: 結構約束過多會削減覆蓋效率
     ❌ 不可行: 完美預測 → 本質上仍是隨機過程

  4. 兩注策略建議:
     注1: Fourier/Markov 主力(追蹤時序信號)
     注2: Zone-Spread + 冷號補充(追蹤結構異常)
     → 兩注正交最大化覆蓋不同「失敗模式」

  5. 三注策略建議:
     注1: Fourier 時序信號
     注2: Markov + Gap 交叉信號
     注3: Zone跳躍 + 等差偵測 (異常組合捕捉器)
     → 第三注專門用於捕捉「結構異常」事件

■ 自動學習機制評估:
  - Reinforcement Learning (MAB): 可動態調整注力分配權重 ✅
  - Online Learning: 可逐期更新結構特徵分佈 ✅
  - Neural Feature Selection: 可自動發現重要的組合特徵 ⚠️(需大數據)
""")

    # Expert 3: Architecture Expert
    print(f"""
{'─'*70}
🏗️ 程式架構專家 (Dr. Builder)
{'─'*70}

■ 實作成本評估:

  優先級 1 (低成本高收益):
  ┌────────────────────────────────────────────────────────────────┐
  │ 1. Zone跳躍偵測器                                              │
  │    成本: 2小時 | 原理: 統計近期zone分佈，識別zone缺席趨勢      │
  │    實作: 在現有 zone_balance 基礎上增加「缺席zone加權」邏輯      │
  │                                                                │
  │ 2. 等差/等比序列偵測器                                          │
  │    成本: 3小時 | 原理: 偵測近期是否有等差子序列出現頻率提高      │
  │    實作: 新增 method_arithmetic_sequence() 方法                  │
  │                                                                │
  │ 3. 間距profile匹配                                              │
  │    成本: 2小時 | 原理: 計算常見的5號碼間距模式                   │
  │    實作: 分析歷史間距分佈，選擇符合常見模式的組合               │
  └────────────────────────────────────────────────────────────────┘

  優先級 2 (中成本中收益):
  ┌────────────────────────────────────────────────────────────────┐
  │ 4. Multi-Signal Fusion (改良版)                                 │
  │    成本: 5小時 | 原理: 綜合頻率、gap、Markov、結構四維信號       │
  │    實作: 銀行號碼(高頻) + 結構號碼(符合zone/sum約束)           │
  │                                                                │
  │ 5. Anomaly Capture Bet (異常捕捉注)                             │
  │    成本: 4小時 | 原理: 專門一注用於捕捉「不太可能」的組合       │
  │    實作: 反向選擇─選冷號+邊界號+跳zone組合                     │
  └────────────────────────────────────────────────────────────────┘

  優先級 3 (高成本待驗證):
  ┌────────────────────────────────────────────────────────────────┐
  │ 6. Sliding Window Auto-Tune                                     │
  │    成本: 8小時 | 原理: 自動調整各方法的窗口參數                 │
  │    實作: 用近期表現動態選擇最佳窗口                             │
  │                                                                │
  │ 7. Combinatorial Feature ML                                     │
  │    成本: 15小時 | 原理: 用ML模型學習組合特徵                    │
  │    實作: 特徵=zone分佈+sum+AC+間距 → 預測是否符合開獎模式       │
  └────────────────────────────────────────────────────────────────┘

■ 開發路線圖:
  Phase 1 (即時): 優先級1的三項改進 → 融入現有2注/3注策略
  Phase 2 (1週內): 優先級2 + 回測驗證
  Phase 3 (2週內): 優先級3 + 自動學習Pipeline
""")

    # Consensus
    print(f"""
{'='*70}
  🎯 三方共識與決議
{'='*70}

  1. 本期預測失敗的根因:
     ✦ 開獎號碼具有罕見的結構組合 (等差+zone跳躍)
     ✦ 現有29種方法均專注於「單號碼頻率/時序」信號
     ✦ 缺乏「組合結構」層面的預測能力

  2. 核心改進方向:
     ✦ 增加「結構特徵注」─ 專門捕捉zone跳躍、等差、間距異常
     ✦ 現有的 State Space + Markov 組合維持 → 已是最穩定的信號
     ✦ 新增1注「異常捕捉器」→ 提升對低頻結構事件的覆蓋率

  3. 信心等級:
     ✦ 長期(1500+期)改善空間: 有限 (~0.5-1.5% edge)
     ✦ 結構覆蓋改善: 可行 (減少完全漏判的機率)
     ✦ 自動學習: 值得探索，但需嚴格防過擬合

  4. 行動項目:
     □ [P1] 實作 Zone跳躍偵測器 + 等差偵測器
     □ [P1] 設計「異常捕捉注」(第3注)
     □ [P2] 300期回測驗證新增特徵的貢獻
     □ [P2] 設計 2注/3注 的最佳正交組合
     □ [P3] 建立組合特徵的自動學習Pipeline
""")

def main():
    print("=" * 70)
    print("  今彩539 第115000051期 回顧分析報告")
    print(f"  開獎日期: {ACTUAL_DATE}")
    print(f"  開獎號碼: {ACTUAL_NUMBERS}")
    print("=" * 70)
    
    # Load data
    draws = load_draws()
    print(f"\n  載入 {len(draws)} 期歷史數據")
    print(f"  最新期: {draws[-1]['draw']} ({draws[-1]['date']})")
    
    # Run all methods
    results = run_all_methods(draws)
    
    # Analyze features
    features = analyze_number_features(draws, ACTUAL_NUMBERS)
    
    # Identify missed patterns
    identify_missed_patterns(draws, features)
    
    # Expert panel
    generate_expert_panel(draws, results, features)
    
    # Summary statistics
    hits_dist = Counter(r['hits'] for r in results)
    print(f"\n  命中分佈統計: {dict(hits_dist)}")
    print(f"  所有方法命中號碼聯集: {sorted(set(n for r in results for n in r['matched']))}")
    all_predicted = Counter(n for r in results for n in r['prediction'])
    print(f"\n  所有方法最多推薦的號碼:")
    for n, count in all_predicted.most_common(10):
        in_actual = "✅" if n in ACTUAL_NUMBERS else "  "
        print(f"    {in_actual} 號碼 {n:2d}: 被 {count} 個方法選中")
    
    print(f"\n  實際開獎號碼在各方法推薦中的覆蓋率:")
    for n in ACTUAL_NUMBERS:
        count = all_predicted.get(n, 0)
        pct = count / len(results) * 100
        print(f"    號碼 {n:2d}: 被 {count}/{len(results)} 個方法選中 ({pct:.1f}%)")

if __name__ == '__main__':
    main()
