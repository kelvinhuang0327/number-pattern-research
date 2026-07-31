"""
大樂透 6注 EWMA Drift 邊際驗證
=============================================
注1-5：TS3 + Markov(w=30) + 頻率正交（已驗證 1500p +1.77%）
注6：EWMA Drift (alpha=0.2) 正交 — 從剩餘 19 個號碼中選

目的：驗證 EWMA Drift 作為第6注的邊際 Edge 是否顯著

方法：
  1. 三階窗口 (150/500/1500p) + H1/H2 分析
  2. 邊際命中率 vs 隨機第6注基準
  3. 500p 排列檢定 (n=200)

EWMA 方向（同時測試）：
  - HIGH: 選正漂移最大（近期出現頻率 > 長期均值，動量追隨）
  - LOW:  選負漂移最大（近期出現頻率 < 長期均值，逆向回歸）
"""

import os
import sys
import copy
import math
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq
from scipy.stats import norm

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49
PICK = 6
P1 = 1 - sum(
    math.comb(6, k) * math.comb(43, 6 - k) / math.comb(49, 6)
    for k in range(3)
)  # ≈ 0.018599


def n_bet_baseline(n):
    return (1 - (1 - P1) ** n) * 100


def marginal_baseline(n):
    """P(Nbet M3+) - P((N-1)bet M3+) = (1-P1)^(N-1) * P1"""
    return ((1 - P1) ** (n - 1)) * P1 * 100


# ──────────────────────────────────────────────────────────
# TS3 核心（沿用 Markov 4bet 的完整實作）
# ──────────────────────────────────────────────────────────

def fourier_rhythm_bet(history, window=500):
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bits = np.array([1 if n in d['numbers'] else 0 for d in h], dtype=float)
        if bits.sum() < 2:
            continue
        yf = fft(bits - bits.mean())
        xf = fftfreq(w, 1)
        pos = xf > 0
        if pos.sum() == 0:
            continue
        peak = np.argmax(np.abs(yf[pos]))
        freq_val = xf[pos][peak]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bits == 1)[0]
            if len(last_hit) == 0:
                continue
            gap = (w - 1) - last_hit[-1]
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    ranked = np.argsort(scores[1:])[::-1] + 1
    return sorted(ranked[:6].tolist())


def cold_numbers_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'] if n <= MAX_NUM)
    candidates = sorted(
        [n for n in range(1, MAX_NUM + 1) if n not in exclude],
        key=lambda x: freq.get(x, 0)
    )
    return sorted(candidates[:PICK])


def tail_balance_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'] if n <= MAX_NUM)

    tail_groups = {i: [] for i in range(10)}
    for n in range(1, MAX_NUM + 1):
        if n not in exclude:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for t in tail_groups:
        tail_groups[t].sort(key=lambda x: -x[1])

    selected = []
    available_tails = sorted(
        [t for t in range(10) if tail_groups[t]],
        key=lambda t: tail_groups[t][0][1],
        reverse=True
    )
    idx_in_group = {t: 0 for t in range(10)}

    while len(selected) < PICK:
        added = False
        for tail in available_tails:
            if len(selected) >= PICK:
                break
            if idx_in_group[tail] < len(tail_groups[tail]):
                num, _ = tail_groups[tail][idx_in_group[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                idx_in_group[tail] += 1
        if not added:
            break

    if len(selected) < PICK:
        remaining = sorted(
            [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in selected],
            key=lambda x: -freq.get(x, 0)
        )
        selected.extend(remaining[:PICK - len(selected)])

    return sorted(selected[:PICK])


def markov_orthogonal_bet(history, exclude=None, window=30):
    """Markov 轉移分數（w=30，已驗證最優）"""
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history

    transitions = Counter()
    for i in range(len(recent) - 1):
        for p in recent[i]['numbers']:
            for q in recent[i + 1]['numbers']:
                transitions[(p, q)] += 1

    if len(history) < 2:
        cands = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
        return sorted(cands[:PICK])

    last_nums = history[-1]['numbers']
    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = sum(transitions.get((p, n), 0) for p in last_nums)

    candidates = sorted(
        [n for n in range(1, MAX_NUM + 1) if n not in exclude],
        key=lambda x: -scores[x]
    )
    return sorted(candidates[:PICK])


# ──────────────────────────────────────────────────────────
# EWMA Drift 信號
# ──────────────────────────────────────────────────────────

def ewma_drift_scores(history, alpha=0.2):
    """
    EWMA 漂移偵測：
    - 以長期平均頻率初始化 EWMA
    - 逐期更新：ewma = α * appeared + (1-α) * ewma
    - drift = ewma - long_term_freq
    - 正值 = 近期出現頻率高於長期均值（上升動量）
    - 負值 = 近期出現頻率低於長期均值（受壓待回彈）
    """
    N = len(history)
    long_freq = {}
    for n in range(1, MAX_NUM + 1):
        long_freq[n] = sum(1 for d in history if n in d['numbers'][:PICK]) / N

    ewma_val = dict(long_freq)  # 以長期均值初始化
    for draw in history:
        nums_set = set(draw['numbers'][:PICK])
        for n in range(1, MAX_NUM + 1):
            x = 1.0 if n in nums_set else 0.0
            ewma_val[n] = alpha * x + (1 - alpha) * ewma_val[n]

    return {n: ewma_val[n] - long_freq[n] for n in range(1, MAX_NUM + 1)}


# ──────────────────────────────────────────────────────────
# 策略生成
# ──────────────────────────────────────────────────────────

def generate_5bet(history):
    """TS3 + Markov(w=30) + 頻率正交"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))

    used3 = set(bet1) | set(bet2) | set(bet3)
    bet4 = markov_orthogonal_bet(history, exclude=used3, window=30)

    used4 = used3 | set(bet4)
    freq100 = Counter(
        n for d in history[-100:] for n in d['numbers'][:PICK] if n <= MAX_NUM
    )
    leftover = sorted(
        [n for n in range(1, MAX_NUM + 1) if n not in used4],
        key=lambda x: -freq100.get(x, 0)
    )
    bet5 = sorted(leftover[:PICK])

    return [bet1, bet2, bet3, bet4, bet5]


def generate_6bet_high_drift(history):
    """注6：從剩餘 19 號中選 EWMA 正漂移最大（動量追隨）"""
    bets5 = generate_5bet(history)
    used5 = set(n for b in bets5 for n in b)
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in used5]

    drift = ewma_drift_scores(history, alpha=0.2)
    remaining.sort(key=lambda x: -drift[x])  # 高漂移優先
    bet6 = sorted(remaining[:PICK])
    return bets5 + [bet6]


def generate_6bet_low_drift(history):
    """注6：從剩餘 19 號中選 EWMA 負漂移最大（逆向回歸）"""
    bets5 = generate_5bet(history)
    used5 = set(n for b in bets5 for n in b)
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in used5]

    drift = ewma_drift_scores(history, alpha=0.2)
    remaining.sort(key=lambda x: drift[x])  # 低漂移優先（最受壓抑）
    bet6 = sorted(remaining[:PICK])
    return bets5 + [bet6]


# ──────────────────────────────────────────────────────────
# 回測引擎
# ──────────────────────────────────────────────────────────

def run_backtest(all_draws, strategy_fn, periods, min_history=200):
    test_start = len(all_draws) - periods
    hits = total = 0
    half = periods // 2
    h1_hits = h1_total = h2_hits = h2_total = 0

    for i in range(periods):
        idx = test_start + i
        if idx < min_history:
            continue
        hist = all_draws[:idx]
        actual = set(all_draws[idx]['numbers'][:PICK])
        try:
            bets = strategy_fn(hist)
        except Exception:
            continue

        hit = any(len(set(b) & actual) >= 3 for b in bets)
        hits += hit
        total += 1
        if i < half:
            h1_total += 1
            h1_hits += hit
        else:
            h2_total += 1
            h2_hits += hit

    n_bets = len(strategy_fn(all_draws[-10:]))
    baseline = n_bet_baseline(n_bets)
    m3_rate = hits / total * 100 if total > 0 else 0
    edge = m3_rate - baseline
    se = (baseline * (100 - baseline) / 100 / total) ** 0.5 if total > 0 else 1
    z = edge / se
    p = 1 - norm.cdf(z)

    return {
        'periods': total, 'm3_rate': m3_rate, 'baseline': baseline,
        'edge': edge, 'z': z, 'p': p,
        'h1_edge': (h1_hits / h1_total * 100 - baseline) if h1_total > 0 else 0,
        'h2_edge': (h2_hits / h2_total * 100 - baseline) if h2_total > 0 else 0,
        'hits': hits,
    }


def permutation_test(all_draws, strategy_fn, periods, n_shuffles=200, seed=42):
    real = run_backtest(all_draws, strategy_fn, periods)
    real_edge = real['edge']

    rng = np.random.RandomState(seed)
    shuffle_edges = []
    for _ in range(n_shuffles):
        shuffled = copy.deepcopy(all_draws)
        pool_nums = [d['numbers'][:] for d in shuffled]
        idx = rng.permutation(len(pool_nums))
        for i, d in enumerate(shuffled):
            d['numbers'] = pool_nums[idx[i]]
        r = run_backtest(shuffled, strategy_fn, periods)
        shuffle_edges.append(r['edge'])

    arr = np.array(shuffle_edges)
    p = float(np.mean(arr >= real_edge))
    d = float((real_edge - arr.mean()) / (arr.std() + 1e-10))
    verdict = 'SIGNAL' if p < 0.05 else 'MARGINAL' if p < 0.10 else 'NO_SIGNAL'
    return {
        'real_edge': real_edge, 'shuffle_mean': arr.mean(),
        'p_value': p, 'cohens_d': d, 'verdict': verdict,
    }


# ──────────────────────────────────────────────────────────
# 主程式
# ──────────────────────────────────────────────────────────

def main():
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"總期數: {len(all_draws)}")
    print(f"P(1注 M3+)   = {P1 * 100:.4f}%")
    print(f"5注基準      = {n_bet_baseline(5):.4f}%")
    print(f"6注基準      = {n_bet_baseline(6):.4f}%")
    print(f"注6隨機邊際基準 = {marginal_baseline(6):.4f}%")

    strategies = [
        ('5注 TS3+M+FO',      generate_5bet),
        ('6注 EWMA高漂移',    generate_6bet_high_drift),
        ('6注 EWMA低漂移',    generate_6bet_low_drift),
    ]

    print("\n" + "=" * 78)
    print("三窗口對比：5注 vs 6注 EWMA-High vs 6注 EWMA-Low")
    print("=" * 78)
    print(f"{'視窗':>6}  {'策略':>16}  {'M3+%':>6}  {'基準%':>6}  {'Edge%':>7}  "
          f"{'z':>5}  {'p':>6}  {'H1%':>7}  {'H2%':>7}")
    print("-" * 78)

    results_cache = {}
    for periods in [150, 500, 1500]:
        for label, fn in strategies:
            r = run_backtest(all_draws, fn, periods)
            results_cache[(periods, label)] = r
            print(f"{periods:6d}  {label:>16}  {r['m3_rate']:6.2f}  {r['baseline']:6.2f}  "
                  f"{r['edge']:+7.2f}  {r['z']:5.2f}  {r['p']:6.4f}  "
                  f"{r['h1_edge']:+7.2f}  {r['h2_edge']:+7.2f}")
        print()

    # 邊際 Edge 計算
    print("=" * 78)
    print("注6 EWMA 邊際 Edge（6注 - 5注，vs 隨機邊際基準）")
    print("=" * 78)
    marg_base = marginal_baseline(6)
    for periods in [150, 500, 1500]:
        r5 = results_cache[(periods, '5注 TS3+M+FO')]
        for label in ['6注 EWMA高漂移', '6注 EWMA低漂移']:
            r6 = results_cache[(periods, label)]
            marginal_hit = r6['m3_rate'] - r5['m3_rate']
            marginal_edge = marginal_hit - marg_base
            print(f"  {periods}p [{label}]：邊際命中率增量={marginal_hit:+.2f}%  "
                  f"邊際基準={marg_base:.2f}%  邊際Edge={marginal_edge:+.2f}%")

    # 500p 排列檢定
    print()
    print("=" * 78)
    print("500p 排列檢定 (n=200)：EWMA 高漂移 & 低漂移 6注整體")
    print("=" * 78)
    for label, fn in [('高漂移', generate_6bet_high_drift), ('低漂移', generate_6bet_low_drift)]:
        perm = permutation_test(all_draws, fn, 500, n_shuffles=200)
        print(f"  [{label}] Real Edge: {perm['real_edge']:+.2f}%  "
              f"Shuffle mean: {perm['shuffle_mean']:+.4f}%  "
              f"p={perm['p_value']:.4f}  d={perm['cohens_d']:.3f}  → {perm['verdict']}")


if __name__ == '__main__':
    main()
