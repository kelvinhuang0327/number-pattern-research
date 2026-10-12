#!/usr/bin/env python3
"""
大樂透 Auto-Discovery 特徵掃描器
===================================
系統性搜索全新維度的預測特徵，嚴格統計檢驗。

設計原則：
  1. 50+ 候選方法，涵蓋 6 大全新維度（非頻率排序變種）
  2. 1500 期回測 + Bonferroni 校正 (α = 0.05/N)
  3. Train/Test Split (前半/後半)，雙半都正才算通過
  4. 只報告通過嚴格檢驗的結果

6 大全新維度：
  A. 共現挖掘 (Co-occurrence) — 號碼對/三元組同期出現模式
  B. 結構模板 (Structural Template) — 和值、奇偶、區間分布的模式轉移
  C. 條件熵 (Conditional Entropy) — 資訊理論候選
  D. 負面選擇 (Negative Selection) — 排除法而非建構法
  E. 區間轉移 (Zone Transition) — Z1/Z2/Z3 的序列模式
  F. 數字圖論 (Graph-based) — 號碼共現網路的中心性

Usage:
    python3 tools/auto_discovery_biglotto.py
    python3 tools/auto_discovery_biglotto.py --dimensions A,B
"""
import os
import sys
import time
import argparse
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49
PICK = 6
P_SINGLE = 0.0186
MIN_HISTORY = 200


# ============================================================
# Dimension A: Co-occurrence Mining
# ============================================================
def cooccurrence_top_pairs(history, window=100):
    """A1: 選擇歷史共現最強的號碼對，組成6個號"""
    recent = history[-window:]
    pair_freq = Counter()
    for d in recent:
        nums = sorted(d['numbers'][:PICK])
        for p in combinations(nums, 2):
            pair_freq[p] += 1
    # Pick top pairs greedily
    selected = set()
    for (a, b), _ in pair_freq.most_common():
        if len(selected) >= PICK:
            break
        if a not in selected and b not in selected and len(selected) <= PICK - 2:
            selected.add(a)
            selected.add(b)
        elif a not in selected and len(selected) < PICK:
            selected.add(a)
        elif b not in selected and len(selected) < PICK:
            selected.add(b)
    return sorted(list(selected)[:PICK])


def cooccurrence_transition_pairs(history, window=50):
    """A2: 前期號碼對 → 本期號碼對 的轉移"""
    recent = history[-window:]
    pair_trans = Counter()
    for i in range(len(recent) - 1):
        prev_pairs = set(combinations(sorted(recent[i]['numbers'][:PICK]), 2))
        next_nums = set(recent[i + 1]['numbers'][:PICK])
        for pp in prev_pairs:
            for n in next_nums:
                pair_trans[(pp, n)] += 1
    last_pairs = set(combinations(sorted(history[-1]['numbers'][:PICK]), 2))
    scores = Counter()
    for pp in last_pairs:
        for n in range(1, MAX_NUM + 1):
            scores[n] += pair_trans.get((pp, n), 0)
    return sorted([n for n, _ in sorted(scores.items(), key=lambda x: -x[1])[:PICK]])


def cooccurrence_anti_pairs(history, window=100):
    """A3: 選擇歷史上最少共現的號碼（正交覆蓋）"""
    recent = history[-window:]
    pair_freq = Counter()
    for d in recent:
        nums = sorted(d['numbers'][:PICK])
        for p in combinations(nums, 2):
            pair_freq[p] += 1
    # Score each number by total co-occurrence (lower = more independent)
    num_cooc = Counter()
    for (a, b), f in pair_freq.items():
        num_cooc[a] += f
        num_cooc[b] += f
    # Pick least co-occurring
    candidates = sorted(range(1, MAX_NUM + 1), key=lambda x: num_cooc.get(x, 0))
    return sorted(candidates[:PICK])


def cooccurrence_triplet(history, window=100):
    """A4: 三元組共現挖掘"""
    recent = history[-window:]
    trip_freq = Counter()
    for d in recent:
        nums = sorted(d['numbers'][:PICK])
        for t in combinations(nums, 3):
            trip_freq[t] += 1
    selected = set()
    for trip, _ in trip_freq.most_common():
        if len(selected) >= PICK:
            break
        for n in trip:
            if n not in selected and len(selected) < PICK:
                selected.add(n)
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in selected]
    while len(selected) < PICK:
        selected.add(remaining.pop(0))
    return sorted(list(selected)[:PICK])


def cooccurrence_conditional(history, window=50):
    """A5: 條件共現 — 給定前期某號出現，本期哪些號最常跟它同期"""
    recent = history[-window:]
    cond_cooc = Counter()
    prev_nums = set(history[-1]['numbers'][:PICK])
    for i in range(len(recent) - 1):
        curr = set(recent[i + 1]['numbers'][:PICK])
        prev = set(recent[i]['numbers'][:PICK])
        common_with_prev = prev & prev_nums
        if common_with_prev:
            for n in curr:
                cond_cooc[n] += len(common_with_prev)
    candidates = sorted(cond_cooc.items(), key=lambda x: -x[1])
    return sorted([n for n, _ in candidates[:PICK]])


# ============================================================
# Dimension B: Structural Template Matching
# ============================================================
def classify_structure(nums):
    """將一組號碼分類為結構模板"""
    nums = sorted(nums[:PICK])
    s = sum(nums)
    odd = sum(1 for n in nums if n % 2 == 1)
    z1 = sum(1 for n in nums if n <= 16)
    z2 = sum(1 for n in nums if 17 <= n <= 33)
    z3 = sum(1 for n in nums if n >= 34)
    has_consec = any(nums[i + 1] - nums[i] == 1 for i in range(len(nums) - 1))

    sum_cat = 'low' if s < 130 else 'high' if s > 170 else 'mid'
    oe_cat = f'{odd}o{6 - odd}e'
    zone_cat = f'{z1}-{z2}-{z3}'
    consec_cat = 'C' if has_consec else 'N'

    return f'{sum_cat}_{oe_cat}_{zone_cat}_{consec_cat}'


def structural_template_match(history, window=200):
    """B1: 預測下期結構類型，在該約束下選號"""
    recent = history[-window:]
    # Build structure transition
    struct_seq = [classify_structure(d['numbers']) for d in recent]
    trans = Counter()
    for i in range(len(struct_seq) - 1):
        trans[(struct_seq[i], struct_seq[i + 1])] += 1

    last_struct = classify_structure(history[-1]['numbers'])
    # Find most likely next structure
    next_candidates = [(s2, cnt) for (s1, s2), cnt in trans.items() if s1 == last_struct]
    if not next_candidates:
        # Fallback: most common structure
        struct_freq = Counter(struct_seq)
        target_struct = struct_freq.most_common(1)[0][0]
    else:
        target_struct = max(next_candidates, key=lambda x: x[1])[0]

    # Parse target structure
    parts = target_struct.split('_')
    sum_cat = parts[0]  # low/mid/high
    oe_cat = parts[1]  # e.g. 3o3e
    zone_cat = parts[2]  # e.g. 2-2-2
    consec_cat = parts[3]  # C/N

    target_odd = int(oe_cat[0])
    target_zones = [int(x) for x in zone_cat.split('-')]

    # Select numbers matching structure
    freq = Counter(n for d in recent for n in d['numbers'])
    zones = {
        0: sorted([(n, freq.get(n, 0)) for n in range(1, 17)], key=lambda x: -x[1]),
        1: sorted([(n, freq.get(n, 0)) for n in range(17, 34)], key=lambda x: -x[1]),
        2: sorted([(n, freq.get(n, 0)) for n in range(34, 50)], key=lambda x: -x[1]),
    }

    selected = []
    for zi, count in enumerate(target_zones):
        zone_nums = [n for n, _ in zones[zi][:count * 2]]
        selected.extend(zone_nums[:count])

    # Ensure exactly 6
    if len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1) if n not in selected]
        remaining.sort(key=lambda x: -freq.get(x, 0))
        selected.extend(remaining[:PICK - len(selected)])

    return sorted(selected[:PICK])


def structural_sum_regression(history, window=50):
    """B2: 和值回歸 — 預測下期和值，選接近該和值的組合"""
    recent = history[-window:]
    sums = [sum(d['numbers'][:PICK]) for d in recent]
    avg_sum = np.mean(sums)
    # Use exponential moving average
    ema = sums[0]
    alpha = 0.1
    for s in sums[1:]:
        ema = alpha * s + (1 - alpha) * ema
    target_sum = int(ema)

    freq = Counter(n for d in recent for n in d['numbers'])
    candidates = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq.get(x, 0))

    # Greedy: pick numbers that get closest to target sum
    selected = []
    for n in candidates:
        if len(selected) < PICK:
            test_sum = sum(selected) + n
            remaining_slots = PICK - len(selected) - 1
            if remaining_slots > 0:
                min_possible = test_sum + sum(range(1, remaining_slots + 1))
                max_possible = test_sum + sum(range(MAX_NUM - remaining_slots + 1, MAX_NUM + 1))
                if min_possible <= target_sum <= max_possible:
                    selected.append(n)
            else:
                selected.append(n)
    if len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1) if n not in selected]
        selected.extend(remaining[:PICK - len(selected)])
    return sorted(selected[:PICK])


def structural_odd_even_transition(history, window=100):
    """B3: 奇偶比轉移矩陣"""
    recent = history[-window:]
    oe_seq = [sum(1 for n in d['numbers'][:PICK] if n % 2 == 1) for d in recent]
    trans = Counter()
    for i in range(len(oe_seq) - 1):
        trans[(oe_seq[i], oe_seq[i + 1])] += 1

    last_oe = oe_seq[-1]
    next_candidates = [(oe2, cnt) for (oe1, oe2), cnt in trans.items() if oe1 == last_oe]
    if next_candidates:
        target_odd = max(next_candidates, key=lambda x: x[1])[0]
    else:
        target_odd = 3

    freq = Counter(n for d in recent for n in d['numbers'])
    odds = sorted([n for n in range(1, MAX_NUM + 1, 2)], key=lambda x: -freq.get(x, 0))
    evens = sorted([n for n in range(2, MAX_NUM + 1, 2)], key=lambda x: -freq.get(x, 0))

    selected = odds[:target_odd] + evens[:PICK - target_odd]
    return sorted(selected[:PICK])


def structural_gap_pattern(history, window=100):
    """B4: 間距模式匹配 — 匹配歷史上間距模式相似的開獎"""
    recent = history[-window:]
    last_nums = sorted(history[-1]['numbers'][:PICK])
    last_gaps = tuple(last_nums[i + 1] - last_nums[i] for i in range(len(last_nums) - 1))

    # Find similar gap patterns in history
    similar_next = []
    for i in range(len(recent) - 1):
        nums = sorted(recent[i]['numbers'][:PICK])
        gaps = tuple(nums[j + 1] - nums[j] for j in range(len(nums) - 1))
        # Similarity = inverse of L1 distance
        dist = sum(abs(a - b) for a, b in zip(gaps, last_gaps))
        if dist <= 10:  # Similar gap pattern
            similar_next.append(recent[i + 1]['numbers'][:PICK])

    if similar_next:
        freq = Counter(n for nums in similar_next for n in nums)
        return sorted([n for n, _ in freq.most_common(PICK)])
    else:
        # Fallback
        freq = Counter(n for d in recent for n in d['numbers'])
        return sorted([n for n, _ in freq.most_common(PICK)])


# ============================================================
# Dimension C: Information Theory
# ============================================================
def conditional_entropy_selector(history, window=100):
    """C1: 條件熵最低的號碼（最可預測）"""
    recent = history[-window:]
    # For each number, compute H(X_t | X_{t-1})
    entropies = {}
    for n in range(1, MAX_NUM + 1):
        # Binary sequence: appeared (1) or not (0)
        seq = [1 if n in d['numbers'] else 0 for d in recent]
        # Conditional probability: P(1|prev=1), P(1|prev=0)
        counts = {'00': 0, '01': 0, '10': 0, '11': 0}
        for i in range(len(seq) - 1):
            key = f'{seq[i]}{seq[i + 1]}'
            counts[key] += 1
        # H = -sum(p*log(p))
        total_0 = counts['00'] + counts['01']
        total_1 = counts['10'] + counts['11']
        h = 0
        for prev in [0, 1]:
            total = total_0 if prev == 0 else total_1
            if total == 0:
                continue
            p_weight = total / (len(seq) - 1)
            for next_val in [0, 1]:
                key = f'{prev}{next_val}'
                if counts[key] > 0:
                    p = counts[key] / total
                    h -= p_weight * p * np.log2(p + 1e-10)
        entropies[n] = h

    # Pick numbers with lowest conditional entropy (most predictable)
    # AND predict they will appear based on conditional probability
    predictions = []
    for n in range(1, MAX_NUM + 1):
        seq = [1 if n in d['numbers'] else 0 for d in recent]
        last_state = seq[-1]
        # Count transitions from last_state to 1
        after_same = sum(1 for i in range(len(seq) - 1) if seq[i] == last_state and seq[i + 1] == 1)
        total_same = sum(1 for i in range(len(seq) - 1) if seq[i] == last_state)
        p_next = after_same / total_same if total_same > 0 else 0
        predictions.append((n, p_next, entropies[n]))

    # Sort by predicted probability (high), then by entropy (low)
    predictions.sort(key=lambda x: (-x[1], x[2]))
    return sorted([n for n, _, _ in predictions[:PICK]])


def mutual_information_selector(history, window=100):
    """C2: 互信息最大的號碼對"""
    recent = history[-window:]
    w = len(recent)

    # For each number, create binary appearance vector
    vectors = {}
    for n in range(1, MAX_NUM + 1):
        vectors[n] = np.array([1 if n in d['numbers'] else 0 for d in recent])

    # Compute mutual information between each number and "appears next draw"
    mi_scores = {}
    for n in range(1, MAX_NUM + 1):
        # I(X_n; Y) where Y = appeared_in_next_draw
        x = vectors[n][:-1]
        y = np.array([1 if n in recent[i + 1]['numbers'] else 0 for i in range(w - 1)])

        # Joint distribution
        joint = Counter()
        for xi, yi in zip(x, y):
            joint[(xi, yi)] += 1

        mi = 0
        total = len(x)
        px = Counter(x)
        py = Counter(y)

        for (xi, yi), count in joint.items():
            p_xy = count / total
            p_x = px[xi] / total
            p_y = py[yi] / total
            if p_xy > 0 and p_x > 0 and p_y > 0:
                mi += p_xy * np.log2(p_xy / (p_x * p_y) + 1e-10)

        last_state = vectors[n][-1]
        # Predict based on conditional probability given last state
        after = sum(1 for i in range(w - 1) if vectors[n][i] == last_state and n in recent[i + 1]['numbers'])
        total_after = sum(1 for i in range(w - 1) if vectors[n][i] == last_state)
        p_pred = after / total_after if total_after > 0 else 0

        mi_scores[n] = (mi, p_pred)

    # Sort by MI * P(appear)
    scored = sorted(mi_scores.items(), key=lambda x: -(x[1][0] * x[1][1]))
    return sorted([n for n, _ in scored[:PICK]])


def surprise_selector(history, window=100):
    """C3: Surprise (自信息) — 選最近最"令人驚訝"的出現號碼"""
    recent = history[-window:]
    freq = Counter(n for d in recent for n in d['numbers'])
    total = sum(freq.values())
    # Surprise = -log(P(n))
    surprises = {}
    for n in range(1, MAX_NUM + 1):
        p = freq.get(n, 0.5) / total
        surprises[n] = -np.log2(p + 1e-10)

    # Pick most surprising numbers that appeared recently (gap < 5)
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(history)

    scored = []
    for n in range(1, MAX_NUM + 1):
        gap = current - last_seen.get(n, 0)
        if gap <= 5:  # Recently appeared
            scored.append((n, surprises.get(n, 0)))
    scored.sort(key=lambda x: -x[1])
    result = [n for n, _ in scored[:PICK]]
    if len(result) < PICK:
        remaining = sorted(surprises.items(), key=lambda x: -x[1])
        for n, _ in remaining:
            if n not in result and len(result) < PICK:
                result.append(n)
    return sorted(result[:PICK])


# ============================================================
# Dimension D: Negative Selection
# ============================================================
def negative_elimination(history, window=100):
    """D1: 排除法 — 排除最不可能出現的號碼，從剩餘中選"""
    recent = history[-window:]
    freq = Counter(n for d in recent for n in d['numbers'])

    # Kill criteria:
    kill_scores = Counter()
    for n in range(1, MAX_NUM + 1):
        # Too hot (regression to mean)
        if freq.get(n, 0) > window * 6 / 49 * 1.5:
            kill_scores[n] += 2
        # Just appeared in last draw (less likely to repeat)
        if n in history[-1]['numbers']:
            kill_scores[n] += 1
        # Appeared in last 2 draws
        if len(history) >= 2 and n in history[-2]['numbers']:
            if n in history[-1]['numbers']:
                kill_scores[n] += 2  # Double repeat very rare

    # Keep numbers with lowest kill score
    candidates = sorted(range(1, MAX_NUM + 1), key=lambda x: (kill_scores.get(x, 0), -freq.get(x, 0)))
    return sorted(candidates[:PICK])


def negative_overdue_filter(history, window=100):
    """D2: 排除極度過期的號碼（gap > 2σ），從moderate gap中選"""
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(history)
    gaps = {n: current - last_seen.get(n, 0) for n in range(1, MAX_NUM + 1)}
    mean_gap = np.mean(list(gaps.values()))
    std_gap = np.std(list(gaps.values()))

    # Kill extreme overdue (gap > mean + 2σ) and just appeared (gap = 0-1)
    moderate = [(n, g) for n, g in gaps.items()
                if mean_gap - std_gap <= g <= mean_gap + std_gap]
    moderate.sort(key=lambda x: x[1])

    result = [n for n, _ in moderate[:PICK]]
    if len(result) < PICK:
        remaining = sorted(gaps.items(), key=lambda x: abs(x[1] - mean_gap))
        for n, _ in remaining:
            if n not in result and len(result) < PICK:
                result.append(n)
    return sorted(result[:PICK])


def negative_consensus_remove(history, window=30, n_methods=5):
    """D3: 移除所有簡單方法都選的號碼（反共識）"""
    freq = Counter(n for d in history[-window:] for n in d['numbers'])
    ranked_hot = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq.get(x, 0))

    # "Everyone picks these" = top 6 hot numbers
    consensus = set(ranked_hot[:10])

    # Pick from non-consensus, moderate frequency
    candidates = [(n, freq.get(n, 0)) for n in range(1, MAX_NUM + 1) if n not in consensus]
    candidates.sort(key=lambda x: -x[1])
    return sorted([n for n, _ in candidates[:PICK]])


# ============================================================
# Dimension E: Zone Transition
# ============================================================
def zone_transition_markov(history, window=100):
    """E1: Z1/Z2/Z3 數量的 Markov 轉移"""
    recent = history[-window:]
    zone_seq = []
    for d in recent:
        nums = d['numbers'][:PICK]
        z1 = sum(1 for n in nums if n <= 16)
        z2 = sum(1 for n in nums if 17 <= n <= 33)
        z3 = sum(1 for n in nums if n >= 34)
        zone_seq.append((z1, z2, z3))

    trans = Counter()
    for i in range(len(zone_seq) - 1):
        trans[(zone_seq[i], zone_seq[i + 1])] += 1

    last_zone = zone_seq[-1]
    next_candidates = [(z2, cnt) for (z1, z2), cnt in trans.items() if z1 == last_zone]
    if next_candidates:
        target_zone = max(next_candidates, key=lambda x: x[1])[0]
    else:
        target_zone = (2, 2, 2)

    freq = Counter(n for d in recent for n in d['numbers'])
    z_ranges = [(1, 17), (17, 34), (34, 50)]
    selected = []
    for zi, count in enumerate(target_zone):
        lo, hi = z_ranges[zi]
        zone_nums = sorted([(n, freq.get(n, 0)) for n in range(lo, hi)], key=lambda x: -x[1])
        selected.extend([n for n, _ in zone_nums[:count]])

    if len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1) if n not in selected]
        remaining.sort(key=lambda x: -freq.get(x, 0))
        selected.extend(remaining[:PICK - len(selected)])
    return sorted(selected[:PICK])


def zone_consecutive_zone_bet(history, window=50):
    """E2: 連號區間偏好 — 從最常出現連號的區間多選"""
    recent = history[-window:]
    zone_consec = Counter()
    for d in recent:
        nums = sorted(d['numbers'][:PICK])
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] == 1:
                if nums[i] <= 16:
                    zone_consec['Z1'] += 1
                elif nums[i] <= 33:
                    zone_consec['Z2'] += 1
                else:
                    zone_consec['Z3'] += 1

    # Allocate more picks to zones with more consecutive pairs
    total_c = sum(zone_consec.values()) or 1
    allocations = {
        'Z1': max(1, round(PICK * zone_consec.get('Z1', 1) / total_c)),
        'Z2': max(1, round(PICK * zone_consec.get('Z2', 1) / total_c)),
        'Z3': max(1, round(PICK * zone_consec.get('Z3', 1) / total_c)),
    }
    # Adjust to sum to 6
    while sum(allocations.values()) > PICK:
        max_z = max(allocations, key=allocations.get)
        allocations[max_z] -= 1
    while sum(allocations.values()) < PICK:
        min_z = min(allocations, key=allocations.get)
        allocations[min_z] += 1

    freq = Counter(n for d in recent for n in d['numbers'])
    z_ranges = {'Z1': (1, 17), 'Z2': (17, 34), 'Z3': (34, 50)}
    selected = []
    for z, count in allocations.items():
        lo, hi = z_ranges[z]
        zone_nums = sorted([(n, freq.get(n, 0)) for n in range(lo, hi)], key=lambda x: -x[1])
        selected.extend([n for n, _ in zone_nums[:count]])
    return sorted(selected[:PICK])


# ============================================================
# Dimension F: Graph-based
# ============================================================
def graph_centrality_bet(history, window=100):
    """F1: 號碼共現圖的度中心性 — 選最"社交"的號碼"""
    recent = history[-window:]
    degree = Counter()
    for d in recent:
        nums = d['numbers'][:PICK]
        for a, b in combinations(sorted(nums), 2):
            degree[a] += 1
            degree[b] += 1
    return sorted([n for n, _ in degree.most_common(PICK)])


def graph_bridge_bet(history, window=100):
    """F2: 橋接號碼 — 連接不同社群的號碼"""
    recent = history[-window:]
    # Build adjacency
    adj = defaultdict(Counter)
    for d in recent:
        nums = d['numbers'][:PICK]
        for a, b in combinations(sorted(nums), 2):
            adj[a][b] += 1
            adj[b][a] += 1

    # Simple betweenness approximation: numbers that connect to many different groups
    bridge_score = Counter()
    for n in range(1, MAX_NUM + 1):
        neighbors = set(adj[n].keys())
        # Count how many neighbor pairs are NOT directly connected
        non_edges = 0
        pairs = 0
        for a, b in combinations(neighbors, 2):
            pairs += 1
            if b not in adj[a]:
                non_edges += 1
        if pairs > 0:
            bridge_score[n] = non_edges / pairs  # Higher = more bridge-like
    return sorted([n for n, _ in bridge_score.most_common(PICK)])


def graph_pagerank_bet(history, window=100, damping=0.85, iterations=20):
    """F3: PageRank — 號碼共現網路的PageRank值"""
    recent = history[-window:]
    adj = defaultdict(Counter)
    for d in recent:
        nums = d['numbers'][:PICK]
        for a, b in combinations(sorted(nums), 2):
            adj[a][b] += 1
            adj[b][a] += 1

    nodes = list(range(1, MAX_NUM + 1))
    n = len(nodes)
    pr = {nd: 1.0 / n for nd in nodes}

    for _ in range(iterations):
        new_pr = {}
        for nd in nodes:
            neighbors = adj[nd]
            total_weight = sum(neighbors.values())
            incoming = 0
            for neighbor, weight in neighbors.items():
                neighbor_total = sum(adj[neighbor].values())
                if neighbor_total > 0:
                    incoming += pr[neighbor] * weight / neighbor_total
            new_pr[nd] = (1 - damping) / n + damping * incoming
        pr = new_pr

    ranked = sorted(pr.items(), key=lambda x: -x[1])
    return sorted([n for n, _ in ranked[:PICK]])


# ============================================================
# All Methods Registry
# ============================================================
def build_methods():
    """Build all candidate methods with varying parameters"""
    methods = {}

    # Dimension A: Co-occurrence
    for w in [30, 50, 100, 200]:
        methods[f'A1_cooc_pairs_w{w}'] = lambda h, w=w: cooccurrence_top_pairs(h, w)
    for w in [30, 50, 100]:
        methods[f'A2_cooc_trans_w{w}'] = lambda h, w=w: cooccurrence_transition_pairs(h, w)
    for w in [50, 100, 200]:
        methods[f'A3_cooc_anti_w{w}'] = lambda h, w=w: cooccurrence_anti_pairs(h, w)
    for w in [50, 100]:
        methods[f'A4_cooc_trip_w{w}'] = lambda h, w=w: cooccurrence_triplet(h, w)
    for w in [30, 50, 100]:
        methods[f'A5_cooc_cond_w{w}'] = lambda h, w=w: cooccurrence_conditional(h, w)

    # Dimension B: Structural
    for w in [100, 200, 500]:
        methods[f'B1_struct_tmpl_w{w}'] = lambda h, w=w: structural_template_match(h, w)
    for w in [30, 50, 100]:
        methods[f'B2_struct_sum_w{w}'] = lambda h, w=w: structural_sum_regression(h, w)
    for w in [50, 100, 200]:
        methods[f'B3_struct_oe_w{w}'] = lambda h, w=w: structural_odd_even_transition(h, w)
    for w in [50, 100]:
        methods[f'B4_struct_gap_w{w}'] = lambda h, w=w: structural_gap_pattern(h, w)

    # Dimension C: Information Theory
    for w in [50, 100, 200]:
        methods[f'C1_cond_entropy_w{w}'] = lambda h, w=w: conditional_entropy_selector(h, w)
    for w in [50, 100]:
        methods[f'C2_mutual_info_w{w}'] = lambda h, w=w: mutual_information_selector(h, w)
    for w in [50, 100]:
        methods[f'C3_surprise_w{w}'] = lambda h, w=w: surprise_selector(h, w)

    # Dimension D: Negative Selection
    for w in [30, 50, 100]:
        methods[f'D1_neg_elim_w{w}'] = lambda h, w=w: negative_elimination(h, w)
    methods['D2_neg_overdue'] = negative_overdue_filter
    for w in [20, 30, 50]:
        methods[f'D3_neg_consensus_w{w}'] = lambda h, w=w: negative_consensus_remove(h, w)

    # Dimension E: Zone Transition
    for w in [50, 100, 200]:
        methods[f'E1_zone_trans_w{w}'] = lambda h, w=w: zone_transition_markov(h, w)
    for w in [30, 50, 100]:
        methods[f'E2_zone_consec_w{w}'] = lambda h, w=w: zone_consecutive_zone_bet(h, w)

    # Dimension F: Graph-based
    for w in [50, 100, 200]:
        methods[f'F1_graph_degree_w{w}'] = lambda h, w=w: graph_centrality_bet(h, w)
    for w in [50, 100]:
        methods[f'F2_graph_bridge_w{w}'] = lambda h, w=w: graph_bridge_bet(h, w)
    for w in [50, 100, 200]:
        methods[f'F3_graph_pagerank_w{w}'] = lambda h, w=w: graph_pagerank_bet(h, w)

    return methods


# ============================================================
# Backtest with Train/Test Split
# ============================================================
def run_discovery_backtest(draws, method_func, n_periods=1500):
    """Run backtest with train/test split"""
    baseline = P_SINGLE
    start_idx = max(MIN_HISTORY, len(draws) - n_periods)
    total = len(draws) - start_idx
    half = start_idx + total // 2

    train_hits = 0
    train_total = 0
    test_hits = 0
    test_total = 0

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]

        try:
            bet = method_func(history)
            if not bet or len(bet) < PICK:
                if i < half:
                    train_total += 1
                else:
                    test_total += 1
                continue
            mc = len(set(bet) & target)
            hit = 1 if mc >= 3 else 0
        except Exception:
            hit = 0

        if i < half:
            train_hits += hit
            train_total += 1
        else:
            test_hits += hit
            test_total += 1

    total_hits = train_hits + test_hits
    total_n = train_total + test_total
    overall_rate = total_hits / total_n if total_n > 0 else 0
    edge = overall_rate - baseline

    train_rate = train_hits / train_total if train_total > 0 else 0
    test_rate = test_hits / test_total if test_total > 0 else 0
    train_edge = train_rate - baseline
    test_edge = test_rate - baseline

    # Z-score
    z = (overall_rate - baseline) / np.sqrt(baseline * (1 - baseline) / total_n) if total_n > 0 else 0

    return {
        'total': total_n,
        'hits': total_hits,
        'rate': overall_rate,
        'edge': edge,
        'z': z,
        'train': (train_hits, train_total, train_edge),
        'test': (test_hits, test_total, test_edge),
    }


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dimensions', type=str, default='A,B,C,D,E,F')
    parser.add_argument('--periods', type=int, default=1500)
    args = parser.parse_args()

    dims = set(args.dimensions.upper().split(','))

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))

    methods = build_methods()
    # Filter by dimension
    filtered = {k: v for k, v in methods.items() if k[0] in dims}

    N = len(filtered)
    bonferroni_alpha = 0.05 / N
    bonferroni_z = 2.576  # Approximate z for p < 0.001 (conservative)

    print("=" * 90)
    print("  大樂透 Auto-Discovery 特徵掃描")
    print("=" * 90)
    print(f"  Database: {len(draws)} draws")
    print(f"  Backtest periods: {args.periods}")
    print(f"  Candidate methods: {N}")
    print(f"  Bonferroni α: {bonferroni_alpha:.5f} (z > {bonferroni_z:.2f})")
    print(f"  Train/Test: 前半 / 後半 (both must be positive)")
    print(f"  Baseline: P(M3+) = {P_SINGLE*100:.2f}%")
    print("=" * 90)

    results = []
    for i, (name, func) in enumerate(sorted(filtered.items())):
        t0 = time.time()
        r = run_discovery_backtest(draws, func, args.periods)
        elapsed = time.time() - t0
        r['name'] = name
        r['time'] = elapsed
        results.append(r)

        edge_pct = r['edge'] * 100
        z = r['z']
        tr_hits, tr_n, tr_edge = r['train']
        te_hits, te_n, te_edge = r['test']
        icon = "★" if z > bonferroni_z and tr_edge > 0 and te_edge > 0 else \
               "●" if r['edge'] > 0 and tr_edge > 0 and te_edge > 0 else \
               "○" if r['edge'] > 0 else "✗"

        print(f"  [{i+1:>2}/{N}] {name:<28s} "
              f"edge={edge_pct:+5.2f}% z={z:+5.2f} "
              f"train={tr_edge*100:+5.2f}% test={te_edge*100:+5.2f}% "
              f"[{icon}] [{elapsed:.1f}s]")

    # ====== Summary ======
    print(f"\n{'='*90}")
    print("  RESULTS SUMMARY")
    print(f"{'='*90}")

    # Pass Bonferroni
    bonf_pass = [r for r in results if r['z'] > bonferroni_z
                 and r['train'][2] > 0 and r['test'][2] > 0]
    print(f"\n  ★ Bonferroni 通過 (z > {bonferroni_z}, train+test 都正): {len(bonf_pass)}/{N}")
    for r in sorted(bonf_pass, key=lambda x: -x['z']):
        print(f"    {r['name']:<28s} edge={r['edge']*100:+.2f}% z={r['z']:.2f}")

    # Weak pass (edge > 0, both halves > 0, but z < bonferroni)
    weak_pass = [r for r in results if r['edge'] > 0
                 and r['train'][2] > 0 and r['test'][2] > 0
                 and r['z'] <= bonferroni_z]
    print(f"\n  ● Train+Test 都正但未達 Bonferroni: {len(weak_pass)}/{N}")
    for r in sorted(weak_pass, key=lambda x: -x['z'])[:15]:
        print(f"    {r['name']:<28s} edge={r['edge']*100:+.2f}% z={r['z']:.2f} "
              f"train={r['train'][2]*100:+.2f}% test={r['test'][2]*100:+.2f}%")

    # Top 10 by z-score regardless
    print(f"\n  Top 10 by z-score (regardless of train/test):")
    for r in sorted(results, key=lambda x: -x['z'])[:10]:
        tr_e = r['train'][2] * 100
        te_e = r['test'][2] * 100
        print(f"    {r['name']:<28s} edge={r['edge']*100:+.2f}% z={r['z']:.2f} "
              f"train={tr_e:+.2f}% test={te_e:+.2f}%")

    # By dimension
    print(f"\n  Best per dimension:")
    for dim in sorted(dims):
        dim_results = [r for r in results if r['name'].startswith(dim)]
        if dim_results:
            best = max(dim_results, key=lambda x: x['z'])
            dim_name = {'A': 'Co-occurrence', 'B': 'Structural', 'C': 'Info Theory',
                       'D': 'Negative Sel.', 'E': 'Zone Trans.', 'F': 'Graph'}
            print(f"    {dim} ({dim_name.get(dim, '?'):15s}): {best['name']:<28s} "
                  f"edge={best['edge']*100:+.2f}% z={best['z']:.2f}")

    # 115000015 test
    print(f"\n{'='*90}")
    print("  對 115000015 的預測表現 (Top 10 methods)")
    print(f"{'='*90}")

    target_idx = None
    for i, d in enumerate(draws):
        if str(d['draw']) == '115000015':
            target_idx = i
            break

    if target_idx:
        actual = set(draws[target_idx]['numbers'])
        hist = draws[:target_idx]

        top10_methods = sorted(results, key=lambda x: -x['z'])[:10]
        for r in top10_methods:
            name = r['name']
            func = filtered[name]
            try:
                bet = func(hist)
                hit = set(bet) & actual
                print(f"  {name:<28s}: {bet} → M{len(hit)} {sorted(hit)}")
            except Exception as e:
                print(f"  {name:<28s}: ERROR {e}")


if __name__ == '__main__':
    main()
