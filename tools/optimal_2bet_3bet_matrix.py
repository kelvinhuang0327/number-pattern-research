#!/usr/bin/env python3
"""
大樂透 2注/3注 最優矩陣研究
=============================================
目標：在已驗證的信號池中，找出最優 2注/3注子集組合

測試矩陣：
  2注組合（C(5,2)=10 種）:
    B1+B2, B1+B3, B1+B4, B1+B5, B2+B3, B2+B4, B2+B5, B3+B4, B3+B5, B4+B5

  3注組合（C(5,3)=10 種）:
    B1+B2+B3 (TS3), B1+B2+B4, B1+B2+B5, B1+B3+B4, B1+B3+B5,
    B1+B4+B5, B2+B3+B4, B2+B3+B5, B2+B4+B5, B3+B4+B5

每個組合：
  1. 1500p 三窗口回測(150/500/1500)
  2. H1/H2 穩定性
  3. 最佳組合做 500p 排列檢定

注碼定義：
  B1 = Fourier Rhythm
  B2 = Cold Numbers (近100期最冷)
  B3 = Tail Balance (尾數均衡)
  B4 = Markov w=30 (正交)
  B5 = Frequency Orthogonal (剩餘熱號)
"""

import os, sys, math, time, copy
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
SEED = 42

P1 = 1 - sum(math.comb(6, k) * math.comb(43, 6-k) / math.comb(49, 6) for k in range(3))

def n_bet_baseline(n):
    return (1 - (1 - P1) ** n) * 100

BET_NAMES = ['B1_Fourier', 'B2_Cold', 'B3_TailBal', 'B4_Markov', 'B5_FreqOrt']

# ══════════════════════════════════════════════════════════
# Individual Bet Generators (all zero-overlap, orthogonal)
# ══════════════════════════════════════════════════════════

def fourier_rhythm_bet(history, window=500):
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bits = np.array([1 if n in d['numbers'] else 0 for d in h], dtype=float)
        if bits.sum() < 2: continue
        yf = fft(bits - bits.mean())
        xf = fftfreq(w, 1)
        pos = xf > 0
        if pos.sum() == 0: continue
        peak = np.argmax(np.abs(yf[pos]))
        fv = xf[pos][peak]
        if fv == 0: continue
        period = 1 / fv
        if 2 < period < w / 2:
            lh = np.where(bits == 1)[0]
            if len(lh) == 0: continue
            gap = (w - 1) - lh[-1]
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores[1:])[::-1] + 1


def generate_all_5_bets(history):
    """Generate all 5 bets, return list of 5 sorted lists"""
    f_rank = fourier_rhythm_bet(history)
    bet1 = sorted(f_rank[:6].tolist())

    excl = set(bet1)
    freq100 = Counter(n for d in history[-100:] for n in d['numbers'][:PICK] if n <= MAX_NUM)

    # B2: Cold
    cands = sorted([n for n in range(1, MAX_NUM+1) if n not in excl],
                   key=lambda x: freq100.get(x, 0))
    bet2 = sorted(cands[:6])
    excl |= set(bet2)

    # B3: TailBalance
    tail_groups = {i: [] for i in range(10)}
    for n in range(1, MAX_NUM+1):
        if n not in excl:
            tail_groups[n % 10].append((n, freq100.get(n, 0)))
    for t in tail_groups: tail_groups[t].sort(key=lambda x: -x[1])
    sel3 = []
    avail = sorted([t for t in range(10) if tail_groups[t]],
                   key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0, reverse=True)
    idx_g = {t: 0 for t in range(10)}
    while len(sel3) < PICK:
        added = False
        for t in avail:
            if len(sel3) >= PICK: break
            if idx_g[t] < len(tail_groups[t]):
                num, _ = tail_groups[t][idx_g[t]]
                if num not in sel3: sel3.append(num); added = True
                idx_g[t] += 1
        if not added: break
    if len(sel3) < PICK:
        rem = [n for n in range(1, MAX_NUM+1) if n not in excl and n not in sel3]
        rem.sort(key=lambda x: -freq100.get(x, 0))
        sel3.extend(rem[:PICK - len(sel3)])
    bet3 = sorted(sel3[:PICK])
    excl |= set(bet3)

    # B4: Markov w=30
    recent30 = history[-30:] if len(history) >= 30 else history
    trans = Counter()
    for i in range(len(recent30)-1):
        for p in recent30[i]['numbers']:
            for q in recent30[i+1]['numbers']:
                trans[(p,q)] += 1
    last_nums = history[-1]['numbers']
    mk = {n: sum(trans.get((p,n),0) for p in last_nums) for n in range(1, MAX_NUM+1)}
    mk_cands = sorted([n for n in range(1, MAX_NUM+1) if n not in excl], key=lambda x: -mk[x])
    bet4 = sorted(mk_cands[:PICK])
    excl |= set(bet4)

    # B5: Freq Orthogonal
    left = sorted([n for n in range(1, MAX_NUM+1) if n not in excl],
                  key=lambda x: -freq100.get(x, 0))
    bet5 = sorted(left[:PICK])

    return [bet1, bet2, bet3, bet4, bet5]


# ══════════════════════════════════════════════════════════
# Backtest Engine
# ══════════════════════════════════════════════════════════

def run_subset_backtest(all_draws, bet_indices, periods, min_hist=200):
    """
    Backtest a subset of bets (e.g., [0,1] for B1+B2).
    Returns M3+ rate, Edge, z, p, H1/H2.
    """
    n_bets = len(bet_indices)
    baseline = n_bet_baseline(n_bets)
    start = max(min_hist, len(all_draws) - periods)

    hits = total = 0
    half_point = (len(all_draws) - start) // 2
    h1_hits = h1_total = h2_hits = h2_total = 0

    for idx in range(start, len(all_draws)):
        history = all_draws[:idx]
        actual = set(all_draws[idx]['numbers'][:PICK])

        try:
            all_bets = generate_all_5_bets(history)
        except:
            continue

        selected_bets = [all_bets[i] for i in bet_indices]
        hit = any(len(set(b) & actual) >= 3 for b in selected_bets)

        hits += hit
        total += 1
        pos = idx - start
        if pos < half_point:
            h1_total += 1; h1_hits += hit
        else:
            h2_total += 1; h2_hits += hit

    if total == 0:
        return None

    rate = hits / total * 100
    edge = rate - baseline
    se = (baseline * (100 - baseline) / 100 / total) ** 0.5
    z = edge / se
    p = 1 - norm.cdf(z)
    h1_edge = (h1_hits / h1_total * 100 - baseline) if h1_total > 0 else 0
    h2_edge = (h2_hits / h2_total * 100 - baseline) if h2_total > 0 else 0

    return {
        'rate': rate, 'baseline': baseline, 'edge': edge,
        'z': z, 'p': p, 'hits': hits, 'total': total,
        'h1_edge': h1_edge, 'h2_edge': h2_edge,
    }


def permutation_test_subset(all_draws, bet_indices, periods, n_perm=300, min_hist=200):
    """Permutation test: shuffle draw numbers, re-run backtest."""
    real = run_subset_backtest(all_draws, bet_indices, periods, min_hist)
    if real is None:
        return None
    real_edge = real['edge']

    rng = np.random.RandomState(SEED)
    perm_edges = []
    for _ in range(n_perm):
        shuffled = copy.deepcopy(all_draws)
        pool = [d['numbers'][:] for d in shuffled]
        perm_idx = rng.permutation(len(pool))
        for i, d in enumerate(shuffled):
            d['numbers'] = pool[perm_idx[i]]
        r = run_subset_backtest(shuffled, bet_indices, periods, min_hist)
        if r: perm_edges.append(r['edge'])

    arr = np.array(perm_edges)
    p = float(np.mean(arr >= real_edge))
    d = float((real_edge - arr.mean()) / (arr.std() + 1e-10))
    return {'real_edge': real_edge, 'perm_p': p, 'cohens_d': d,
            'shuffle_mean': arr.mean(), 'shuffle_std': arr.std()}


# ══════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════

def main():
    from itertools import combinations
    t0 = time.time()

    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"總期數: {len(all_draws)}")

    # ── Section 1: All 2-bet combinations (C(5,2)=10) ──
    print("\n" + "=" * 85)
    print("Section 1: 全部 2注子集 回測 (1500p)")
    print("=" * 85)
    print(f"{'組合':>16}  {'M3+%':>6}  {'基準%':>6}  {'Edge%':>7}  {'z':>6}  "
          f"{'p':>8}  {'H1%':>7}  {'H2%':>7}  {'穩定':>4}")
    print("-" * 85)

    two_bet_results = []
    for combo in combinations(range(5), 2):
        r = run_subset_backtest(all_draws, list(combo), 1500)
        name = '+'.join(BET_NAMES[i].split('_')[0] + BET_NAMES[i].split('_')[1][:3]
                        for i in combo)
        stable = 'Y' if r['h1_edge'] > 0 and r['h2_edge'] > 0 else 'N'
        print(f"{name:>16}  {r['rate']:6.2f}  {r['baseline']:6.2f}  {r['edge']:+7.2f}  "
              f"{r['z']:6.2f}  {r['p']:8.5f}  {r['h1_edge']:+7.2f}  {r['h2_edge']:+7.2f}  {stable:>4}")
        two_bet_results.append((combo, name, r))

    # Sort by edge
    two_bet_results.sort(key=lambda x: -x[2]['edge'])
    best_2 = two_bet_results[0]
    print(f"\n最優 2注: {best_2[1]} (Edge={best_2[2]['edge']:+.2f}%)")

    # ── Section 2: All 3-bet combinations (C(5,3)=10) ──
    print("\n" + "=" * 85)
    print("Section 2: 全部 3注子集 回測 (1500p)")
    print("=" * 85)
    print(f"{'組合':>22}  {'M3+%':>6}  {'基準%':>6}  {'Edge%':>7}  {'z':>6}  "
          f"{'p':>8}  {'H1%':>7}  {'H2%':>7}  {'穩定':>4}")
    print("-" * 85)

    three_bet_results = []
    for combo in combinations(range(5), 3):
        r = run_subset_backtest(all_draws, list(combo), 1500)
        name = '+'.join(BET_NAMES[i].split('_')[1][:4] for i in combo)
        stable = 'Y' if r['h1_edge'] > 0 and r['h2_edge'] > 0 else 'N'
        print(f"{name:>22}  {r['rate']:6.2f}  {r['baseline']:6.2f}  {r['edge']:+7.2f}  "
              f"{r['z']:6.2f}  {r['p']:8.5f}  {r['h1_edge']:+7.2f}  {r['h2_edge']:+7.2f}  {stable:>4}")
        three_bet_results.append((combo, name, r))

    three_bet_results.sort(key=lambda x: -x[2]['edge'])
    best_3 = three_bet_results[0]
    print(f"\n最優 3注: {best_3[1]} (Edge={best_3[2]['edge']:+.2f}%)")

    # ── Section 3: Multi-window validation for top candidates ──
    print("\n" + "=" * 85)
    print("Section 3: 最優候選三窗口驗證 (150/500/1500p)")
    print("=" * 85)

    top_candidates = [
        best_2,
        two_bet_results[1] if len(two_bet_results) > 1 else best_2,
        best_3,
        three_bet_results[1] if len(three_bet_results) > 1 else best_3,
    ]

    # Deduplicate
    seen = set()
    unique_candidates = []
    for c in top_candidates:
        key = str(c[0])
        if key not in seen:
            seen.add(key)
            unique_candidates.append(c)

    print(f"\n{'組合':>22}  {'窗口':>6}  {'M3+%':>6}  {'基準%':>6}  {'Edge%':>7}  "
          f"{'z':>6}  {'H1%':>7}  {'H2%':>7}")
    print("-" * 78)

    for combo, name, _ in unique_candidates:
        for periods in [150, 500, 1500]:
            r = run_subset_backtest(all_draws, list(combo), periods)
            print(f"{name:>22}  {periods:6d}  {r['rate']:6.2f}  {r['baseline']:6.2f}  "
                  f"{r['edge']:+7.2f}  {r['z']:6.2f}  {r['h1_edge']:+7.2f}  {r['h2_edge']:+7.2f}")
        print()

    # ── Section 4: Permutation Test for best 2-bet and best 3-bet ──
    print("=" * 85)
    print("Section 4: 排列檢定 (500p, n=300)")
    print("=" * 85)

    for label, (combo, name, _) in [('最優2注', best_2), ('最優3注', best_3)]:
        print(f"\n[{label}: {name}]")
        print(f"計算中...", end="", flush=True)
        perm = permutation_test_subset(all_draws, list(combo), 500, n_perm=300)
        print(f" 完成")
        print(f"  Real Edge:    {perm['real_edge']:+.2f}%")
        print(f"  Shuffle mean: {perm['shuffle_mean']:+.4f}% ± {perm['shuffle_std']:.4f}%")
        print(f"  Perm p:       {perm['perm_p']:.4f}")
        print(f"  Cohen's d:    {perm['cohens_d']:.3f}")
        bonf = 0.05 / 10  # 10 combinations tested
        if perm['perm_p'] < bonf:
            print(f"  Bonferroni:   ✅ 通過 (p={perm['perm_p']:.4f} < {bonf:.4f})")
        else:
            print(f"  Bonferroni:   ❌ 未通過 (p={perm['perm_p']:.4f} >= {bonf:.4f})")

    # ── Section 5: Generate actual prediction matrix ──
    print("\n" + "=" * 85)
    print("Section 5: 可直接使用的預測矩陣（下一期）")
    print("=" * 85)

    history = all_draws[:]
    all_bets = generate_all_5_bets(history)
    last_draw = all_draws[-1]
    print(f"\n基準期: {last_draw.get('draw', '?')} ({last_draw.get('date', '?')})")

    print(f"\n{'注':>4}  {'信號':>12}  {'號碼':>30}  {'唯一':>4}")
    print("-" * 58)
    for i, bet in enumerate(all_bets):
        print(f"B{i+1:>3}  {BET_NAMES[i]:>12}  {str(bet):>30}  {6:4d}")

    unique_all = len(set(n for b in all_bets for n in b))
    print(f"\n5注總覆蓋: {unique_all}/49 號碼 ({unique_all/49*100:.1f}%)")

    # Best 2-bet matrix
    b2_idx = list(best_2[0])
    b2_bets = [all_bets[i] for i in b2_idx]
    b2_unique = len(set(n for b in b2_bets for n in b))
    print(f"\n┌── 最優 2注矩陣: {best_2[1]} ──┐")
    for i, idx in enumerate(b2_idx):
        print(f"│  注{i+1}: {BET_NAMES[idx]:>12} → {all_bets[idx]}  │")
    print(f"│  覆蓋: {b2_unique}/49 ({b2_unique/49*100:.1f}%)  Edge: {best_2[2]['edge']:+.2f}%     │")
    print(f"└────────────────────────────────────────────┘")

    # Best 3-bet matrix
    b3_idx = list(best_3[0])
    b3_bets = [all_bets[i] for i in b3_idx]
    b3_unique = len(set(n for b in b3_bets for n in b))
    print(f"\n┌── 最優 3注矩陣: {best_3[1]} ──┐")
    for i, idx in enumerate(b3_idx):
        print(f"│  注{i+1}: {BET_NAMES[idx]:>12} → {all_bets[idx]}  │")
    print(f"│  覆蓋: {b3_unique}/49 ({b3_unique/49*100:.1f}%)  Edge: {best_3[2]['edge']:+.2f}%     │")
    print(f"└────────────────────────────────────────────┘")

    # ── Section 6: Cost-Benefit ──
    print("\n" + "=" * 85)
    print("Section 6: 成本效益分析")
    print("=" * 85)

    COST = 100  # per bet
    PRIZES = {'M3': 400, 'M4': 1000, 'M5': 20000, 'M6': 500000}
    DRAWS_PER_YEAR = 104

    configs = [
        ('2注最優', 2, best_2[2]['rate']),
        ('3注最優', 3, best_3[2]['rate']),
        ('3注TS3', 3, None),  # will look up
        ('5注TS3MFO', 5, None),
    ]

    # Get 5-bet and TS3 rates
    r_5bet = run_subset_backtest(all_draws, [0,1,2,3,4], 1500)
    r_ts3 = run_subset_backtest(all_draws, [0,1,2], 1500)

    print(f"\n{'策略':>12}  {'注數':>4}  {'每期成本':>8}  {'年成本':>8}  {'M3+%':>6}  "
          f"{'年M3收益':>8}  {'年淨EV':>10}  {'ROI':>8}")
    print("-" * 80)

    for n_bets, label, rate in [
        (2, '2注最優', best_2[2]['rate']),
        (3, '3注最優', best_3[2]['rate']),
        (3, '3注TS3', r_ts3['rate']),
        (5, '5注TS3MFO', r_5bet['rate']),
    ]:
        cost_per_draw = n_bets * COST
        annual_cost = cost_per_draw * DRAWS_PER_YEAR
        m3_revenue = rate / 100 * DRAWS_PER_YEAR * PRIZES['M3']
        # Rough M4 estimate: ~10% of M3 rate
        m4_revenue = rate / 100 * 0.08 * DRAWS_PER_YEAR * PRIZES['M4']
        total_revenue = m3_revenue + m4_revenue
        net_ev = total_revenue - annual_cost
        roi = net_ev / annual_cost * 100
        print(f"{label:>12}  {n_bets:4d}  {cost_per_draw:8,}  {annual_cost:8,}  {rate:6.2f}  "
              f"{total_revenue:8,.0f}  {net_ev:+10,.0f}  {roi:+7.1f}%")

    elapsed = time.time() - t0
    print(f"\n總耗時: {elapsed:.1f}s")


if __name__ == '__main__':
    main()
