#!/usr/bin/env python3
"""
大樂透 Triple Strike + Markov 正交注4 回測
=============================================
在已驗證的 Triple Strike 3注基礎上，新增 Markov 轉移矩陣正交注。
正交注僅從 TS3 未選號碼中選擇 Markov 排名最高的6個。

驗證方法:
  1. 三階窗口驗證 (150/500/1500)
  2. 10 seed 穩定性 (Markov 是確定性策略，結果應完全一致)
  3. 前半/後半衰減分析
  4. Markov 邊際貢獻 vs 隨機第4注

Mandatory Rules:
  1. 4-bet baseline: P(4) = 1 - (1 - 0.0186)^4 = 7.23%
  2. Strict temporal isolation: history = draws[:idx]
  3. Fixed seed: 42
  4. Big Lotto P_single(M3+) = 1.86%

Usage:
    python3 tools/backtest_biglotto_markov_4bet.py
    python3 tools/backtest_biglotto_markov_4bet.py --seeds 10
"""
import os
import sys
import time
import json
import numpy as np
from collections import Counter
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
SEED = 42
_SUM_WIN = 300   # sum 統計動態窗口

P_SINGLE = 0.0186
BASELINES = {
    1: P_SINGLE,
    2: 1 - (1 - P_SINGLE) ** 2,
    3: 1 - (1 - P_SINGLE) ** 3,
    4: 1 - (1 - P_SINGLE) ** 4,
}

WINDOWS = [150, 500, 1500]
MIN_HISTORY_BUFFER = 150


# ============================================================
# Triple Strike Components (synced with predict_biglotto_triple_strike.py v2)
# ============================================================
def _sum_target(history):
    """
    根據前期 sum 層級計算下期目標 sum 範圍 (均值回歸, Lift=1.495x)。
    LOW  → [mean, mean+σ]
    HIGH → [mean-σ, mean]
    MID  → [mean-0.5σ, mean+0.5σ]
    """
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
    """注1: Fourier Rhythm — FFT 週期分析"""
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
    """
    注2: Sum-Constrained Cold Numbers (v2, synced with Triple Strike v2)
    ======================================================================
    1. 取近 window 期頻率最低的 pool_size 個冷號候選池
    2. 從候選池枚舉 C(pool_size, 6) 組合，
       選出 sum 最接近「前期結構預測目標範圍」中點的組合
    驗證: 1500期 Edge +1.46% (vs 原版 +1.06%), ROBUST, 三窗口全正
    """
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
    """注3: Tail Balance — 尾數平衡覆蓋"""
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
        if not added:
            break

    if len(selected) < 6:
        remaining = [n for n in range(1, MAX_NUM + 1)
                     if n not in selected and n not in exclude]
        remaining.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(remaining[:6 - len(selected)])

    return sorted(selected[:6])


def generate_triple_strike(history):
    """生成 Triple Strike 3注 (exact replica)"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


# ============================================================
# Markov Orthogonal 4th Bet
# ============================================================
def markov_orthogonal_bet(history, exclude=None, markov_window=100):
    """
    Markov 正交注4: 基於轉移矩陣的條件機率預測。

    原理:
      1. 建立一階 Markov 轉移矩陣 (前期號碼 → 本期號碼)
      2. 根據前一期6個號碼，計算每個號碼的轉移分數
      3. 從 exclude 集合外選擇分數最高的6個號碼

    確定性策略 (無隨機成分)。

    Args:
        history: 歷史開獎記錄 (up to but not including target draw)
        exclude: 已被其他注選擇的號碼集合
        markov_window: 轉移矩陣計算窗口 (default: 100)

    Returns:
        sorted list of 6 numbers
    """
    exclude = exclude or set()

    # Use windowed history for transition matrix
    window = min(markov_window, len(history))
    recent = history[-window:]

    # Build transition count matrix
    transitions = Counter()
    for i in range(len(recent) - 1):
        prev_nums = recent[i]['numbers']
        next_nums = recent[i + 1]['numbers']
        for p in prev_nums:
            for n in next_nums:
                transitions[(p, n)] += 1

    if len(history) < 2:
        # Fallback: just pick first available numbers
        candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
        return sorted(candidates[:PICK])

    # Score each number based on transition from last draw
    last_draw_nums = history[-1]['numbers']
    scores = Counter()
    for prev_num in last_draw_nums:
        for n in range(1, MAX_NUM + 1):
            scores[n] += transitions.get((prev_num, n), 0)

    # Select top-6 from candidates not in exclude
    candidates = [(n, scores[n]) for n in range(1, MAX_NUM + 1) if n not in exclude]
    candidates.sort(key=lambda x: -x[1])

    selected = [n for n, _ in candidates[:PICK]]

    # Ensure we have 6 numbers
    if len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1)
                     if n not in exclude and n not in selected]
        selected.extend(remaining[:PICK - len(selected)])

    return sorted(selected[:PICK])


def generate_ts3_markov4(history, markov_window=100):
    """生成 Triple Strike 3注 + Markov 正交注4"""
    # First 3 bets: exact Triple Strike
    ts3_bets = generate_triple_strike(history)

    # Collect all used numbers
    ts3_used = set()
    for bet in ts3_bets:
        ts3_used.update(bet)

    # 4th bet: Markov orthogonal (only from unused numbers)
    bet4 = markov_orthogonal_bet(history, exclude=ts3_used,
                                  markov_window=markov_window)

    return ts3_bets + [bet4]


# ============================================================
# Backtest Engine
# ============================================================
def run_backtest(draws, strategy_func, n_bets, n_periods, seed=42, label=""):
    """
    Run backtest with strict temporal isolation.

    Returns dict with detailed results.
    """
    np.random.seed(seed)

    baseline = BASELINES.get(n_bets, BASELINES[1])

    start_idx = len(draws) - n_periods
    if start_idx < MIN_HISTORY_BUFFER:
        actual_periods = len(draws) - MIN_HISTORY_BUFFER
        start_idx = MIN_HISTORY_BUFFER

    hits = {3: 0, 4: 0, 5: 0, 6: 0}
    total = 0
    first_half_hits = 0
    second_half_hits = 0

    # Track per-bet contribution
    bet_solo_hits = [0] * n_bets
    marginal_hits = [0] * n_bets  # Only this bet hit, others didn't

    half_point = start_idx + (len(draws) - start_idx) // 2

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]  # STRICT ISOLATION

        try:
            bets = strategy_func(history)
        except Exception as e:
            total += 1
            continue

        best_match = 0
        any_hit = False
        hit_bets = []

        for b_idx, b in enumerate(bets):
            match_count = len(set(b) & target)
            if match_count > best_match:
                best_match = match_count
            if match_count >= 3:
                bet_solo_hits[b_idx] += 1
                hit_bets.append(b_idx)
                any_hit = True

        if best_match >= 3:
            hits[min(best_match, 6)] += 1

        # Track marginal contribution
        if any_hit:
            for b_idx in hit_bets:
                # Check if this was the ONLY bet that hit
                others_hit = any(bi != b_idx for bi in hit_bets)
                if not others_hit:
                    marginal_hits[b_idx] += 1

        if any_hit and i < half_point:
            first_half_hits += 1
        elif any_hit and i >= half_point:
            second_half_hits += 1

        total += 1

    m3_plus = sum(hits.values())
    win_rate = m3_plus / total if total > 0 else 0
    edge = win_rate - baseline

    half_n = half_point - start_idx
    second_half_n = total - half_n

    return {
        'total': total,
        'hits_m3': hits[3],
        'hits_m4': hits[4],
        'hits_m5': hits[5],
        'hits_m6': hits[6],
        'm3_plus': m3_plus,
        'win_rate': win_rate,
        'baseline': baseline,
        'edge': edge,
        'first_half': (first_half_hits, half_n),
        'second_half': (second_half_hits, second_half_n),
        'bet_solo_hits': bet_solo_hits,
        'marginal_hits': marginal_hits,
    }


# ============================================================
# Main
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', type=int, default=1,
                        help='Number of seeds for stability test (default: 1)')
    parser.add_argument('--markov-window', type=int, default=100,
                        help='Markov transition matrix window (default: 100)')
    parser.add_argument('--windows', type=str, default='150,500,1500',
                        help='Test windows (default: 150,500,1500)')
    args = parser.parse_args()

    windows = [int(x) for x in args.windows.split(',')]
    markov_window = args.markov_window
    n_seeds = args.seeds

    # Load data
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = db.get_all_draws('BIG_LOTTO')
    draws = sorted(draws, key=lambda x: (x['date'], x['draw']))

    print("=" * 80)
    print("  大樂透 Triple Strike + Markov 正交注4 回測")
    print("=" * 80)
    print(f"  Database: {len(draws)} draws")
    print(f"  Date range: {draws[0]['date']} ~ {draws[-1]['date']}")
    print(f"  Markov window: {markov_window}")
    print(f"  Test windows: {windows}")
    print(f"  Seeds: {n_seeds}")
    print(f"  Baselines:")
    for nb in [3, 4]:
        print(f"    {nb}-bet: {BASELINES[nb]*100:.2f}%")
    print("=" * 80)

    # ====== Phase 1: Triple Strike 3注 baseline ======
    print("\n" + "=" * 80)
    print("  Phase 1: Triple Strike 3注 (基準)")
    print("=" * 80)

    ts3_results = {}
    for w in windows:
        t0 = time.time()
        r = run_backtest(draws, generate_triple_strike, 3, w, seed=SEED)
        elapsed = time.time() - t0
        ts3_results[w] = r
        wr = r['win_rate'] * 100
        bl = r['baseline'] * 100
        ed = r['edge'] * 100
        icon = "PASS" if ed > 0 else "FAIL"
        print(f"  {w:>4}期: {r['m3_plus']}/{r['total']} = {wr:.2f}% "
              f"(base {bl:.2f}%, edge {ed:+.2f}%) [{icon}] [{elapsed:.1f}s]")

    # ====== Phase 2: TS3 + Markov 4注 ======
    print("\n" + "=" * 80)
    print("  Phase 2: Triple Strike 3注 + Markov 正交注4 (4注)")
    print("=" * 80)

    ts4_func = lambda h: generate_ts3_markov4(h, markov_window=markov_window)

    ts4_results = {}
    for w in windows:
        t0 = time.time()
        r = run_backtest(draws, ts4_func, 4, w, seed=SEED)
        elapsed = time.time() - t0
        ts4_results[w] = r
        wr = r['win_rate'] * 100
        bl = r['baseline'] * 100
        ed = r['edge'] * 100
        icon = "PASS" if ed > 0 else "FAIL"

        # Half analysis
        fh, fn = r['first_half']
        sh, sn = r['second_half']
        fh_rate = fh / fn * 100 if fn > 0 else 0
        sh_rate = sh / sn * 100 if sn > 0 else 0

        print(f"  {w:>4}期: {r['m3_plus']}/{r['total']} = {wr:.2f}% "
              f"(base {bl:.2f}%, edge {ed:+.2f}%) [{icon}] [{elapsed:.1f}s]")
        print(f"         前半: {fh}/{fn} = {fh_rate:.2f}%, 後半: {sh}/{sn} = {sh_rate:.2f}%")

    # ====== Phase 3: Marginal Analysis ======
    print("\n" + "=" * 80)
    print("  Phase 3: Markov 注4 邊際貢獻分析")
    print("=" * 80)

    for w in windows:
        r4 = ts4_results[w]
        r3 = ts3_results[w]

        marginal_m3 = r4['m3_plus'] - r3['m3_plus']
        marginal_rate = marginal_m3 / r4['total'] * 100
        random_marginal = P_SINGLE * 100
        marginal_edge = marginal_rate - random_marginal

        print(f"\n  {w}期:")
        print(f"    TS3 M3+:     {r3['m3_plus']}")
        print(f"    TS3+M4 M3+:  {r4['m3_plus']}")
        print(f"    Markov 邊際:  {marginal_m3} hits ({marginal_rate:.2f}%)")
        print(f"    隨機第4注期望: {random_marginal:.2f}%")
        print(f"    邊際 Edge:    {marginal_edge:+.2f}%")

        # Per-bet contribution
        if r4['bet_solo_hits']:
            bet_labels = ['Fourier', 'Cold', 'Tail', 'Markov']
            print(f"    各注 M3+ hits: ", end="")
            for bi, bh in enumerate(r4['bet_solo_hits']):
                label = bet_labels[bi] if bi < len(bet_labels) else f"Bet{bi+1}"
                print(f"{label}={bh} ", end="")
            print()

        # Marginal-only hits (Markov caught what TS3 missed)
        if r4['marginal_hits']:
            markov_exclusive = r4['marginal_hits'][3] if len(r4['marginal_hits']) > 3 else 0
            print(f"    Markov 獨佔命中: {markov_exclusive} "
                  f"(TS3全漏, 僅Markov命中)")

    # ====== Phase 4: Stability Decay Analysis ======
    print("\n" + "=" * 80)
    print("  Phase 4: 穩定性與衰減分析")
    print("=" * 80)

    if 150 in ts4_results and 1500 in ts4_results:
        e150 = ts4_results[150]['edge'] * 100
        e500 = ts4_results.get(500, {}).get('edge', 0) * 100
        e1500 = ts4_results[1500]['edge'] * 100

        decay = e150 - e1500
        if e150 <= 0 and e1500 > 0:
            stability = "LATE_BLOOMER"
        elif e150 > 0 and e1500 <= 0:
            stability = "SHORT_MOMENTUM"
        elif e1500 <= 0:
            stability = "INEFFECTIVE"
        elif abs(decay) < 0.5 and e1500 > 0:
            stability = "ROBUST"
        else:
            stability = "MODERATE_DECAY"

        print(f"  TS3+Markov 4注:")
        print(f"    150期 Edge:  {e150:+.2f}%")
        print(f"    500期 Edge:  {e500:+.2f}%")
        print(f"    1500期 Edge: {e1500:+.2f}%")
        print(f"    衰減率: {decay:+.2f}%")
        print(f"    穩定性: {stability}")

        # Z-score for significance
        n = ts4_results[1500]['total']
        p_obs = ts4_results[1500]['win_rate']
        p_base = BASELINES[4]
        z = (p_obs - p_base) / np.sqrt(p_base * (1 - p_base) / n) if n > 0 else 0
        print(f"    1500期 z-score: {z:.2f} (p<0.05 需 z>1.645)")

    # ====== Phase 5: Multi-seed stability (if requested) ======
    if n_seeds > 1:
        print("\n" + "=" * 80)
        print(f"  Phase 5: {n_seeds}-seed 穩定性驗證 (1500期)")
        print("=" * 80)

        seed_results = []
        for seed in range(n_seeds):
            r = run_backtest(draws, ts4_func, 4, 1500, seed=seed)
            edge = r['edge'] * 100
            seed_results.append(edge)
            print(f"  seed={seed}: M3+={r['m3_plus']}/{r['total']} edge={edge:+.2f}%")

        mean_edge = np.mean(seed_results)
        std_edge = np.std(seed_results)
        min_edge = min(seed_results)
        max_edge = max(seed_results)

        print(f"\n  Mean Edge: {mean_edge:+.2f}%")
        print(f"  Std:  {std_edge:.2f}%")
        print(f"  Range: [{min_edge:+.2f}%, {max_edge:+.2f}%]")
        print(f"  全正: {'YES' if min_edge > 0 else 'NO'}")

        if std_edge < 0.01:
            print(f"  確定性驗證: PASS (std≈0, 無隨機成分)")
        else:
            print(f"  確定性驗證: FAIL (有隨機成分)")

    # ====== Phase 6: Markov Window Sensitivity ======
    print("\n" + "=" * 80)
    print("  Phase 6: Markov Window 敏感度分析 (1500期)")
    print("=" * 80)

    for mw in [30, 50, 100, 200, 500]:
        ts4_mw = lambda h, w=mw: generate_ts3_markov4(h, markov_window=w)
        t0 = time.time()
        r = run_backtest(draws, ts4_mw, 4, 1500, seed=SEED)
        elapsed = time.time() - t0
        ed = r['edge'] * 100
        marginal = (r['m3_plus'] - ts3_results[1500]['m3_plus'])
        icon = "PASS" if ed > 0 else "FAIL"
        print(f"  window={mw:>3}: M3+={r['m3_plus']}/{r['total']} "
              f"edge={ed:+.2f}% marginal={marginal:+d} [{icon}] [{elapsed:.1f}s]")

    # ====== Final Summary ======
    print("\n" + "=" * 80)
    print("  FINAL SUMMARY")
    print("=" * 80)

    print("\n┌──────────┬─────────────────┬─────────────────┬─────────────┐")
    print("│ 窗口      │ TS3 (3注)       │ TS3+Markov (4注) │ Markov邊際  │")
    print("├──────────┼─────────────────┼─────────────────┼─────────────┤")

    for w in windows:
        r3 = ts3_results[w]
        r4 = ts4_results[w]
        e3 = r3['edge'] * 100
        e4 = r4['edge'] * 100
        marginal = r4['m3_plus'] - r3['m3_plus']
        m_rate = marginal / r4['total'] * 100
        m_edge = m_rate - P_SINGLE * 100
        print(f"│ {w:>4}期    │ {e3:+5.2f}% ({r3['m3_plus']:>3}hits) │ {e4:+5.2f}% ({r4['m3_plus']:>3}hits) │ {m_edge:+5.2f}% ({marginal:>2}h) │")

    print("└──────────┴─────────────────┴─────────────────┴─────────────┘")

    # Decision
    e1500_4 = ts4_results[1500]['edge'] * 100
    e1500_3 = ts3_results[1500]['edge'] * 100
    marginal_1500 = (ts4_results[1500]['m3_plus'] - ts3_results[1500]['m3_plus'])
    marginal_edge_1500 = marginal_1500 / ts4_results[1500]['total'] * 100 - P_SINGLE * 100

    print(f"\n  決策判定:")
    print(f"  - TS3+Markov 4注 1500期 Edge: {e1500_4:+.2f}%", end="")
    if e1500_4 > 0:
        print(" → 全局正邊際")
    else:
        print(" → 全局負邊際 (不採納)")

    print(f"  - Markov 邊際 Edge: {marginal_edge_1500:+.2f}%", end="")
    if marginal_edge_1500 > 0:
        print(" → 邊際正貢獻 (優於隨機第4注)")
    else:
        print(" → 邊際無貢獻 (不優於隨機)")

    print(f"  - 原 TS3 不受影響: Edge {e1500_3:+.2f}% (注1-3 品質守護)")

    if e1500_4 > 0 and marginal_edge_1500 > 0:
        print(f"\n  ★ 結論: 建議採納 Markov 正交注4")
    elif e1500_4 > 0 and marginal_edge_1500 <= 0:
        print(f"\n  ⚠ 結論: 全局正但邊際不顯著, 需進一步驗證")
    else:
        print(f"\n  ✗ 結論: 不採納")


if __name__ == '__main__':
    main()
