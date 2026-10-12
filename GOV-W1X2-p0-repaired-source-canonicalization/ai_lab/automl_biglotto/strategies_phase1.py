"""
Phase 1: 已知方法極限挖掘
70+ 策略 × 超參數變體 = ~200 種配置
每個策略函數：(history: List[Dict]) -> List[List[int]]
"""
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations
from typing import List, Dict, Callable, Tuple

from .config import MAX_NUM, PICK, PRIMES


# ============================================================
# 輔助函數
# ============================================================
def _top_n_by_score(scores: Dict[int, float], n: int = PICK) -> List[int]:
    """從分數字典中選出最高分的 n 個號碼"""
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([num for num, _ in ranked[:n]])


def _ensure_valid(numbers: List[int], n: int = PICK) -> List[int]:
    """確保輸出有效：n 個 1-MAX_NUM 的不重複整數"""
    valid = sorted(set(num for num in numbers if 1 <= num <= MAX_NUM))[:n]
    if len(valid) < n:
        remaining = [i for i in range(1, MAX_NUM + 1) if i not in valid]
        np.random.shuffle(remaining)
        valid.extend(remaining[:n - len(valid)])
    return sorted(valid[:n])


# ============================================================
# 類別 1: 統計類 (Statistical)
# ============================================================
def frequency_predict(history, window=50):
    """頻率選號"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    return [_top_n_by_score(freq)]


def cold_number_predict(history, window=100):
    """冷號選號（頻率最低）"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    for n in range(1, MAX_NUM + 1):
        if n not in freq:
            freq[n] = 0
    coldest = sorted(freq.items(), key=lambda x: x[1])
    return [sorted([n for n, _ in coldest[:PICK]])]


def deviation_predict(history, window=50, threshold=1.5):
    """偏差選號（偏離期望最多的號碼）"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    expected = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        dev = abs(freq.get(n, 0) - expected)
        scores[n] = dev
    return [_top_n_by_score(scores)]


def hot_cold_mix_predict(history, window=50):
    """熱冷混合：3 熱 + 3 冷"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    for n in range(1, MAX_NUM + 1):
        if n not in freq:
            freq[n] = 0
    ranked = sorted(freq.items(), key=lambda x: -x[1])
    hot3 = [n for n, _ in ranked[:3]]
    cold3 = [n for n, _ in ranked[-3:]]
    return [sorted(hot3 + cold3)]


def deviation_complement_predict(history, window=50, echo_boost=1.5):
    """偏差互補+回聲 (P0) — 已驗證有效"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])

    # Bet 1: Hot + Echo
    scores_hot = {}
    lag2_set = set(history[-2]['numbers'][:PICK]) if len(history) >= 2 else set()
    for n in range(1, MAX_NUM + 1):
        s = freq.get(n, 0)
        if n in lag2_set:
            s *= echo_boost
        scores_hot[n] = s
    bet1 = _top_n_by_score(scores_hot)

    # Bet 2: Cold (exclude bet1)
    scores_cold = {}
    for n in range(1, MAX_NUM + 1):
        if n not in bet1:
            scores_cold[n] = -freq.get(n, 0)
    bet2 = _top_n_by_score(scores_cold)

    return [bet1, bet2]


# ============================================================
# 類別 2: 機率類 (Probabilistic)
# ============================================================
def bayesian_predict(history, window=100):
    """貝葉斯估計"""
    recent = history[-window:] if len(history) >= window else history
    alpha = 1.0  # Prior
    scores = {}
    for n in range(1, MAX_NUM + 1):
        count = sum(1 for d in recent if n in d['numbers'][:PICK])
        scores[n] = (count + alpha) / (len(recent) + alpha * 2)
    return [_top_n_by_score(scores)]


def conditional_entropy_predict(history, window=100):
    """條件熵最低的號碼"""
    recent = history[-window:] if len(history) >= window else history
    predictions = []
    for n in range(1, MAX_NUM + 1):
        seq = [1 if n in d['numbers'][:PICK] else 0 for d in recent]
        last_state = seq[-1] if seq else 0
        after = sum(1 for i in range(len(seq) - 1)
                    if seq[i] == last_state and seq[i + 1] == 1)
        total_after = sum(1 for i in range(len(seq) - 1)
                         if seq[i] == last_state)
        p_next = after / total_after if total_after > 0 else 0
        # 條件熵
        counts = {'00': 0, '01': 0, '10': 0, '11': 0}
        for i in range(len(seq) - 1):
            counts[f'{seq[i]}{seq[i+1]}'] += 1
        total_0 = counts['00'] + counts['01']
        total_1 = counts['10'] + counts['11']
        h = 0
        for prev in [0, 1]:
            t = total_0 if prev == 0 else total_1
            if t == 0:
                continue
            pw = t / (len(seq) - 1) if len(seq) > 1 else 0
            for nv in [0, 1]:
                k = f'{prev}{nv}'
                if counts[k] > 0:
                    p = counts[k] / t
                    h -= pw * p * np.log2(p + 1e-10)
        predictions.append((n, p_next, h))
    predictions.sort(key=lambda x: (-x[1], x[2]))
    return [sorted([n for n, _, _ in predictions[:PICK]])]


def mutual_info_predict(history, window=100):
    """互信息最高的號碼"""
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w < 5:
        return [sorted(range(1, PICK + 1))]
    mi_scores = {}
    for n in range(1, MAX_NUM + 1):
        vec = np.array([1 if n in d['numbers'][:PICK] else 0 for d in recent])
        x = vec[:-1]
        y = vec[1:]
        joint = Counter(zip(x.tolist(), y.tolist()))
        mi = 0
        total = len(x)
        px = Counter(x.tolist())
        py = Counter(y.tolist())
        for (xi, yi), c in joint.items():
            p_xy = c / total
            p_x = px[xi] / total
            p_y = py[yi] / total
            if p_xy > 0 and p_x > 0 and p_y > 0:
                mi += p_xy * np.log2(p_xy / (p_x * p_y) + 1e-10)
        last_state = vec[-1]
        after = sum(1 for i in range(w - 1) if vec[i] == last_state
                    and n in recent[i + 1]['numbers'][:PICK])
        total_after = sum(1 for i in range(w - 1) if vec[i] == last_state)
        p_pred = after / total_after if total_after > 0 else 0
        mi_scores[n] = mi * p_pred
    return [_top_n_by_score(mi_scores)]


def surprise_predict(history, window=100):
    """驚奇度選號"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    total = sum(freq.values())
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers'][:PICK]:
            last_seen[n] = i
    current = len(history)
    scored = []
    for n in range(1, MAX_NUM + 1):
        gap = current - last_seen.get(n, 0)
        p = freq.get(n, 0.5) / total if total > 0 else 1 / MAX_NUM
        surprise = -np.log2(p + 1e-10)
        if gap <= 5:
            scored.append((n, surprise))
    scored.sort(key=lambda x: -x[1])
    result = [n for n, _ in scored[:PICK]]
    if len(result) < PICK:
        remaining = sorted(range(1, MAX_NUM + 1),
                          key=lambda x: -freq.get(x, 0))
        for n in remaining:
            if n not in result and len(result) < PICK:
                result.append(n)
    return [sorted(result[:PICK])]


def mle_predict(history, window=100):
    """最大似然估計"""
    recent = history[-window:] if len(history) >= window else history
    scores = {}
    for n in range(1, MAX_NUM + 1):
        count = sum(1 for d in recent if n in d['numbers'][:PICK])
        scores[n] = count / len(recent) if len(recent) > 0 else 0
    return [_top_n_by_score(scores)]


# ============================================================
# 類別 3: 數學規律類 (Mathematical)
# ============================================================
def sum_range_predict(history, window=100):
    """和值範圍選號"""
    recent = history[-window:] if len(history) >= window else history
    sums = [sum(d['numbers'][:PICK]) for d in recent]
    target = int(np.mean(sums))
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    candidates = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq.get(x, 0))
    selected = []
    for n in candidates:
        if len(selected) < PICK:
            test_sum = sum(selected) + n
            remaining = PICK - len(selected) - 1
            if remaining > 0:
                min_p = test_sum + sum(range(1, remaining + 1))
                max_p = test_sum + sum(range(MAX_NUM - remaining + 1, MAX_NUM + 1))
                if min_p <= target <= max_p:
                    selected.append(n)
            else:
                selected.append(n)
    return [_ensure_valid(selected)]


def odd_even_predict(history, window=100):
    """奇偶平衡選號"""
    recent = history[-window:] if len(history) >= window else history
    oe_seq = [sum(1 for n in d['numbers'][:PICK] if n % 2 == 1) for d in recent]
    target_odd = int(round(np.mean(oe_seq)))
    target_odd = max(1, min(5, target_odd))
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    odds = sorted([n for n in range(1, MAX_NUM + 1, 2)], key=lambda x: -freq.get(x, 0))
    evens = sorted([n for n in range(2, MAX_NUM + 1, 2)], key=lambda x: -freq.get(x, 0))
    return [sorted(odds[:target_odd] + evens[:PICK - target_odd])]


def mod_arithmetic_predict(history, window=50, mod=10):
    """模運算頻率選號"""
    recent = history[-window:] if len(history) >= window else history
    mod_freq = Counter()
    for d in recent:
        for n in d['numbers'][:PICK]:
            mod_freq[n % mod] += 1
    # 選最頻繁的模組，從中選號
    top_mods = sorted(mod_freq.items(), key=lambda x: -x[1])[:3]
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    candidates = []
    for m, _ in top_mods:
        nums = [n for n in range(1, MAX_NUM + 1) if n % mod == m]
        nums.sort(key=lambda x: -freq.get(x, 0))
        candidates.extend(nums[:2])
    return [_ensure_valid(candidates)]


def prime_composite_predict(history, window=100):
    """質數/合數平衡"""
    recent = history[-window:] if len(history) >= window else history
    prime_ratio = []
    for d in recent:
        cnt = sum(1 for n in d['numbers'][:PICK] if n in PRIMES)
        prime_ratio.append(cnt)
    target_primes = int(round(np.mean(prime_ratio)))
    target_primes = max(1, min(5, target_primes))
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    primes_sorted = sorted([n for n in PRIMES if n <= MAX_NUM], key=lambda x: -freq.get(x, 0))
    composites = sorted([n for n in range(1, MAX_NUM + 1) if n not in PRIMES],
                        key=lambda x: -freq.get(x, 0))
    return [sorted(primes_sorted[:target_primes] + composites[:PICK - target_primes])]


def ac_value_predict(history, window=100):
    """AC 值優化"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    candidates = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq.get(x, 0))[:15]
    best_ac = -1
    best_combo = None
    for combo in combinations(candidates, PICK):
        combo_sorted = sorted(combo)
        diffs = set()
        for i in range(len(combo_sorted)):
            for j in range(i + 1, len(combo_sorted)):
                diffs.add(combo_sorted[j] - combo_sorted[i])
        ac = len(diffs) - (PICK - 1)
        if ac > best_ac:
            best_ac = ac
            best_combo = list(combo_sorted)
    return [best_combo if best_combo else _ensure_valid(candidates[:PICK])]


# ============================================================
# 類別 4: 序列分析 (Sequence Analysis)
# ============================================================
def markov_order1_predict(history, window=30):
    """一階 Markov"""
    recent = history[-window:] if len(history) >= window else history
    trans = Counter()
    for i in range(len(recent) - 1):
        for p in recent[i]['numbers'][:PICK]:
            for n in recent[i + 1]['numbers'][:PICK]:
                trans[(p, n)] += 1
    scores = Counter()
    for prev in history[-1]['numbers'][:PICK]:
        for n in range(1, MAX_NUM + 1):
            scores[n] += trans.get((prev, n), 0)
    return [_top_n_by_score(scores)]


def markov_order2_predict(history, window=50):
    """二階 Markov"""
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 3:
        return [sorted(range(1, PICK + 1))]
    trans = Counter()
    for i in range(len(recent) - 2):
        for p1 in recent[i]['numbers'][:PICK]:
            for p2 in recent[i + 1]['numbers'][:PICK]:
                for n in recent[i + 2]['numbers'][:PICK]:
                    trans[(p1, p2, n)] += 1
    scores = Counter()
    if len(history) >= 2:
        for p1 in history[-2]['numbers'][:PICK]:
            for p2 in history[-1]['numbers'][:PICK]:
                for n in range(1, MAX_NUM + 1):
                    scores[n] += trans.get((p1, p2, n), 0)
    return [_top_n_by_score(scores)] if scores else [sorted(range(1, PICK + 1))]


def markov_order3_predict(history, window=100):
    """三階 Markov"""
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 4:
        return [sorted(range(1, PICK + 1))]
    trans = Counter()
    for i in range(len(recent) - 3):
        for p1 in recent[i]['numbers'][:PICK]:
            for p2 in recent[i + 1]['numbers'][:PICK]:
                for p3 in recent[i + 2]['numbers'][:PICK]:
                    for n in recent[i + 3]['numbers'][:PICK]:
                        trans[(p1, p2, p3, n)] += 1
    scores = Counter()
    if len(history) >= 3:
        for p1 in history[-3]['numbers'][:PICK]:
            for p2 in history[-2]['numbers'][:PICK]:
                for p3 in history[-1]['numbers'][:PICK]:
                    for n in range(1, MAX_NUM + 1):
                        scores[n] += trans.get((p1, p2, p3, n), 0)
    return [_top_n_by_score(scores)] if scores else [sorted(range(1, PICK + 1))]


def lag2_echo_predict(history, window=50, echo_boost=1.5):
    """Lag-2 回聲選號"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    lag2_set = set(history[-2]['numbers'][:PICK]) if len(history) >= 2 else set()
    scores = {}
    for n in range(1, MAX_NUM + 1):
        s = freq.get(n, 0)
        if n in lag2_set:
            s *= echo_boost
        scores[n] = s
    return [_top_n_by_score(scores)]


def pattern_match_predict(history, window=100, pattern_size=3):
    """模式匹配"""
    if len(history) < pattern_size + 1:
        return [sorted(range(1, PICK + 1))]
    last_pattern = [set(history[-(i + 1)]['numbers'][:PICK]) for i in range(pattern_size)]
    freq = Counter()
    for i in range(len(history) - pattern_size - 1):
        pattern = [set(history[i + j]['numbers'][:PICK]) for j in range(pattern_size)]
        similarity = sum(len(pattern[j] & last_pattern[j]) for j in range(pattern_size))
        if similarity >= pattern_size * 2:
            for n in history[i + pattern_size]['numbers'][:PICK]:
                freq[n] += similarity
    if freq:
        return [_top_n_by_score(freq)]
    return [frequency_predict(history, window)[0]]


def cycle_analysis_predict(history, window=200):
    """週期分析"""
    recent = history[-window:] if len(history) >= window else history
    scores = {}
    for n in range(1, MAX_NUM + 1):
        appearances = [i for i, d in enumerate(recent) if n in d['numbers'][:PICK]]
        if len(appearances) >= 3:
            gaps = [appearances[i + 1] - appearances[i] for i in range(len(appearances) - 1)]
            avg_gap = np.mean(gaps)
            last_gap = len(recent) - 1 - appearances[-1]
            scores[n] = 1.0 / (abs(last_gap - avg_gap) + 1)
        else:
            scores[n] = 0
    return [_top_n_by_score(scores)]


# ============================================================
# 類別 5: 時間窗分析 (Window Analysis)
# ============================================================
def trend_exponential_predict(history, decay=0.05):
    """指數加權趨勢"""
    scores = {}
    for n in range(1, MAX_NUM + 1):
        s = 0
        for i, d in enumerate(history[-200:]):
            if n in d['numbers'][:PICK]:
                age = min(200, len(history)) - 1 - i
                s += np.exp(-decay * age)
        scores[n] = s
    return [_top_n_by_score(scores)]


def adaptive_window_predict(history):
    """自適應窗口：選擇最近表現最佳的窗口"""
    best_window = 50
    best_score = -1
    for w in [20, 50, 100, 200]:
        if len(history) < w + 10:
            continue
        recent = history[-w:]
        freq = Counter(n for d in recent for n in d['numbers'][:PICK])
        # 以最近10期的命中率衡量窗口好壞
        last10 = history[-10:]
        score = 0
        for d in last10:
            actual = set(d['numbers'][:PICK])
            top6 = set(_top_n_by_score(freq))
            score += len(top6 & actual)
        if score > best_score:
            best_score = score
            best_window = w
    return frequency_predict(history, best_window)


def multi_window_consensus_predict(history, windows=None):
    """多窗口共識"""
    if windows is None:
        windows = [20, 50, 100]
    votes = Counter()
    for w in windows:
        bet = frequency_predict(history, w)[0]
        for n in bet:
            votes[n] += 1
    return [_top_n_by_score(votes)]


# ============================================================
# 類別 6: 分布分析 (Distribution)
# ============================================================
def zone_balance_predict(history, window=100):
    """區間平衡選號"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    zones = [(1, 16), (17, 33), (34, 49)]
    selected = []
    per_zone = PICK // 3
    for lo, hi in zones:
        zone_nums = sorted([(n, freq.get(n, 0)) for n in range(lo, hi + 1)],
                          key=lambda x: -x[1])
        selected.extend([n for n, _ in zone_nums[:per_zone]])
    while len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1) if n not in selected]
        remaining.sort(key=lambda x: -freq.get(x, 0))
        selected.append(remaining[0])
    return [sorted(selected[:PICK])]


def zone_transition_predict(history, window=100):
    """區間轉移 Markov"""
    recent = history[-window:] if len(history) >= window else history
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
    last = zone_seq[-1] if zone_seq else (2, 2, 2)
    candidates = [(z2, c) for (z1, z2), c in trans.items() if z1 == last]
    target = max(candidates, key=lambda x: x[1])[0] if candidates else (2, 2, 2)
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    z_ranges = [(1, 17), (17, 34), (34, 50)]
    selected = []
    for zi, count in enumerate(target):
        lo, hi = z_ranges[zi]
        zone_nums = sorted([(n, freq.get(n, 0)) for n in range(lo, hi)], key=lambda x: -x[1])
        selected.extend([n for n, _ in zone_nums[:count]])
    return [_ensure_valid(selected)]


def tail_balance_predict(history, window=100):
    """尾數平衡"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    tail_freq = Counter()
    for d in recent:
        for n in d['numbers'][:PICK]:
            tail_freq[n % 10] += 1
    # 選尾數分散的號碼
    all_nums = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq.get(x, 0))
    selected = []
    used_tails = set()
    for n in all_nums:
        tail = n % 10
        if tail not in used_tails and len(selected) < PICK:
            selected.append(n)
            used_tails.add(tail)
    while len(selected) < PICK:
        for n in all_nums:
            if n not in selected:
                selected.append(n)
                break
    return [sorted(selected[:PICK])]


def consecutive_constraint_predict(history, window=100, max_consec=1):
    """連號約束"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    candidates = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq.get(x, 0))
    selected = []
    for n in candidates:
        if len(selected) >= PICK:
            break
        consec_count = sum(1 for s in selected if abs(s - n) == 1)
        if consec_count <= max_consec:
            selected.append(n)
    return [_ensure_valid(selected)]


def spread_constraint_predict(history, window=100, min_spread=25):
    """間距約束"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    candidates = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq.get(x, 0))
    best = None
    best_score = -1
    for combo in combinations(candidates[:20], PICK):
        s = sorted(combo)
        spread = s[-1] - s[0]
        if spread >= min_spread:
            score = sum(freq.get(n, 0) for n in combo)
            if score > best_score:
                best_score = score
                best = list(s)
    return [best if best else _ensure_valid(candidates[:PICK])]


# ============================================================
# 類別 7: 蒙特卡羅 (Monte Carlo)
# ============================================================
def monte_carlo_predict(history, window=100, n_samples=1000):
    """蒙特卡羅模擬"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    total = sum(freq.values())
    probs = np.array([freq.get(n, 0.5) for n in range(1, MAX_NUM + 1)], dtype=float)
    probs /= probs.sum()

    vote = Counter()
    for _ in range(n_samples):
        sample = np.random.choice(range(1, MAX_NUM + 1), size=PICK, replace=False, p=probs)
        for n in sample:
            vote[n] += 1
    return [_top_n_by_score(vote)]


def constraint_satisfaction_predict(history, window=100):
    """約束滿足"""
    recent = history[-window:] if len(history) >= window else history
    sums = [sum(d['numbers'][:PICK]) for d in recent]
    target_sum = int(np.mean(sums))
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    probs = np.array([freq.get(n, 0.5) for n in range(1, MAX_NUM + 1)], dtype=float)
    probs /= probs.sum()
    best = None
    best_diff = 999
    for _ in range(500):
        sample = sorted(np.random.choice(range(1, MAX_NUM + 1), size=PICK, replace=False, p=probs).tolist())
        diff = abs(sum(sample) - target_sum)
        if diff < best_diff:
            best_diff = diff
            best = sample
    return [best if best else _ensure_valid(list(range(1, PICK + 1)))]


def weighted_random_predict(history, window=50):
    """加權隨機"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    probs = np.array([freq.get(n, 0.5) for n in range(1, MAX_NUM + 1)], dtype=float)
    probs /= probs.sum()
    sample = sorted(np.random.choice(range(1, MAX_NUM + 1), size=PICK, replace=False, p=probs).tolist())
    return [sample]


# ============================================================
# 類別 8: 機器學習 (ML)
# ============================================================
def random_forest_predict(history, window=200, n_trees=50):
    """隨機森林"""
    try:
        from sklearn.ensemble import RandomForestClassifier
    except ImportError:
        return frequency_predict(history, window)

    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 30:
        return frequency_predict(history, 50)

    # 特徵：前5期的頻率 + gap
    X, y = [], []
    for i in range(10, len(recent)):
        feat = []
        for n in range(1, MAX_NUM + 1):
            cnt = sum(1 for d in recent[max(0, i - 10):i] if n in d['numbers'][:PICK])
            gap = i - max([j for j in range(i) if n in recent[j]['numbers'][:PICK]], default=0)
            feat.extend([cnt, gap])
        target = [1 if n in recent[i]['numbers'][:PICK] else 0 for n in range(1, MAX_NUM + 1)]
        X.append(feat)
        y.append(target)

    X = np.array(X)
    y = np.array(y)

    scores = {}
    for col in range(MAX_NUM):
        clf = RandomForestClassifier(n_estimators=n_trees, max_depth=3, random_state=42)
        clf.fit(X[:-1], y[:-1, col])
        prob = clf.predict_proba(X[-1:])
        scores[col + 1] = prob[0][1] if len(prob[0]) > 1 else prob[0][0]

    return [_top_n_by_score(scores)]


def gradient_boosting_predict(history, window=200, n_est=50):
    """梯度提升"""
    try:
        from sklearn.ensemble import GradientBoostingClassifier
    except ImportError:
        return frequency_predict(history, window)

    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 30:
        return frequency_predict(history, 50)

    X, y_all = [], []
    for i in range(10, len(recent)):
        feat = []
        for n in range(1, MAX_NUM + 1):
            cnt = sum(1 for d in recent[max(0, i - 10):i] if n in d['numbers'][:PICK])
            feat.append(cnt)
        target = [1 if n in recent[i]['numbers'][:PICK] else 0 for n in range(1, MAX_NUM + 1)]
        X.append(feat)
        y_all.append(target)

    X = np.array(X)
    y_all = np.array(y_all)

    scores = {}
    for col in range(MAX_NUM):
        if np.sum(y_all[:-1, col]) < 2:
            scores[col + 1] = 0
            continue
        clf = GradientBoostingClassifier(n_estimators=n_est, max_depth=2, random_state=42)
        clf.fit(X[:-1], y_all[:-1, col])
        prob = clf.predict_proba(X[-1:])
        scores[col + 1] = prob[0][1] if len(prob[0]) > 1 else prob[0][0]

    return [_top_n_by_score(scores)]


def logistic_regression_predict(history, window=200):
    """邏輯回歸"""
    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError:
        return frequency_predict(history, window)

    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 30:
        return frequency_predict(history, 50)

    X, y_all = [], []
    for i in range(10, len(recent)):
        feat = []
        for n in range(1, MAX_NUM + 1):
            cnt = sum(1 for d in recent[max(0, i - 10):i] if n in d['numbers'][:PICK])
            feat.append(cnt)
        target = [1 if n in recent[i]['numbers'][:PICK] else 0 for n in range(1, MAX_NUM + 1)]
        X.append(feat)
        y_all.append(target)

    X = np.array(X)
    y_all = np.array(y_all)

    scores = {}
    for col in range(MAX_NUM):
        if np.sum(y_all[:-1, col]) < 2:
            scores[col + 1] = 0
            continue
        clf = LogisticRegression(max_iter=200, random_state=42)
        clf.fit(X[:-1], y_all[:-1, col])
        prob = clf.predict_proba(X[-1:])
        scores[col + 1] = prob[0][1] if len(prob[0]) > 1 else prob[0][0]

    return [_top_n_by_score(scores)]


def clustering_predict(history, window=100, n_clusters=5):
    """聚類選號"""
    try:
        from sklearn.cluster import KMeans
    except ImportError:
        return frequency_predict(history, window)

    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    features = []
    for n in range(1, MAX_NUM + 1):
        f = freq.get(n, 0) / len(recent)
        gap = len(history)
        for i in range(len(history) - 1, -1, -1):
            if n in history[i]['numbers'][:PICK]:
                gap = len(history) - 1 - i
                break
        features.append([f, gap / 100.0, n / MAX_NUM])

    X = np.array(features)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)

    # 每個聚類選最高頻的
    selected = []
    for c in range(n_clusters):
        cluster_nums = [i + 1 for i, l in enumerate(labels) if l == c]
        cluster_nums.sort(key=lambda x: -freq.get(x, 0))
        if cluster_nums and len(selected) < PICK:
            selected.append(cluster_nums[0])
    while len(selected) < PICK:
        for n in sorted(range(1, MAX_NUM + 1), key=lambda x: -freq.get(x, 0)):
            if n not in selected:
                selected.append(n)
                break
    return [sorted(selected[:PICK])]


# ============================================================
# 類別 9: 集成 (Ensemble)
# ============================================================
def voting_ensemble_predict(history, n_methods=5):
    """多策略投票"""
    methods = [
        lambda h: frequency_predict(h, 50),
        lambda h: markov_order1_predict(h, 30),
        lambda h: bayesian_predict(h, 100),
        lambda h: zone_balance_predict(h, 100),
        lambda h: lag2_echo_predict(h, 50),
        lambda h: deviation_predict(h, 50),
        lambda h: cycle_analysis_predict(h, 200),
    ]
    votes = Counter()
    for m in methods[:n_methods]:
        try:
            bet = m(history)[0]
            for n in bet:
                votes[n] += 1
        except Exception:
            continue
    return [_top_n_by_score(votes)]


def stacking_ensemble_predict(history, window=100):
    """堆疊集成"""
    methods = [
        lambda h: frequency_predict(h, 50),
        lambda h: markov_order1_predict(h, 30),
        lambda h: bayesian_predict(h, 100),
    ]
    weights = [1.5, 1.0, 1.2]
    scores = Counter()
    for m, w in zip(methods, weights):
        try:
            bet = m(history)[0]
            for n in bet:
                scores[n] += w
        except Exception:
            continue
    return [_top_n_by_score(scores)]


# ============================================================
# 類別 10: 負面選擇 (Negative Selection)
# ============================================================
def negative_elimination_predict(history, window=100):
    """排除法"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    kill_scores = Counter()
    expected = len(recent) * PICK / MAX_NUM
    for n in range(1, MAX_NUM + 1):
        if freq.get(n, 0) > expected * 1.5:
            kill_scores[n] += 2
        if n in history[-1]['numbers'][:PICK]:
            kill_scores[n] += 1
        if len(history) >= 2 and n in history[-2]['numbers'][:PICK]:
            if n in history[-1]['numbers'][:PICK]:
                kill_scores[n] += 2
    candidates = sorted(range(1, MAX_NUM + 1),
                        key=lambda x: (kill_scores.get(x, 0), -freq.get(x, 0)))
    return [sorted(candidates[:PICK])]


def anti_consensus_predict(history, window=30):
    """反共識"""
    freq = Counter(n for d in history[-window:] for n in d['numbers'][:PICK])
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq.get(x, 0))
    consensus = set(ranked[:10])
    candidates = [(n, freq.get(n, 0)) for n in range(1, MAX_NUM + 1) if n not in consensus]
    candidates.sort(key=lambda x: -x[1])
    return [sorted([n for n, _ in candidates[:PICK]])]


def contrarian_predict(history, window=50):
    """逆向選號"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    for n in range(1, MAX_NUM + 1):
        if n not in freq:
            freq[n] = 0
    coldest = sorted(freq.items(), key=lambda x: x[1])
    return [sorted([n for n, _ in coldest[:PICK]])]


# ============================================================
# 類別 11: 圖論 (Graph)
# ============================================================
def cooccurrence_pairs_predict(history, window=100):
    """共現對"""
    recent = history[-window:] if len(history) >= window else history
    pair_freq = Counter()
    for d in recent:
        nums = sorted(d['numbers'][:PICK])
        for p in combinations(nums, 2):
            pair_freq[p] += 1
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
    return [sorted(list(selected)[:PICK])]


def cooccurrence_triplet_predict(history, window=100):
    """三元組共現"""
    recent = history[-window:] if len(history) >= window else history
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
    return [_ensure_valid(list(selected))]


def anti_pairs_predict(history, window=100):
    """反共現（正交覆蓋）"""
    recent = history[-window:] if len(history) >= window else history
    pair_freq = Counter()
    for d in recent:
        nums = sorted(d['numbers'][:PICK])
        for p in combinations(nums, 2):
            pair_freq[p] += 1
    num_cooc = Counter()
    for (a, b), f in pair_freq.items():
        num_cooc[a] += f
        num_cooc[b] += f
    candidates = sorted(range(1, MAX_NUM + 1), key=lambda x: num_cooc.get(x, 0))
    return [sorted(candidates[:PICK])]


def graph_centrality_predict(history, window=100):
    """度中心性"""
    recent = history[-window:] if len(history) >= window else history
    degree = Counter()
    for d in recent:
        nums = d['numbers'][:PICK]
        for a, b in combinations(sorted(nums), 2):
            degree[a] += 1
            degree[b] += 1
    return [_top_n_by_score(degree)]


# ============================================================
# 類別 12: 已驗證策略 (Validated)
# ============================================================
def fourier_rhythm_predict(history, window=500):
    """FFT 頻率節奏"""
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 20:
        return frequency_predict(history, 50)
    scores = {}
    for num in range(1, MAX_NUM + 1):
        seq = np.array([1.0 if num in d['numbers'][:PICK] else 0.0 for d in recent])
        seq = seq - seq.mean()
        if np.std(seq) < 1e-6:
            scores[num] = 0
            continue
        fft_res = np.fft.rfft(seq)
        power = np.abs(fft_res) ** 2
        if len(power) > 1:
            freqs = np.fft.rfftfreq(len(seq))
            main_idx = np.argmax(power[1:]) + 1
            period = 1.0 / freqs[main_idx] if freqs[main_idx] > 0 else len(seq)
            last_idx = 0
            for i in range(len(recent) - 1, -1, -1):
                if num in recent[i]['numbers'][:PICK]:
                    last_idx = i
                    break
            gap = len(recent) - 1 - last_idx
            alignment = 1.0 / (abs(gap - period) + 1)
            scores[num] = alignment * (power[main_idx] / (np.sum(power) + 1e-10))
        else:
            scores[num] = 0
    return [_top_n_by_score(scores)]


def triple_strike_3bet_predict(history, window=500):
    """Triple Strike 3注（已驗證 +0.98%）"""
    # Bet 1: Fourier Rhythm
    bet1 = fourier_rhythm_predict(history, window)[0]
    # Bet 2: Cold (exclude bet1)
    recent = history[-100:] if len(history) >= 100 else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    for n in range(1, MAX_NUM + 1):
        if n not in freq:
            freq[n] = 0
    cold_candidates = sorted([(n, f) for n, f in freq.items() if n not in bet1],
                            key=lambda x: x[1])
    bet2 = sorted([n for n, _ in cold_candidates[:PICK]])
    # Bet 3: Tail Balance (exclude bet1+bet2)
    used = set(bet1) | set(bet2)
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in used]
    remaining.sort(key=lambda x: -freq.get(x, 0))
    used_tails = set()
    bet3 = []
    for n in remaining:
        tail = n % 10
        if tail not in used_tails and len(bet3) < PICK:
            bet3.append(n)
            used_tails.add(tail)
    while len(bet3) < PICK:
        for n in remaining:
            if n not in bet3:
                bet3.append(n)
                break
    return [bet1, sorted(bet2[:PICK]), sorted(bet3[:PICK])]


def ts3_markov_freqortho_5bet_predict(history):
    """TS3+Markov+頻率正交 5注（已驗證 +1.77%, p=0.008）"""
    bets = triple_strike_3bet_predict(history)[:]
    used = set()
    for b in bets:
        used.update(b)
    # Bet 4: Markov (w=30, exclude used)
    recent30 = history[-30:] if len(history) >= 30 else history
    trans = Counter()
    for i in range(len(recent30) - 1):
        for p in recent30[i]['numbers'][:PICK]:
            for n in recent30[i + 1]['numbers'][:PICK]:
                trans[(p, n)] += 1
    scores = Counter()
    for prev in history[-1]['numbers'][:PICK]:
        for n in range(1, MAX_NUM + 1):
            if n not in used:
                scores[n] += trans.get((prev, n), 0)
    bet4 = _top_n_by_score(scores) if scores else _ensure_valid(
        [n for n in range(1, MAX_NUM + 1) if n not in used][:PICK])
    used.update(bet4)
    # Bet 5: Frequency Orthogonal (remaining)
    recent50 = history[-50:] if len(history) >= 50 else history
    freq50 = Counter(n for d in recent50 for n in d['numbers'][:PICK])
    remaining = [(n, freq50.get(n, 0)) for n in range(1, MAX_NUM + 1) if n not in used]
    remaining.sort(key=lambda x: -x[1])
    bet5 = sorted([n for n, _ in remaining[:PICK]])
    bets.extend([bet4, bet5])
    return bets


# ============================================================
# 策略註冊表 (Strategy Registry)
# ============================================================
def build_all_strategies() -> Dict[str, Callable]:
    """建立所有策略的完整字典"""
    strategies = {}

    # 統計類
    for w in [20, 50, 100, 200, 500]:
        strategies[f'frequency_w{w}'] = lambda h, w=w: frequency_predict(h, w)
    for w in [50, 100, 200]:
        strategies[f'cold_w{w}'] = lambda h, w=w: cold_number_predict(h, w)
    for w in [50, 100]:
        for t in [1.0, 1.5, 2.0]:
            strategies[f'deviation_w{w}_t{t}'] = lambda h, w=w, t=t: deviation_predict(h, w, t)
    for w in [50, 100]:
        strategies[f'hot_cold_mix_w{w}'] = lambda h, w=w: hot_cold_mix_predict(h, w)
    for w in [50, 100]:
        for eb in [1.0, 1.5, 2.0]:
            strategies[f'deviation_echo_P0_w{w}_e{eb}'] = lambda h, w=w, eb=eb: deviation_complement_predict(h, w, eb)

    # 機率類
    for w in [50, 100, 200]:
        strategies[f'bayesian_w{w}'] = lambda h, w=w: bayesian_predict(h, w)
    for w in [50, 100, 200]:
        strategies[f'cond_entropy_w{w}'] = lambda h, w=w: conditional_entropy_predict(h, w)
    for w in [50, 100]:
        strategies[f'mutual_info_w{w}'] = lambda h, w=w: mutual_info_predict(h, w)
    for w in [50, 100]:
        strategies[f'surprise_w{w}'] = lambda h, w=w: surprise_predict(h, w)
    for w in [50, 100]:
        strategies[f'mle_w{w}'] = lambda h, w=w: mle_predict(h, w)

    # 數學類
    for w in [50, 100]:
        strategies[f'sum_range_w{w}'] = lambda h, w=w: sum_range_predict(h, w)
    for w in [50, 100]:
        strategies[f'odd_even_w{w}'] = lambda h, w=w: odd_even_predict(h, w)
    for m in [5, 7, 10]:
        strategies[f'mod_arith_m{m}'] = lambda h, m=m: mod_arithmetic_predict(h, 50, m)
    strategies['prime_composite'] = prime_composite_predict
    strategies['ac_value'] = ac_value_predict

    # 序列類
    for w in [20, 30, 50, 100]:
        strategies[f'markov_o1_w{w}'] = lambda h, w=w: markov_order1_predict(h, w)
    for w in [50, 100]:
        strategies[f'markov_o2_w{w}'] = lambda h, w=w: markov_order2_predict(h, w)
    for w in [100, 200]:
        strategies[f'markov_o3_w{w}'] = lambda h, w=w: markov_order3_predict(h, w)
    for w in [50, 100]:
        for eb in [1.0, 1.5, 2.0]:
            strategies[f'lag2_echo_w{w}_e{eb}'] = lambda h, w=w, eb=eb: lag2_echo_predict(h, w, eb)
    for ps in [3, 4, 5]:
        strategies[f'pattern_match_ps{ps}'] = lambda h, ps=ps: pattern_match_predict(h, 100, ps)
    strategies['cycle_analysis'] = cycle_analysis_predict

    # 時窗類
    for d in [0.02, 0.05, 0.1, 0.2]:
        strategies[f'trend_exp_d{d}'] = lambda h, d=d: trend_exponential_predict(h, d)
    strategies['adaptive_window'] = adaptive_window_predict
    strategies['multi_window_consensus'] = multi_window_consensus_predict

    # 分布類
    for w in [50, 100, 200]:
        strategies[f'zone_balance_w{w}'] = lambda h, w=w: zone_balance_predict(h, w)
    for w in [50, 100, 200]:
        strategies[f'zone_transition_w{w}'] = lambda h, w=w: zone_transition_predict(h, w)
    for w in [50, 100]:
        strategies[f'tail_balance_w{w}'] = lambda h, w=w: tail_balance_predict(h, w)
    for mc in [0, 1]:
        strategies[f'consec_constraint_mc{mc}'] = lambda h, mc=mc: consecutive_constraint_predict(h, 100, mc)
    for sp in [25, 30, 35]:
        strategies[f'spread_constraint_sp{sp}'] = lambda h, sp=sp: spread_constraint_predict(h, 100, sp)

    # 蒙特卡羅
    for ns in [500, 1000]:
        strategies[f'monte_carlo_ns{ns}'] = lambda h, ns=ns: monte_carlo_predict(h, 100, ns)
    strategies['constraint_sat'] = constraint_satisfaction_predict
    strategies['weighted_random'] = weighted_random_predict

    # ML
    strategies['random_forest'] = random_forest_predict
    strategies['gradient_boosting'] = gradient_boosting_predict
    strategies['logistic_regression'] = logistic_regression_predict
    for nc in [3, 5, 7]:
        strategies[f'clustering_nc{nc}'] = lambda h, nc=nc: clustering_predict(h, 100, nc)

    # 集成
    for nm in [3, 5, 7]:
        strategies[f'voting_ensemble_n{nm}'] = lambda h, nm=nm: voting_ensemble_predict(h, nm)
    strategies['stacking_ensemble'] = stacking_ensemble_predict

    # 負面選擇
    for w in [30, 50, 100]:
        strategies[f'neg_elim_w{w}'] = lambda h, w=w: negative_elimination_predict(h, w)
    for w in [20, 30, 50]:
        strategies[f'anti_consensus_w{w}'] = lambda h, w=w: anti_consensus_predict(h, w)
    for w in [30, 50, 100]:
        strategies[f'contrarian_w{w}'] = lambda h, w=w: contrarian_predict(h, w)

    # 圖論
    for w in [50, 100, 200]:
        strategies[f'cooc_pairs_w{w}'] = lambda h, w=w: cooccurrence_pairs_predict(h, w)
    for w in [50, 100]:
        strategies[f'cooc_triplet_w{w}'] = lambda h, w=w: cooccurrence_triplet_predict(h, w)
    for w in [50, 100]:
        strategies[f'anti_pairs_w{w}'] = lambda h, w=w: anti_pairs_predict(h, w)
    for w in [50, 100, 200]:
        strategies[f'graph_centrality_w{w}'] = lambda h, w=w: graph_centrality_predict(h, w)

    # 已驗證
    strategies['fourier_rhythm'] = fourier_rhythm_predict
    strategies['triple_strike_3bet'] = triple_strike_3bet_predict
    strategies['ts3_markov_freqortho_5bet'] = ts3_markov_freqortho_5bet_predict

    return strategies


def build_quick_strategies() -> Dict[str, Callable]:
    """快速模式：每類只取代表性策略"""
    return {
        'frequency_w50': lambda h: frequency_predict(h, 50),
        'frequency_w100': lambda h: frequency_predict(h, 100),
        'cold_w100': lambda h: cold_number_predict(h, 100),
        'deviation_w50': lambda h: deviation_predict(h, 50),
        'hot_cold_mix_w50': lambda h: hot_cold_mix_predict(h, 50),
        'deviation_echo_P0': lambda h: deviation_complement_predict(h, 50, 1.5),
        'bayesian_w100': lambda h: bayesian_predict(h, 100),
        'cond_entropy_w100': lambda h: conditional_entropy_predict(h, 100),
        'mutual_info_w100': lambda h: mutual_info_predict(h, 100),
        'sum_range_w100': lambda h: sum_range_predict(h, 100),
        'odd_even_w100': lambda h: odd_even_predict(h, 100),
        'prime_composite': prime_composite_predict,
        'markov_o1_w30': lambda h: markov_order1_predict(h, 30),
        'markov_o2_w50': lambda h: markov_order2_predict(h, 50),
        'lag2_echo_w50': lambda h: lag2_echo_predict(h, 50, 1.5),
        'cycle_analysis': cycle_analysis_predict,
        'trend_exp_d005': lambda h: trend_exponential_predict(h, 0.05),
        'adaptive_window': adaptive_window_predict,
        'zone_balance_w100': lambda h: zone_balance_predict(h, 100),
        'zone_transition_w100': lambda h: zone_transition_predict(h, 100),
        'tail_balance_w100': lambda h: tail_balance_predict(h, 100),
        'monte_carlo_ns1000': lambda h: monte_carlo_predict(h, 100, 1000),
        'constraint_sat': constraint_satisfaction_predict,
        'random_forest': random_forest_predict,
        'clustering_nc5': lambda h: clustering_predict(h, 100, 5),
        'voting_ensemble_n5': lambda h: voting_ensemble_predict(h, 5),
        'neg_elim_w100': lambda h: negative_elimination_predict(h, 100),
        'anti_consensus_w30': lambda h: anti_consensus_predict(h, 30),
        'cooc_pairs_w100': lambda h: cooccurrence_pairs_predict(h, 100),
        'graph_centrality_w100': lambda h: graph_centrality_predict(h, 100),
        'fourier_rhythm': fourier_rhythm_predict,
        'triple_strike_3bet': triple_strike_3bet_predict,
        'ts3_markov_freqortho_5bet': ts3_markov_freqortho_5bet_predict,
    }
