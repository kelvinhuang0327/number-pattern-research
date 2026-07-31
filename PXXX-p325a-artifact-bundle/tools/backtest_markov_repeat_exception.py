#!/usr/bin/env python3
"""
Markov 重複號碼例外處理 — 1500期驗證
==========================================
假設: 連續兩期都出現的號碼 (history[-2] ∩ history[-1]) 具有「持續性」信號，
      在 Markov 轉移分數上給予額外加成，以提升預測覆蓋率。

驗證流程:
  0. 實證測試: P(n in draw t+1 | n in draw t AND n in draw t-1) vs 基準 6/49
  1. Grid Search: boost_factor = [0.1, 0.2, 0.3, 0.5, 1.0]
  2. 三窗口驗證: 150 / 500 / 1500 期
  3. 對比基準: TS3 + Markov(w=30) 4注 (MEMORY: Edge +1.23%)
  4. McNemar 邊際顯著性測試

基準設定:
  - Markov window: 30 (已驗證最佳)
  - 4-bet baseline: P(4) = 1 - (1-0.0186)^4 = 7.25%
  - Strict temporal isolation

用法:
    python3 tools/backtest_markov_repeat_exception.py
"""
import os, sys, time
import numpy as np
from collections import Counter
from itertools import product as iproduct
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49
PICK = 6
SEED = 42
P_SINGLE = 0.0186
BASELINES = {
    3: 1 - (1 - P_SINGLE) ** 3,   # 5.49%
    4: 1 - (1 - P_SINGLE) ** 4,   # 7.25%
}
MARKOV_WINDOW = 30   # 已驗證最佳窗口
WINDOWS = [150, 500, 1500]
MIN_HISTORY = 150


# ──────────────────────────────────────────────
# Step 0: 實證測試 — 連續重複出現的統計特性
# ──────────────────────────────────────────────

def empirical_repeat_lift(draws):
    """
    計算 P(n 出現在 t | n 同時出現在 t-1 和 t-2) 的 Lift。
    如果 Lift >> 1.0，表示連續重複具有預測力。
    """
    total_repeat_candidates = 0
    repeat_appeared = 0
    consecutive_events = []

    for i in range(2, len(draws)):
        prev2 = set(draws[i-2]['numbers'])
        prev1 = set(draws[i-1]['numbers'])
        current = set(draws[i]['numbers'])

        repeat_set = prev2 & prev1   # 連續兩期都有的號碼

        for n in repeat_set:
            total_repeat_candidates += 1
            if n in current:
                repeat_appeared += 1

        if repeat_set:
            consecutive_events.append(len(repeat_set & current))

    baseline = PICK / MAX_NUM  # 6/49 ≈ 12.24%
    actual_rate = repeat_appeared / total_repeat_candidates if total_repeat_candidates > 0 else 0
    lift = actual_rate / baseline if baseline > 0 else 0

    # 期望的連續重複事件總量
    expected_hits = total_repeat_candidates * baseline

    # z-test
    z = (repeat_appeared - expected_hits) / np.sqrt(
        expected_hits * (1 - baseline)
    ) if expected_hits > 0 else 0

    # 統計: 每期平均有幾個連續重複號碼
    n_draw_pairs = len(draws) - 2
    avg_repeat_per_draw = total_repeat_candidates / n_draw_pairs if n_draw_pairs > 0 else 0

    return {
        'total_candidates': total_repeat_candidates,
        'appeared': repeat_appeared,
        'actual_rate': actual_rate,
        'baseline': baseline,
        'lift': lift,
        'z': z,
        'avg_repeat_per_draw': avg_repeat_per_draw,
    }


# ──────────────────────────────────────────────
# Triple Strike 完整實作
# ──────────────────────────────────────────────

def fourier_rhythm_bet(history, window=500):
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {n: np.zeros(w) for n in range(1, MAX_NUM + 1)}
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
        if len(pos_yf) == 0:
            continue
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


def cold_numbers_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    return sorted(sorted(candidates, key=lambda x: freq.get(x, 0))[:6])


def tail_balance_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
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
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


# ──────────────────────────────────────────────
# Markov 核心: 原版 (w=30)
# ──────────────────────────────────────────────

def markov_orthogonal_bet(history, exclude=None, markov_window=MARKOV_WINDOW,
                           repeat_boost_factor=0.0):
    """
    Markov 轉移矩陣正交注4。
    repeat_boost_factor > 0 時啟用「連續重複例外」加成。
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

    # ── 重複號碼例外加成 ──
    if repeat_boost_factor > 0 and len(history) >= 2:
        last_draw = set(history[-1]['numbers'])
        prev_draw = set(history[-2]['numbers'])
        repeat_nums = last_draw & prev_draw  # 連續兩期都出現

        if scores and repeat_nums:
            max_score = max(scores.values()) if scores else 1
            for n in repeat_nums:
                if n not in exclude:
                    scores[n] += max_score * repeat_boost_factor

    candidates = [(n, scores[n]) for n in range(1, MAX_NUM + 1) if n not in exclude]
    candidates.sort(key=lambda x: -x[1])
    selected = [n for n, _ in candidates[:PICK]]

    if len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1)
                     if n not in exclude and n not in selected]
        selected.extend(remaining[:PICK - len(selected)])

    return sorted(selected[:PICK])


def generate_ts3_markov4(history, markov_window=MARKOV_WINDOW,
                          repeat_boost_factor=0.0):
    ts3_bets = generate_triple_strike(history)
    ts3_used = set(n for bet in ts3_bets for n in bet)
    bet4 = markov_orthogonal_bet(
        history, exclude=ts3_used,
        markov_window=markov_window,
        repeat_boost_factor=repeat_boost_factor
    )
    return ts3_bets + [bet4]


# ──────────────────────────────────────────────
# 回測引擎
# ──────────────────────────────────────────────

def run_backtest(draws, strategy_func, n_bets, n_periods, **kwargs):
    np.random.seed(SEED)
    baseline = BASELINES.get(n_bets, BASELINES[4])

    start_idx = max(len(draws) - n_periods, MIN_HISTORY)
    hits = {3: 0, 4: 0, 5: 0, 6: 0}
    total = 0
    bet4_solo = 0      # 僅 Markov 注4 命中 (TS3全漏)
    bet4_any = 0       # Markov 注4 有命中

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]
        bets = strategy_func(history, **kwargs)

        ts3_max = max((len(set(b) & target) for b in bets[:3]), default=0)
        m4 = len(set(bets[3]) & target) if len(bets) >= 4 else 0
        best = max(ts3_max, m4)

        if best >= 3:
            hits[min(best, 6)] += 1
        if m4 >= 3:
            bet4_any += 1
            if ts3_max < 3:
                bet4_solo += 1
        total += 1

    m3p = sum(hits.values())
    win_rate = m3p / total if total else 0
    return {
        'total': total, 'm3_plus': m3p,
        'win_rate': win_rate, 'edge': win_rate - baseline,
        'baseline': baseline,
        'bet4_any': bet4_any, 'bet4_solo': bet4_solo,
    }


# ──────────────────────────────────────────────
# 衰減分類
# ──────────────────────────────────────────────

def classify(e150, e500, e1500):
    if e1500 > 0 and e500 > 0 and e150 > 0:
        return "ROBUST" if abs(e150 - e1500) < 0.6 else "MODERATE_DECAY"
    if e1500 > 0 and e500 <= 0:
        return "LATE_BLOOMER"
    if e1500 <= 0 and e150 > 0:
        return "SHORT_MOMENTUM"
    if e1500 <= 0:
        return "INEFFECTIVE"
    return "MIXED"


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))

    print(f"大樂透資料: {len(draws)} 期")
    print(f"最新: {draws[-1]['draw']} ({draws[-1]['date']})")

    # ══════════════════════════════════════════
    # Step 0: 實證統計測試
    # ══════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  Step 0: 連續重複出現號碼 實證 Lift 測試")
    print("=" * 70)

    lift_data = empirical_repeat_lift(draws)
    baseline_pct = lift_data['baseline'] * 100
    actual_pct   = lift_data['actual_rate'] * 100

    print(f"  分析期數: {len(draws) - 2}")
    print(f"  每期平均連續重複號碼數: {lift_data['avg_repeat_per_draw']:.2f} 個")
    print(f"  總候選次數: {lift_data['total_candidates']}")
    print(f"  基準 P(出現): {baseline_pct:.2f}% (6/49)")
    print(f"  實際 P(出現 | 連續重複): {actual_pct:.2f}%")
    print(f"  Lift: {lift_data['lift']:.4f}x")
    print(f"  z-score: {lift_data['z']:.2f}", end="")
    if abs(lift_data['z']) > 1.96:
        print("  ← 統計顯著 (p<0.05)")
    elif abs(lift_data['z']) > 1.645:
        print("  ← 邊緣顯著 (p<0.10)")
    else:
        print("  ← 不顯著")

    if lift_data['lift'] > 1.05:
        print(f"\n  → Lift > 1.05: 有正信號，測試加成機制")
    elif lift_data['lift'] > 0.95:
        print(f"\n  → Lift ≈ 1.0: 信號微弱，但仍測試加成效果")
    else:
        print(f"\n  → Lift < 0.95: 負信號 (連續重複反而不利)，預期加成無效")

    # ══════════════════════════════════════════
    # Step 1: 基準 TS3+Markov(w=30, boost=0)
    # ══════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  Step 1: 基準 TS3+Markov(w=30) 4注 (boost=0)")
    print("=" * 70)

    base_fn = lambda h: generate_ts3_markov4(h, markov_window=MARKOV_WINDOW,
                                              repeat_boost_factor=0.0)
    base_res = {}
    for w in WINDOWS:
        t0 = time.time()
        r = run_backtest(draws, base_fn, 4, w)
        base_res[w] = r
        print(f"  {w:4d}期: M3+={r['m3_plus']:3d}/{r['total']:4d} "
              f"({r['win_rate']*100:.2f}%)  Edge={r['edge']*100:+.2f}%  "
              f"注4獨佔={r['bet4_solo']}  ({time.time()-t0:.1f}s)")

    # ══════════════════════════════════════════
    # Step 2: Grid Search — boost_factor
    # ══════════════════════════════════════════
    BOOST_FACTORS = [0.1, 0.2, 0.3, 0.5, 1.0]

    print("\n" + "=" * 70)
    print(f"  Step 2: Grid Search — boost_factor × {len(WINDOWS)} 窗口")
    print("=" * 70)
    print(f"\n{'boost':>7} {'150p':>8} {'500p':>8} {'1500p':>8} {'Δ1500':>7} "
          f"{'三窗口':>6} {'注4獨佔(1500)':>12} {'模式'}")
    print("-" * 70)

    grid_results = []
    for bf in BOOST_FACTORS:
        fn = lambda h, f=bf: generate_ts3_markov4(h, markov_window=MARKOV_WINDOW,
                                                    repeat_boost_factor=f)
        res = {}
        t0 = time.time()
        for w in WINDOWS:
            res[w] = run_backtest(draws, fn, 4, w)

        e = {w: res[w]['edge'] * 100 for w in WINDOWS}
        d1500 = e[1500] - base_res[1500]['edge'] * 100
        all_pos = all(e[w] > 0 for w in WINDOWS)
        mode = classify(e[150], e[500], e[1500])
        solo1500 = res[1500]['bet4_solo']

        print(f"  {bf:>5.1f}  {e[150]:>+7.2f}% {e[500]:>+7.2f}% {e[1500]:>+7.2f}%  "
              f"{d1500:>+6.2f}%  {'✓' if all_pos else ' ':>6}  {solo1500:>12}  {mode}")

        grid_results.append({'boost': bf, 'e': e, 'delta': d1500,
                              'all_pos': all_pos, 'mode': mode, 'res': res})

    # ══════════════════════════════════════════
    # Step 3: McNemar 邊際顯著性 (best config vs baseline)
    # ══════════════════════════════════════════
    best = max(grid_results, key=lambda x: x['e'][1500])
    base_r = base_res[1500]
    best_r = best['res'][1500]

    print("\n" + "=" * 70)
    print("  Step 3: McNemar 邊際顯著性 (1500期)")
    print("=" * 70)

    m3p_base  = base_r['m3_plus']
    m3p_best  = best_r['m3_plus']
    delta_hits = m3p_best - m3p_base

    # Simplified McNemar approximation
    # b = extra hits in best vs base (conservative: = delta_hits)
    # c = 0 (assume best never loses vs base in 1500p context)
    b = max(delta_hits, 0)
    c = max(-delta_hits, 0)
    n_total = base_r['total']

    if b + c > 0:
        chi2 = (abs(b - c) - 1) ** 2 / (b + c)
        import math
        p_approx = math.exp(-chi2 / 2)  # chi2(1) approximation
    else:
        chi2 = 0
        p_approx = 1.0

    z_marginal = delta_hits / np.sqrt(n_total * base_r['baseline'] * (1 - base_r['baseline'])) if n_total > 0 else 0

    print(f"  基準 1500期 M3+: {m3p_base}")
    print(f"  最佳 (boost={best['boost']}) M3+: {m3p_best}")
    print(f"  Δ hits: {delta_hits:+d}")
    print(f"  z (邊際): {z_marginal:.2f}")
    print(f"  McNemar χ²: {chi2:.2f}  p≈{p_approx:.3f}")

    # ══════════════════════════════════════════
    # 最終結論
    # ══════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  最終結論")
    print("=" * 70)

    base_e150  = base_res[150]['edge']  * 100
    base_e500  = base_res[500]['edge']  * 100
    base_e1500 = base_res[1500]['edge'] * 100
    best_e150  = best['e'][150]
    best_e500  = best['e'][500]
    best_e1500 = best['e'][1500]

    print(f"\n  基準 TS3+Markov(w=30):")
    print(f"    150p={base_e150:+.2f}%  500p={base_e500:+.2f}%  1500p={base_e1500:+.2f}%")
    print(f"    模式: {classify(base_e150, base_e500, base_e1500)}")

    print(f"\n  最佳 boost={best['boost']}:")
    print(f"    150p={best_e150:+.2f}%  500p={best_e500:+.2f}%  1500p={best_e1500:+.2f}%")
    print(f"    Δ1500: {best['delta']:+.2f}%")
    print(f"    模式: {best['mode']}")

    if best['e'][1500] > base_e1500 + 0.10 and best['all_pos']:
        verdict = "✅ 採納: 三窗口全正且 1500p 顯著改善"
    elif best['e'][1500] > base_e1500 + 0.05:
        verdict = "⚠️  邊緣改善 (< 0.10%)，不顯著，不採納"
    else:
        verdict = "❌ 拒絕: 無顯著改善 (Δ1500 < 0.05%)，保留原版"

    print(f"\n  Lift 實證: {lift_data['lift']:.3f}x  (z={lift_data['z']:.2f})")
    print(f"  判決: {verdict}")
    print("=" * 70)


if __name__ == '__main__':
    main()
