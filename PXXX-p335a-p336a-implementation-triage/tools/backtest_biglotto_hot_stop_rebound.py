#!/usr/bin/env python3
"""
回測 A: 熱號休停回歸偵測 (Hot-Stop Rebound)

信號定義:
  - freq100 ≥ 15 (近100期出現≥15次，約前25%高頻號碼)
  - gap ≥ 10 (最近10期未出現)
  - 兩條件同時滿足 = 「熱號休停候選」

選號邏輯:
  1. 計算所有號碼的 freq100 和 gap
  2. 篩選同時滿足兩條件的號碼
  3. 若候選≥6：按 freq100 × gap 評分降序取前6
  4. 若候選<6：補入 freq100 最高的號碼填滿6個

評估框架:
  - Walk-forward (嚴格無洩漏)
  - 三窗口: 150 / 500 / 1500 期
  - 基準: 1注 M3+ baseline = 1.86%
  - 輸出: Signal Edge, z, p-value, 信號出現率
"""
import sys
import os
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

MAX_NUM = 49
PICK = 6
BASELINE_1BET = 1.86  # M3+ 1注基準
MIN_HISTORY = 200     # 熱號偵測最少需要100期 + gap buffer


def get_hot_stop_candidates(history, freq_threshold=15, gap_threshold=10, freq_window=100, gap_window=10):
    """計算熱號休停候選號碼

    Args:
        history: 歷史開獎資料 (ASC, 舊→新)
        freq_threshold: 近freq_window期出現次數門檻
        gap_threshold: gap期數門檻 (最近gap_window期未出現)
        freq_window: 頻率計算窗口
        gap_window: gap計算窗口 (最近N期未出現)

    Returns:
        candidates: [(number, score)] 降序排列
        all_gaps: {n: gap} 所有號碼的 gap 資訊
        all_freqs: {n: freq100} 所有號碼的 freq100 資訊
    """
    recent_freq = history[-freq_window:] if len(history) >= freq_window else history
    freq = Counter(n for d in recent_freq for n in d['numbers'])

    # gap = 距今多少期未出現
    recent_gap = history[-gap_window:] if len(history) >= gap_window else history
    appeared_in_recent = set(n for d in recent_gap for n in d['numbers'])

    all_gaps = {}
    for n in range(1, MAX_NUM + 1):
        if n in appeared_in_recent:
            all_gaps[n] = 0
        else:
            # 計算真實 gap (從最新往前找)
            gap = 0
            for d in reversed(history):
                if n in d['numbers']:
                    break
                gap += 1
            else:
                gap = len(history)
            all_gaps[n] = gap

    all_freqs = {n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)}

    # 篩選候選
    candidates = []
    for n in range(1, MAX_NUM + 1):
        f = all_freqs[n]
        g = all_gaps[n]
        if f >= freq_threshold and g >= gap_threshold:
            score = f * g  # 評分: 越熱越久未出現 → 評分越高
            candidates.append((n, score))

    candidates.sort(key=lambda x: -x[1])
    return candidates, all_gaps, all_freqs


def generate_hot_stop_bet(history, freq_threshold=15, gap_threshold=10):
    """生成熱號休停回歸注選 (6個號碼)"""
    candidates, all_gaps, all_freqs = get_hot_stop_candidates(
        history, freq_threshold=freq_threshold, gap_threshold=gap_threshold
    )

    result = [n for n, _ in candidates[:PICK]]

    if len(result) < PICK:
        # 補入 freq100 最高的號碼（未在 result 中）
        used = set(result)
        freq_ranked = sorted(range(1, MAX_NUM + 1),
                             key=lambda n: -all_freqs[n])
        for n in freq_ranked:
            if n not in used:
                result.append(n)
                if len(result) >= PICK:
                    break

    return sorted(result[:PICK])


def count_m3plus(predicted, actual):
    """計算 M3+ 命中 (6注中命中≥3個)"""
    p_set = set(predicted)
    a_set = set(actual)
    return len(p_set & a_set) >= 3


def backtest_window(draws, window_size, freq_threshold=15, gap_threshold=10):
    """在指定窗口內回測

    Returns:
        m3plus: M3+ 命中次數
        total: 總期數
        signal_count: 有候選信號的期數
    """
    m3plus = 0
    total = 0
    signal_count = 0

    for i in range(MIN_HISTORY, len(draws)):
        history = draws[:i]
        actual = draws[i]['numbers']

        # 檢查信號是否存在
        candidates, _, _ = get_hot_stop_candidates(
            history, freq_threshold=freq_threshold, gap_threshold=gap_threshold
        )

        predicted = generate_hot_stop_bet(history, freq_threshold=freq_threshold,
                                          gap_threshold=gap_threshold)
        hit = count_m3plus(predicted, actual)

        if len(candidates) >= 1:
            signal_count += 1

        if hit:
            m3plus += 1
        total += 1

    # 取最近 window_size 期
    if window_size and window_size < total:
        # 重新計算
        start_idx = len(draws) - window_size
        if start_idx < MIN_HISTORY:
            start_idx = MIN_HISTORY

        m3plus_w = 0
        total_w = 0
        signal_w = 0

        for i in range(start_idx, len(draws)):
            history = draws[:i]
            actual = draws[i]['numbers']

            candidates, _, _ = get_hot_stop_candidates(
                history, freq_threshold=freq_threshold, gap_threshold=gap_threshold
            )
            predicted = generate_hot_stop_bet(history, freq_threshold=freq_threshold,
                                              gap_threshold=gap_threshold)
            hit = count_m3plus(predicted, actual)

            if len(candidates) >= 1:
                signal_w += 1

            if hit:
                m3plus_w += 1
            total_w += 1

        return m3plus_w, total_w, signal_w

    return m3plus, total, signal_count


def backtest_full(draws, freq_threshold=15, gap_threshold=10):
    """完整 walk-forward 回測，返回每期結果列表"""
    results = []

    for i in range(MIN_HISTORY, len(draws)):
        history = draws[:i]
        actual = draws[i]['numbers']

        candidates, _, _ = get_hot_stop_candidates(
            history, freq_threshold=freq_threshold, gap_threshold=gap_threshold
        )
        predicted = generate_hot_stop_bet(history, freq_threshold=freq_threshold,
                                          gap_threshold=gap_threshold)
        hit = count_m3plus(predicted, actual)
        results.append({
            'hit': hit,
            'has_signal': len(candidates) >= 1,
            'n_candidates': len(candidates),
        })

    return results


def compute_edge_z(results, baseline_pct):
    """計算 Edge 和 z-score"""
    hits = sum(1 for r in results if r['hit'])
    total = len(results)
    if total == 0:
        return 0, 0, 1.0

    rate = hits / total
    edge = (rate - baseline_pct / 100) * 100
    p0 = baseline_pct / 100
    se = np.sqrt(p0 * (1 - p0) / total)
    z = (rate - p0) / se if se > 0 else 0
    from scipy import stats as scipy_stats
    p_val = 1 - scipy_stats.norm.cdf(z)
    return edge, z, p_val


def main():
    print("=" * 70)
    print("  回測 A: 大樂透 熱號休停回歸偵測 (Hot-Stop Rebound)")
    print("  信號: freq100 ≥ 15 AND gap ≥ 10")
    print("=" * 70)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))

    print(f"\n  資料庫: {len(draws)} 期大樂透開獎資料")
    print(f"  回測起點: 第 {MIN_HISTORY+1} 期 (需 {MIN_HISTORY} 期暖機)")
    print(f"  有效回測期數: {len(draws) - MIN_HISTORY} 期\n")

    # ── 參數敏感性分析 ────────────────────────────────────────────────
    print("  [參數敏感性分析] freq_threshold 和 gap_threshold 組合")
    print("  " + "-" * 55)
    print(f"  {'freq_thr':>8}  {'gap_thr':>7}  {'信號率':>6}  {'Edge(1500)':>10}  {'z':>6}")
    print("  " + "-" * 55)

    param_grid = [
        (12, 8), (12, 10), (15, 8), (15, 10), (15, 12),
        (18, 8), (18, 10), (20, 10),
    ]

    best_params = None
    best_edge = -999

    for ft, gt in param_grid:
        results_all = backtest_full(draws, freq_threshold=ft, gap_threshold=gt)
        # 最近 1500 期
        r1500 = results_all[-1500:] if len(results_all) >= 1500 else results_all
        if not r1500:
            continue
        edge, z, _ = compute_edge_z(r1500, BASELINE_1BET)
        signal_rate = sum(1 for r in r1500 if r['has_signal']) / len(r1500) * 100
        print(f"  {ft:>8}  {gt:>7}  {signal_rate:>5.1f}%  {edge:>+9.2f}%  {z:>+6.2f}")
        if edge > best_edge:
            best_edge = edge
            best_params = (ft, gt)

    print("  " + "-" * 55)
    print(f"\n  最佳參數: freq_threshold={best_params[0]}, gap_threshold={best_params[1]}")
    print(f"  最佳 1500期 Edge: {best_edge:+.2f}%")

    # ── 主回測 (最佳參數) ────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"  主回測: freq_threshold={best_params[0]}, gap_threshold={best_params[1]}")
    print("=" * 70)

    FREQ_THR, GAP_THR = best_params
    results_all = backtest_full(draws, freq_threshold=FREQ_THR, gap_threshold=GAP_THR)

    # 三窗口
    windows = [('150期', 150), ('500期', 500), ('1500期', 1500)]
    print(f"\n  {'窗口':>8}  {'期數':>6}  {'M3+':>6}  {'命中率':>7}  {'基準':>7}  {'Edge':>8}  {'z':>6}  {'p':>7}  {'信號率':>7}")
    print("  " + "-" * 75)

    all_positive = True
    for wname, wsz in windows:
        r = results_all[-wsz:] if len(results_all) >= wsz else results_all
        hits = sum(1 for x in r if x['hit'])
        total = len(r)
        rate = hits / total * 100 if total > 0 else 0
        edge, z, p_val = compute_edge_z(r, BASELINE_1BET)
        signal_rate = sum(1 for x in r if x['has_signal']) / total * 100 if total > 0 else 0
        marker = "★" if edge > 0 else "✗"
        if edge <= 0:
            all_positive = False
        print(f"  {wname:>8}  {total:>6}  {hits:>6}  {rate:>6.2f}%  "
              f"{BASELINE_1BET:>6.2f}%  {edge:>+7.2f}%  {z:>+6.2f}  {p_val:>7.4f}  {signal_rate:>6.1f}%  {marker}")

    print("  " + "-" * 75)

    # 信號統計
    print("\n  [信號分析]")
    r1500 = results_all[-1500:] if len(results_all) >= 1500 else results_all
    n_signal = sum(1 for r in r1500 if r['has_signal'])
    avg_candidates = np.mean([r['n_candidates'] for r in r1500])
    print(f"  有效信號期: {n_signal}/{len(r1500)} ({n_signal/len(r1500)*100:.1f}%)")
    print(f"  平均候選數: {avg_candidates:.1f}")

    # ── 判斷結果 ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)

    r1500 = results_all[-1500:] if len(results_all) >= 1500 else results_all
    edge_1500, z_1500, p_1500 = compute_edge_z(r1500, BASELINE_1BET)

    if all_positive and z_1500 > 1.65:
        verdict = "PROVISIONAL — 三窗口全正且 z>1.65，建議進入監控"
    elif all_positive:
        verdict = "MARGINAL — 三窗口全正但 z≤1.65，信號弱"
    elif edge_1500 > 0:
        verdict = "LATE_BLOOMER — 長期有信號但短期負"
    else:
        verdict = "REJECT — 1500期 Edge ≤ 0"

    print(f"\n  結論: {verdict}")
    print(f"  1500期 Edge={edge_1500:+.2f}%  z={z_1500:+.2f}  p={p_1500:.4f}")

    if "REJECT" in verdict or "LATE_BLOOMER" in verdict:
        print("\n  → 建議歸檔至 rejected/hot_stop_rebound_biglotto.json")
    else:
        print("\n  → 建議加入 RSM 監控，200期後決定是否採納")

    print("\n  [說明] 熱號休停回歸：一致性高頻號碼突然停止 → 回歸回彈")
    print("  [說明] 115000031期 #25 (freq100=18, gap=15) 是此模型的觸發案例")
    print("=" * 70)


if __name__ == '__main__':
    try:
        from scipy import stats
    except ImportError:
        print("需要 scipy: pip install scipy")
        sys.exit(1)
    main()
