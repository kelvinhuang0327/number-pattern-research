#!/usr/bin/env python3
"""
大樂透 Cold Pool / Z3條件 / 特別號→主球 三合一回測
=====================================================
P0a: Cold pool=12 vs pool=15 (Sum-Constrained)
P0b: Z3=0 後冷號域限縮至 Z3(33~49)
P1a: 特別號→主球 條件 Lift 統計

三窗口驗證: 150/500/1500
McNemar vs 原始版本

Usage:
    python3 tools/backtest_cold_zone_special.py
"""
import os
import sys
import time
import numpy as np
from collections import Counter
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
    1: P_SINGLE,
    2: 1 - (1 - P_SINGLE) ** 2,
    3: 1 - (1 - P_SINGLE) ** 3,
    5: 1 - (1 - P_SINGLE) ** 5,
}

WINDOWS = [150, 500, 1500]
MIN_BUF = 150


# ============================================================
# Shared Components
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


def fourier_rhythm_bet(history, window=500):
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


def cold_numbers_bet_z3_aware(history, window=100, exclude=None,
                               pool_size=12, use_sum_constraint=True):
    """
    Z3=0 後限縮冷號域至 Z3(33~49):
    如果上一期 Z3=0，則只從 Z3 區間(33-49)選冷號
    否則使用標準邏輯
    """
    exclude = exclude or set()
    prev_nums = history[-1]['numbers']
    prev_z3 = sum(1 for n in prev_nums if n > 32)

    if prev_z3 == 0:
        # Z3=0 條件：只從 Z3 區間(33~49) 選冷號
        recent = history[-window:] if len(history) >= window else history
        all_nums = [n for d in recent for n in d['numbers']]
        freq = Counter(all_nums)
        z3_candidates = [n for n in range(33, MAX_NUM + 1) if n not in exclude]
        z3_sorted = sorted(z3_candidates, key=lambda x: freq.get(x, 0))

        if use_sum_constraint and len(history) >= 2:
            pool = z3_sorted[:min(pool_size, len(z3_sorted))]
            if len(pool) >= 6:
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
                if best_combo:
                    return sorted(best_combo)

            return sorted(z3_sorted[:6])
        else:
            return sorted(z3_sorted[:6])
    else:
        return cold_numbers_bet(history, window, exclude, pool_size, use_sum_constraint)


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


# ============================================================
# Strategy Variants
# ============================================================
def ts3_pool12(history):
    """原始 TS3 (pool=12) — 基準"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1), pool_size=12)
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


def ts3_pool15(history):
    """TS3 with Cold pool=15"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1), pool_size=15)
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


def ts3_pool18(history):
    """TS3 with Cold pool=18"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1), pool_size=18)
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


def ts3_z3_aware(history):
    """TS3 with Z3-aware Cold (Z3=0 後限縮至Z3)"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet_z3_aware(history, exclude=set(bet1), pool_size=12)
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


def ts3_z3_aware_pool15(history):
    """TS3 with Z3-aware Cold pool=15"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet_z3_aware(history, exclude=set(bet1), pool_size=15)
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


# ============================================================
# Backtest Engine
# ============================================================
def run_bt(draws, func, n_bets, n_periods, label=""):
    np.random.seed(SEED)
    baseline = BASELINES.get(n_bets, BASELINES[3])
    start_idx = max(len(draws) - n_periods, MIN_BUF)
    hits, total = 0, 0

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]
        try:
            bets = func(history)
        except Exception:
            total += 1
            continue
        best = max((len(set(b) & target) for b in bets), default=0)
        if best >= 3:
            hits += 1
        total += 1

    if total == 0:
        return None
    rate = hits / total
    edge = rate - baseline
    z = edge / np.sqrt(baseline * (1 - baseline) / total)
    p = 2 * (1 - scipy_norm.cdf(abs(z)))
    return {
        'label': label, 'total': total, 'hits': hits,
        'rate': rate, 'baseline': baseline,
        'edge_pct': edge * 100, 'z': z, 'p': p
    }


def mcnemar(draws, func_a, func_b, n_periods):
    start_idx = max(len(draws) - n_periods, MIN_BUF)
    b_wins, a_wins = 0, 0
    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        h = draws[:i]
        try:
            hit_a = any(len(set(b) & target) >= 3 for b in func_a(h))
            hit_b = any(len(set(b) & target) >= 3 for b in func_b(h))
        except Exception:
            continue
        if hit_b and not hit_a:
            b_wins += 1
        elif hit_a and not hit_b:
            a_wins += 1
    td = a_wins + b_wins
    if td == 0:
        return 0, 1.0, a_wins, b_wins
    from scipy.stats import chi2 as chi2_dist
    chi2 = (abs(a_wins - b_wins) - 1) ** 2 / td
    p = 1 - chi2_dist.cdf(chi2, df=1)
    return chi2, p, a_wins, b_wins


def pr(r):
    if not r:
        return
    sig = "***" if r['p'] < 0.01 else ("**" if r['p'] < 0.05 else ("*" if r['p'] < 0.10 else ""))
    print(f"  {r['label']:<42s} {r['hits']:4d}/{r['total']:5d} "
          f"= {r['rate']:.4f}  bl={r['baseline']:.4f}  "
          f"Edge={r['edge_pct']:+.2f}%  z={r['z']:+.2f}{sig}")


# ============================================================
# P1a: 特別號→主球 統計分析
# ============================================================
def analyze_special_to_main(draws):
    """分析特別號在下期轉為主球的 Lift"""
    print(f"\n{'='*70}")
    print(f"  P1a: 特別號→主球 轉換 Lift 分析")
    print(f"{'='*70}")

    total = 0
    sp_to_main = 0
    sp_to_main_cold = 0  # 特別號是冷的情況
    sp_cold_total = 0

    for i in range(1, len(draws)):
        sp = draws[i-1].get('special', 0)
        if not sp or sp == 0:
            continue
        target = set(draws[i]['numbers'])
        total += 1
        if sp in target:
            sp_to_main += 1

        # 條件 Lift: 特別號是否是冷號(近50期頻率低)
        if i >= 50:
            recent = draws[max(0, i-50):i]
            freq = Counter(n for d in recent for n in d['numbers'])
            expected = 50 * 6 / 49
            sp_freq = freq.get(sp, 0)
            if sp_freq < expected - 1:  # 冷號
                sp_cold_total += 1
                if sp in target:
                    sp_to_main_cold += 1

    baseline_p = 6 / 49
    if total > 0:
        p_sp = sp_to_main / total
        lift = p_sp / baseline_p
        print(f"\n  全體: P(特別號→下期主球) = {sp_to_main}/{total} "
              f"= {p_sp:.4f} (基準={baseline_p:.4f}, Lift={lift:.3f}x)")

    if sp_cold_total > 0:
        p_cold = sp_to_main_cold / sp_cold_total
        lift_cold = p_cold / baseline_p
        print(f"  冷號: P(冷特別號→主球) = {sp_to_main_cold}/{sp_cold_total} "
              f"= {p_cold:.4f} (Lift={lift_cold:.3f}x)")

    # 按 gap 分層
    print(f"\n  特別號 gap 分層:")
    print(f"  {'gap區間':12s} {'次數':>6s} {'轉主球':>8s} {'條件P':>8s} {'Lift':>8s}")
    print(f"  {'-'*48}")

    gap_bins = [(0, 4), (5, 9), (10, 19), (20, 49)]
    for lo, hi in gap_bins:
        cnt, hit_cnt = 0, 0
        for i in range(1, len(draws)):
            sp = draws[i-1].get('special', 0)
            if not sp or sp == 0:
                continue
            # 計算特別號的 gap
            gap = 0
            for j in range(i-2, -1, -1):
                if sp in draws[j]['numbers'] or draws[j].get('special') == sp:
                    gap = (i - 1) - j - 1
                    break
                gap = (i - 1) - j
            if lo <= gap <= hi:
                cnt += 1
                if sp in set(draws[i]['numbers']):
                    hit_cnt += 1

        if cnt >= 10:
            cp = hit_cnt / cnt
            lift = cp / baseline_p
            marker = " ***" if lift > 1.3 else (" **" if lift > 1.1 else "")
            print(f"  gap {lo:2d}~{hi:2d}     {cnt:>6d} {hit_cnt:>8d} {cp:>7.3f}  {lift:>6.3f}x{marker}")

    return sp_to_main, total


def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"\n資料: {len(draws)} 期大樂透  seed={SEED}")
    t0 = time.time()

    # ============================================================
    # P0a: Cold pool size sweep
    # ============================================================
    print(f"\n{'='*70}")
    print(f"  P0a: Cold Pool Size 回測 (pool=12 vs 15 vs 18)")
    print(f"{'='*70}")

    strategies_a = [
        ("TS3 Cold pool=12 (基準)        ", ts3_pool12, 3),
        ("TS3 Cold pool=15               ", ts3_pool15, 3),
        ("TS3 Cold pool=18               ", ts3_pool18, 3),
    ]

    for w in WINDOWS:
        print(f"\n  --- {w}期窗口 ---")
        for label, func, nb in strategies_a:
            r = run_bt(draws, func, nb, w, label=label)
            pr(r)

    # McNemar pool=12 vs pool=15
    chi2, pval, a_wins, b_wins = mcnemar(draws, ts3_pool12, ts3_pool15, 1500)
    print(f"\n  McNemar pool=12 vs pool=15 (1500p): χ²={chi2:.2f}, p={pval:.4f}"
          f" (12獨贏={a_wins}, 15獨贏={b_wins})")

    # McNemar pool=12 vs pool=18
    chi2_18, pval_18, a18, b18 = mcnemar(draws, ts3_pool12, ts3_pool18, 1500)
    print(f"  McNemar pool=12 vs pool=18 (1500p): χ²={chi2_18:.2f}, p={pval_18:.4f}"
          f" (12獨贏={a18}, 18獨贏={b18})")

    # ============================================================
    # P0b: Z3=0 aware Cold
    # ============================================================
    print(f"\n{'='*70}")
    print(f"  P0b: Z3=0 後冷號域限縮 (Z3-Aware Cold)")
    print(f"{'='*70}")

    strategies_b = [
        ("TS3 原始 (基準)                ", ts3_pool12, 3),
        ("TS3 Z3-Aware Cold pool=12      ", ts3_z3_aware, 3),
        ("TS3 Z3-Aware Cold pool=15      ", ts3_z3_aware_pool15, 3),
    ]

    for w in WINDOWS:
        print(f"\n  --- {w}期窗口 ---")
        for label, func, nb in strategies_b:
            r = run_bt(draws, func, nb, w, label=label)
            pr(r)

    # McNemar
    chi2_z3, pval_z3, az3, bz3 = mcnemar(draws, ts3_pool12, ts3_z3_aware, 1500)
    print(f"\n  McNemar 原始 vs Z3-Aware (1500p): χ²={chi2_z3:.2f}, p={pval_z3:.4f}"
          f" (原始獨贏={az3}, Z3獨贏={bz3})")

    # ============================================================
    # P1a: 特別號→主球
    # ============================================================
    analyze_special_to_main(draws)

    # ============================================================
    # 摘要
    # ============================================================
    elapsed = time.time() - t0
    print(f"\n{'='*70}")
    print(f"  摘要")
    print(f"{'='*70}")

    print(f"\n  耗時: {elapsed:.1f}s")

    # 結論輸出
    print(f"\n  各方案 1500p Edge:")
    for label, func, nb in strategies_a + strategies_b[1:]:
        r = run_bt(draws, func, nb, 1500, label=label)
        if r:
            verdict = "✓" if r['edge_pct'] > run_bt(draws, ts3_pool12, 3, 1500)['edge_pct'] else "≈/✗"
            print(f"  {r['label']:<42s} {r['edge_pct']:+.2f}%  z={r['z']:+.2f}  {verdict}")


if __name__ == "__main__":
    main()
