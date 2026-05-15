#!/usr/bin/env python3
"""
大樂透 P1+偏差互補 5注回測
============================
研究問題：在已驗證的4注 P1+偏差互補 基礎上，哪種第5注附加方法最佳？

4注架構（固定）：
  注1: P1 Neighbor  (上期 ±1 鄰域 → Fourier+Markov 排名 Top-6)
  注2: P1 Cold      (排除注1 → Sum-Constrained 冷號 Top-6)
  注3: DevComp Hot  (排除注1+2 → 近50期偏差互補 Hot Top-6)
  注4: DevComp Cold (排除注1+2+3 → 近50期偏差互補 Cold Top-6)

第5注候選（排除注1-4已用號碼，剩餘約25個號碼中選6）：
  A. Freq-Top        : 剩餘號碼按近100期頻率排序（最高頻）
  B. Freq-Bottom     : 剩餘號碼按近100期頻率排序（最低頻，冷號）
  C. Fourier-Residual: 剩餘號碼按Fourier scores排序
  D. Markov-Residual : 剩餘號碼按Markov scores排序
  E. Sum-Constrained : 剩餘號碼中取Sum最接近均值的組合

優化：
  - 先將全部1500期的4注選號預先計算並快取
  - 再逐一對每個候選方法做5注延伸
  - Permutation test 只需隨機打亂第5注（剩餘號碼池），極快

Usage:
    python3 tools/backtest_p1dev_5bet.py
"""
import os
import sys
import time
import random
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations as _icombs
from scipy.fft import fft, fftfreq
from scipy.stats import norm as scipy_norm
from scipy.stats import chi2 as chi2_dist

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49
PICK = 6
SEED = 42
_SUM_WIN = 300
N_PERM = 2000

P_SINGLE = 0.0186
BASELINES = {
    4: 1 - (1 - P_SINGLE) ** 4,
    5: 1 - (1 - P_SINGLE) ** 5,
}

WINDOWS = [150, 500, 1500]
MIN_BUF = 150


# ============================================================
# Shared utilities
# ============================================================
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


def fourier_scores_full(history, window=500):
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
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            scores[n] = 0.0
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
        else:
            scores[n] = 0.0
    return scores


def markov_scores_func(history, markov_window=30):
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


def cold_numbers_bet(history, window=100, exclude=None, pool_size=12):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))
    if len(history) < 2 or pool_size <= 6:
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


def p1_neighbor_cold_2bet(history):
    prev_nums = history[-1]['numbers']
    neighbor_pool = set()
    for n in prev_nums:
        for d in range(-1, 2):
            nn = n + d
            if 1 <= nn <= MAX_NUM:
                neighbor_pool.add(nn)
    f_scores = fourier_scores_full(history, window=500)
    mk = markov_scores_func(history, markov_window=30)
    f_max = max(f_scores.values()) if f_scores else 1
    mk_max = max(mk.values()) if mk else 1
    neighbor_scores = {}
    for n in neighbor_pool:
        fs = f_scores.get(n, 0) / (f_max or 1)
        ms = mk.get(n, 0) / (mk_max or 1)
        neighbor_scores[n] = fs + 0.5 * ms
    ranked = sorted(neighbor_scores.items(), key=lambda x: -x[1])
    bet1 = sorted([n for n, _ in ranked[:PICK]])
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    return [bet1, bet2]


def deviation_complement_2bet(history, window=50, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) > window else history
    total = len(recent)
    expected = total * PICK / MAX_NUM
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    hot, cold = [], []
    for n in range(1, MAX_NUM + 1):
        if n in exclude:
            continue
        f = freq.get(n, 0)
        dev = f - expected
        if dev > 1:
            hot.append((n, dev))
        elif dev < -1:
            cold.append((n, abs(dev)))
    hot.sort(key=lambda x: -x[1])
    cold.sort(key=lambda x: -x[1])
    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1) | exclude
    if len(bet1) < PICK:
        mid = sorted(
            [n for n in range(1, MAX_NUM + 1) if n not in used],
            key=lambda n: abs(freq.get(n, 0) - expected)
        )
        for n in mid:
            if len(bet1) < PICK:
                bet1.append(n)
                used.add(n)
    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK:
            bet2.append(n)
            used.add(n)
    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK:
                bet2.append(n)
                used.add(n)
    return [sorted(bet1[:PICK]), sorted(bet2[:PICK])]


def p1_deviation_4bet(history):
    p1_bets = p1_neighbor_cold_2bet(history)
    used_p1 = set(n for b in p1_bets for n in b)
    dev_bets = deviation_complement_2bet(history, exclude=used_p1)
    return p1_bets + dev_bets


# ============================================================
# 第5注候選方法（接收 history + residual_pool）
# ============================================================
def bet5_freq_top(history, pool):
    """A: 剩餘號碼按近100期頻率排序（最高頻）"""
    recent = history[-100:] if len(history) >= 100 else history
    freq = Counter(n for d in recent for n in d['numbers'])
    ranked = sorted(pool, key=lambda n: -freq.get(n, 0))
    return frozenset(ranked[:PICK])


def bet5_freq_bottom(history, pool):
    """B: 剩餘號碼按近100期頻率排序（最低頻）"""
    recent = history[-100:] if len(history) >= 100 else history
    freq = Counter(n for d in recent for n in d['numbers'])
    ranked = sorted(pool, key=lambda n: freq.get(n, 0))
    return frozenset(ranked[:PICK])


def bet5_fourier_residual(history, pool):
    """C: 剩餘號碼按Fourier scores排序"""
    scores = fourier_scores_full(history, window=500)
    ranked = sorted(pool, key=lambda n: -scores.get(n, 0))
    return frozenset(ranked[:PICK])


def bet5_markov_residual(history, pool):
    """D: 剩餘號碼按Markov scores排序"""
    mk = markov_scores_func(history, markov_window=30)
    ranked = sorted(pool, key=lambda n: -mk.get(n, 0))
    return frozenset(ranked[:PICK])


def bet5_sum_constrained(history, pool):
    """E: 剩餘號碼中取Sum最接近均值的6個"""
    if len(pool) <= PICK:
        return frozenset(pool[:PICK])
    tlo, thi = _sum_target(history)
    tmid = (tlo + thi) / 2.0
    recent = history[-100:] if len(history) >= 100 else history
    freq = Counter(n for d in recent for n in d['numbers'])
    expected = len(recent) * PICK / MAX_NUM
    pool_sorted = sorted(pool, key=lambda n: abs(freq.get(n, 0) - expected))
    pool_cand = pool_sorted[:18] if len(pool_sorted) > 18 else pool_sorted
    best_combo, best_dist, best_in_range = None, float('inf'), False
    for combo in _icombs(pool_cand, 6):
        s = sum(combo)
        in_range = (tlo <= s <= thi)
        dist = abs(s - tmid)
        if in_range and (not best_in_range or dist < best_dist):
            best_combo, best_dist, best_in_range = combo, dist, True
        elif not in_range and not best_in_range and dist < best_dist:
            best_combo, best_dist = combo, dist
    if best_combo:
        return frozenset(best_combo)
    return frozenset(pool_cand[:PICK])


BET5_METHODS = [
    ("A FreqTop(熱號)",     bet5_freq_top),
    ("B FreqBot(冷號)",     bet5_freq_bottom),
    ("C Fourier殘差",       bet5_fourier_residual),
    ("D Markov殘差",        bet5_markov_residual),
    ("E Sum均值約束",       bet5_sum_constrained),
]


# ============================================================
# 核心：預計算所有期的4注選號 + 第5注候選
# ============================================================
def precompute_all(draws, start_idx):
    """
    預先計算 start_idx 到 len(draws)-1 的所有期：
      - base4_bets[i]: 4注選號 (list of 4 frozensets)
      - base4_hit[i]: 4注是否命中 (bool)
      - residual_pool[i]: 剩餘號碼 list
      - target[i]: 開獎號碼 frozenset
      - bet5_hits[method_name][i]: 第5注是否命中 (bool)
    """
    N = len(draws) - start_idx
    print(f"  預計算 {N} 期... ", end='', flush=True)
    t0 = time.time()

    targets = []
    base4_hits = []
    residual_pools = []
    bet5_results = {name: [] for name, _ in BET5_METHODS}

    for i in range(start_idx, len(draws)):
        target = frozenset(draws[i]['numbers'])
        history = draws[:i]
        targets.append(target)

        try:
            bets4 = p1_deviation_4bet(history)
        except Exception:
            base4_hits.append(False)
            residual_pools.append([])
            for name, _ in BET5_METHODS:
                bet5_results[name].append(False)
            continue

        used = set(n for b in bets4 for n in b)
        hit4 = any(len(set(b) & target) >= 3 for b in bets4)
        base4_hits.append(hit4)

        pool = [n for n in range(1, MAX_NUM + 1) if n not in used]
        residual_pools.append(pool)

        for name, func in BET5_METHODS:
            try:
                b5 = func(history, pool)
                hit5 = len(b5 & target) >= 3
            except Exception:
                hit5 = False
            bet5_results[name].append(hit5)

    print(f"完成 ({time.time()-t0:.1f}s)")
    return targets, base4_hits, residual_pools, bet5_results


# ============================================================
# 計算 Edge
# ============================================================
def calc_edge_5bet(base4_hits, bet5_hits_list, n_periods, baseline5, label=""):
    N = len(base4_hits)
    start = max(0, N - n_periods)
    b4 = base4_hits[start:]
    b5 = bet5_hits_list[start:]
    hits = sum(1 for h4, h5 in zip(b4, b5) if h4 or h5)
    total = len(b4)
    if total == 0:
        return None
    rate = hits / total
    edge = rate - baseline5
    z = (rate - baseline5) / np.sqrt(baseline5 * (1 - baseline5) / total)
    p = 2 * (1 - scipy_norm.cdf(abs(z)))
    return {
        'label': label, 'hits': hits, 'total': total,
        'rate': rate, 'baseline': baseline5,
        'edge_abs': edge * 100, 'z': z, 'p': p
    }


def calc_edge_4bet(base4_hits, n_periods, baseline4, label=""):
    N = len(base4_hits)
    start = max(0, N - n_periods)
    b4 = base4_hits[start:]
    hits = sum(b4)
    total = len(b4)
    if total == 0:
        return None
    rate = hits / total
    edge = rate - baseline4
    z = (rate - baseline4) / np.sqrt(baseline4 * (1 - baseline4) / total)
    p = 2 * (1 - scipy_norm.cdf(abs(z)))
    return {
        'label': label, 'hits': hits, 'total': total,
        'rate': rate, 'baseline': baseline4,
        'edge_abs': edge * 100, 'z': z, 'p': p
    }


def pr(r):
    if not r:
        return
    sig = "***" if r['p'] < 0.01 else ("**" if r['p'] < 0.05 else ("*" if r['p'] < 0.10 else ""))
    print(f"  {r['label']:<38s} {r['hits']:4d}/{r['total']:5d} "
          f"= {r['rate']:.4f}  基準={r['baseline']:.4f}  "
          f"Edge={r['edge_abs']:+.2f}%  z={r['z']:+.2f}{sig}")


# ============================================================
# Permutation test（只打亂第5注）
# ============================================================
def permutation_test_fast(base4_hits, residual_pools, targets, bet5_hits_arr,
                           n_periods, n_perm=N_PERM, seed=SEED):
    """
    快速 permutation test：
    對每一期，從剩餘號碼池隨機取6個作為第5注，重複 n_perm 次。
    比較實際第5注 marginal 命中率 vs 隨機分佈。
    """
    rng = random.Random(seed)
    N = len(base4_hits)
    start = max(0, N - n_periods)
    b4 = base4_hits[start:]
    b5_actual = bet5_hits_arr[start:]
    pools = residual_pools[start:]
    tgts = targets[start:]
    total = len(b4)

    # 實際邊際：第5注命中且4注未命中的數量
    actual_marginal = sum(1 for h4, h5 in zip(b4, b5_actual) if h5 and not h4)
    actual_marginal_rate = actual_marginal / total * 100

    # 隨機基準：每次 permutation 都隨機選第5注
    rand_marginals = []
    for _ in range(n_perm):
        marginal = 0
        for h4, pool, tgt in zip(b4, pools, tgts):
            if h4 or len(pool) < PICK:
                continue  # 4注已命中，第5注邊際=0；或pool太小
            b5_rand = frozenset(rng.sample(pool, PICK))
            if len(b5_rand & tgt) >= 3:
                marginal += 1
        rand_marginals.append(marginal / total * 100)

    rand_arr = np.array(rand_marginals)
    perm_p = np.mean(rand_arr >= actual_marginal_rate)

    # 也計算全命中率（4注OR第5注）
    actual_total_hits = sum(1 for h4, h5 in zip(b4, b5_actual) if h4 or h5)
    rand_total_hits_dist = []
    rng2 = random.Random(seed + 1)
    for _ in range(min(200, n_perm)):
        th = sum(
            1 for h4, pool, tgt in zip(b4, pools, tgts)
            if h4 or (len(pool) >= PICK and len(frozenset(rng2.sample(pool, PICK)) & tgt) >= 3)
        )
        rand_total_hits_dist.append(th / total * 100)

    return {
        'actual_marginal': actual_marginal,
        'actual_marginal_rate': actual_marginal_rate,
        'actual_total_hits': actual_total_hits,
        'actual_total_rate': actual_total_hits / total * 100,
        'rand_marginal_mean': np.mean(rand_arr),
        'rand_marginal_std': np.std(rand_arr),
        'perm_p': perm_p,
        'signal': 'SIGNAL DETECTED' if perm_p <= 0.05 else ('MARGINAL' if perm_p <= 0.10 else 'NOISE'),
        'n_perm': n_perm,
        'total': total
    }


# ============================================================
# McNemar
# ============================================================
def mcnemar_5vs4(base4_hits, bet5_hits_arr, n_periods):
    N = len(base4_hits)
    start = max(0, N - n_periods)
    b4 = base4_hits[start:]
    combined = [h4 or h5 for h4, h5 in zip(b4, bet5_hits_arr[start:])]
    # 5注獨贏: combined但非b4
    five_wins = sum(1 for h4, hc in zip(b4, combined) if hc and not h4)
    # 4注獨贏: b4但5注不增加（因為5注包含4注，所以4注獨贏=0）
    # 正確表述：5注中第5注獨自貢獻 vs 無用
    # McNemar: (combined) vs (b4)
    b_wins = five_wins  # 5注組合贏（加了第5注後多命中）
    a_wins = 0           # 4注反而贏：不可能（加注不會減少命中）
    total_disc = a_wins + b_wins
    if total_disc == 0:
        return 0, 1.0, a_wins, b_wins
    chi2 = (abs(a_wins - b_wins) - 1) ** 2 / total_disc
    p = 1 - chi2_dist.cdf(chi2, df=1)
    return chi2, p, a_wins, b_wins


def main():
    np.random.seed(SEED)
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"\n資料: {len(draws)} 期大樂透  seed={SEED}")
    print(f"研究問題: P1+偏差互補 4注 + 最佳第5注\n")
    t0 = time.time()

    # 預計算（對最大窗口 1500 期）
    start_idx = max(len(draws) - 1500, MIN_BUF)
    targets, base4_hits, residual_pools, bet5_results = precompute_all(draws, start_idx)

    # ── 三窗口 Edge 比較 ──
    print(f"\n{'='*72}")
    print(f"  三窗口 Edge 比較")
    print(f"{'='*72}")

    all_results = {w: {} for w in WINDOWS}
    N = len(base4_hits)

    for w in WINDOWS:
        print(f"\n--- {w}期窗口 (5注基準={BASELINES[5]*100:.2f}%) ---")
        # 4注
        r4 = calc_edge_4bet(base4_hits, w, BASELINES[4], label="4注 P1+偏差互補 (基準)")
        pr(r4)
        all_results[w]['4注'] = r4

        # 各5注候選
        for name, _ in BET5_METHODS:
            b5_list = bet5_results[name]
            # 合併命中：4注OR5注
            combined = [h4 or h5 for h4, h5 in zip(base4_hits, b5_list)]
            r5 = calc_edge_5bet(base4_hits, combined, w, BASELINES[5], label=f"5注+{name}")
            pr(r5)
            all_results[w][name] = r5

    # ── 摘要表 ──
    print(f"\n{'='*72}")
    print(f"  三窗口摘要")
    print(f"{'='*72}")
    print(f"  {'策略':<28s} {'150p':>8s} {'500p':>8s} {'1500p':>8s}  {'模式'}")
    print(f"  {'-'*65}")

    row_4 = all_results[150].get('4注', {}), all_results[500].get('4注', {}), all_results[1500].get('4注', {})
    edges_4 = [r.get('edge_abs', 0) for r in row_4]
    print(f"  {'4注 P1+偏差互補':<28s} {edges_4[0]:>+7.2f}% {edges_4[1]:>+7.2f}% {edges_4[2]:>+7.2f}%  4注基準")

    best_name, best_edges = None, None
    best_1500 = -999
    for name, _ in BET5_METHODS:
        edges = [all_results[w].get(name, {}).get('edge_abs', 0) for w in WINDOWS]
        if all(e > 0 for e in edges):
            mode = "ROBUST ✓"
        elif edges[2] > 0 and edges[0] < 0:
            mode = "LATE_BLOOMER"
        elif edges[0] > 0 and edges[2] < 0:
            mode = "SHORT_MOMENTUM"
        else:
            mode = "MIXED"
        print(f"  {'5注+'+name:<28s} {edges[0]:>+7.2f}% {edges[1]:>+7.2f}% {edges[2]:>+7.2f}%  {mode}")
        if edges[2] > best_1500:
            best_1500 = edges[2]
            best_name = name
            best_edges = edges

    print(f"\n  1500期最佳5注候選: 5注+{best_name}  Edge={best_1500:+.2f}%")

    # ── Permutation test for each candidate ──
    print(f"\n{'='*72}")
    print(f"  Permutation Test (1500期, n={N_PERM}) — 各候選方法")
    print(f"{'='*72}")
    print(f"  {'候選方法':<28s} {'邊際命中':>8s} {'隨機均值':>9s} {'perm_p':>8s}  訊號")
    print(f"  {'-'*65}")

    perm_results = {}
    for name, _ in BET5_METHODS:
        b5_list = bet5_results[name]
        combined = [h4 or h5 for h4, h5 in zip(base4_hits, b5_list)]
        pr_r = permutation_test_fast(
            base4_hits, residual_pools, targets, combined,
            n_periods=1500, n_perm=N_PERM, seed=SEED
        )
        perm_results[name] = pr_r
        print(f"  {'5注+'+name:<28s} {pr_r['actual_marginal_rate']:>+7.3f}%  "
              f"{pr_r['rand_marginal_mean']:>+8.3f}%  "
              f"{pr_r['perm_p']:>7.4f}   {pr_r['signal']}")

    # ── 最佳候選 McNemar ──
    best_b5_combined = [h4 or h5 for h4, h5 in zip(base4_hits, bet5_results[best_name])]
    chi2, pval, a_wins, b_wins = mcnemar_5vs4(base4_hits, best_b5_combined, 1500)
    print(f"\n  McNemar (最佳5注+{best_name} vs 4注, 1500期):")
    print(f"  第5注新增命中={b_wins}期, χ²={chi2:.2f}, p={pval:.4f}"
          f"  {'顯著' if pval < 0.05 else '邊際' if pval < 0.10 else '不顯著'}")

    # ── 結論 ──
    print(f"\n{'='*72}")
    print(f"  最終結論")
    print(f"{'='*72}")
    r4_1500 = all_results[1500].get('4注', {})
    r5_best = all_results[1500].get(best_name, {})
    perm_best = perm_results.get(best_name, {})

    print(f"  4注 P1+偏差互補   Edge={r4_1500.get('edge_abs', 0):+.2f}%")
    print(f"  最佳5注候選       Edge={r5_best.get('edge_abs', 0):+.2f}%  (+{best_name})")
    if best_edges:
        print(f"  三窗口: 150p={best_edges[0]:+.2f}%  500p={best_edges[1]:+.2f}%  1500p={best_edges[2]:+.2f}%")
    if perm_best:
        print(f"  Permutation p={perm_best['perm_p']:.4f}  → {perm_best['signal']}")
    print()

    # 通過標準：三窗口全正 + perm p <= 0.05
    robust = best_edges and all(e > 0 for e in best_edges)
    sig = perm_best and perm_best['perm_p'] <= 0.05

    if robust and sig:
        print(f"  ✅ 建議採納 5注+{best_name}")
        print(f"     三窗口全正 + permutation SIGNAL DETECTED")
    elif robust and perm_best and perm_best['perm_p'] <= 0.10:
        print(f"  ⚠️  邊際採納 5注+{best_name}")
        print(f"     三窗口全正但 perm p={perm_best['perm_p']:.4f} MARGINAL，需監控")
    elif robust:
        print(f"  ⚠️  三窗口全正但 perm 未達顯著，第5注信號弱")
    else:
        print(f"  ❌ 不建議採納任何5注候選")
        print(f"     三窗口未全正 或 permutation NOISE")

    print(f"\n  耗時: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
