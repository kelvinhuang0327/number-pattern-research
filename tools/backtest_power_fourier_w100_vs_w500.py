#!/usr/bin/env python3
"""
威力彩 Fourier w100 vs w500 獨立回測
=====================================
研究目標: 在 PP3v1 框架下，只改 Fourier 窗口 w500→w100
研究方法: 1500期 walk-forward OOS，三窗口驗證 (150/500/1500)
          McNemar 比較兩版本 hit≥1 / hit≥2

PP3v1 框架 (不變):
  注1: Fourier Top6 (測試不同 window)
  注2: Fourier Next6 (測試不同 window)
  注3: Echo/Cold

結論基準 (採納):
  - 三窗口 Edge 全正
  - MC perm p ≤ 0.05
  - McNemar hit≥2 p < 0.05 且方向為 w100 勝
"""
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq
import random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))
from lottery_api.database import DatabaseManager

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

MAX_NUM = 38
PICK = 6
MIN_HISTORY = 600  # walk-forward 最小起始期數


def get_fourier_rank(history, window):
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
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores)[::-1]


def generate_pp3(history, window):
    """PP3v1 框架，只改 Fourier 窗口"""
    f_rank = get_fourier_rank(history, window)

    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0:
        idx_1 += 1
    bet1 = set(f_rank[idx_1:idx_1+6].tolist())

    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0:
        idx_2 += 1
    bet2 = set(f_rank[idx_2:idx_2+6].tolist())

    exclude = bet1 | bet2

    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in exclude]
    else:
        echo_nums = []

    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq.get(x, 0))
    bet3 = set((echo_nums + remaining)[:6])

    return [bet1, bet2, bet3]


def count_hits(bets, actual):
    actual_set = set(actual)
    return max(len(b & actual_set) for b in bets)


def random_3bet_hits(actual, n_sim=1):
    actual_set = set(actual)
    results = []
    for _ in range(n_sim):
        bets = []
        used = set()
        for _ in range(3):
            pool = [n for n in range(1, MAX_NUM + 1) if n not in used]
            pick = set(random.sample(pool, PICK))
            bets.append(pick)
            used |= pick
        results.append(max(len(b & actual_set) for b in bets))
    return results


def run_backtest(draws, window, n_periods=1500):
    total = len(draws)
    start = max(MIN_HISTORY, total - n_periods)
    test_draws = draws[start:]

    hits = []
    for i, draw in enumerate(test_draws):
        history = draws[:start + i]  # walk-forward: only past data
        bets = generate_pp3(history, window)
        actual = [n for n in draw['numbers'] if n <= MAX_NUM]
        h = count_hits(bets, actual)
        hits.append(h)

    hits = np.array(hits)
    n = len(hits)

    # M2+ rate (hit≥2 per bet = hit≥2 across 3 bets)
    # 基準: 3注隨機 M2+ 率
    baseline_m2 = 0.182  # 威力彩 3注 M2+ 理論基準 (來自已驗證資料)
    actual_m2 = np.mean(hits >= 2)
    edge = actual_m2 - baseline_m2

    return hits, edge, n


def window_stats(hits, baseline=0.182):
    n = len(hits)
    m2 = np.mean(hits >= 2)
    m1 = np.mean(hits >= 1)
    edge = m2 - baseline
    return {'n': n, 'm1': m1, 'm2': m2, 'edge': edge}


def permutation_test(hits, baseline=0.182, n_perm=200, seed=42):
    rng = np.random.RandomState(seed)
    obs = np.mean(hits >= 2) - baseline
    count = 0
    for _ in range(n_perm):
        shuffled = rng.permutation(hits)
        sim = np.mean(shuffled >= 2) - baseline
        if sim >= obs:
            count += 1
    return count / n_perm


def mcnemar(hits_a, hits_b, threshold=2):
    assert len(hits_a) == len(hits_b)
    a_only = np.sum((hits_a >= threshold) & (hits_b < threshold))
    b_only = np.sum((hits_b >= threshold) & (hits_a < threshold))
    if a_only + b_only == 0:
        return 1.0, 0, 0
    chi2 = (abs(a_only - b_only) - 1) ** 2 / (a_only + b_only)
    from scipy.stats import chi2 as chi2_dist
    p = 1 - chi2_dist.cdf(chi2, df=1)
    return p, a_only, b_only


def main():
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    total = len(draws)

    print("=" * 70)
    print("  威力彩 Fourier w100 vs w500 — PP3v1 框架獨立研究")
    print(f"  資料庫: {total} 期")
    print(f"  Random seed: {SEED}")
    print("=" * 70)

    windows = [100, 500]
    results = {}

    for w in windows:
        print(f"\n[Fourier w={w}] 回測中...")
        hits_1500, edge_1500, n_1500 = run_backtest(draws, w, n_periods=1500)
        hits_500, _, n_500 = run_backtest(draws, w, n_periods=500)
        hits_150, _, n_150 = run_backtest(draws, w, n_periods=150)

        s1500 = window_stats(hits_1500)
        s500 = window_stats(hits_500)
        s150 = window_stats(hits_150)

        perm_p = permutation_test(hits_1500, n_perm=200, seed=SEED)

        results[w] = {
            'hits_1500': hits_1500,
            'hits_500': hits_500,
            'hits_150': hits_150,
            's1500': s1500,
            's500': s500,
            's150': s150,
            'perm_p': perm_p,
        }

        print(f"  150期  Edge: {s150['edge']:+.2%}  M2+: {s150['m2']:.1%}")
        print(f"  500期  Edge: {s500['edge']:+.2%}  M2+: {s500['m2']:.1%}")
        print(f"  1500期 Edge: {s1500['edge']:+.2%}  M2+: {s1500['m2']:.1%}")
        print(f"  Perm p={perm_p:.3f} {'✅ SIGNAL' if perm_p <= 0.05 else '⚠️ MARGINAL' if perm_p <= 0.10 else '❌ NO SIGNAL'}")

    # McNemar 比較
    print("\n" + "=" * 70)
    print("  McNemar 比較 (w100 vs w500, 1500期)")
    print("=" * 70)

    hits_100 = results[100]['hits_1500']
    hits_500_arr = results[500]['hits_1500']

    # 確保對齊 (取較短的)
    n_min = min(len(hits_100), len(hits_500_arr))
    hits_100 = hits_100[-n_min:]
    hits_500_arr = hits_500_arr[-n_min:]

    for thr, label in [(1, 'hit≥1'), (2, 'hit≥2'), (3, 'hit≥3')]:
        p, a_only, b_only = mcnemar(hits_100, hits_500_arr, threshold=thr)
        winner = 'w100勝' if a_only > b_only else 'w500勝' if b_only > a_only else '平手'
        sig = '✅ 顯著' if p < 0.05 else '— 不顯著'
        print(f"  {label}: w100_only={a_only}, w500_only={b_only}, p={p:.3f}  {winner} {sig}")

    # 結論
    print("\n" + "=" * 70)
    print("  研究結論")
    print("=" * 70)

    r100 = results[100]
    r500 = results[500]

    all_pos_100 = all([r100['s150']['edge'] > 0, r100['s500']['edge'] > 0, r100['s1500']['edge'] > 0])
    all_pos_500 = all([r500['s150']['edge'] > 0, r500['s500']['edge'] > 0, r500['s1500']['edge'] > 0])

    print(f"  w100 三窗口全正: {'✅' if all_pos_100 else '❌'}")
    print(f"  w500 三窗口全正: {'✅' if all_pos_500 else '❌'}")
    print(f"  w100 perm p={r100['perm_p']:.3f}  w500 perm p={r500['perm_p']:.3f}")

    edge_diff = r100['s1500']['edge'] - r500['s1500']['edge']
    print(f"  1500期 Edge 差異: w100-w500 = {edge_diff:+.2%}")

    p_h2, a2, b2 = mcnemar(hits_100[-n_min:], hits_500_arr[-n_min:], threshold=2)
    if p_h2 < 0.05 and a2 > b2:
        verdict = "✅ ADOPT — w100 顯著優於 w500 (hit≥2 McNemar p<0.05)"
    elif p_h2 < 0.05 and b2 > a2:
        verdict = "❌ REJECT — w500 顯著優於 w100"
    else:
        verdict = f"— HOLD — McNemar hit≥2 p={p_h2:.3f} 不顯著，維持 w500"

    print(f"\n  最終判定: {verdict}")

    # 歸檔建議
    if "ADOPT" in verdict:
        print("\n  建議: 可升格部署 w100 到 PP3v1")
    else:
        print("\n  建議: 維持 PP3v1 w500，w100 研究結案")
        print("  歸檔: rejected/fourier_w100_pp3_power.json")

    print("=" * 70)


if __name__ == "__main__":
    main()
