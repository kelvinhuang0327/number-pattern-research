#!/usr/bin/env python3
"""
Gap Dynamic Threshold — 1500期驗證
====================================
假設: 在 cold_numbers_bet 中加入 gap 動態門檻,
      對超過門檻期數未出現的號碼給予「有效頻率調降」,
      使其被優先選入冷號池。

修改範圍: Triple Strike 的 Bet 2 (Cold Numbers)

Grid Search:
  gap_threshold = [10, 12, 15, 18]
  gap_weight    = [0.5, 1.0, 1.5, 2.0]

對比基準: Triple Strike 原版 (1500p Edge +0.98%)

用法:
    python3 tools/backtest_gap_dynamic_1500.py
"""
import os, sys, json, time
import numpy as np
from collections import Counter
from itertools import product

try:
    from scipy.fft import fft, fftfreq
except ImportError:
    from numpy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49
PICK = 6
SEED = 42
WINDOWS = [150, 500, 1500]
MIN_HISTORY = 150
BASELINES = {1: 0.0186, 2: 0.0369, 3: 0.0549, 4: 0.0725, 5: 0.0898}

# ──────────────────────────────────────────────
# 共用工具
# ──────────────────────────────────────────────

def compute_gaps(history):
    """計算每個號碼距今最近一次出現的期數 (gap)。"""
    gaps = {n: len(history) for n in range(1, MAX_NUM + 1)}
    for i, draw in enumerate(reversed(history)):
        for n in draw['numbers']:
            if gaps[n] == len(history):   # 尚未找到
                gaps[n] = i
    return gaps


# ──────────────────────────────────────────────
# Bet 1: Fourier Rhythm (原版, 不修改)
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


# ──────────────────────────────────────────────
# Bet 2a: Cold Numbers 原版
# ──────────────────────────────────────────────

def cold_numbers_bet_original(history, window=100, exclude=None):
    """原版: 純頻率排序，取最冷的 6 個。"""
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    return sorted(sorted(candidates, key=lambda x: freq.get(x, 0))[:6])


# ──────────────────────────────────────────────
# Bet 2b: Cold Numbers + Gap Dynamic Threshold (新版)
# ──────────────────────────────────────────────

def cold_numbers_bet_gap_dynamic(history, window=100, exclude=None,
                                  gap_threshold=12, gap_weight=1.0):
    """
    Gap 動態門檻版:
      combined_score(n) = freq(n) - gap_weight * max(0, gap(n) - gap_threshold)
      score 越低 → 越優先被選入冷號池
    """
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    gaps = compute_gaps(history)

    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]

    def score(n):
        f = freq.get(n, 0)
        g = gaps.get(n, len(history))
        return f - gap_weight * max(0, g - gap_threshold)

    return sorted(sorted(candidates, key=score)[:6])


# ──────────────────────────────────────────────
# Bet 3: Tail Balance (原版, 不修改)
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# 策略組合函式
# ──────────────────────────────────────────────

def triple_strike_original(history, **_):
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet_original(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


def triple_strike_gap_dynamic(history, gap_threshold=12, gap_weight=1.0):
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet_gap_dynamic(
        history, exclude=set(bet1),
        gap_threshold=gap_threshold, gap_weight=gap_weight
    )
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


# ──────────────────────────────────────────────
# 回測引擎
# ──────────────────────────────────────────────

def run_backtest(draws, strategy_func, n_periods, **kwargs):
    """
    嚴格時序隔離回測。
    strategy_func(history, **kwargs) → list[list[int]]
    """
    np.random.seed(SEED)
    n_bets = 3
    baseline = BASELINES[n_bets]

    total_draws = len(draws)
    start_idx = total_draws - n_periods
    if start_idx < MIN_HISTORY:
        start_idx = MIN_HISTORY

    hits = {3: 0, 4: 0, 5: 0, 6: 0}
    total = 0

    for i in range(start_idx, total_draws):
        target = set(draws[i]['numbers'])
        history = draws[:i]   # 嚴格隔離：不含當期
        bets = strategy_func(history, **kwargs)
        best = max((len(set(b) & target) for b in bets), default=0)
        if best >= 3:
            hits[min(best, 6)] += 1
        total += 1

    m3_plus = sum(hits.values())
    win_rate = m3_plus / total if total > 0 else 0
    edge = win_rate - baseline
    return {
        'total': total,
        'm3_plus': m3_plus,
        'win_rate': win_rate,
        'edge': edge,
        'hits': dict(hits),
        'baseline': baseline,
    }


# ──────────────────────────────────────────────
# Grid Search
# ──────────────────────────────────────────────

def run_grid_search(draws):
    GAP_THRESHOLDS = [10, 12, 15, 18]
    GAP_WEIGHTS    = [0.5, 1.0, 1.5, 2.0]

    results = {}

    # ── 基準: 原版 Triple Strike ──
    print("\n[基準] Triple Strike 原版 — 計算中…")
    base_results = {}
    for w in WINDOWS:
        r = run_backtest(draws, triple_strike_original, w)
        base_results[w] = r
        print(f"  {w:4d}期: M3+={r['m3_plus']:3d}/{r['total']:4d} "
              f"({r['win_rate']*100:.2f}%) Edge={r['edge']*100:+.2f}%")
    results['baseline'] = base_results

    # ── Grid Search ──
    configs = list(product(GAP_THRESHOLDS, GAP_WEIGHTS))
    total_configs = len(configs)
    print(f"\n[Grid Search] {total_configs} 組設定 × {len(WINDOWS)} 個窗口\n")

    grid_results = []
    for ci, (gt, gw) in enumerate(configs, 1):
        label = f"gap_t{gt}_w{gw}"
        print(f"  [{ci:2d}/{total_configs}] gap_threshold={gt:2d}, gap_weight={gw} … ", end='', flush=True)
        t0 = time.time()
        config_res = {}
        for w in WINDOWS:
            r = run_backtest(draws, triple_strike_gap_dynamic, w,
                             gap_threshold=gt, gap_weight=gw)
            config_res[w] = r
        dt = time.time() - t0

        # 主要指標：1500期 Edge
        e150  = config_res[150]['edge']  * 100
        e500  = config_res[500]['edge']  * 100
        e1500 = config_res[1500]['edge'] * 100
        delta_1500 = e1500 - base_results[1500]['edge'] * 100

        print(f"150p={e150:+.2f}% 500p={e500:+.2f}% 1500p={e1500:+.2f}% "
              f"Δ1500={delta_1500:+.2f}%  ({dt:.1f}s)")

        grid_results.append({
            'label': label,
            'gap_threshold': gt,
            'gap_weight': gw,
            'e150': e150,
            'e500': e500,
            'e1500': e1500,
            'delta_1500': delta_1500,
            'all_positive': (e150 > 0 and e500 > 0 and e1500 > 0),
            'results': config_res,
        })

    return results, grid_results


# ──────────────────────────────────────────────
# 衰減模式分析
# ──────────────────────────────────────────────

def classify_decay(e150, e500, e1500):
    if e1500 > 0 and e500 > 0 and e150 > 0:
        if e500 >= e150 * 0.8 or e1500 >= e500 * 0.8:
            return "ROBUST"
        return "MODERATE_DECAY"
    if e1500 > 0 and e500 > 0 and e150 <= 0:
        return "LATE_BLOOMER"
    if e1500 <= 0 and e150 > 0:
        return "SHORT_MOMENTUM"
    if e1500 > 0 and e500 <= 0:
        return "LATE_BLOOMER"
    if e1500 <= 0:
        return "INEFFECTIVE"
    return "UNKNOWN"


# ──────────────────────────────────────────────
# 結果報告
# ──────────────────────────────────────────────

def print_report(base_results, grid_results):
    base_e150  = base_results[150]['edge']  * 100
    base_e500  = base_results[500]['edge']  * 100
    base_e1500 = base_results[1500]['edge'] * 100

    print("\n" + "=" * 80)
    print("  Gap Dynamic Threshold — 1500期驗證結果")
    print("=" * 80)

    # 基準
    print(f"\n【基準】Triple Strike 原版")
    print(f"  150p: {base_e150:+.2f}%  500p: {base_e500:+.2f}%  1500p: {base_e1500:+.2f}%  "
          f"模式: {classify_decay(base_e150, base_e500, base_e1500)}")

    # 全 Grid 結果表
    print(f"\n{'設定':<20} {'150p':>8} {'500p':>8} {'1500p':>8} {'Δ1500':>8} {'三窗口全正':>10} {'模式':<18}")
    print("-" * 80)

    # 按 1500p Edge 降序
    sorted_grid = sorted(grid_results, key=lambda x: -x['e1500'])
    for r in sorted_grid:
        ap = "✓" if r['all_positive'] else " "
        mode = classify_decay(r['e150'], r['e500'], r['e1500'])
        print(f"  {r['label']:<18} {r['e150']:>+7.2f}% {r['e500']:>+7.2f}% "
              f"{r['e1500']:>+7.2f}% {r['delta_1500']:>+7.2f}%   {ap:<10} {mode}")

    # Top 5
    print("\n【Top-5 設定 (by 1500p Edge)】")
    for i, r in enumerate(sorted_grid[:5], 1):
        ap_mark = "★ 三窗口全正" if r['all_positive'] else ""
        mode = classify_decay(r['e150'], r['e500'], r['e1500'])
        print(f"  #{i}: gap_threshold={r['gap_threshold']:2d}, gap_weight={r['gap_weight']:.1f}  "
              f"→ 150p={r['e150']:+.2f}% / 500p={r['e500']:+.2f}% / 1500p={r['e1500']:+.2f}%  "
              f"{mode} {ap_mark}")

    # 改善數量統計
    improved = [r for r in grid_results if r['e1500'] > base_e1500]
    improved_all = [r for r in grid_results if r['all_positive'] and r['e1500'] > base_e1500]
    print(f"\n  1500p Edge 改善數: {len(improved)}/{len(grid_results)} 組設定")
    print(f"  三窗口全正且改善:  {len(improved_all)}/{len(grid_results)} 組設定")

    # 最佳設定
    best = sorted_grid[0]
    print(f"\n【最佳設定】gap_threshold={best['gap_threshold']}, gap_weight={best['gap_weight']}")
    print(f"  150p: {best['e150']:+.2f}%  500p: {best['e500']:+.2f}%  1500p: {best['e1500']:+.2f}%")
    print(f"  vs 基準: Δ1500 = {best['delta_1500']:+.2f}%")
    print(f"  模式: {classify_decay(best['e150'], best['e500'], best['e1500'])}")

    # 結論
    print("\n【結論】")
    if best['e1500'] > base_e1500 + 0.1:
        if best['all_positive']:
            print(f"  ✅ 採納建議: gap_threshold={best['gap_threshold']}, gap_weight={best['gap_weight']}")
            print(f"     1500p Edge 從 {base_e1500:+.2f}% 提升至 {best['e1500']:+.2f}% (+{best['delta_1500']:.2f}%)")
            print(f"     三窗口全正，策略健康")
        else:
            print(f"  ⚠️  有改善但非三窗口全正，需謹慎評估")
            print(f"     建議對比三窗口全正的次佳設定")
    else:
        print(f"  ❌ 無顯著改善 (Δ1500 < 0.1%)，建議保留原版")

    print("=" * 80)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'),
                   key=lambda x: (x['date'], x['draw']))

    print(f"大樂透資料: {len(draws)} 期")
    print(f"最新一期: {draws[-1]['draw']} ({draws[-1]['date']})")
    print(f"最舊一期: {draws[0]['draw']} ({draws[0]['date']})")

    if len(draws) < MIN_HISTORY + max(WINDOWS):
        print(f"資料不足，需至少 {MIN_HISTORY + max(WINDOWS)} 期")
        return

    t_start = time.time()
    base_results, grid_results = run_grid_search(draws)
    elapsed = time.time() - t_start

    print_report(base_results['baseline'], grid_results)
    print(f"\n  總耗時: {elapsed:.1f}s")


if __name__ == '__main__':
    main()
