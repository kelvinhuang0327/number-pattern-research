"""
Phase 3: 極限搜尋研究AI (Extreme Search Research AI)
=====================================================
6 大策略類別 + 7 項搜尋方法升級

類別 1: 微弱信號放大 (Ultra-Weak Signal Amplification)
類別 2: 非線性組合 (Non-Linear Combination)
類別 3: 條件觸發 (Conditional Trigger) — 不一定每期都下注
類別 4: 罕見事件 (Rare Event)
類別 5: 非平穩 (Non-Stationary / Drift-Adaptive)
類別 6: 反直覺 (Counter-Intuitive)

搜尋升級: 特徵交叉暴力搜尋、高階統計矩、PCA 隱變量、KL 散度漂移、
         局部區間挖掘、Regime Switching、集合層級評估

每個策略：strategy(history: List[Dict]) -> List[List[int]]
條件策略：返回 [] 表示跳過此期
"""
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations
from typing import List, Dict, Callable, Tuple, Optional

from .config import MAX_NUM, PICK, PRIMES, FEATURE_NAMES, NUM_FEATURES
from .feature_library import FeatureLibrary


# ============================================================
# 共用輔助函數
# ============================================================
def _top_n(scores: Dict[int, float], n: int = PICK) -> List[int]:
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([num for num, _ in ranked[:n]])


def _ensure_valid(numbers: List[int], n: int = PICK) -> List[int]:
    valid = sorted(set(num for num in numbers if 1 <= num <= MAX_NUM))[:n]
    if len(valid) < n:
        remaining = [i for i in range(1, MAX_NUM + 1) if i not in valid]
        np.random.shuffle(remaining)
        valid.extend(remaining[:n - len(valid)])
    return sorted(valid[:n])


def _freq_map(history, window, pick=PICK):
    recent = history[-window:] if len(history) >= window else history
    freq = Counter()
    for d in recent:
        for n in d['numbers'][:pick]:
            freq[n] += 1
    return freq, len(recent)


def _draw_features(history, window=30):
    """計算整期層級特徵 (非個別號碼)"""
    recent = history[-window:] if len(history) >= window else history
    features = []
    for d in recent:
        nums = sorted(d['numbers'][:PICK])
        s = sum(nums)
        spread = nums[-1] - nums[0]
        odd_count = sum(1 for n in nums if n % 2 == 1)
        zones = [0, 0, 0]
        for n in nums:
            z = 0 if n <= 16 else (1 if n <= 33 else 2)
            zones[z] += 1
        consec = sum(1 for i in range(len(nums) - 1) if nums[i + 1] - nums[i] == 1)
        features.append({
            'sum': s, 'spread': spread, 'odd_count': odd_count,
            'zones': zones, 'consec': consec, 'numbers': nums
        })
    return features


# ============================================================
# 類別 1: 微弱信號放大 (Ultra-Weak Signal Amplification)
# ============================================================
def stacked_micro_signals(history, window=100):
    """
    堆疊 20+ 微弱信號：每個特徵 normalize 到 [0,1] 後加總。
    單一特徵邊際 ~0，但堆疊可能放大。
    """
    fl = FeatureLibrary()
    feat = fl.extract_all(history[-window:] if len(history) >= window else history)

    # normalize per column
    for j in range(feat.shape[1]):
        col = feat[:, j]
        mn, mx = col.min(), col.max()
        if mx - mn > 1e-8:
            feat[:, j] = (col - mn) / (mx - mn)
        else:
            feat[:, j] = 0.5

    scores = {}
    for i in range(MAX_NUM):
        scores[i + 1] = float(feat[i].sum())
    return [_top_n(scores)]


def rank_aggregation_borda(history, window=100):
    """
    Borda 排名聚合：10 種評分方法各產生排名，取平均排名最佳者。
    """
    methods_scores = []

    # M1: freq_50
    freq, _ = _freq_map(history, 50)
    methods_scores.append({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})

    # M2: freq_100
    freq, _ = _freq_map(history, 100)
    methods_scores.append({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})

    # M3: cold_100 (inverted)
    freq, _ = _freq_map(history, 100)
    methods_scores.append({n: -freq.get(n, 0) for n in range(1, MAX_NUM + 1)})

    # M4: gap score (larger gap = higher score)
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers'][:PICK]:
            last_seen[n] = i
    methods_scores.append({n: len(history) - last_seen.get(n, 0) for n in range(1, MAX_NUM + 1)})

    # M5: lag1 echo
    lag1 = set(history[-1]['numbers'][:PICK]) if history else set()
    methods_scores.append({n: (10.0 if n in lag1 else 0.0) for n in range(1, MAX_NUM + 1)})

    # M6: lag2 echo
    lag2 = set(history[-2]['numbers'][:PICK]) if len(history) >= 2 else set()
    methods_scores.append({n: (10.0 if n in lag2 else 0.0) for n in range(1, MAX_NUM + 1)})

    # M7: deviation (overdue)
    freq100, w = _freq_map(history, 100)
    expected = w * PICK / MAX_NUM
    methods_scores.append({n: expected - freq100.get(n, 0) for n in range(1, MAX_NUM + 1)})

    # M8: EMA weighted frequency
    ema = {}
    for n in range(1, MAX_NUM + 1):
        score = 0
        for j, d in enumerate(history[-200:]):
            if n in d['numbers'][:PICK]:
                age = min(200, len(history)) - 1 - j
                score += np.exp(-0.05 * age)
        ema[n] = score
    methods_scores.append(ema)

    # M9: neighbor boost
    freq100, _ = _freq_map(history, 100)
    nb = {}
    for n in range(1, MAX_NUM + 1):
        s = 0
        cnt = 0
        for adj in [n - 1, n + 1]:
            if 1 <= adj <= MAX_NUM:
                s += freq100.get(adj, 0)
                cnt += 1
        nb[n] = s / cnt if cnt > 0 else 0
    methods_scores.append(nb)

    # M10: zone deficit
    freq100, w100 = _freq_map(history, 100)
    zones_expected = {0: 16 / 49 * PICK * w100, 1: 17 / 49 * PICK * w100, 2: 16 / 49 * PICK * w100}
    zones_actual = {0: 0, 1: 0, 2: 0}
    for n in range(1, MAX_NUM + 1):
        z = 0 if n <= 16 else (1 if n <= 33 else 2)
        zones_actual[z] += freq100.get(n, 0)
    zone_deficit = {}
    for n in range(1, MAX_NUM + 1):
        z = 0 if n <= 16 else (1 if n <= 33 else 2)
        zone_deficit[n] = zones_expected[z] - zones_actual[z]
    methods_scores.append(zone_deficit)

    # Borda aggregation
    all_ranks = {n: 0 for n in range(1, MAX_NUM + 1)}
    for ms in methods_scores:
        ranked = sorted(ms.items(), key=lambda x: -x[1])
        for rank, (num, _) in enumerate(ranked):
            all_ranks[num] += rank  # 排名越小越好

    # 選出平均排名最佳 (最小)
    best = sorted(all_ranks.items(), key=lambda x: x[1])
    return [sorted([n for n, _ in best[:PICK]])]


def consensus_threshold(history, window=100, min_agree=4):
    """
    共識門檻策略：多種方法投票，只選至少 min_agree 種方法都推薦的號碼。
    """
    methods = [
        lambda h: set(_top_n({n: f.get(n, 0) for n in range(1, MAX_NUM + 1)}, 12))
        for f in [_freq_map(h, w)[0] for w, h in [(50, history), (100, history)]]
    ]

    # 直接計算投票
    votes = Counter()
    pools = []

    # Pool 1: freq top-12 w50
    f50, _ = _freq_map(history, 50)
    top12_f50 = set(_top_n({n: f50.get(n, 0) for n in range(1, MAX_NUM + 1)}, 12))
    pools.append(top12_f50)

    # Pool 2: freq top-12 w100
    f100, _ = _freq_map(history, 100)
    top12_f100 = set(_top_n({n: f100.get(n, 0) for n in range(1, MAX_NUM + 1)}, 12))
    pools.append(top12_f100)

    # Pool 3: gap overdue top-12
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers'][:PICK]:
            last_seen[n] = i
    gap_scores = {n: len(history) - last_seen.get(n, 0) for n in range(1, MAX_NUM + 1)}
    pools.append(set(_top_n(gap_scores, 12)))

    # Pool 4: deviation top-12
    f100, w = _freq_map(history, 100)
    expected = w * PICK / MAX_NUM
    dev = {n: abs(f100.get(n, 0) - expected) for n in range(1, MAX_NUM + 1)}
    pools.append(set(_top_n(dev, 12)))

    # Pool 5: lag1+lag2
    lag1 = set(history[-1]['numbers'][:PICK]) if history else set()
    lag2 = set(history[-2]['numbers'][:PICK]) if len(history) >= 2 else set()
    echo_scores = {n: (5 if n in lag1 else 0) + (3 if n in lag2 else 0) for n in range(1, MAX_NUM + 1)}
    pools.append(set(_top_n(echo_scores, 12)))

    # Pool 6: EMA
    ema = {}
    for n in range(1, MAX_NUM + 1):
        s = 0
        for j, d in enumerate(history[-100:]):
            if n in d['numbers'][:PICK]:
                s += np.exp(-0.05 * (min(100, len(history)) - 1 - j))
        ema[n] = s
    pools.append(set(_top_n(ema, 12)))

    # Pool 7: Markov-like (transition)
    if len(history) >= 2:
        trans = Counter()
        recent50 = history[-50:]
        for i in range(len(recent50) - 1):
            for p in recent50[i]['numbers'][:PICK]:
                for n in recent50[i + 1]['numbers'][:PICK]:
                    trans[(p, n)] += 1
        last_nums = history[-1]['numbers'][:PICK]
        mk = Counter()
        for prev in last_nums:
            for n in range(1, MAX_NUM + 1):
                mk[n] += trans.get((prev, n), 0)
        pools.append(set(_top_n(dict(mk), 12)))
    else:
        pools.append(set())

    # Count votes
    for pool in pools:
        for n in pool:
            votes[n] += 1

    # Select numbers meeting threshold
    candidates = [n for n, v in votes.items() if v >= min_agree]
    if len(candidates) >= PICK:
        # pick top by vote count, then freq
        ranked = sorted(candidates, key=lambda n: (-votes[n], -f100.get(n, 0)))
        return [sorted(ranked[:PICK])]
    elif len(candidates) > 0:
        return [_ensure_valid(candidates)]
    else:
        # fallback: top by votes
        ranked = sorted(votes.items(), key=lambda x: -x[1])
        return [sorted([n for n, _ in ranked[:PICK]])]


def weighted_z_ensemble(history, window=100):
    """
    Z-score 加權集成：多窗口 z-score 加權求和。
    每個號碼在不同窗口的 z-score 求和，放大一致性信號。
    """
    z_total = {n: 0.0 for n in range(1, MAX_NUM + 1)}
    for w in [20, 50, 100, 200]:
        freq, actual_w = _freq_map(history, w)
        expected = actual_w * PICK / MAX_NUM
        se = np.sqrt(expected * (1 - PICK / MAX_NUM)) if expected > 0 else 1
        for n in range(1, MAX_NUM + 1):
            z = (freq.get(n, 0) - expected) / se if se > 0 else 0
            z_total[n] += z
    return [_top_n(z_total)]


# ============================================================
# 類別 2: 非線性組合 (Non-Linear Combination)
# ============================================================
def feature_cross_top_pairs(history, window=100, top_k=10):
    """
    系統性特徵交叉：計算 C(35,2)=595 對，用歷史排名積分篩選最佳交叉對。
    用 top_k 交叉特徵的聚合分數選號。
    """
    fl = FeatureLibrary()
    feat = fl.extract_all(history[-window:] if len(history) >= window else history)

    # normalize
    for j in range(feat.shape[1]):
        col = feat[:, j]
        mn, mx = col.min(), col.max()
        if mx - mn > 1e-8:
            feat[:, j] = (col - mn) / (mx - mn)
        else:
            feat[:, j] = 0.5

    # 計算每對交叉特徵的區分度 (top-6 vs bottom-43 的差距)
    n_feat = feat.shape[1]
    cross_quality = []
    for fi in range(n_feat):
        for fj in range(fi + 1, n_feat):
            cross = feat[:, fi] * feat[:, fj]
            top6_idx = np.argsort(-cross)[:PICK]
            top6_mean = cross[top6_idx].mean()
            rest_mean = np.delete(cross, top6_idx).mean()
            spread = top6_mean - rest_mean
            cross_quality.append((fi, fj, spread, cross))

    cross_quality.sort(key=lambda x: -x[2])

    # 用 top_k 交叉分數的加總選號
    scores = np.zeros(MAX_NUM)
    for fi, fj, spread, cross in cross_quality[:top_k]:
        scores += cross

    result = {}
    for i in range(MAX_NUM):
        result[i + 1] = float(scores[i])
    return [_top_n(result)]


def multiplicative_ensemble(history, window=100):
    """
    乘法集成：策略信心值相乘（非加法），放大一致性。
    """
    # 多方法信心度
    confidences = np.ones(MAX_NUM)

    # C1: freq normalized
    freq, w = _freq_map(history, window)
    max_f = max(freq.values()) if freq else 1
    for n in range(1, MAX_NUM + 1):
        confidences[n - 1] *= (0.5 + freq.get(n, 0) / max_f)

    # C2: gap overdue normalized
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers'][:PICK]:
            last_seen[n] = i
    max_gap = len(history) + 1
    for n in range(1, MAX_NUM + 1):
        gap = len(history) - last_seen.get(n, 0)
        confidences[n - 1] *= (0.5 + gap / max_gap)

    # C3: lag echo
    lag1 = set(history[-1]['numbers'][:PICK]) if history else set()
    lag2 = set(history[-2]['numbers'][:PICK]) if len(history) >= 2 else set()
    for n in range(1, MAX_NUM + 1):
        boost = 1.0
        if n in lag1:
            boost *= 1.3
        if n in lag2:
            boost *= 1.2
        confidences[n - 1] *= boost

    # C4: zone balance
    freq100, w100 = _freq_map(history, 100)
    zone_totals = [0, 0, 0]
    zone_sizes = [16, 17, 16]
    for n in range(1, MAX_NUM + 1):
        z = 0 if n <= 16 else (1 if n <= 33 else 2)
        zone_totals[z] += freq100.get(n, 0)
    zone_expected = [zs / MAX_NUM * PICK * w100 for zs in zone_sizes]
    for n in range(1, MAX_NUM + 1):
        z = 0 if n <= 16 else (1 if n <= 33 else 2)
        deficit_ratio = zone_expected[z] / (zone_totals[z] + 1e-10)
        confidences[n - 1] *= max(0.5, min(2.0, deficit_ratio))

    result = {i + 1: float(confidences[i]) for i in range(MAX_NUM)}
    return [_top_n(result)]


def quadratic_interaction(history, window=100):
    """
    二次交互效應：freq × gap、freq × deviation 等二次項組合。
    """
    freq, w = _freq_map(history, window)
    expected = w * PICK / MAX_NUM

    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers'][:PICK]:
            last_seen[n] = i

    scores = {}
    for n in range(1, MAX_NUM + 1):
        f_norm = freq.get(n, 0) / w if w > 0 else 0
        gap = len(history) - last_seen.get(n, 0)
        gap_norm = gap / MAX_NUM
        dev = abs(freq.get(n, 0) - expected) / (expected + 1e-10)

        # 二次交互
        score = (f_norm * gap_norm * 3.0 +  # overdue hot number
                 f_norm * dev * 2.0 +        # deviating hot
                 gap_norm * dev * 1.5)        # deviating overdue
        scores[n] = score

    return [_top_n(scores)]


# ============================================================
# 類別 3: 條件觸發 (Conditional Trigger)
# 返回 [] = 跳過此期
# ============================================================
def skip_low_confidence(history, window=100, threshold=0.6):
    """
    低信心跳過：多方法一致性 < threshold 時不下注。
    """
    pools = []

    # Method 1: freq top-10
    f50, _ = _freq_map(history, 50)
    pools.append(set(_top_n({n: f50.get(n, 0) for n in range(1, MAX_NUM + 1)}, 10)))

    # Method 2: freq100 top-10
    f100, _ = _freq_map(history, 100)
    pools.append(set(_top_n({n: f100.get(n, 0) for n in range(1, MAX_NUM + 1)}, 10)))

    # Method 3: gap top-10
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers'][:PICK]:
            last_seen[n] = i
    gap_s = {n: len(history) - last_seen.get(n, 0) for n in range(1, MAX_NUM + 1)}
    pools.append(set(_top_n(gap_s, 10)))

    # Method 4: deviation
    expected = len(history[-100:]) * PICK / MAX_NUM
    dev_s = {n: abs(f100.get(n, 0) - expected) for n in range(1, MAX_NUM + 1)}
    pools.append(set(_top_n(dev_s, 10)))

    # Method 5: EMA
    ema = {}
    for n in range(1, MAX_NUM + 1):
        s = 0
        for j, d in enumerate(history[-100:]):
            if n in d['numbers'][:PICK]:
                s += np.exp(-0.05 * (min(100, len(history)) - 1 - j))
        ema[n] = s
    pools.append(set(_top_n(ema, 10)))

    # 計算最大共識
    votes = Counter()
    for pool in pools:
        for n in pool:
            votes[n] += 1

    max_agreement = max(votes.values()) if votes else 0
    confidence = max_agreement / len(pools)

    if confidence < threshold:
        return []  # 跳過

    # 挑選高共識號碼
    ranked = sorted(votes.items(), key=lambda x: -x[1])
    return [sorted([n for n, _ in ranked[:PICK]])]


def regime_gated(history, window=100, regime_window=10):
    """
    Regime 門控：只在偵測到有利 regime 時下注。
    判斷：近 regime_window 期的 M3+ 率（對比多種策略）高於平均才下注。
    """
    if len(history) < regime_window + 50:
        return []

    # 計算近 regime_window 期的「sum 偏差」做 regime indicator
    recent = history[-regime_window:]
    sums = [sum(d['numbers'][:PICK]) for d in recent]
    avg_sum = np.mean(sums)

    # 歷史平均 sum
    hist_sums = [sum(d['numbers'][:PICK]) for d in history[-200:]]
    hist_avg = np.mean(hist_sums)
    hist_std = np.std(hist_sums) + 1e-10

    # regime signal: sum 偏差大 = 不穩定期 → 跳過
    z_sum = abs(avg_sum - hist_avg) / hist_std
    if z_sum > 1.5:
        return []  # 不穩定 regime，跳過

    # 正常 regime：使用頻率法下注
    freq, w = _freq_map(history, window)
    return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]


def post_anomaly_trigger(history, window=50):
    """
    異常後觸發：在極端 sum 開獎後的 1-2 期下注。
    研究假說：極端事件後有均值回歸傾向。
    """
    if len(history) < 50:
        return []

    # 檢查上一期是否異常
    last_sum = sum(history[-1]['numbers'][:PICK])
    sums = [sum(d['numbers'][:PICK]) for d in history[-100:]]
    avg = np.mean(sums)
    std = np.std(sums) + 1e-10

    z = abs(last_sum - avg) / std
    if z < 1.5:
        return []  # 上期不夠異常，跳過

    # 異常後：偏向均值回歸方向
    if last_sum > avg:
        # 上期偏高 → 下期偏低號碼更可能
        scores = {n: (MAX_NUM + 1 - n) for n in range(1, MAX_NUM + 1)}
    else:
        # 上期偏低 → 下期偏高號碼更可能
        scores = {n: n for n in range(1, MAX_NUM + 1)}

    # 混合頻率信號
    freq, _ = _freq_map(history, 50)
    max_f = max(freq.values()) if freq else 1
    for n in range(1, MAX_NUM + 1):
        scores[n] += freq.get(n, 0) / max_f * 10

    return [_top_n(scores)]


def gap_trigger(history, gap_multiplier=2.0):
    """
    缺口觸發：只在某號碼缺席 > 平均缺口×multiplier 時，才將該號碼納入。
    至少要 6 個號碼觸發才下注，否則跳過。
    """
    if len(history) < 100:
        return []

    last_seen = {}
    all_gaps = defaultdict(list)
    for i, d in enumerate(history):
        for n in d['numbers'][:PICK]:
            if n in last_seen:
                all_gaps[n].append(i - last_seen[n])
            last_seen[n] = i

    current_idx = len(history)
    triggered = []
    urgency = {}
    for n in range(1, MAX_NUM + 1):
        cur_gap = current_idx - last_seen.get(n, 0)
        avg_gap = np.mean(all_gaps[n]) if all_gaps[n] else PICK
        if cur_gap > avg_gap * gap_multiplier:
            triggered.append(n)
            urgency[n] = cur_gap / (avg_gap + 1e-10)

    if len(triggered) < PICK:
        return []  # 沒有足夠觸發，跳過

    ranked = sorted(triggered, key=lambda n: -urgency[n])
    return [sorted(ranked[:PICK])]


def volatility_gate(history, window=30, low_vol_only=True):
    """
    波動率門控：只在低波動期下注（假說：低波動 = 更可預測）。
    """
    if len(history) < 60:
        return []

    # 計算近期 per-draw sum 波動
    recent_sums = [sum(d['numbers'][:PICK]) for d in history[-window:]]
    recent_vol = np.std(recent_sums)

    # 歷史波動
    hist_sums = [sum(d['numbers'][:PICK]) for d in history[-200:]]
    hist_vol = np.std(hist_sums) + 1e-10

    vol_ratio = recent_vol / hist_vol

    if low_vol_only and vol_ratio > 1.0:
        return []  # 高波動期，跳過

    if not low_vol_only and vol_ratio < 1.0:
        return []  # 低波動期，跳過

    freq, _ = _freq_map(history, 50)
    return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]


# ============================================================
# 類別 4: 罕見事件 (Rare Event)
# ============================================================
def extreme_sum_follow(history, window=200, tail_pct=0.10):
    """
    極端 sum 後追蹤：在歷史中找出 sum 在尾端 10% 的開獎，
    分析它們下一期的號碼分布，用於預測。
    """
    if len(history) < window + 1:
        return [_top_n({n: 0 for n in range(1, MAX_NUM + 1)})]

    recent = history[-window:]
    sums = [sum(d['numbers'][:PICK]) for d in recent]
    low_th = np.percentile(sums, tail_pct * 100)
    high_th = np.percentile(sums, (1 - tail_pct) * 100)

    # 找出極端 sum 後的下一期號碼
    follow_freq = Counter()
    n_events = 0
    for i in range(len(recent) - 1):
        s = sums[i]
        if s <= low_th or s >= high_th:
            n_events += 1
            for n in recent[i + 1]['numbers'][:PICK]:
                follow_freq[n] += 1

    if n_events < 3:
        # 資料太少，回退到頻率法
        freq, _ = _freq_map(history, 100)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    return [_top_n({n: follow_freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]


def consecutive_follow(history, window=200):
    """
    連號後追蹤：當上一期有連號時，分析歷史中連號後出現的號碼模式。
    """
    if len(history) < 50:
        freq, _ = _freq_map(history, 50)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    # 檢查是否有連號
    recent = history[-window:] if len(history) >= window else history

    follow_freq = Counter()
    n_events = 0
    for i in range(len(recent) - 1):
        nums = sorted(recent[i]['numbers'][:PICK])
        has_consec = any(nums[j + 1] - nums[j] == 1 for j in range(len(nums) - 1))
        if has_consec:
            n_events += 1
            for n in recent[i + 1]['numbers'][:PICK]:
                follow_freq[n] += 1

    if n_events < 5:
        freq, _ = _freq_map(history, 100)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    scores = {n: follow_freq.get(n, 0) / n_events for n in range(1, MAX_NUM + 1)}
    return [_top_n(scores)]


def drought_break_follow(history, window=200, drought_threshold=15):
    """
    乾旱突破追蹤：當某號碼結束長期缺席時，它的「鄰居」下期更常出現？
    """
    if len(history) < 50:
        freq, _ = _freq_map(history, 50)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    recent = history[-window:] if len(history) >= window else history

    # 找出每期「結束乾旱」的號碼
    last_seen = {}
    neighbor_boost = Counter()
    n_events = 0
    for i, d in enumerate(recent):
        for n in d['numbers'][:PICK]:
            if n in last_seen and (i - last_seen[n]) > drought_threshold:
                n_events += 1
                # 看下一期的鄰居是否出現
                if i + 1 < len(recent):
                    next_nums = set(recent[i + 1]['numbers'][:PICK])
                    for adj in [n - 2, n - 1, n, n + 1, n + 2]:
                        if 1 <= adj <= MAX_NUM and adj in next_nums:
                            neighbor_boost[adj] += 1
            last_seen[n] = i

    if n_events < 3:
        freq, _ = _freq_map(history, 100)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    # 現在誰剛結束乾旱？
    current_drought_breakers = set()
    if len(history) >= 2:
        prev_last_seen = {}
        for i, d in enumerate(history[:-1]):
            for n in d['numbers'][:PICK]:
                prev_last_seen[n] = i
        for n in history[-1]['numbers'][:PICK]:
            if n in prev_last_seen and (len(history) - 1 - prev_last_seen[n]) > drought_threshold:
                current_drought_breakers.add(n)

    scores = {n: 0.0 for n in range(1, MAX_NUM + 1)}
    for n in current_drought_breakers:
        for adj in [n - 2, n - 1, n, n + 1, n + 2]:
            if 1 <= adj <= MAX_NUM:
                scores[adj] += 5.0

    # 加上基礎頻率
    freq, _ = _freq_map(history, 100)
    for n in range(1, MAX_NUM + 1):
        scores[n] += freq.get(n, 0) * 0.1

    return [_top_n(scores)]


def zone_burst_follow(history, window=20, burst_threshold=4):
    """
    區域爆發追蹤：當某一區域在最近 window 期爆發 (佔比 > burst_threshold)，
    預測下一期該區域會降溫，轉移到其他區域。
    """
    if len(history) < window:
        freq, _ = _freq_map(history, 50)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    # 區域定義
    zones = {0: range(1, 17), 1: range(17, 34), 2: range(34, 50)}
    recent = history[-window:]
    zone_counts = {0: 0, 1: 0, 2: 0}
    for d in recent:
        for n in d['numbers'][:PICK]:
            z = 0 if n <= 16 else (1 if n <= 33 else 2)
            zone_counts[z] += 1

    # 找出爆發區域
    per_draw_expected = PICK / 3
    burst_zones = set()
    for z, cnt in zone_counts.items():
        if cnt / window > per_draw_expected * 1.3:  # 超過期望 30%
            burst_zones.add(z)

    if not burst_zones:
        freq, _ = _freq_map(history, 50)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    # 從非爆發區域選號
    cool_zones = set(range(3)) - burst_zones
    scores = {}
    freq, _ = _freq_map(history, 100)
    for n in range(1, MAX_NUM + 1):
        z = 0 if n <= 16 else (1 if n <= 33 else 2)
        if z in cool_zones:
            scores[n] = freq.get(n, 0) + 3
        else:
            scores[n] = freq.get(n, 0) * 0.5

    return [_top_n(scores)]


# ============================================================
# 類別 5: 非平穩 / 漂移自適應 (Non-Stationary / Drift-Adaptive)
# ============================================================
def drift_adaptive_ewma(history, alpha=0.1, window=200):
    """
    EWMA 漂移偵測：追蹤每個號碼頻率的指數加權移動平均，
    選擇 EWMA 上升中的號碼。
    """
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 20:
        return [_top_n({n: 0 for n in range(1, MAX_NUM + 1)})]

    # 計算 EWMA
    ewma = {n: 0.0 for n in range(1, MAX_NUM + 1)}
    for d in recent:
        appeared = set(d['numbers'][:PICK])
        for n in range(1, MAX_NUM + 1):
            x = 1.0 if n in appeared else 0.0
            ewma[n] = alpha * x + (1 - alpha) * ewma[n]

    # 計算 EWMA 趨勢 (近期 vs 中期)
    ewma_mid = {n: 0.0 for n in range(1, MAX_NUM + 1)}
    mid_data = recent[:-min(20, len(recent) // 2)] if len(recent) > 20 else recent
    for d in mid_data:
        appeared = set(d['numbers'][:PICK])
        for n in range(1, MAX_NUM + 1):
            x = 1.0 if n in appeared else 0.0
            ewma_mid[n] = alpha * x + (1 - alpha) * ewma_mid[n]

    # 上升趨勢 = ewma_now > ewma_mid
    scores = {}
    for n in range(1, MAX_NUM + 1):
        trend = ewma[n] - ewma_mid[n]
        scores[n] = ewma[n] + trend * 5.0  # 趨勢加權

    return [_top_n(scores)]


def changepoint_adaptive(history, cusum_threshold=3.0, window=300):
    """
    CUSUM 變點偵測：偵測頻率分布的結構性轉變，
    轉變後只使用轉變後的資料。
    """
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 50:
        freq, _ = _freq_map(history, 50)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    # CUSUM on total sum per draw
    sums = [sum(d['numbers'][:PICK]) for d in recent]
    avg = np.mean(sums)
    cusum_pos = 0
    cusum_neg = 0
    change_point = 0

    for i, s in enumerate(sums):
        cusum_pos = max(0, cusum_pos + s - avg - 0.5)
        cusum_neg = max(0, cusum_neg - s + avg - 0.5)
        if cusum_pos > cusum_threshold * np.std(sums) or cusum_neg > cusum_threshold * np.std(sums):
            change_point = i
            cusum_pos = 0
            cusum_neg = 0

    # 使用變點後資料
    if change_point > 0 and change_point < len(recent) - 10:
        post_change = recent[change_point:]
    else:
        post_change = recent[-50:]

    freq = Counter()
    for d in post_change:
        for n in d['numbers'][:PICK]:
            freq[n] += 1

    return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]


def kl_drift_selector(history, window_short=30, window_long=200):
    """
    KL 散度漂移選號：比較短期 vs 長期頻率分布的 KL 散度，
    選擇短期偏離最大方向的號碼。
    """
    freq_s, ws = _freq_map(history, window_short)
    freq_l, wl = _freq_map(history, window_long)

    scores = {}
    for n in range(1, MAX_NUM + 1):
        p_short = (freq_s.get(n, 0) + 1) / (ws * PICK / MAX_NUM * MAX_NUM + MAX_NUM)
        p_long = (freq_l.get(n, 0) + 1) / (wl * PICK / MAX_NUM * MAX_NUM + MAX_NUM)
        # 個別號碼的 KL 貢獻 (short vs long)
        kl_contribution = p_short * np.log(p_short / (p_long + 1e-10) + 1e-10)
        scores[n] = kl_contribution if kl_contribution > 0 else 0

    return [_top_n(scores)]


def regime_momentum(history, regime_window=15, window=100):
    """
    Regime Momentum：偵測近期 regime (偏高/偏低/平衡)，
    在同 regime 狀態下使用 regime-specific 歷史資料。
    """
    if len(history) < 100:
        freq, _ = _freq_map(history, 50)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    # 判斷當前 regime
    recent_sums = [sum(d['numbers'][:PICK]) for d in history[-regime_window:]]
    avg_recent = np.mean(recent_sums)

    long_sums = [sum(d['numbers'][:PICK]) for d in history[-window:]]
    avg_long = np.mean(long_sums)
    std_long = np.std(long_sums) + 1e-10

    z = (avg_recent - avg_long) / std_long

    if z > 0.5:
        regime = 'high'
    elif z < -0.5:
        regime = 'low'
    else:
        regime = 'neutral'

    # 找出同 regime 的歷史期
    regime_history = []
    for i in range(regime_window, len(history) - regime_window):
        local_avg = np.mean([sum(history[j]['numbers'][:PICK])
                            for j in range(max(0, i - regime_window), i)])
        local_z = (local_avg - avg_long) / std_long
        if regime == 'high' and local_z > 0.5:
            regime_history.append(history[i])
        elif regime == 'low' and local_z < -0.5:
            regime_history.append(history[i])
        elif regime == 'neutral' and abs(local_z) <= 0.5:
            regime_history.append(history[i])

    if len(regime_history) < 10:
        freq, _ = _freq_map(history, 50)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    freq = Counter()
    for d in regime_history[-100:]:
        for n in d['numbers'][:PICK]:
            freq[n] += 1

    return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]


# ============================================================
# 類別 6: 反直覺 (Counter-Intuitive)
# ============================================================
def anti_streak(history, streak_threshold=3, window=100):
    """
    反連續：排除連續出現 >= streak_threshold 期的號碼（均值回歸假說）。
    """
    if len(history) < streak_threshold:
        freq, _ = _freq_map(history, 50)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    # 找出連續出現的號碼
    streak_nums = set()
    for n in range(1, MAX_NUM + 1):
        streak = 0
        for j in range(len(history) - 1, max(len(history) - 20, -1), -1):
            if n in history[j]['numbers'][:PICK]:
                streak += 1
            else:
                break
        if streak >= streak_threshold:
            streak_nums.add(n)

    # 從非連續號碼中選
    freq, _ = _freq_map(history, window)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        if n in streak_nums:
            scores[n] = 0  # 排除
        else:
            scores[n] = freq.get(n, 0)

    return [_top_n(scores)]


def anti_hot_zone(history, window=50):
    """
    反熱區：刻意避開最熱區域，從較冷區域選號。
    """
    freq, _ = _freq_map(history, window)
    zone_totals = {0: 0, 1: 0, 2: 0}
    for n in range(1, MAX_NUM + 1):
        z = 0 if n <= 16 else (1 if n <= 33 else 2)
        zone_totals[z] += freq.get(n, 0)

    hottest = max(zone_totals, key=zone_totals.get)

    scores = {}
    for n in range(1, MAX_NUM + 1):
        z = 0 if n <= 16 else (1 if n <= 33 else 2)
        if z == hottest:
            scores[n] = freq.get(n, 0) * 0.3  # 降權
        else:
            scores[n] = freq.get(n, 0) * 1.5  # 加權

    return [_top_n(scores)]


def max_entropy_pick(history, window=100):
    """
    最大熵選號：選出使組合 Shannon 熵最大化的 6 個號碼。
    相對於近期分布，entropy max = 最「平衡」的選擇。
    """
    freq, w = _freq_map(history, window)
    total = sum(freq.values()) or 1

    # 每個號碼的頻率概率
    probs = {}
    for n in range(1, MAX_NUM + 1):
        probs[n] = (freq.get(n, 0) + 0.5) / (total + MAX_NUM * 0.5)

    # 選擇使聯合熵最大的組合（近似：選與均勻分布偏差最小的號碼）
    target_p = 1.0 / MAX_NUM
    deviation = {}
    for n in range(1, MAX_NUM + 1):
        deviation[n] = -abs(probs[n] - target_p)  # 偏差越小 = 分數越高

    return [_top_n(deviation)]


def coverage_gap_exploit(history, window=100):
    """
    覆蓋缺口利用：選擇能最大化「未覆蓋號碼對」空間的組合。
    """
    freq, _ = _freq_map(history, window)
    recent = history[-window:] if len(history) >= window else history

    # 統計所有出現的號碼對
    pair_counts = Counter()
    for d in recent:
        nums = d['numbers'][:PICK]
        for a, b in combinations(sorted(nums), 2):
            pair_counts[(a, b)] += 1

    # 找出最不常出現的號碼對涉及的號碼
    scores = Counter()
    all_pairs = list(combinations(range(1, MAX_NUM + 1), 2))
    cold_pairs = sorted(all_pairs, key=lambda p: pair_counts.get(p, 0))

    for a, b in cold_pairs[:100]:  # top-100 coldest pairs
        scores[a] += 1
        scores[b] += 1

    return [_top_n({n: scores.get(n, 0) for n in range(1, MAX_NUM + 1)})]


def contrarian_recent(history, window=20):
    """
    近期反向：選擇近 window 期「最少出現」的號碼。
    短窗口反向 = 純粹均值回歸賭注。
    """
    freq, _ = _freq_map(history, window)
    inv_scores = {}
    for n in range(1, MAX_NUM + 1):
        inv_scores[n] = -freq.get(n, 0)
    return [_top_n(inv_scores)]


# ============================================================
# 搜尋升級 A: 高階統計矩 (Higher-Order Moments)
# ============================================================
def skewness_signal(history, window=100):
    """
    偏態信號：計算每個號碼出現間隔的偏態 (skewness)，
    正偏態 = 間隔右尾長 = 可能即將出現。
    """
    if len(history) < 50:
        return [_top_n({n: 0 for n in range(1, MAX_NUM + 1)})]

    recent = history[-window:] if len(history) >= window else history

    scores = {}
    for n in range(1, MAX_NUM + 1):
        gaps = []
        last_idx = None
        for i, d in enumerate(recent):
            if n in d['numbers'][:PICK]:
                if last_idx is not None:
                    gaps.append(i - last_idx)
                last_idx = i

        if len(gaps) >= 3:
            mean = np.mean(gaps)
            std = np.std(gaps) + 1e-10
            skew = np.mean(((np.array(gaps) - mean) / std) ** 3)
            scores[n] = skew  # 正偏態 → 長尾 → 可能 overdue
        else:
            scores[n] = 0

    return [_top_n(scores)]


def kurtosis_signal(history, window=100):
    """
    峰態信號：計算間隔的峰態 (kurtosis)，
    高峰態 = 有極端間隔 = 行為不規律 → 可能即將爆發。
    """
    if len(history) < 50:
        return [_top_n({n: 0 for n in range(1, MAX_NUM + 1)})]

    recent = history[-window:] if len(history) >= window else history

    scores = {}
    for n in range(1, MAX_NUM + 1):
        gaps = []
        last_idx = None
        for i, d in enumerate(recent):
            if n in d['numbers'][:PICK]:
                if last_idx is not None:
                    gaps.append(i - last_idx)
                last_idx = i

        if len(gaps) >= 4:
            mean = np.mean(gaps)
            std = np.std(gaps) + 1e-10
            kurt = np.mean(((np.array(gaps) - mean) / std) ** 4) - 3
            # 結合 overdue
            cur_gap = len(recent) - (last_idx if last_idx is not None else 0)
            scores[n] = kurt * (cur_gap / (mean + 1e-10))
        else:
            scores[n] = 0

    return [_top_n(scores)]


# ============================================================
# 搜尋升級 B: PCA 隱變量 (Latent Variables via PCA)
# ============================================================
def pca_latent_scores(history, window=100, n_components=3):
    """
    PCA 隱變量選號：對 (49, 35) 特徵矩陣做 PCA，
    用前 n_components 主成分的載荷選號。
    """
    fl = FeatureLibrary()
    feat = fl.extract_all(history[-window:] if len(history) >= window else history)

    # Standardize
    mean = feat.mean(axis=0)
    std = feat.std(axis=0) + 1e-8
    feat_std = (feat - mean) / std

    # PCA via SVD
    try:
        U, S, Vt = np.linalg.svd(feat_std, full_matrices=False)
        # 前 n_components 的載荷
        scores = np.zeros(MAX_NUM)
        for c in range(min(n_components, len(S))):
            component_score = feat_std @ Vt[c]
            # 加權 by explained variance
            scores += component_score * S[c]
    except Exception:
        scores = np.zeros(MAX_NUM)

    result = {i + 1: float(scores[i]) for i in range(MAX_NUM)}
    return [_top_n(result)]


# ============================================================
# 搜尋升級 C: 集合層級評估 (Set-Level Evaluation)
# ============================================================
def set_constraint_learned(history, window=200, n_samples=500):
    """
    學習集合約束：從歷史開獎學習「好的」6 號組合的特性
    (sum range, odd/even, zone分布, spread)，
    然後生成符合約束的候選組合，評分後選最佳。
    """
    recent = history[-window:] if len(history) >= window else history

    # 學習約束
    sums = [sum(d['numbers'][:PICK]) for d in recent]
    spreads = [max(d['numbers'][:PICK]) - min(d['numbers'][:PICK]) for d in recent]
    odds = [sum(1 for n in d['numbers'][:PICK] if n % 2 == 1) for d in recent]

    sum_lo, sum_hi = np.percentile(sums, 15), np.percentile(sums, 85)
    spread_lo, spread_hi = np.percentile(spreads, 10), np.percentile(spreads, 90)
    odd_lo, odd_hi = np.percentile(odds, 15), np.percentile(odds, 85)

    # 號碼個別分數
    freq, _ = _freq_map(history, 100)

    # 生成 & 篩選候選
    best_pick = None
    best_score = -1

    for _ in range(n_samples):
        # 加權隨機抽樣
        weights = np.array([freq.get(n, 0) + 1 for n in range(1, MAX_NUM + 1)], dtype=float)
        weights /= weights.sum()
        pick = np.random.choice(range(1, MAX_NUM + 1), size=PICK, replace=False, p=weights)
        pick = sorted(pick.tolist())

        # 約束檢查
        s = sum(pick)
        sp = pick[-1] - pick[0]
        od = sum(1 for n in pick if n % 2 == 1)

        if not (sum_lo <= s <= sum_hi):
            continue
        if not (spread_lo <= sp <= spread_hi):
            continue
        if not (odd_lo <= od <= odd_hi):
            continue

        # 評分
        score = sum(freq.get(n, 0) for n in pick)
        if score > best_score:
            best_score = score
            best_pick = pick

    if best_pick is None:
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    return [best_pick]


def set_diversity_max(history, window=100, n_samples=300):
    """
    集合多樣性最大化：生成多個候選組合，
    選出與近期開獎「最不像」（最大距離）的組合。
    """
    freq, _ = _freq_map(history, 100)
    recent_sets = [set(d['numbers'][:PICK]) for d in history[-10:]]

    best_pick = None
    best_diversity = -1

    for _ in range(n_samples):
        weights = np.array([freq.get(n, 0) + 1 for n in range(1, MAX_NUM + 1)], dtype=float)
        weights /= weights.sum()
        pick = set(np.random.choice(range(1, MAX_NUM + 1), size=PICK, replace=False, p=weights))

        # 多樣性 = 與近期所有開獎的平均 Jaccard 距離
        if recent_sets:
            dists = [1 - len(pick & rs) / len(pick | rs) for rs in recent_sets]
            diversity = np.mean(dists)
        else:
            diversity = 0

        if diversity > best_diversity:
            best_diversity = diversity
            best_pick = sorted(pick)

    if best_pick is None:
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    return [best_pick]


# ============================================================
# 搜尋升級 D: 局部區間挖掘 (Local Interval Mining)
# ============================================================
def local_peak_mining(history, base_window=100, scan_windows=[30, 50, 80]):
    """
    局部巔峰挖掘：在不同回看窗口尋找「局部最佳」策略。
    用 scan 窗口中命中率最高的窗口。
    """
    best_freq = None
    best_score = -1

    for sw in scan_windows:
        if len(history) < sw + 10:
            continue

        freq, w = _freq_map(history, sw)
        # 評分：top-6 頻率衰減比 (集中度越高越好)
        sorted_f = sorted(freq.values(), reverse=True)
        if len(sorted_f) >= PICK:
            top_sum = sum(sorted_f[:PICK])
            total = sum(sorted_f) + 1e-10
            concentrate = top_sum / total
            if concentrate > best_score:
                best_score = concentrate
                best_freq = freq

    if best_freq is None:
        best_freq, _ = _freq_map(history, 50)

    return [_top_n({n: best_freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]


# ============================================================
# 搜尋升級 E: Set-Level Markov (集合層級 Markov)
# ============================================================
def set_markov_transition(history, window=100):
    """
    集合層級 Markov：追蹤「整期特性」→「下期特性」的轉移。
    例如：sum 偏高 → 下期偏低的號碼更容易出現。
    """
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 20:
        freq, _ = _freq_map(history, 50)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    # 分類每期 regime
    sums = [sum(d['numbers'][:PICK]) for d in recent]
    median_sum = np.median(sums)

    # 轉移表：regime → 下期號碼頻率
    trans_freq = {'high': Counter(), 'low': Counter()}
    for i in range(len(recent) - 1):
        regime = 'high' if sums[i] >= median_sum else 'low'
        for n in recent[i + 1]['numbers'][:PICK]:
            trans_freq[regime][n] += 1

    # 當前 regime
    last_sum = sum(history[-1]['numbers'][:PICK])
    cur_regime = 'high' if last_sum >= median_sum else 'low'

    freq = trans_freq[cur_regime]
    if not freq:
        freq, _ = _freq_map(history, 50)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]


def odd_even_regime_follow(history, window=100):
    """
    奇偶 Regime 追蹤：根據上期奇偶比 → 調整下期奇偶權重。
    """
    if len(history) < 20:
        freq, _ = _freq_map(history, 50)
        return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]

    recent = history[-window:] if len(history) >= window else history

    # 建立轉移表
    odd_to_odd_freq = Counter()
    odd_to_even_freq = Counter()
    even_to_odd_freq = Counter()
    even_to_even_freq = Counter()

    for i in range(len(recent) - 1):
        cur_odds = sum(1 for n in recent[i]['numbers'][:PICK] if n % 2 == 1)
        is_odd_heavy = cur_odds > PICK / 2

        for n in recent[i + 1]['numbers'][:PICK]:
            if is_odd_heavy:
                if n % 2 == 1:
                    odd_to_odd_freq[n] += 1
                else:
                    odd_to_even_freq[n] += 1
            else:
                if n % 2 == 1:
                    even_to_odd_freq[n] += 1
                else:
                    even_to_even_freq[n] += 1

    # 當前 regime
    last_odds = sum(1 for n in history[-1]['numbers'][:PICK] if n % 2 == 1)
    is_odd_heavy = last_odds > PICK / 2

    freq = Counter()
    if is_odd_heavy:
        for n, c in odd_to_odd_freq.items():
            freq[n] += c
        for n, c in odd_to_even_freq.items():
            freq[n] += c
    else:
        for n, c in even_to_odd_freq.items():
            freq[n] += c
        for n, c in even_to_even_freq.items():
            freq[n] += c

    return [_top_n({n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)})]


# ============================================================
# 搜尋升級 F: 多臂賭博機自適應選擇 (Multi-Armed Bandit)
# ============================================================
def ucb1_number_selection(history, window=200):
    """
    UCB1 號碼選擇：把每個號碼當作一個臂，
    reward = 出現與否，使用 UCB1 選最佳號碼。
    """
    recent = history[-window:] if len(history) >= window else history
    n_rounds = len(recent)
    if n_rounds < 10:
        return [_top_n({n: 0 for n in range(1, MAX_NUM + 1)})]

    counts = {n: 0 for n in range(1, MAX_NUM + 1)}
    rewards = {n: 0 for n in range(1, MAX_NUM + 1)}

    for d in recent:
        for n in d['numbers'][:PICK]:
            counts[n] = counts.get(n, 0) + 1
            rewards[n] = rewards.get(n, 0) + 1

    # UCB1 scores
    scores = {}
    for n in range(1, MAX_NUM + 1):
        if counts[n] > 0:
            avg_reward = rewards[n] / counts[n]
            explore = np.sqrt(2 * np.log(n_rounds) / counts[n])
            scores[n] = avg_reward + explore
        else:
            scores[n] = float('inf')  # 未探索 → 最高優先

    return [_top_n(scores)]


def thompson_sampling_selection(history, window=200, seed=42):
    """
    Thompson Sampling 號碼選擇：Beta 分布取樣。
    """
    np.random.seed(seed)
    recent = history[-window:] if len(history) >= window else history

    alpha = {n: 1.0 for n in range(1, MAX_NUM + 1)}  # prior successes
    beta_param = {n: 1.0 for n in range(1, MAX_NUM + 1)}  # prior failures

    for d in recent:
        appeared = set(d['numbers'][:PICK])
        for n in range(1, MAX_NUM + 1):
            if n in appeared:
                alpha[n] += 1
            else:
                beta_param[n] += 1

    # Thompson sampling: draw from Beta(alpha, beta)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = np.random.beta(alpha[n], beta_param[n])

    return [_top_n(scores)]


# ============================================================
# 建構所有 Phase 3 策略
# ============================================================
def build_phase3_strategies() -> Dict[str, Callable]:
    """回傳所有 Phase 3 策略的 {name: func} 字典"""
    strategies = {}

    # === 類別 1: 微弱信號放大 ===
    for w in [50, 100, 200]:
        strategies[f'P3_stacked_micro_w{w}'] = lambda h, w=w: stacked_micro_signals(h, window=w)

    strategies['P3_borda_rank_w100'] = lambda h: rank_aggregation_borda(h, window=100)
    strategies['P3_borda_rank_w200'] = lambda h: rank_aggregation_borda(h, window=200)

    for t in [3, 4, 5]:
        strategies[f'P3_consensus_th{t}'] = lambda h, t=t: consensus_threshold(h, min_agree=t)

    for w in [50, 100]:
        strategies[f'P3_z_ensemble_w{w}'] = lambda h, w=w: weighted_z_ensemble(h, window=w)

    # === 類別 2: 非線性組合 ===
    for k in [5, 10, 20]:
        strategies[f'P3_feat_cross_top{k}'] = lambda h, k=k: feature_cross_top_pairs(h, top_k=k)

    strategies['P3_multiplicative'] = multiplicative_ensemble
    strategies['P3_multiplicative_w50'] = lambda h: multiplicative_ensemble(h, window=50)

    strategies['P3_quadratic_w50'] = lambda h: quadratic_interaction(h, window=50)
    strategies['P3_quadratic_w100'] = lambda h: quadratic_interaction(h, window=100)

    # === 類別 3: 條件觸發 ===
    for th in [0.4, 0.6, 0.8]:
        strategies[f'P3_skip_conf_{th}'] = lambda h, th=th: skip_low_confidence(h, threshold=th)

    strategies['P3_regime_gated'] = regime_gated
    strategies['P3_regime_gated_rw20'] = lambda h: regime_gated(h, regime_window=20)

    strategies['P3_post_anomaly'] = post_anomaly_trigger
    strategies['P3_post_anomaly_w100'] = lambda h: post_anomaly_trigger(h, window=100)

    for gm in [1.5, 2.0, 2.5]:
        strategies[f'P3_gap_trigger_{gm}'] = lambda h, gm=gm: gap_trigger(h, gap_multiplier=gm)

    strategies['P3_vol_gate_low'] = lambda h: volatility_gate(h, low_vol_only=True)
    strategies['P3_vol_gate_high'] = lambda h: volatility_gate(h, low_vol_only=False)

    # === 類別 4: 罕見事件 ===
    strategies['P3_extreme_sum_follow'] = extreme_sum_follow
    strategies['P3_extreme_sum_follow_5pct'] = lambda h: extreme_sum_follow(h, tail_pct=0.05)

    strategies['P3_consec_follow'] = consecutive_follow
    strategies['P3_consec_follow_w100'] = lambda h: consecutive_follow(h, window=100)

    for dt in [10, 15, 20]:
        strategies[f'P3_drought_break_{dt}'] = lambda h, dt=dt: drought_break_follow(h, drought_threshold=dt)

    strategies['P3_zone_burst'] = zone_burst_follow
    strategies['P3_zone_burst_w30'] = lambda h: zone_burst_follow(h, window=30)

    # === 類別 5: 非平穩 ===
    for a in [0.05, 0.1, 0.2]:
        strategies[f'P3_drift_ewma_a{a}'] = lambda h, a=a: drift_adaptive_ewma(h, alpha=a)

    strategies['P3_changepoint'] = changepoint_adaptive
    strategies['P3_changepoint_th2'] = lambda h: changepoint_adaptive(h, cusum_threshold=2.0)

    for ws in [20, 30, 50]:
        strategies[f'P3_kl_drift_s{ws}'] = lambda h, ws=ws: kl_drift_selector(h, window_short=ws)

    strategies['P3_regime_momentum'] = regime_momentum
    strategies['P3_regime_momentum_rw20'] = lambda h: regime_momentum(h, regime_window=20)

    # === 類別 6: 反直覺 ===
    for st in [2, 3, 4]:
        strategies[f'P3_anti_streak_{st}'] = lambda h, st=st: anti_streak(h, streak_threshold=st)

    strategies['P3_anti_hot_zone'] = anti_hot_zone
    strategies['P3_anti_hot_zone_w100'] = lambda h: anti_hot_zone(h, window=100)

    strategies['P3_max_entropy'] = max_entropy_pick
    strategies['P3_max_entropy_w50'] = lambda h: max_entropy_pick(h, window=50)

    strategies['P3_coverage_gap'] = coverage_gap_exploit
    strategies['P3_coverage_gap_w50'] = lambda h: coverage_gap_exploit(h, window=50)

    strategies['P3_contrarian_w20'] = lambda h: contrarian_recent(h, window=20)
    strategies['P3_contrarian_w30'] = lambda h: contrarian_recent(h, window=30)

    # === 搜尋升級 ===
    strategies['P3_skewness'] = skewness_signal
    strategies['P3_skewness_w200'] = lambda h: skewness_signal(h, window=200)

    strategies['P3_kurtosis'] = kurtosis_signal
    strategies['P3_kurtosis_w200'] = lambda h: kurtosis_signal(h, window=200)

    strategies['P3_pca_latent'] = pca_latent_scores
    strategies['P3_pca_latent_5c'] = lambda h: pca_latent_scores(h, n_components=5)

    strategies['P3_set_constraint'] = set_constraint_learned
    strategies['P3_set_constraint_w300'] = lambda h: set_constraint_learned(h, window=300)

    strategies['P3_set_diversity'] = set_diversity_max

    strategies['P3_local_peak'] = local_peak_mining

    strategies['P3_set_markov'] = set_markov_transition
    strategies['P3_oe_regime'] = odd_even_regime_follow

    strategies['P3_ucb1'] = ucb1_number_selection
    strategies['P3_ucb1_w100'] = lambda h: ucb1_number_selection(h, window=100)

    strategies['P3_thompson'] = thompson_sampling_selection
    strategies['P3_thompson_w100'] = lambda h: thompson_sampling_selection(h, window=100)

    return strategies


def build_phase3_quick() -> Dict[str, Callable]:
    """精簡版：每類別取 2 個代表策略，共 ~20 個"""
    strategies = {}

    # Cat 1
    strategies['P3_stacked_micro_w100'] = lambda h: stacked_micro_signals(h, window=100)
    strategies['P3_borda_rank_w100'] = lambda h: rank_aggregation_borda(h, window=100)
    strategies['P3_consensus_th4'] = lambda h: consensus_threshold(h, min_agree=4)

    # Cat 2
    strategies['P3_feat_cross_top10'] = lambda h: feature_cross_top_pairs(h, top_k=10)
    strategies['P3_multiplicative'] = multiplicative_ensemble
    strategies['P3_quadratic_w100'] = lambda h: quadratic_interaction(h, window=100)

    # Cat 3
    strategies['P3_skip_conf_0.6'] = lambda h: skip_low_confidence(h, threshold=0.6)
    strategies['P3_regime_gated'] = regime_gated
    strategies['P3_post_anomaly'] = post_anomaly_trigger
    strategies['P3_gap_trigger_2.0'] = lambda h: gap_trigger(h, gap_multiplier=2.0)

    # Cat 4
    strategies['P3_extreme_sum_follow'] = extreme_sum_follow
    strategies['P3_consec_follow'] = consecutive_follow
    strategies['P3_drought_break_15'] = lambda h: drought_break_follow(h, drought_threshold=15)

    # Cat 5
    strategies['P3_drift_ewma_a0.1'] = lambda h: drift_adaptive_ewma(h, alpha=0.1)
    strategies['P3_changepoint'] = changepoint_adaptive
    strategies['P3_kl_drift_s30'] = lambda h: kl_drift_selector(h, window_short=30)
    strategies['P3_regime_momentum'] = regime_momentum

    # Cat 6
    strategies['P3_anti_streak_3'] = lambda h: anti_streak(h, streak_threshold=3)
    strategies['P3_max_entropy'] = max_entropy_pick
    strategies['P3_coverage_gap'] = coverage_gap_exploit
    strategies['P3_contrarian_w20'] = lambda h: contrarian_recent(h, window=20)

    # Search upgrades
    strategies['P3_skewness'] = skewness_signal
    strategies['P3_kurtosis'] = kurtosis_signal
    strategies['P3_pca_latent'] = pca_latent_scores
    strategies['P3_set_constraint'] = set_constraint_learned
    strategies['P3_set_markov'] = set_markov_transition
    strategies['P3_ucb1'] = ucb1_number_selection
    strategies['P3_thompson'] = thompson_sampling_selection

    return strategies


def count_strategies():
    """統計策略數量"""
    full = build_phase3_strategies()
    quick = build_phase3_quick()
    return {
        'full': len(full),
        'quick': len(quick),
        'categories': {
            'ultra_weak_signal': len([k for k in full if 'stacked' in k or 'borda' in k or 'consensus' in k or 'z_ensemble' in k]),
            'nonlinear_combo': len([k for k in full if 'feat_cross' in k or 'multiplicative' in k or 'quadratic' in k]),
            'conditional_trigger': len([k for k in full if 'skip' in k or 'regime_gated' in k or 'anomaly' in k or 'gap_trigger' in k or 'vol_gate' in k]),
            'rare_event': len([k for k in full if 'extreme' in k or 'consec' in k or 'drought' in k or 'zone_burst' in k]),
            'non_stationary': len([k for k in full if 'drift' in k or 'changepoint' in k or 'kl_drift' in k or 'regime_momentum' in k]),
            'counter_intuitive': len([k for k in full if 'anti_' in k or 'entropy' in k or 'coverage' in k or 'contrarian' in k]),
        }
    }
