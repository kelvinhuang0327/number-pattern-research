#!/usr/bin/env python3
"""
P0~P3 四階段優化策略實作與完整回測
====================================
P0: 鄰號注入層 (Neighbor Injection)
P1: 鄰號+冷號 2注策略
P2: MAB 信號權重動態調節
P3: 和值/區間狀態檢測器

每個階段獨立回測：1500期三窗口(150/500/1500) + z-test 顯著性
"""
import os
import sys
import time
import json
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations as _icombs
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

# ============================================================
# Constants
# ============================================================
MAX_NUM = 49
PICK = 6
P_SINGLE = 0.0186

BASELINES = {
    1: P_SINGLE * 100,
    2: (1 - (1 - P_SINGLE) ** 2) * 100,
    3: (1 - (1 - P_SINGLE) ** 3) * 100,
    4: (1 - (1 - P_SINGLE) ** 4) * 100,
    5: (1 - (1 - P_SINGLE) ** 5) * 100,
}

WINDOWS = [150, 500, 1500]
_SUM_WIN = 300


# ============================================================
# Base Components (from Triple Strike)
# ============================================================
def fourier_rhythm_bet(history, window=500):
    """Fourier Rhythm — FFT 週期分析"""
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM:
                bitstreams[n][idx] = 1
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    sorted_idx = np.argsort(scores[1:])[::-1] + 1
    return sorted(sorted_idx[:6].tolist())


def fourier_scores_full(history, window=500):
    """返回所有號碼的 Fourier 分數 (用於排名)"""
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM:
                bitstreams[n][idx] = 1
    scores = {}
    for n in range(1, MAX_NUM + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            scores[n] = 0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            scores[n] = 0
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
        else:
            scores[n] = 0
    return scores


def _sum_target(history):
    h = history[-_SUM_WIN:] if len(history) >= _SUM_WIN else history
    sums = [sum(d['numbers']) for d in h]
    mu, sg = np.mean(sums), np.std(sums)
    last_s = sum(history[-1]['numbers'])
    if last_s < mu - 0.5 * sg:
        return mu, mu + sg
    if last_s > mu + 0.5 * sg:
        return mu - sg, mu
    return mu - 0.5 * sg, mu + 0.5 * sg


def cold_numbers_bet(history, window=100, exclude=None,
                     pool_size=12, use_sum_constraint=True):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))
    if not use_sum_constraint or len(history) < 2 or pool_size <= 6:
        return sorted(sorted_cold[:6])
    pool = sorted_cold[:pool_size]
    tlo, thi = _sum_target(history)
    tmid = (tlo + thi) / 2.0
    best_combo, best_dist, best_in_range = None, float('inf'), False
    for combo in _icombs(pool, 6):
        s = sum(combo)
        in_range = (tlo <= s <= thi)
        dist = abs(s - tmid)
        if in_range and (not best_in_range or dist < best_dist):
            best_combo, best_dist, best_in_range = combo, dist, True
        elif not in_range and not best_in_range and dist < best_dist:
            best_combo, best_dist = combo, dist
    return sorted(best_combo) if best_combo else sorted(pool[:6])


def tail_balance_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    tail_groups = {i: [] for i in range(10)}
    for n in range(1, MAX_NUM + 1):
        if n not in exclude:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for t in tail_groups:
        tail_groups[t].sort(key=lambda x: x[1], reverse=True)
    selected = []
    available_tails = sorted(
        [t for t in range(10) if tail_groups[t]],
        key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0,
        reverse=True
    )
    idx_in_group = {t: 0 for t in range(10)}
    while len(selected) < 6:
        added = False
        for tail in available_tails:
            if len(selected) >= 6:
                break
            if idx_in_group[tail] < len(tail_groups[tail]):
                num, _ = tail_groups[tail][idx_in_group[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                idx_in_group[tail] += 1
            if not added and idx_in_group[tail] >= len(tail_groups[tail]):
                pass
        if not added:
            break
    if len(selected) < 6:
        remaining = [n for n in range(1, MAX_NUM + 1) if n not in selected and n not in exclude]
        remaining.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(remaining[:6 - len(selected)])
    return sorted(selected[:6])


def markov_scores(history, markov_window=30):
    """Markov 轉移分數"""
    recent = history[-markov_window:] if len(history) >= markov_window else history
    transitions = defaultdict(Counter)
    for i in range(len(recent) - 1):
        curr = recent[i]['numbers']
        nxt = recent[i + 1]['numbers']
        for cn in curr:
            for nn in nxt:
                transitions[cn][nn] += 1
    prev_nums = history[-1]['numbers']
    scores = Counter()
    for pn in prev_nums:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                scores[n] += cnt / total
    return scores


def markov_orthogonal_bet(history, exclude=None, markov_window=30):
    exclude = exclude or set()
    mk_scores = markov_scores(history, markov_window)
    candidates = sorted(
        [(n, s) for n, s in mk_scores.items() if n not in exclude and 1 <= n <= MAX_NUM],
        key=lambda x: -x[1]
    )
    bet = [n for n, _ in candidates[:PICK]]
    if len(bet) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in exclude and n not in bet and len(bet) < PICK:
                bet.append(n)
    return sorted(bet[:PICK])


# ============================================================
# Neighbor utilities
# ============================================================
def get_neighbor_set(numbers, delta=1):
    """获取一组号码的邻号集（±delta，排除号码本身）"""
    neighbors = set()
    for n in numbers:
        for d in range(-delta, delta + 1):
            if d == 0:
                continue
            nn = n + d
            if 1 <= nn <= MAX_NUM:
                neighbors.add(nn)
    return neighbors


def get_neighbor_set_including_self(numbers, delta=1):
    """获取一组号码的邻域（含自身）"""
    neighbors = set()
    for n in numbers:
        for d in range(-delta, delta + 1):
            nn = n + d
            if 1 <= nn <= MAX_NUM:
                neighbors.add(nn)
    return neighbors


# ============================================================
# P0: NEIGHBOR INJECTION (鄰號注入)
# ============================================================
def triple_strike_with_neighbor_injection(history, n_inject=1):
    """
    P0: Triple Strike + 鄰號注入
    在每注中保留 n_inject 個鄰號位（選 Fourier 排名最高的鄰號）
    """
    prev_nums = history[-1]['numbers']
    neighbor_pool = get_neighbor_set(prev_nums, delta=1)

    # 取 Fourier 分數做排名
    f_scores = fourier_scores_full(history, window=500)

    # 鄰號按 Fourier 排名
    neighbor_ranked = sorted(neighbor_pool, key=lambda n: -f_scores.get(n, 0))

    # 注1: Fourier + neighbor injection
    fourier_base = fourier_rhythm_bet(history, window=500)
    bet1 = _inject_neighbors(fourier_base, neighbor_ranked, n_inject, set())
    used = set(bet1)

    # 注2: Cold + neighbor injection
    cold_base = cold_numbers_bet(history, window=100, exclude=used)
    remaining_neighbors = [n for n in neighbor_ranked if n not in used]
    bet2 = _inject_neighbors(cold_base, remaining_neighbors, n_inject, used)
    used.update(bet2)

    # 注3: Tail + neighbor injection
    tail_base = tail_balance_bet(history, window=100, exclude=used)
    remaining_neighbors2 = [n for n in neighbor_ranked if n not in used]
    bet3 = _inject_neighbors(tail_base, remaining_neighbors2, n_inject, used)

    return [bet1, bet2, bet3]


def _inject_neighbors(base_bet, neighbor_ranked, n_inject, global_used):
    """將 n_inject 個最佳鄰號注入到一注中，替換排名最低的原始號碼"""
    # 已經在注中的鄰號不再注入
    existing_neighbors = [n for n in base_bet if n in set(neighbor_ranked)]
    need_inject = max(0, n_inject - len(existing_neighbors))

    if need_inject == 0:
        return sorted(base_bet)

    # 找出要注入的鄰號（不在 base_bet 也不在 global_used）
    to_inject = []
    for n in neighbor_ranked:
        if n not in base_bet and n not in global_used and len(to_inject) < need_inject:
            to_inject.append(n)

    if not to_inject:
        return sorted(base_bet)

    # 替換 base_bet 中排名最低的（保留原始邏輯的優先號碼）
    result = list(base_bet)
    # 移除末尾的（排名最低的）
    for _ in range(len(to_inject)):
        if result:
            result.pop()  # 移除最後一個（排名最低）
    result.extend(to_inject)

    return sorted(result[:PICK])


# ============================================================
# P1: NEIGHBOR + COLD 2-BET (鄰號+冷號 2注)
# ============================================================
def neighbor_cold_2bet(history, cold_window=100, cold_pool=12):
    """
    P1: 鄰號+冷號 2注策略
    注1: 純鄰號 Top 6（上期 ±1，按 Fourier 分排名）
    注2: 冷號 Top 6（排除注1，Sum-Constrained）
    """
    prev_nums = history[-1]['numbers']
    neighbor_pool = get_neighbor_set_including_self(prev_nums, delta=1)

    # 用 Fourier + Markov 綜合排名鄰號
    f_scores = fourier_scores_full(history, window=500)
    mk = markov_scores(history, markov_window=30)

    # 鄰號得分 = Fourier + 0.5 * Markov (歸一化)
    f_max = max(f_scores.values()) if f_scores else 1
    mk_max = max(mk.values()) if mk else 1
    neighbor_scores = {}
    for n in neighbor_pool:
        fs = f_scores.get(n, 0) / (f_max or 1)
        ms = mk.get(n, 0) / (mk_max or 1)
        neighbor_scores[n] = fs + 0.5 * ms

    neighbor_ranked = sorted(neighbor_scores.items(), key=lambda x: -x[1])
    bet1 = sorted([n for n, _ in neighbor_ranked[:PICK]])
    used = set(bet1)

    # 注2: Cold (排除注1) + Sum constraint
    bet2 = cold_numbers_bet(history, window=cold_window, exclude=used,
                            pool_size=cold_pool, use_sum_constraint=True)

    return [bet1, bet2]


# ============================================================
# P2: MAB SIGNAL WEIGHT ADJUSTER (MAB 信號權重動態調節)
# ============================================================
def mab_fusion_3bet(history, lookback=50):
    """
    P2: MAB (Thomson Sampling) 多信號融合 3注
    動態調整 Fourier/Cold/Markov/Neighbor 的融合權重
    根據近 lookback 期各信號域的命中率調整
    """
    # 計算近期各信號域的命中率（用於 Beta 分佈參數）
    alpha_fourier, beta_fourier = 1, 1  # Beta 先驗
    alpha_cold, beta_cold = 1, 1
    alpha_markov, beta_markov = 1, 1
    alpha_neighbor, beta_neighbor = 1, 1

    lb = min(lookback, len(history) - 2)
    for i in range(lb):
        idx = len(history) - lb + i - 1
        if idx < 50:
            continue
        h = history[:idx + 1]
        actual = set(history[idx + 1]['numbers'])
        prev_nums = h[-1]['numbers']

        # Fourier hit?
        try:
            f_bet = set(fourier_rhythm_bet(h, window=min(500, len(h))))
            if len(f_bet & actual) >= 2:
                alpha_fourier += 1
            else:
                beta_fourier += 1
        except:
            beta_fourier += 1

        # Cold hit?
        recent = h[-100:] if len(h) >= 100 else h
        freq = Counter(n for d in recent for n in d['numbers'])
        cold_6 = set(sorted(range(1, MAX_NUM + 1), key=lambda n: freq.get(n, 0))[:6])
        if len(cold_6 & actual) >= 2:
            alpha_cold += 1
        else:
            beta_cold += 1

        # Markov hit?
        mk = markov_scores(h, markov_window=30)
        markov_6 = set(n for n, _ in sorted(mk.items(), key=lambda x: -x[1])[:6])
        if len(markov_6 & actual) >= 2:
            alpha_markov += 1
        else:
            beta_markov += 1

        # Neighbor hit?
        nb = get_neighbor_set_including_self(prev_nums, delta=1)
        nb_top6 = set(sorted(nb)[:6])
        if len(nb_top6 & actual) >= 2:
            alpha_neighbor += 1
        else:
            beta_neighbor += 1

    # Thompson Sampling: 從 Beta 分奪取權重
    np.random.seed(42)  # 確定性
    w_fourier = np.random.beta(alpha_fourier, beta_fourier)
    w_cold = np.random.beta(alpha_cold, beta_cold)
    w_markov = np.random.beta(alpha_markov, beta_markov)
    w_neighbor = np.random.beta(alpha_neighbor, beta_neighbor)

    # 綜合得分
    f_scores = fourier_scores_full(history, window=500)
    mk_sc = markov_scores(history, markov_window=30)
    prev_nums = history[-1]['numbers']
    nb_set = get_neighbor_set_including_self(prev_nums, delta=1)

    recent = history[-100:] if len(history) >= 100 else history
    freq = Counter(n for d in recent for n in d['numbers'])

    # Cold score: 反轉頻率
    max_freq = max(freq.values()) if freq else 1
    cold_scores = {n: (max_freq - freq.get(n, 0)) / max_freq for n in range(1, MAX_NUM + 1)}

    # Neighbor score
    nb_scores = {n: (1.0 if n in nb_set else 0.0) for n in range(1, MAX_NUM + 1)}

    # 歸一化
    f_max = max(f_scores.values()) or 1
    mk_max = max(mk_sc.values()) or 1

    combined = {}
    for n in range(1, MAX_NUM + 1):
        combined[n] = (
            w_fourier * (f_scores.get(n, 0) / f_max) +
            w_cold * cold_scores.get(n, 0) +
            w_markov * (mk_sc.get(n, 0) / mk_max) +
            w_neighbor * nb_scores.get(n, 0)
        )

    ranked = sorted(combined.items(), key=lambda x: -x[1])

    # 3注：Top6, 7-12, 13-18
    bet1 = sorted([n for n, _ in ranked[:6]])
    bet2 = sorted([n for n, _ in ranked[6:12]])
    bet3 = sorted([n for n, _ in ranked[12:18]])

    return [bet1, bet2, bet3]


# ============================================================
# P3: SUM/ZONE STATE DETECTOR (和值/區間狀態檢測)
# ============================================================
def state_aware_3bet(history, sum_window=50):
    """
    P3: 和值/區間狀態感知 3注
    偵測當前狀態，調整選號範圍：
    - 上期和值偏高(>mean+0.5σ) → 下期傾向低和值，收窄到11-40
    - 上期和值偏低(<mean-0.5σ) → 下期傾向高和值，放寬兩端
    - 中性 → 正常策略
    結合 Fourier + Neighbor + Cold，根據狀態調整
    """
    recent = history[-sum_window:] if len(history) >= sum_window else history
    sums = [sum(d['numbers']) for d in recent]
    mu, sg = np.mean(sums), np.std(sums)
    last_sum = sum(history[-1]['numbers'])

    # 狀態判斷
    if last_sum > mu + 0.5 * sg:
        state = 'HIGH'  # 下期預期回落
        prefer_low = True
        prefer_high = False
    elif last_sum < mu - 0.5 * sg:
        state = 'LOW'   # 下期預期回升
        prefer_low = False
        prefer_high = True
    else:
        state = 'MID'
        prefer_low = False
        prefer_high = False

    # 區間偏好調整
    zone_weights = {n: 1.0 for n in range(1, MAX_NUM + 1)}
    if prefer_low:
        # 壓制高區 (>35)，加強中低區
        for n in range(1, MAX_NUM + 1):
            if n <= 25:
                zone_weights[n] = 1.3
            elif n <= 35:
                zone_weights[n] = 1.0
            else:
                zone_weights[n] = 0.5
    elif prefer_high:
        # 壓制低區 (<15)，加強中高區
        for n in range(1, MAX_NUM + 1):
            if n <= 15:
                zone_weights[n] = 0.5
            elif n <= 30:
                zone_weights[n] = 1.0
            else:
                zone_weights[n] = 1.3

    # 取各信號分數
    f_scores = fourier_scores_full(history, window=500)
    mk_sc = markov_scores(history, markov_window=30)
    prev_nums = history[-1]['numbers']
    nb_set = get_neighbor_set_including_self(prev_nums, delta=1)

    recent_100 = history[-100:] if len(history) >= 100 else history
    freq = Counter(n for d in recent_100 for n in d['numbers'])
    max_freq = max(freq.values()) if freq else 1

    f_max = max(f_scores.values()) or 1
    mk_max = max(mk_sc.values()) or 1

    combined = {}
    for n in range(1, MAX_NUM + 1):
        base = (
            0.35 * (f_scores.get(n, 0) / f_max) +
            0.25 * ((max_freq - freq.get(n, 0)) / max_freq) +
            0.25 * (mk_sc.get(n, 0) / mk_max) +
            0.15 * (1.0 if n in nb_set else 0.0)
        )
        combined[n] = base * zone_weights[n]

    ranked = sorted(combined.items(), key=lambda x: -x[1])

    bet1 = sorted([n for n, _ in ranked[:6]])
    used = set(bet1)

    # 注2: 鄰號+Cold (排除注1)
    nb_ranked = sorted(
        [(n, combined[n]) for n in nb_set if n not in used],
        key=lambda x: -x[1]
    )
    cold_ranked = sorted(
        [(n, freq.get(n, 0)) for n in range(1, MAX_NUM + 1) if n not in used],
        key=lambda x: x[1]
    )
    # 混合: 3個鄰號 + 3個冷號
    bet2_pool = [n for n, _ in nb_ranked[:3]] + [n for n, _ in cold_ranked[:3]]
    bet2_pool = list(dict.fromkeys(bet2_pool))  # 去重保序
    if len(bet2_pool) < 6:
        extras = [n for n, _ in cold_ranked if n not in bet2_pool and n not in used]
        bet2_pool.extend(extras[:6 - len(bet2_pool)])
    bet2 = sorted(bet2_pool[:6])
    used.update(bet2)

    # 注3: 剩餘最佳
    remaining = sorted(
        [(n, combined[n]) for n in range(1, MAX_NUM + 1) if n not in used],
        key=lambda x: -x[1]
    )
    bet3 = sorted([n for n, _ in remaining[:6]])

    return [bet1, bet2, bet3]


# ============================================================
# STANDARD BACKTEST ENGINE
# ============================================================
def run_backtest(predict_func, all_draws, test_periods, n_bets, label=""):
    """標準回測引擎 (無數據洩漏)"""
    m3_plus = 0
    total = 0
    per_bet_hits = Counter()  # 各注命中統計

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 150:  # 至少150期訓練
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])

        try:
            bets = predict_func(hist)
            assert len(bets) == n_bets, f"Expected {n_bets} bets, got {len(bets)}"

            any_hit = False
            for j, bet in enumerate(bets):
                hits = len(set(bet) & actual)
                if hits >= 3:
                    any_hit = True
                    per_bet_hits[j] += 1
            if any_hit:
                m3_plus += 1
            total += 1
        except Exception as e:
            total += 1  # 還是算一期

    if total == 0:
        return None

    rate = m3_plus / total * 100
    baseline = BASELINES.get(n_bets, 0)
    edge = rate - baseline

    # z-test
    p_hat = m3_plus / total
    p0 = baseline / 100
    se = np.sqrt(p0 * (1 - p0) / total) if p0 > 0 else 0.01
    z = (p_hat - p0) / se if se > 0 else 0

    return {
        'label': label,
        'periods': total,
        'm3_plus': m3_plus,
        'rate': rate,
        'baseline': baseline,
        'edge': edge,
        'z': z,
        'per_bet': dict(per_bet_hits),
    }


def three_tier_validation(predict_func, all_draws, n_bets, label=""):
    """三窗口驗證 (150/500/1500)"""
    print(f"\n{'='*70}")
    print(f"  {label} — 三窗口回測 ({n_bets}注)")
    print(f"{'='*70}")

    results = {}
    for window in WINDOWS:
        t0 = time.time()
        r = run_backtest(predict_func, all_draws, window, n_bets, f"{label}_{window}p")
        elapsed = time.time() - t0
        if r:
            results[window] = r
            sig = "★" if abs(r['z']) > 1.96 else " "
            print(f"  {window:4d}期: M3+={r['m3_plus']:3d}/{r['periods']} "
                  f"({r['rate']:.2f}%) 基準={r['baseline']:.2f}% "
                  f"Edge={r['edge']:+.2f}% z={r['z']:.2f}{sig} [{elapsed:.1f}s]")
            if r['per_bet']:
                bet_str = " ".join(f"注{k+1}:{v}" for k, v in sorted(r['per_bet'].items()))
                print(f"         各注命中: {bet_str}")

    # 模式判定
    if len(results) == 3:
        edges = [results[w]['edge'] for w in WINDOWS]
        e150, e500, e1500 = edges

        if e1500 < 0:
            if e150 > 0 or e500 > 0:
                pattern = "SHORT_MOMENTUM"
                verdict = "⚠️ 短期正但長期失效"
            else:
                pattern = "INEFFECTIVE"
                verdict = "❌ 全段無效"
        elif e150 < 0 and e1500 > 0:
            pattern = "LATE_BLOOMER"
            verdict = "⚠️ 近期差但長期穩"
        elif all(e > 0 for e in edges):
            pattern = "STABLE"
            verdict = "✅ 三窗口全正"
        else:
            pattern = "MIXED"
            verdict = "⚠️ 混合模式"

        print(f"\n  模式: {pattern} — {verdict}")
        print(f"  Edge走勢: 150p={e150:+.2f}% → 500p={e500:+.2f}% → 1500p={e1500:+.2f}%")

        return results, pattern
    return results, "INSUFFICIENT_DATA"


# ============================================================
# ORIGINAL TRIPLE STRIKE (BASELINE)
# ============================================================
def original_triple_strike(history):
    """原版 Triple Strike (作為對照基準)"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


def original_p0_2bet(history):
    """原版 P0偏差互補+回聲 2注"""
    window, echo_boost = 50, 1.5
    recent = history[-window:] if len(history) > window else history
    expected = len(recent) * PICK / MAX_NUM
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = freq.get(n, 0) - expected
    if len(history) >= 3:
        for n in history[-2]['numbers']:
            if n <= MAX_NUM:
                scores[n] += echo_boost
    hot = sorted([(n, s) for n, s in scores.items() if s > 1],
                 key=lambda x: x[1], reverse=True)
    cold = sorted([(n, abs(s)) for n, s in scores.items() if s < -1],
                  key=lambda x: x[1], reverse=True)
    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)
    if len(bet1) < PICK:
        mid = sorted(range(1, MAX_NUM + 1), key=lambda n: abs(scores[n]))
        for n in mid:
            if n not in used and len(bet1) < PICK:
                bet1.append(n); used.add(n)
    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK:
            bet2.append(n); used.add(n)
    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK:
                bet2.append(n); used.add(n)
    return [sorted(bet1[:PICK]), sorted(bet2[:PICK])]


# ============================================================
# MAIN: RUN ALL STAGES
# ============================================================
def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))

    print(f"大樂透資料: {len(all_draws)} 期")
    print(f"最新期: {all_draws[-1]['draw']} ({all_draws[-1]['date']})")

    all_results = {}

    # ============ BASELINE: Original Triple Strike ============
    print("\n" + "#" * 70)
    print("#  BASELINE: 原版 Triple Strike 3注")
    print("#" * 70)
    r_baseline_3, p_baseline_3 = three_tier_validation(
        original_triple_strike, all_draws, 3, "Baseline_TS3"
    )
    all_results['baseline_ts3'] = {'results': {k: v for k, v in r_baseline_3.items()}, 'pattern': p_baseline_3}

    # ============ BASELINE: Original P0 2-bet ============
    print("\n" + "#" * 70)
    print("#  BASELINE: 原版 P0偏差互補+回聲 2注")
    print("#" * 70)
    r_baseline_2, p_baseline_2 = three_tier_validation(
        original_p0_2bet, all_draws, 2, "Baseline_P0_2bet"
    )
    all_results['baseline_p0'] = {'results': {k: v for k, v in r_baseline_2.items()}, 'pattern': p_baseline_2}

    # ============ P0: NEIGHBOR INJECTION ============
    print("\n" + "#" * 70)
    print("#  P0: Triple Strike + 鄰號注入 (n_inject=1) 3注")
    print("#" * 70)

    def p0_strategy(hist):
        return triple_strike_with_neighbor_injection(hist, n_inject=1)

    r_p0, p_p0 = three_tier_validation(p0_strategy, all_draws, 3, "P0_NeighborInject_3bet")
    all_results['p0_neighbor_inject'] = {'results': {k: v for k, v in r_p0.items()}, 'pattern': p_p0}

    # ============ P1: NEIGHBOR + COLD 2-BET ============
    print("\n" + "#" * 70)
    print("#  P1: 鄰號+冷號 2注策略")
    print("#" * 70)

    def p1_strategy(hist):
        return neighbor_cold_2bet(hist, cold_window=100, cold_pool=12)

    r_p1, p_p1 = three_tier_validation(p1_strategy, all_draws, 2, "P1_NeighborCold_2bet")
    all_results['p1_neighbor_cold'] = {'results': {k: v for k, v in r_p1.items()}, 'pattern': p_p1}

    # ============ P2: MAB FUSION 3-BET ============
    print("\n" + "#" * 70)
    print("#  P2: MAB 信號權重動態融合 3注")
    print("#" * 70)

    def p2_strategy(hist):
        return mab_fusion_3bet(hist, lookback=50)

    r_p2, p_p2 = three_tier_validation(p2_strategy, all_draws, 3, "P2_MAB_Fusion_3bet")
    all_results['p2_mab_fusion'] = {'results': {k: v for k, v in r_p2.items()}, 'pattern': p_p2}

    # ============ P3: STATE-AWARE 3-BET ============
    print("\n" + "#" * 70)
    print("#  P3: 和值/區間狀態感知 3注")
    print("#" * 70)

    def p3_strategy(hist):
        return state_aware_3bet(hist, sum_window=50)

    r_p3, p_p3 = three_tier_validation(p3_strategy, all_draws, 3, "P3_StateAware_3bet")
    all_results['p3_state_aware'] = {'results': {k: v for k, v in r_p3.items()}, 'pattern': p_p3}

    # ============ SUMMARY ============
    print("\n" + "=" * 70)
    print("  綜合比較")
    print("=" * 70)
    print(f"\n  {'策略':<35} | {'150p Edge':>10} | {'500p Edge':>10} | {'1500p Edge':>10} | {'模式':<20}")
    print(f"  {'-'*35} | {'-'*10} | {'-'*10} | {'-'*10} | {'-'*20}")

    for key, data in all_results.items():
        results = data['results']
        pattern = data['pattern']
        edges = []
        for w in WINDOWS:
            if w in results:
                edges.append(f"{results[w]['edge']:+.2f}%")
            else:
                edges.append("N/A")
        label = results.get(1500, results.get(500, results.get(150, {})))
        name = label.get('label', key).replace(f"_{WINDOWS[-1]}p", "").replace(f"_{WINDOWS[0]}p", "")
        print(f"  {name:<35} | {edges[0]:>10} | {edges[1]:>10} | {edges[2]:>10} | {pattern:<20}")

    # 115000025 期驗證
    print("\n" + "=" * 70)
    print("  115000025期回顧驗證 — 各策略預測結果")
    print("=" * 70)

    actual_25 = set([12, 19, 22, 27, 28, 31])
    # 找到截止 115000024 的歷史
    cutoff = None
    for i, d in enumerate(all_draws):
        if str(d['draw']) == '115000024':
            cutoff = i + 1
            break
    if cutoff:
        hist_24 = all_draws[:cutoff]

        strategies = [
            ("Baseline TS3", lambda h: original_triple_strike(h)),
            ("Baseline P0 2bet", lambda h: original_p0_2bet(h)),
            ("P0 NeighborInject", lambda h: triple_strike_with_neighbor_injection(h, n_inject=1)),
            ("P1 NeighborCold 2bet", lambda h: neighbor_cold_2bet(h)),
            ("P2 MAB Fusion 3bet", lambda h: mab_fusion_3bet(h, lookback=50)),
            ("P3 StateAware 3bet", lambda h: state_aware_3bet(h)),
        ]

        for name, func in strategies:
            try:
                bets = func(hist_24)
                best_hit = 0
                details = []
                for j, bet in enumerate(bets):
                    hit = len(set(bet) & actual_25)
                    best_hit = max(best_hit, hit)
                    details.append(f"注{j+1}:{bet}→{hit}中")
                m3_mark = "🎯" if best_hit >= 3 else "  "
                print(f"  {m3_mark} {name:<25} 最佳:{best_hit}中 | {' | '.join(details)}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")

    # Save results
    output_path = os.path.join(project_root, 'p0_p3_backtest_results.json')
    serializable = {}
    for k, v in all_results.items():
        serializable[k] = {
            'pattern': v['pattern'],
            'results': {str(w): {kk: vv for kk, vv in r.items()} for w, r in v['results'].items()}
        }
    with open(output_path, 'w') as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    print(f"\n  結果已保存: {output_path}")


if __name__ == "__main__":
    main()
