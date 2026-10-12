#!/usr/bin/env python3
"""
大樂透 TS3+Markov(w=30)+頻率正交 5注 回測
==========================================
策略結構:
  注1: Fourier Rhythm (FFT 週期分析, window=500)
  注2: Sum-Constrained Cold (pool=12, Sum均值回歸, window=100)   ← TS3 v2
  注3: Tail Balance (尾數平衡覆蓋, window=100)
  注4: Markov Orthogonal (轉移矩陣, window=30)                   ← 已驗證最佳 w=30
  注5: Frequency Leftover (排除注1-4後，近100期頻率最高前6)

驗證方法:
  1. 三階窗口驗證 (150/500/1500)
  2. 前半/後半衰減分析
  3. McNemar vs 4注差異顯著性
  4. 邊際貢獻分析 (注5 vs 隨機第5注)

Mandatory Rules:
  1. 5-bet baseline: P(5) = 1 - (1 - 0.0186)^5 = 9.00%
  2. Strict temporal isolation: history = draws[:idx]
  3. Fixed seed: 42
  4. Big Lotto P_single(M3+) = 1.86%

Usage:
    python3 tools/backtest_biglotto_5bet_ts3markov.py
    python3 tools/backtest_biglotto_5bet_ts3markov.py --markov-window 30
"""
import os
import sys
import time
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
    5: 1 - (1 - P_SINGLE) ** 5,
}

WINDOWS = [150, 500, 1500]
MIN_HISTORY_BUFFER = 150


# ============================================================
# Triple Strike v2 Components (synced with predict_biglotto_triple_strike.py v2)
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
    注2: Sum-Constrained Cold Numbers (v2)
    取冷號 pool=12，枚舉 C(12,6)，選 sum 最接近目標範圍的組合
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


def markov_orthogonal_bet(history, exclude=None, markov_window=30):
    """
    注4: Markov 正交 — 轉移矩陣條件機率 (w=30 最佳)
    """
    exclude = exclude or set()
    window = min(markov_window, len(history))
    recent = history[-window:]

    transitions = Counter()
    for i in range(len(recent) - 1):
        prev_nums = recent[i]['numbers']
        next_nums = recent[i + 1]['numbers']
        for p in prev_nums:
            for n in next_nums:
                transitions[(p, n)] += 1

    if len(history) < 2:
        candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
        return sorted(candidates[:PICK])

    last_draw_nums = history[-1]['numbers']
    scores = Counter()
    for prev_num in last_draw_nums:
        for n in range(1, MAX_NUM + 1):
            scores[n] += transitions.get((prev_num, n), 0)

    candidates = [(n, scores[n]) for n in range(1, MAX_NUM + 1) if n not in exclude]
    candidates.sort(key=lambda x: -x[1])
    selected = [n for n, _ in candidates[:PICK]]

    if len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1)
                     if n not in exclude and n not in selected]
        selected.extend(remaining[:PICK - len(selected)])

    return sorted(selected[:PICK])


def frequency_orthogonal_bet(history, exclude=None, window=100):
    """
    注5: 頻率正交 — 從剩餘號碼中選近N期頻率最高前6
    """
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)

    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    candidates.sort(key=lambda x: freq.get(x, 0), reverse=True)

    return sorted(candidates[:PICK])


# ============================================================
# 5-bet Strategy
# ============================================================
def generate_ts3_markov_freq_5bet(history, markov_window=30):
    """生成 TS3+Markov(w=30)+頻率正交 5注"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    used_3 = set(bet1) | set(bet2) | set(bet3)
    bet4 = markov_orthogonal_bet(history, exclude=used_3, markov_window=markov_window)
    used_4 = used_3 | set(bet4)
    bet5 = frequency_orthogonal_bet(history, exclude=used_4)
    return [bet1, bet2, bet3, bet4, bet5]


def generate_ts3_markov_4bet(history, markov_window=30):
    """生成 TS3+Markov(w=30) 4注 (用於對比)"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    used_3 = set(bet1) | set(bet2) | set(bet3)
    bet4 = markov_orthogonal_bet(history, exclude=used_3, markov_window=markov_window)
    return [bet1, bet2, bet3, bet4]


def generate_triple_strike(history):
    """生成 Triple Strike 3注 (用於對比)"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


# ============================================================
# Backtest Engine
# ============================================================
def run_backtest(draws, strategy_func, n_bets, n_periods, seed=42, label=""):
    np.random.seed(seed)
    baseline = BASELINES.get(n_bets, BASELINES[1])

    start_idx = len(draws) - n_periods
    if start_idx < MIN_HISTORY_BUFFER:
        start_idx = MIN_HISTORY_BUFFER

    hits = {3: 0, 4: 0, 5: 0, 6: 0}
    total = 0
    first_half_hits = 0
    second_half_hits = 0
    bet_solo_hits = [0] * n_bets
    marginal_hits = [0] * n_bets

    half_point = start_idx + (len(draws) - start_idx) // 2

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]  # STRICT ISOLATION

        try:
            bets = strategy_func(history)
        except Exception:
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

        if any_hit:
            for b_idx in hit_bets:
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
    parser.add_argument('--markov-window', type=int, default=30,
                        help='Markov window (default: 30, validated best)')
    parser.add_argument('--windows', type=str, default='150,500,1500',
                        help='Test windows (default: 150,500,1500)')
    args = parser.parse_args()

    windows = [int(x) for x in args.windows.split(',')]
    markov_window = args.markov_window

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = db.get_all_draws('BIG_LOTTO')
    draws = sorted(draws, key=lambda x: (x['date'], x['draw']))

    print("=" * 80)
    print("  大樂透 TS3+Markov(w=30)+頻率正交 5注 回測")
    print("=" * 80)
    print(f"  Database: {len(draws)} draws")
    print(f"  Date range: {draws[0]['date']} ~ {draws[-1]['date']}")
    print(f"  Markov window: {markov_window}")
    print(f"  Triple Strike: v2 (Sum-Constrained Cold, pool=12)")
    print(f"  Test windows: {windows}")
    print(f"  Baselines:")
    for nb in [3, 4, 5]:
        print(f"    {nb}-bet: {BASELINES[nb]*100:.2f}%")
    print("=" * 80)

    # ====== Phase 1: Triple Strike 3注 baseline ======
    print("\n[Phase 1] Triple Strike v2 3注 (基準)")
    print("-" * 60)
    ts3_results = {}
    for w in windows:
        t0 = time.time()
        r = run_backtest(draws, generate_triple_strike, 3, w, seed=SEED)
        elapsed = time.time() - t0
        ts3_results[w] = r
        ed = r['edge'] * 100
        icon = "PASS" if ed > 0 else "FAIL"
        print(f"  {w:>4}期: {r['m3_plus']}/{r['total']} = {r['win_rate']*100:.2f}% "
              f"(base {r['baseline']*100:.2f}%, edge {ed:+.2f}%) [{icon}] [{elapsed:.1f}s]")

    # ====== Phase 2: TS3+Markov 4注 ======
    print("\n[Phase 2] TS3+Markov(w=30) 4注")
    print("-" * 60)
    ts4_func = lambda h: generate_ts3_markov_4bet(h, markov_window=markov_window)
    ts4_results = {}
    for w in windows:
        t0 = time.time()
        r = run_backtest(draws, ts4_func, 4, w, seed=SEED)
        elapsed = time.time() - t0
        ts4_results[w] = r
        ed = r['edge'] * 100
        icon = "PASS" if ed > 0 else "FAIL"
        fh, fn = r['first_half']
        sh, sn = r['second_half']
        fh_rate = fh / fn * 100 if fn > 0 else 0
        sh_rate = sh / sn * 100 if sn > 0 else 0
        print(f"  {w:>4}期: {r['m3_plus']}/{r['total']} = {r['win_rate']*100:.2f}% "
              f"(base {r['baseline']*100:.2f}%, edge {ed:+.2f}%) [{icon}] [{elapsed:.1f}s]")
        print(f"         前半: {fh}/{fn} = {fh_rate:.2f}%, 後半: {sh}/{sn} = {sh_rate:.2f}%")

    # ====== Phase 3: TS3+Markov+Freq 5注 ======
    print("\n[Phase 3] TS3+Markov(w=30)+頻率正交 5注 ★")
    print("-" * 60)
    ts5_func = lambda h: generate_ts3_markov_freq_5bet(h, markov_window=markov_window)
    ts5_results = {}
    for w in windows:
        t0 = time.time()
        r = run_backtest(draws, ts5_func, 5, w, seed=SEED)
        elapsed = time.time() - t0
        ts5_results[w] = r
        ed = r['edge'] * 100
        icon = "PASS" if ed > 0 else "FAIL"
        fh, fn = r['first_half']
        sh, sn = r['second_half']
        fh_rate = fh / fn * 100 if fn > 0 else 0
        sh_rate = sh / sn * 100 if sn > 0 else 0
        print(f"  {w:>4}期: {r['m3_plus']}/{r['total']} = {r['win_rate']*100:.2f}% "
              f"(base {r['baseline']*100:.2f}%, edge {ed:+.2f}%) [{icon}] [{elapsed:.1f}s]")
        print(f"         前半: {fh}/{fn} = {fh_rate:.2f}%, 後半: {sh}/{sn} = {sh_rate:.2f}%")

    # ====== Phase 4: 邊際貢獻分析 ======
    print("\n[Phase 4] 邊際貢獻分析")
    print("-" * 60)
    for w in windows:
        r3 = ts3_results[w]
        r4 = ts4_results[w]
        r5 = ts5_results[w]

        # 注5 邊際
        marginal5 = r5['m3_plus'] - r4['m3_plus']
        m5_rate = marginal5 / r5['total'] * 100 if r5['total'] > 0 else 0
        m5_edge = m5_rate - P_SINGLE * 100

        print(f"\n  {w}期:")
        print(f"    3注 M3+: {r3['m3_plus']} ({r3['edge']*100:+.2f}%)")
        print(f"    4注 M3+: {r4['m3_plus']} ({r4['edge']*100:+.2f}%)")
        print(f"    5注 M3+: {r5['m3_plus']} ({r5['edge']*100:+.2f}%)")
        print(f"    注5邊際: +{marginal5}hits = {m5_rate:.2f}% (期望 {P_SINGLE*100:.2f}%, 邊際edge {m5_edge:+.2f}%)")

        # Per-bet hits
        if r5['bet_solo_hits']:
            bet_labels = ['Fourier', 'Cold', 'Tail', 'Markov', 'FreqOrth']
            hits_str = ', '.join(f"{bet_labels[bi]}={r5['bet_solo_hits'][bi]}"
                                  for bi in range(len(r5['bet_solo_hits'])))
            print(f"    各注命中: {hits_str}")

    # ====== Phase 5: 穩定性分析 ======
    print("\n[Phase 5] 穩定性與衰減分析")
    print("-" * 60)
    for label, results, n_bets in [("TS3 (3注)", ts3_results, 3),
                                    ("TS3+Markov (4注)", ts4_results, 4),
                                    ("TS3+Markov+Freq (5注)", ts5_results, 5)]:
        if 150 not in results or 1500 not in results:
            continue
        e150 = results[150]['edge'] * 100
        e500 = results.get(500, {}).get('edge', 0) * 100
        e1500 = results[1500]['edge'] * 100

        if e150 <= 0 and e1500 > 0:
            stability = "LATE_BLOOMER"
        elif e150 > 0 and e1500 <= 0:
            stability = "SHORT_MOMENTUM"
        elif e1500 <= 0:
            stability = "INEFFECTIVE"
        elif all(results.get(w, {}).get('edge', -1) > 0 for w in [150, 500, 1500]):
            stability = "ROBUST"
        else:
            stability = "MODERATE_DECAY"

        n = results[1500]['total']
        p_obs = results[1500]['win_rate']
        p_base = BASELINES[n_bets]
        z = (p_obs - p_base) / np.sqrt(p_base * (1 - p_base) / n) if n > 0 else 0

        print(f"\n  {label}:")
        print(f"    150p={e150:+.2f}%, 500p={e500:+.2f}%, 1500p={e1500:+.2f}%")
        print(f"    穩定性: {stability}, z={z:.2f}")

    # ====== McNemar Test: 5注 vs 4注 ======
    print("\n[Phase 6] McNemar Test: 5注 vs 4注 (1500期)")
    print("-" * 60)
    # Re-run aligned for McNemar
    w = 1500
    start_idx = max(len(draws) - w, MIN_HISTORY_BUFFER)

    n_4only = 0  # 4注命中但5注未額外提升
    n_5extra = 0  # 5注比4注多命中 (注5獨立貢獻)
    b_count = 0
    c_count = 0

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]

        try:
            bets4 = generate_ts3_markov_4bet(history, markov_window)
            bets5 = generate_ts3_markov_freq_5bet(history, markov_window)
        except Exception:
            continue

        hit4 = any(len(set(b) & target) >= 3 for b in bets4)
        hit5 = any(len(set(b) & target) >= 3 for b in bets5)

        if hit4 and not hit5:
            b_count += 1
        elif not hit4 and hit5:
            c_count += 1

    n_discordant = b_count + c_count
    if n_discordant > 0:
        chi2 = (abs(b_count - c_count) - 1) ** 2 / n_discordant
    else:
        chi2 = 0

    import math
    # p-value approximation using chi-squared with df=1
    # Using simple approximation: p ≈ exp(-chi2/2) for large chi2
    def chi2_p(x):
        # Approximation of p-value for chi-sq df=1
        if x <= 0:
            return 1.0
        # Use normal approximation: z = sqrt(2*chi2) - sqrt(2*df-1)
        z_approx = (2 * x) ** 0.5 - (2 * 1 - 1) ** 0.5
        # p = 1 - Phi(z) ≈ exp(-z^2/2) / (z * sqrt(2*pi)) for large z
        if z_approx <= 0:
            return 1.0
        # Simple erfc approximation
        t = 1 / (1 + 0.2316419 * z_approx)
        poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
        p_one = poly * math.exp(-z_approx ** 2 / 2) / (2 * math.pi) ** 0.5
        return 2 * p_one  # two-tailed

    p_val = chi2_p(chi2)
    print(f"  5注命中/4注未命中 (c): {c_count}")
    print(f"  4注命中/5注未命中 (b): {b_count}")
    print(f"  McNemar χ²={chi2:.2f}, p≈{p_val:.3f}")
    sig = "顯著 p<0.05" if p_val < 0.05 else ("邊際顯著 p<0.10" if p_val < 0.10 else "不顯著")
    print(f"  → {sig} ({'c>>b 5注顯著改善' if c_count > b_count else 'b≥c 未顯著改善'})")

    # ====== Final Summary ======
    print("\n" + "=" * 80)
    print("  FINAL SUMMARY")
    print("=" * 80)

    print("\n┌──────────┬─────────────────┬─────────────────┬─────────────────┐")
    print("│ 窗口      │ TS3 (3注)       │ TS3+Markov(4注)  │ +FreqOrth(5注)  │")
    print("├──────────┼─────────────────┼─────────────────┼─────────────────┤")

    for w in windows:
        r3 = ts3_results.get(w, {})
        r4 = ts4_results.get(w, {})
        r5 = ts5_results.get(w, {})
        e3 = r3.get('edge', 0) * 100
        e4 = r4.get('edge', 0) * 100
        e5 = r5.get('edge', 0) * 100
        print(f"│ {w:>4}期    │ {e3:+5.2f}% ({r3.get('m3_plus',0):>3}hits) │ "
              f"{e4:+5.2f}% ({r4.get('m3_plus',0):>3}hits) │ "
              f"{e5:+5.2f}% ({r5.get('m3_plus',0):>3}hits) │")

    print("└──────────┴─────────────────┴─────────────────┴─────────────────┘")

    # Decision
    e1500_5 = ts5_results.get(1500, {}).get('edge', 0) * 100
    e1500_4 = ts4_results.get(1500, {}).get('edge', 0) * 100
    marginal5_1500 = (ts5_results.get(1500, {}).get('m3_plus', 0) -
                       ts4_results.get(1500, {}).get('m3_plus', 0))
    n1500 = ts5_results.get(1500, {}).get('total', 1)
    m5_edge_1500 = marginal5_1500 / n1500 * 100 - P_SINGLE * 100

    all_pos_5 = all(ts5_results.get(w, {}).get('edge', -1) > 0 for w in [150, 500, 1500])

    n = ts5_results.get(1500, {}).get('total', 0)
    p_obs = ts5_results.get(1500, {}).get('win_rate', 0)
    p_base = BASELINES[5]
    z_1500 = (p_obs - p_base) / np.sqrt(p_base * (1 - p_base) / n) if n > 0 else 0

    print(f"\n  決策判定:")
    print(f"  - 5注 1500期 Edge: {e1500_5:+.2f}%, z={z_1500:.2f}")
    print(f"  - 三窗口全正: {'YES ★' if all_pos_5 else 'NO'}")
    print(f"  - 注5 邊際 Edge: {m5_edge_1500:+.2f}% (vs 隨機第5注)")
    print(f"  - McNemar: χ²={chi2:.2f}")
    print()

    if e1500_5 > 0 and all_pos_5:
        print("  ★ 結論: 5注策略 ROBUST，建議採納")
    elif e1500_5 > 0:
        print("  ⚠ 結論: 5注全局正但非三窗口全正，MODERATE_DECAY")
    else:
        print("  ✗ 結論: 5注全局負邊際，不採納")

    print("=" * 80)


if __name__ == '__main__':
    main()
