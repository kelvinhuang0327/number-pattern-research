"""
大樂透 6注回測驗證
注1-5：TS3+Markov+FreqOrtho（已驗證）
注6：lag2_echo_w50_e1.5 正交加入

目的：驗證第6注的邊際 Edge 是否顯著正值
"""

import os
import sys
import copy
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
    __import__('math').comb(6, k) * __import__('math').comb(43, 6 - k) / __import__('math').comb(49, 6)
    for k in range(3)
)  # ≈ 0.018599


def n_bet_baseline(n):
    return (1 - (1 - P1) ** n) * 100


def marginal_baseline(n):
    """P(Nbet M3+) - P((N-1)bet M3+) = (1-P1)^(N-1) * P1"""
    return ((1 - P1) ** (n - 1)) * P1 * 100


# ────────────────────────────────────────────────────────────
# 核心選號邏輯
# ────────────────────────────────────────────────────────────

def get_fourier_rank(history, window=500):
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
        last_hit = np.where(bits == 1)[0]
        if len(last_hit) == 0:
            continue
        gap = (w - 1) - last_hit[-1]
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores[1:])[::-1] + 1  # 1-indexed, descending


def lag2_echo_scores(history, window=50, echo_boost=1.5):
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'][:PICK] if n <= MAX_NUM)
    lag2 = set(history[-2]['numbers'][:PICK]) if len(history) >= 2 else set()
    scores = {}
    for n in range(1, MAX_NUM + 1):
        s = freq.get(n, 0)
        if n in lag2:
            s *= echo_boost
        scores[n] = s
    return scores


def generate_5bet(history):
    """注1-5：TS3(Fourier/Echo/Cold) + Markov正交 + 頻率正交"""
    f_rank = get_fourier_rank(history)

    # 注1：Fourier top 6
    bet1 = sorted(f_rank[:6].tolist())

    # 注2：Fourier next 6
    bet2 = sorted(f_rank[6:12].tolist())

    # 注3：Echo + Cold
    exclude12 = set(bet1) | set(bet2)
    recent100 = history[-100:]
    freq100 = Counter(n for d in recent100 for n in d['numbers'][:PICK] if n <= MAX_NUM)

    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'][:PICK]
                     if n <= MAX_NUM and n not in exclude12]
    else:
        echo_nums = []

    rem3 = [n for n in range(1, MAX_NUM + 1) if n not in exclude12 and n not in echo_nums]
    rem3.sort(key=lambda x: freq100.get(x, 0))  # coldest first
    bet3 = sorted((echo_nums + rem3)[:6])

    # 注4-5：剩餘號碼按近100期頻率排序
    used3 = set(bet1) | set(bet2) | set(bet3)
    leftover = [n for n in range(1, MAX_NUM + 1) if n not in used3]
    leftover.sort(key=lambda x: freq100.get(x, 0), reverse=True)

    bet4 = sorted(leftover[:6])
    bet5 = sorted(leftover[6:12])

    return [bet1, bet2, bet3, bet4, bet5]


def generate_6bet(history):
    """注1-5 同上，注6：lag2_echo 正交"""
    bets5 = generate_5bet(history)
    used5 = set(n for b in bets5 for n in b)

    # 注6：從剩餘 19 個號碼中，按 lag2_echo 分數排序取前 6
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in used5]
    echo_sc = lag2_echo_scores(history, window=50, echo_boost=1.5)
    remaining.sort(key=lambda x: echo_sc.get(x, 0), reverse=True)
    bet6 = sorted(remaining[:6])

    return bets5 + [bet6]


# ────────────────────────────────────────────────────────────
# 回測引擎
# ────────────────────────────────────────────────────────────

def run_backtest_single(all_draws, strategy_fn, periods, min_history=200):
    test_start = len(all_draws) - periods
    hits = 0
    total = 0
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
        if hit:
            hits += 1
        total += 1

        if i < half:
            h1_total += 1
            if hit:
                h1_hits += 1
        else:
            h2_total += 1
            if hit:
                h2_hits += 1

    m3_rate = hits / total * 100 if total > 0 else 0
    n_bets = len(strategy_fn(all_draws[-10:]))  # detect bet count
    baseline = n_bet_baseline(n_bets)
    edge = m3_rate - baseline
    z = edge / (baseline * (100 - baseline) / 100 / total) ** 0.5 if total > 0 else 0
    p = 1 - norm.cdf(z)

    h1_rate = h1_hits / h1_total * 100 if h1_total > 0 else 0
    h2_rate = h2_hits / h2_total * 100 if h2_total > 0 else 0
    h1_edge = h1_rate - baseline
    h2_edge = h2_rate - baseline

    return {
        'periods': total, 'm3_rate': m3_rate, 'baseline': baseline,
        'edge': edge, 'z': z, 'p': p,
        'h1_edge': h1_edge, 'h2_edge': h2_edge,
        'hits': hits,
    }


def permutation_test(all_draws, strategy_fn, periods, n_shuffles=200, seed=42):
    real = run_backtest_single(all_draws, strategy_fn, periods)
    real_edge = real['edge']

    rng = np.random.RandomState(seed)
    shuffle_edges = []
    for _ in range(n_shuffles):
        shuffled = copy.deepcopy(all_draws)
        pool_nums = [d['numbers'][:] for d in shuffled]
        idx = rng.permutation(len(pool_nums))
        for i, d in enumerate(shuffled):
            d['numbers'] = pool_nums[idx[i]]
        r = run_backtest_single(shuffled, strategy_fn, periods)
        shuffle_edges.append(r['edge'])

    arr = np.array(shuffle_edges)
    p = float(np.mean(arr >= real_edge))
    d = float((real_edge - arr.mean()) / (arr.std() + 1e-10))
    return {
        'real_edge': real_edge,
        'shuffle_mean': arr.mean(),
        'p_value': p,
        'cohens_d': d,
        'verdict': 'SIGNAL' if p < 0.05 else 'MARGINAL' if p < 0.10 else 'NO_SIGNAL',
    }


# ────────────────────────────────────────────────────────────
# 主程式
# ────────────────────────────────────────────────────────────

def main():
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"總期數: {len(all_draws)}")
    print(f"P(1注 M3+) = {P1*100:.4f}%")
    print(f"5注基準 = {n_bet_baseline(5):.4f}%")
    print(f"6注基準 = {n_bet_baseline(6):.4f}%")
    print(f"注6 邊際基準 = {marginal_baseline(6):.4f}%")

    print("\n" + "=" * 70)
    print("三窗口對比：5注 vs 6注")
    print("=" * 70)
    print(f"{'視窗':>6}  {'策略':>8}  {'M3+%':>6}  {'基準%':>6}  {'Edge%':>7}  "
          f"{'z':>5}  {'p':>6}  {'H1%':>7}  {'H2%':>7}")
    print("-" * 70)

    for periods in [150, 500, 1500]:
        for label, fn in [('5注', generate_5bet), ('6注', generate_6bet)]:
            r = run_backtest_single(all_draws, fn, periods)
            print(f"{periods:6d}  {label:>8}  {r['m3_rate']:6.2f}  {r['baseline']:6.2f}  "
                  f"{r['edge']:+7.2f}  {r['z']:5.2f}  {r['p']:6.4f}  "
                  f"{r['h1_edge']:+7.2f}  {r['h2_edge']:+7.2f}")
        print()

    # 邊際 Edge 計算
    print("=" * 70)
    print("注6 邊際 Edge（6注 - 5注，以隨機邊際基準校正）")
    print("=" * 70)
    marg_base = marginal_baseline(6)
    for periods in [150, 500, 1500]:
        r5 = run_backtest_single(all_draws, generate_5bet, periods)
        r6 = run_backtest_single(all_draws, generate_6bet, periods)
        # 邊際：有多少期 6注命中而 5注未命中
        # 用 hit6_rate - hit5_rate vs marginal_baseline
        marginal_hit = r6['m3_rate'] - r5['m3_rate']
        marginal_edge = marginal_hit - marg_base
        print(f"  {periods}p：邊際命中率增量={marginal_hit:+.2f}%  "
              f"邊際基準={marg_base:.2f}%  邊際Edge={marginal_edge:+.2f}%")

    # 500p 排列檢定
    print()
    print("=" * 70)
    print("500p 排列檢定 (n=200)：6注整體")
    print("=" * 70)
    perm = permutation_test(all_draws, generate_6bet, 500, n_shuffles=200)
    print(f"  Real Edge:    {perm['real_edge']:+.2f}%")
    print(f"  Shuffle mean: {perm['shuffle_mean']:+.4f}%")
    print(f"  p-value:      {perm['p_value']:.4f}")
    print(f"  Cohen's d:    {perm['cohens_d']:.3f}")
    print(f"  Verdict:      {perm['verdict']}")


if __name__ == '__main__':
    main()
