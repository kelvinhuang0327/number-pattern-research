#!/usr/bin/env python3
"""
大樂透 Zone Transition Matrix 分析
====================================
分析 Z1/Z2/Z3 的期間轉移模式，特別針對 Z3=0 的先行指標。

Zone 定義:
  Z1 = 1~16  (16個號碼)
  Z2 = 17~32 (16個號碼)
  Z3 = 33~49 (17個號碼)

分析目標:
  1. Zone Transition Matrix: P(next_z | prev_z) for each zone count
  2. Z3=0 先行指標: 前一期的 Zone 分佈是否能預測 Z3=0
  3. 各種先行指標的 Lift 值計算
  4. 基於 Zone Transition 的選號優化可行性評估

Usage:
    python3 tools/backtest_zone_transition.py
"""
import os
import sys
import numpy as np
from collections import defaultdict, Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49
PICK = 6

# Zone boundaries
Z1_MAX = 16   # 1~16
Z2_MAX = 32   # 17~32
# Z3 = 33~49

def get_zone(n):
    if n <= Z1_MAX:
        return 1
    elif n <= Z2_MAX:
        return 2
    else:
        return 3

def zone_counts(numbers):
    """回傳 (z1, z2, z3) 三區號碼數量"""
    z1 = sum(1 for n in numbers if n <= Z1_MAX)
    z2 = sum(1 for n in numbers if Z1_MAX < n <= Z2_MAX)
    z3 = sum(1 for n in numbers if n > Z2_MAX)
    return z1, z2, z3


def analyze_zone_distribution(draws):
    """分析歷史 Zone 分佈統計"""
    counts = Counter()
    for d in draws:
        zc = zone_counts(d['numbers'])
        counts[zc] += 1

    total = len(draws)
    print("=" * 60)
    print("  Zone 分佈統計 (Z1=1~16, Z2=17~32, Z3=33~49)")
    print("=" * 60)
    print(f"  總期數: {total}")
    print()
    print(f"  {'(Z1,Z2,Z3)':15s} {'次數':>6s} {'頻率':>8s}")
    print(f"  {'-'*35}")

    sorted_counts = sorted(counts.items(), key=lambda x: -x[1])
    for zc, cnt in sorted_counts[:20]:
        pct = cnt / total * 100
        marker = " ← Z3=0" if zc[2] == 0 else ""
        print(f"  {str(zc):15s} {cnt:>6d} {pct:>7.2f}%{marker}")

    print()
    z3_0_total = sum(v for k, v in counts.items() if k[2] == 0)
    print(f"  Z3=0 合計: {z3_0_total}/{total} = {z3_0_total/total*100:.2f}%")
    z3_1_total = sum(v for k, v in counts.items() if k[2] == 1)
    print(f"  Z3=1 合計: {z3_1_total}/{total} = {z3_1_total/total*100:.2f}%")
    z3_2_total = sum(v for k, v in counts.items() if k[2] == 2)
    print(f"  Z3=2 合計: {z3_2_total}/{total} = {z3_2_total/total*100:.2f}%")
    z3_3plus = sum(v for k, v in counts.items() if k[2] >= 3)
    print(f"  Z3≥3 合計: {z3_3plus}/{total} = {z3_3plus/total*100:.2f}%")
    return counts, total


def analyze_zone_transition_matrix(draws):
    """
    建立 Zone 轉移矩陣：
    P(next Z3_count | prev Z3_count)
    以及各種 Zone 狀態的轉移概率
    """
    print()
    print("=" * 60)
    print("  Z3 計數轉移矩陣")
    print("  P(next_Z3 | prev_Z3)")
    print("=" * 60)

    # Z3 count transition: 0,1,2,3,4+ → 0,1,2,3,4+
    MAX_Z = 5  # 0~4+
    trans = np.zeros((MAX_Z, MAX_Z), dtype=int)

    for i in range(1, len(draws)):
        prev_z3 = min(zone_counts(draws[i-1]['numbers'])[2], MAX_Z - 1)
        curr_z3 = min(zone_counts(draws[i]['numbers'])[2], MAX_Z - 1)
        trans[prev_z3][curr_z3] += 1

    # Normalize
    row_sums = trans.sum(axis=1, keepdims=True)
    trans_prob = np.where(row_sums > 0, trans / row_sums, 0)

    labels = ['Z3=0', 'Z3=1', 'Z3=2', 'Z3=3', 'Z3≥4']
    header = "前期↓\\下期→"
    print(f"\n  {header:12s}", end='')
    for l in labels:
        print(f" {l:>8s}", end='')
    print(f" {'樣本數':>8s}")
    print(f"  {'-'*70}")

    for i, row_label in enumerate(labels):
        print(f"  {row_label:12s}", end='')
        for j in range(MAX_Z):
            print(f" {trans_prob[i][j]:>7.2%} ", end='')
        print(f" {trans[i].sum():>8d}")

    # 基準：整體 Z3=0 頻率
    total = len(draws) - 1
    z3_0_count = trans[:, 0].sum()
    baseline = z3_0_count / total

    print(f"\n  全體 Z3=0 基準頻率: {baseline:.4f} ({baseline*100:.2f}%)")
    print()

    # Lift 分析
    print("  Z3=0 先行指標 Lift 分析:")
    print(f"  {'前期狀態':15s} {'Z3=0次數':>10s} {'總次數':>8s} {'條件P':>8s} {'Lift':>8s}")
    print(f"  {'-'*55}")

    for i, row_label in enumerate(labels):
        cond_count = trans[i][0]
        row_total = trans[i].sum()
        if row_total > 0:
            cond_p = cond_count / row_total
            lift = cond_p / baseline
            marker = " *** " if lift > 1.3 else (" ** " if lift > 1.1 else "")
            print(f"  {row_label:15s} {cond_count:>10d} {row_total:>8d} {cond_p:>7.2%}  {lift:>6.3f}x{marker}")

    return trans, baseline


def analyze_full_zone_state_transition(draws):
    """
    更細緻的 Zone 狀態轉移：完整 (z1,z2,z3) 組合 → Z3=0 概率
    """
    print()
    print("=" * 60)
    print("  完整 Zone 狀態 → Z3=0 轉移分析")
    print("  (前期完整分佈 → 下期 Z3=0 的 Lift)")
    print("=" * 60)

    # 前期 Zone 狀態 → 下期 Z3 計數
    prev_to_next_z3 = defaultdict(list)
    for i in range(1, len(draws)):
        prev_zc = zone_counts(draws[i-1]['numbers'])
        curr_z3 = zone_counts(draws[i]['numbers'])[2]
        prev_to_next_z3[prev_zc].append(curr_z3)

    total_draws = len(draws) - 1
    total_z3_0 = sum(1 for i in range(1, len(draws))
                     if zone_counts(draws[i]['numbers'])[2] == 0)
    baseline = total_z3_0 / total_draws

    results = []
    for prev_zc, next_z3_list in prev_to_next_z3.items():
        n = len(next_z3_list)
        n_z3_0 = sum(1 for z in next_z3_list if z == 0)
        if n >= 20:  # 最少20個樣本才計算
            cond_p = n_z3_0 / n
            lift = cond_p / baseline
            results.append((prev_zc, n, n_z3_0, cond_p, lift))

    results.sort(key=lambda x: -x[4])

    print(f"\n  Z3=0 全體基準: {baseline:.4f} ({baseline*100:.2f}%)")
    print(f"\n  {'前期(Z1,Z2,Z3)':18s} {'樣本':>6s} {'Z3=0':>6s} {'條件P':>8s} {'Lift':>8s}")
    print(f"  {'-'*52}")

    for (zc, n, n_z3_0, cp, lift) in results:
        marker = " ***" if lift > 1.3 else (" **" if lift > 1.1 else ("" if lift > 0.9 else " (low)"))
        print(f"  {str(zc):18s} {n:>6d} {n_z3_0:>6d} {cp:>7.2%}  {lift:>6.3f}x{marker}")

    return results, baseline


def analyze_z3_high_to_z3_zero(draws):
    """
    特別分析: Z3 高數量後是否更容易出現 Z3=0 (均值回歸假說)
    """
    print()
    print("=" * 60)
    print("  Z3 均值回歸假說: 前期 Z3 多 → 下期 Z3=0 概率?")
    print("=" * 60)

    # 計算連續 Z3 分佈
    z3_counts = [zone_counts(d['numbers'])[2] for d in draws]
    z3_mean = np.mean(z3_counts)
    z3_std = np.std(z3_counts)
    print(f"\n  Z3 計數歷史統計:")
    print(f"  均值 = {z3_mean:.3f}, 標準差 = {z3_std:.3f}")
    print(f"  分位數: 10%={np.percentile(z3_counts, 10):.1f}, "
          f"25%={np.percentile(z3_counts, 25):.1f}, "
          f"75%={np.percentile(z3_counts, 75):.1f}, "
          f"90%={np.percentile(z3_counts, 90):.1f}")

    # 連續2期 Z3=0 的概率
    consecutive_z3_0 = sum(1 for i in range(1, len(draws))
                           if z3_counts[i] == 0 and z3_counts[i-1] == 0)
    z3_0_total = sum(1 for z in z3_counts if z == 0)
    total = len(draws) - 1
    baseline = z3_0_total / len(draws)
    if z3_0_total > 1:
        cond_p = consecutive_z3_0 / z3_0_total
        print(f"\n  P(連續Z3=0): {consecutive_z3_0}/{z3_0_total} = {cond_p:.4f}"
              f" (基準={baseline:.4f}, Lift={cond_p/baseline:.3f}x)")

    # 前2期 Z3 平均高 → Z3=0 概率
    print(f"\n  前期 Z3 均值窗口 vs 下期 Z3=0:")
    for window in [1, 2, 3, 5]:
        above_mean_idx = []
        below_mean_idx = []
        for i in range(window, len(draws)):
            prev_z3_avg = np.mean(z3_counts[i-window:i])
            if prev_z3_avg > z3_mean:
                above_mean_idx.append(i)
            else:
                below_mean_idx.append(i)

        above_z3_0 = sum(1 for i in above_mean_idx if z3_counts[i] == 0)
        below_z3_0 = sum(1 for i in below_mean_idx if z3_counts[i] == 0)

        if above_mean_idx and below_mean_idx:
            pa = above_z3_0 / len(above_mean_idx)
            pb = below_z3_0 / len(below_mean_idx)
            lift_a = pa / baseline
            lift_b = pb / baseline
            print(f"  window={window}: "
                  f"前期Z3>均值({len(above_mean_idx)}期) → Z3=0: {pa:.3f} (Lift={lift_a:.3f}x); "
                  f"前期Z3≤均值({len(below_mean_idx)}期) → Z3=0: {pb:.3f} (Lift={lift_b:.3f}x)")


def analyze_z2_heavy_precursor(draws):
    """
    特別分析: 前期 Z2 密集 (Z2≥4) 是否影響 Z3=0 或 Z2 繼續密集的概率
    """
    print()
    print("=" * 60)
    print("  前期 Z2 密集 (Z2≥4) 先行指標分析")
    print("=" * 60)

    z3_counts = [zone_counts(d['numbers'])[2] for d in draws]
    z2_counts = [zone_counts(d['numbers'])[1] for d in draws]

    total = len(draws) - 1
    z3_0_total = sum(1 for z in z3_counts[1:] if z == 0)
    baseline_z3_0 = z3_0_total / total
    z2_heavy_total = sum(1 for z in z2_counts[1:] if z >= 4)
    baseline_z2_heavy = z2_heavy_total / total

    print(f"\n  Z3=0 基準: {baseline_z3_0:.4f}")
    print(f"  Z2≥4 基準: {baseline_z2_heavy:.4f}")
    print()

    # 前期 Z2 計數 → 下期 Z3=0 概率
    print(f"  {'前期Z2計數':12s} {'樣本':>6s} {'→Z3=0':>8s} {'條件P':>8s} {'Lift':>8s}")
    print(f"  {'-'*46}")
    for prev_z2 in range(7):
        idx_list = [i for i in range(1, len(draws)) if z2_counts[i-1] == prev_z2]
        if not idx_list:
            continue
        n_z3_0 = sum(1 for i in idx_list if z3_counts[i] == 0)
        cp = n_z3_0 / len(idx_list)
        lift = cp / baseline_z3_0
        marker = " ***" if lift > 1.3 else (" **" if lift > 1.1 else "")
        print(f"  前期Z2={prev_z2}     {len(idx_list):>6d} {n_z3_0:>8d} {cp:>7.3f}  {lift:>6.3f}x{marker}")

    # 本期 Z2 密集本身的概率
    print(f"\n  {'前期Z2計數':12s} {'樣本':>6s} {'→Z2≥4':>8s} {'條件P':>8s} {'Lift':>8s}")
    print(f"  {'-'*46}")
    for prev_z2 in range(7):
        idx_list = [i for i in range(1, len(draws)) if z2_counts[i-1] == prev_z2]
        if not idx_list:
            continue
        n_z2_heavy = sum(1 for i in idx_list if z2_counts[i] >= 4)
        cp = n_z2_heavy / len(idx_list)
        lift = cp / baseline_z2_heavy
        marker = " ***" if lift > 1.3 else (" **" if lift > 1.1 else "")
        print(f"  前期Z2={prev_z2}     {len(idx_list):>6d} {n_z2_heavy:>8d} {cp:>7.3f}  {lift:>6.3f}x{marker}")


def analyze_consecutive_zone_patterns(draws, lookback=3):
    """
    分析連續N期的 Zone 模式是否有預測力
    """
    print()
    print("=" * 60)
    print(f"  連續 {lookback} 期 Zone 模式分析")
    print("  (連續前{lookback}期 Z3 趨勢 → Z3=0 概率)")
    print("=" * 60)

    z3_counts = [zone_counts(d['numbers'])[2] for d in draws]
    total = len(draws) - lookback
    z3_0_total = sum(1 for z in z3_counts[lookback:] if z == 0)
    baseline = z3_0_total / total

    print(f"\n  Z3=0 基準: {baseline:.4f}")

    # 連續遞增 vs 遞減 vs 保持
    trends = {'increasing': [], 'decreasing': [], 'stable': [], 'volatile': []}
    for i in range(lookback, len(draws)):
        prev = z3_counts[i-lookback:i]
        if all(prev[j] <= prev[j+1] for j in range(len(prev)-1)):
            trends['increasing'].append(i)
        elif all(prev[j] >= prev[j+1] for j in range(len(prev)-1)):
            trends['decreasing'].append(i)
        elif max(prev) - min(prev) <= 1:
            trends['stable'].append(i)
        else:
            trends['volatile'].append(i)

    print(f"\n  {'Z3趨勢':15s} {'樣本':>6s} {'→Z3=0':>8s} {'條件P':>8s} {'Lift':>8s}")
    print(f"  {'-'*50}")
    for trend, idx_list in trends.items():
        if not idx_list:
            continue
        n_z3_0 = sum(1 for i in idx_list if z3_counts[i] == 0)
        cp = n_z3_0 / len(idx_list)
        lift = cp / baseline
        marker = " ***" if lift > 1.3 else (" **" if lift > 1.1 else "")
        print(f"  {trend:15s} {len(idx_list):>6d} {n_z3_0:>8d} {cp:>7.3f}  {lift:>6.3f}x{marker}")

    # 高 Z3 後的最大持續低 Z3 期數
    print(f"\n  Z3 過高後的冷卻模式:")
    high_z3_follows = defaultdict(list)
    for i in range(1, len(draws)):
        prev_z3 = z3_counts[i-1]
        if prev_z3 >= 3:
            for lag in range(1, min(6, len(draws) - i)):
                high_z3_follows[lag].append(z3_counts[i + lag - 1] if i + lag - 1 < len(draws) else None)

    if high_z3_follows:
        print(f"  (前期Z3≥3 之後各期 Z3 均值):")
        for lag in sorted(high_z3_follows.keys()):
            vals = [v for v in high_z3_follows[lag] if v is not None]
            if vals:
                print(f"  lag={lag}: Z3均值={np.mean(vals):.3f} (基準={np.mean(z3_counts):.3f})")


def build_zone_transition_selector(draws, target_idx):
    """
    基於 Zone 轉移概率建立號碼權重偏置。
    給定前一期的 Zone 分佈，計算「下期各 Zone 的期望配置數量」。
    返回每個號碼的 zone_weight (可乘以其他信號分數)
    """
    # 計算歷史轉移矩陣
    prev_z3_list = [zone_counts(draws[i-1]['numbers'])[2] for i in range(1, target_idx)]
    curr_z3_list = [zone_counts(draws[i]['numbers'])[2] for i in range(1, target_idx)]

    # 最近100期前期Z3 → 下期Z3的期望值
    window = min(100, target_idx - 1)
    recent_prev = prev_z3_list[-window:]
    recent_curr = curr_z3_list[-window:]

    prev_z3_now = zone_counts(draws[target_idx-1]['numbers'])[2]

    # 當前期 Z3=k 時，下期各 Zone 的期望
    matches = [(c, r) for p, c, r in zip(
        prev_z3_list[-window:],
        [zone_counts(draws[i]['numbers'])[1] for i in range(target_idx-window, target_idx)],
        [zone_counts(draws[i]['numbers'])[2] for i in range(target_idx-window, target_idx)]
    ) if p == prev_z3_now]

    # 返回期望 Z3 數量
    if not matches:
        return 2.0  # 預設期望
    z2_vals, z3_vals = zip(*matches) if matches else ([], [])
    return np.mean(z3_vals) if z3_vals else 2.0


def evaluate_zone_signal_for_selection(draws):
    """
    評估：如果用 Zone Transition 調整選號策略，能否提升 M3+ 命中率？
    方法：若 P(Z3=0 | prev_zone) 顯著高於基準，則減少 Z3 號碼的配置。
    """
    print()
    print("=" * 60)
    print("  Zone Transition 選號調整可行性評估")
    print("=" * 60)

    MIN_BUF = 150
    z3_counts = [zone_counts(d['numbers'])[2] for d in draws]

    # 計算各期的 Zone 轉移概率
    lift_threshold = 1.3  # 需要超過此 Lift 才調整
    adjusted_correct = 0
    conservative_correct = 0
    total_decisions = 0

    # 假設我們的決策是：選 Z3 號碼幾個
    # 根據前一期 Zone 狀態做調整
    for i in range(MIN_BUF, len(draws)):
        history = draws[:i]
        prev_z3 = zone_counts(draws[i-1]['numbers'])[2]

        # 計算歷史中前期Z3=prev_z3 時，下期Z3=0 的頻率
        n_match = 0
        n_z3_0 = 0
        for j in range(1, i):
            pz = zone_counts(draws[j-1]['numbers'])[2]
            cz = zone_counts(draws[j]['numbers'])[2]
            if pz == prev_z3:
                n_match += 1
                if cz == 0:
                    n_z3_0 += 1

        actual_z3 = z3_counts[i]
        total_z3_0 = sum(1 for z in z3_counts[1:i] if z == 0)
        baseline = total_z3_0 / (i - 1) if i > 1 else 0.069

        if n_match >= 20:
            cond_p = n_z3_0 / n_match
            lift = cond_p / baseline if baseline > 0 else 1.0

            # 保守策略：固定預測 Z3≈2
            conservative_correct += 1 if actual_z3 >= 1 else 0

            # 調整策略：若 lift>1.3 則預測 Z3=0 或 Z3=1
            if lift > lift_threshold:
                adjusted_correct += 1 if actual_z3 <= 1 else 0
            else:
                adjusted_correct += 1 if actual_z3 >= 1 else 0

            total_decisions += 1

    if total_decisions > 0:
        print(f"\n  決策樣本數: {total_decisions}")
        print(f"  保守策略 (固定 Z3≥1) 正確率: "
              f"{conservative_correct}/{total_decisions} = {conservative_correct/total_decisions:.2%}")
        print(f"  Zone轉移調整策略正確率: "
              f"{adjusted_correct}/{total_decisions} = {adjusted_correct/total_decisions:.2%}")
        diff = (adjusted_correct - conservative_correct) / total_decisions * 100
        print(f"  差異: {diff:+.2f}%")

        if diff > 1.0:
            print(f"  ✓ Zone 轉移調整有效（+{diff:.2f}%）")
        else:
            print(f"  ✗ Zone 轉移調整無顯著改善（差異 {diff:+.2f}%）")


def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"\n資料載入: {len(draws)} 期大樂透")

    # 分析1：基本 Zone 分佈統計
    counts, total = analyze_zone_distribution(draws)

    # 分析2：Z3 轉移矩陣
    trans, baseline = analyze_zone_transition_matrix(draws)

    # 分析3：完整 Zone 狀態轉移 → Z3=0
    results, baseline_full = analyze_full_zone_state_transition(draws)

    # 分析4：Z3 均值回歸假說
    analyze_z3_high_to_z3_zero(draws)

    # 分析5：Z2 密集先行指標
    analyze_z2_heavy_precursor(draws)

    # 分析6：連續 Zone 模式
    analyze_consecutive_zone_patterns(draws, lookback=3)

    # 分析7：選號可行性評估
    evaluate_zone_signal_for_selection(draws)

    # 最終結論
    print()
    print("=" * 60)
    print("  最終結論")
    print("=" * 60)

    max_lift = max((r[4] for r in results if r[1] >= 30), default=1.0)
    print(f"\n  完整Zone狀態 → Z3=0 最大Lift: {max_lift:.3f}x")

    if max_lift >= 1.3:
        print(f"  ✓ 存在先行指標 (Lift≥1.3): Zone 轉移信號有實用價值")
        print(f"  → 建議: 在符合先行條件時減少Z3號碼配置，增加Z1/Z2")
    elif max_lift >= 1.1:
        print(f"  ▲ 信號存在但弱 (1.1≤Lift<1.3): 統計顯著性存疑")
        print(f"  → 結論: 信號真實但幅度不足以調整選號策略")
    else:
        print(f"  ✗ 無有效先行指標 (Lift<1.1): Z3=0 是隨機事件")
        print(f"  → 結論: 現有選號策略（含Z3覆蓋）在期望值層面仍是最優")

    print()
    print(f"  115000025期 Z3=0 再次確認為極低概率事件 (歷史 ~6.9%)")
    print(f"  若無顯著先行指標，此類損失屬不可避免的統計尾部風險")
    print()


if __name__ == "__main__":
    main()
