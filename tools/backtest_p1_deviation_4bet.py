#!/usr/bin/env python3
"""
大樂透 P1+偏差互補 4-bet 互補組合 回測
=========================================
動機：
  McNemar 矩陣顯示 P1（鄰號+冷號）vs 偏差互補 互補率極高：
  P1獨贏61期, 偏差互補獨贏60期 (1500期中)
  → 若兩策略命中的期數幾乎不重疊，合併4注的 M3+ 率可能接近「疊加」

策略結構：
  注1: P1 Neighbor  (上期 ±1 鄰域 → Fourier+Markov 排名 Top-6)
  注2: P1 Cold      (排除注1 → Sum-Constrained 冷號 Top-6)
  注3: DevComp Hot  (排除注1+2 → 近50期偏差互補 Hot Top-6)
  注4: DevComp Cold (排除注1+2+3 → 近50期偏差互補 Cold Top-6)

比較基準：
  - TS3+Markov 4注 (已驗證 1500p Edge +1.70%)
  - P1 2注 獨立 (已驗證 1500p Edge +1.05%)
  - 偏差互補 2注 (已驗證 1500p Edge +0.51%)

三窗口驗證: 150 / 500 / 1500 期
McNemar vs TS3+Markov 4注

Usage:
    python3 tools/backtest_p1_deviation_4bet.py
"""
import os
import sys
import time
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations as _icombs
from scipy.fft import fft, fftfreq
from scipy.stats import norm as scipy_norm

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49
PICK = 6
SEED = 42
_SUM_WIN = 300

P_SINGLE = 0.0186
BASELINES = {
    2: 1 - (1 - P_SINGLE) ** 2,
    3: 1 - (1 - P_SINGLE) ** 3,
    4: 1 - (1 - P_SINGLE) ** 4,
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


# ============================================================
# P1: Neighbor + Cold 2-bet
# ============================================================
def p1_neighbor_cold_2bet(history):
    prev_nums = history[-1]['numbers']
    # 鄰域 pool (含自身)
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


# ============================================================
# 偏差互補 2-bet (with exclude support)
# ============================================================
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


# ============================================================
# Markov Orthogonal (for TS3+Markov 4bet reference)
# ============================================================
def fourier_rhythm_bet(history, window=500):
    scores = fourier_scores_full(history, window)
    sorted_idx = sorted(range(1, MAX_NUM + 1), key=lambda n: -scores.get(n, 0))
    return sorted(sorted_idx[:6])


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
        tail_groups[t].sort(key=lambda x: -x[1])
    selected, idx_in_group = [], {t: 0 for t in range(10)}
    available = sorted([t for t in range(10) if tail_groups[t]],
                       key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0,
                       reverse=True)
    while len(selected) < 6:
        added = False
        for tail in available:
            if len(selected) >= 6:
                break
            if idx_in_group[tail] < len(tail_groups[tail]):
                num, _ = tail_groups[tail][idx_in_group[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                idx_in_group[tail] += 1
        if not added:
            break
    if len(selected) < 6:
        rem = [n for n in range(1, MAX_NUM + 1) if n not in selected and n not in exclude]
        rem.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(rem[:6 - len(selected)])
    return sorted(selected[:6])


def markov_orthogonal_bet(history, exclude=None, markov_window=30):
    exclude = exclude or set()
    mk = markov_scores_func(history, markov_window)
    candidates = sorted(
        [(n, mk.get(n, 0)) for n in range(1, MAX_NUM + 1) if n not in exclude],
        key=lambda x: -x[1]
    )
    selected = [n for n, _ in candidates[:PICK]]
    if len(selected) < PICK:
        rem = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in selected]
        selected.extend(rem[:PICK - len(selected)])
    return sorted(selected[:PICK])


def ts3_markov_4bet(history):
    """已驗證 TS3+Markov 4注（基準線）"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    used3 = set(bet1) | set(bet2) | set(bet3)
    bet4 = markov_orthogonal_bet(history, exclude=used3)
    return [bet1, bet2, bet3, bet4]


# ============================================================
# P1+偏差互補 4-bet 組合
# ============================================================
def p1_deviation_4bet(history):
    """
    P1+偏差互補 4注組合:
      注1+2: P1 Neighbor+Cold
      注3+4: 偏差互補 Hot+Cold (排除注1+2)
    """
    p1_bets = p1_neighbor_cold_2bet(history)
    used_p1 = set(n for b in p1_bets for n in b)
    dev_bets = deviation_complement_2bet(history, exclude=used_p1)
    return p1_bets + dev_bets


# ============================================================
# Backtest Engine
# ============================================================
def run_backtest(draws, strategy_func, n_bets, n_periods, label=""):
    np.random.seed(SEED)
    baseline = BASELINES.get(n_bets, BASELINES[4])
    start_idx = max(len(draws) - n_periods, MIN_BUF)
    hits, total = 0, 0
    per_bet_solo = [0] * n_bets

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]
        try:
            bets = strategy_func(history)
        except Exception:
            total += 1
            continue

        best = max((len(set(b) & target) for b in bets), default=0)
        if best >= 3:
            hits += 1
        for b_idx, b in enumerate(bets):
            if len(set(b) & target) >= 3:
                per_bet_solo[b_idx] += 1
        total += 1

    if total == 0:
        return None
    rate = hits / total
    edge = rate - baseline
    z = (rate - baseline) / np.sqrt(baseline * (1 - baseline) / total)
    p = 2 * (1 - scipy_norm.cdf(abs(z)))
    return {
        'label': label, 'n_periods': n_periods, 'actual': total,
        'hits': hits, 'rate': rate, 'baseline': baseline,
        'edge_abs': edge * 100,
        'z': z, 'p': p, 'per_bet_solo': per_bet_solo
    }


def mcnemar(draws, func_a, func_b, n_periods):
    start_idx = max(len(draws) - n_periods, MIN_BUF)
    b_wins, a_wins = 0, 0
    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]
        try:
            hit_a = any(len(set(b) & target) >= 3 for b in func_a(history))
            hit_b = any(len(set(b) & target) >= 3 for b in func_b(history))
        except Exception:
            continue
        if hit_b and not hit_a:
            b_wins += 1
        elif hit_a and not hit_b:
            a_wins += 1
    total_disc = a_wins + b_wins
    if total_disc == 0:
        return 0, 1.0, a_wins, b_wins
    from scipy.stats import chi2 as chi2_dist
    chi2 = (abs(a_wins - b_wins) - 1) ** 2 / total_disc
    p = 1 - chi2_dist.cdf(chi2, df=1)
    return chi2, p, a_wins, b_wins


def pr(r):
    if not r:
        return
    sig = "***" if r['p'] < 0.01 else ("**" if r['p'] < 0.05 else ("*" if r['p'] < 0.10 else ""))
    print(f"  {r['label']:<40s} {r['hits']:4d}/{r['actual']:5d} "
          f"= {r['rate']:.4f}  基準={r['baseline']:.4f}  "
          f"Edge={r['edge_abs']:+.2f}%  z={r['z']:+.2f}{sig}")


def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"\n資料: {len(draws)} 期大樂透  seed={SEED}")
    t0 = time.time()

    strategies = [
        ("P1 鄰號+冷號 2注           ", p1_neighbor_cold_2bet, 2),
        ("偏差互補 2注               ", lambda h: deviation_complement_2bet(h), 2),
        ("P1+偏差互補 4注 (互補組合)  ", p1_deviation_4bet, 4),
        ("TS3+Markov 4注 (對照組)    ", ts3_markov_4bet, 4),
    ]

    results = {w: {} for w in WINDOWS}
    for w in WINDOWS:
        print(f"\n{'='*70}")
        print(f"  {w}期窗口")
        print(f"{'='*70}")
        for label, func, n_bets in strategies:
            r = run_backtest(draws, func, n_bets, w, label=label)
            results[w][label.strip()] = r
            pr(r)

    # McNemar: P1+偏差互補 vs TS3+Markov (1500期)
    print(f"\n{'='*70}")
    print(f"  McNemar 顯著性 (1500期)")
    print(f"{'='*70}")
    chi2, pval, a_wins, b_wins = mcnemar(draws, ts3_markov_4bet, p1_deviation_4bet, 1500)
    print(f"  P1+偏差互補 vs TS3+Markov: χ²={chi2:.2f}, p={pval:.4f}"
          f" (TS3獨贏={a_wins}, P1+Dev獨贏={b_wins})")

    # 互補性分析
    chi2_2, pval_2, a2, b2 = mcnemar(draws, p1_neighbor_cold_2bet,
                                      lambda h: deviation_complement_2bet(h), 1500)
    print(f"  P1 vs 偏差互補 (2注各自): χ²={chi2_2:.2f}, p={pval_2:.4f}"
          f" (P1獨贏={b2}, Dev獨贏={a2})")

    # 摘要
    print(f"\n{'='*70}")
    print(f"  最終摘要")
    print(f"{'='*70}")
    print(f"\n  {'策略':<30s} {'150p':>8s} {'500p':>8s} {'1500p':>8s} {'模式'}")
    print(f"  {'-'*62}")
    for label, func, n_bets in strategies:
        edges = [results[w].get(label.strip(), {}).get('edge_abs', 0) for w in WINDOWS]
        # 判斷模式
        if all(e > 0 for e in edges):
            mode = "ROBUST"
        elif edges[2] > 0 and edges[0] < 0:
            mode = "LATE_BLOOMER"
        elif edges[0] > 0 and edges[2] < 0:
            mode = "SHORT_MOMENTUM"
        else:
            mode = "MIXED"
        print(f"  {label:<30s} {edges[0]:>+7.2f}% {edges[1]:>+7.2f}% {edges[2]:>+7.2f}%  {mode}")

    print(f"\n  4注基準: {BASELINES[4]:.4f} ({BASELINES[4]*100:.2f}%)")

    # 關鍵結論
    r4_p1dev = results[1500].get('P1+偏差互補 4注 (互補組合)')
    r4_ts3 = results[1500].get('TS3+Markov 4注 (對照組)')
    if r4_p1dev and r4_ts3:
        diff = r4_p1dev['edge_abs'] - r4_ts3['edge_abs']
        print(f"\n  P1+偏差互補 vs TS3+Markov 1500p Edge差: {diff:+.2f}%")
        if diff > 0.3:
            print(f"  ✓ P1+偏差互補 組合優於 TS3+Markov，值得考慮替換 4注策略")
        elif diff < -0.3:
            print(f"  ✗ TS3+Markov 仍優，P1+偏差互補 4注不採納")
        else:
            print(f"  ≈ 兩者相當，P1+偏差互補 可作為替代方案（命中期數不同）")

    print(f"\n  耗時: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
