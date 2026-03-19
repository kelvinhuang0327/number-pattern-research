#!/usr/bin/env python3
"""
115000054 期深度特徵研究 - 2注/3注方案可行性 + 高階特徵分析
"""
import sys, os, json
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

ACTUAL = {2, 8, 15, 29, 31}
ACTUAL_LIST = [2, 8, 15, 29, 31]

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(all_draws, key=lambda x: (x['date'], x['draw']))

    print("=" * 70)
    print("  深度特徵研究 - 115000054 期")
    print("=" * 70)

    # === Feature 1: Hot number streak detection ===
    print("\n  ━━━ FEATURE 1: 熱號連續出現偵測 ━━━")
    recent_20 = history[-20:]
    for n in ACTUAL_LIST:
        appearances = []
        for i, d in enumerate(recent_20):
            if n in d['numbers']:
                appearances.append(20-i)  # Recency
        print(f"  {n:02d}: 近20期出現{len(appearances)}次, 位置:{appearances if appearances else '無'}")

    # === Feature 2: Repeat number (from previous draw) ===
    print("\n  ━━━ FEATURE 2: 前期號碼延續分析 ━━━")
    prev_repeat_count = []
    for i in range(1, min(200, len(history))):
        prev = set(history[-i-1]['numbers'])
        curr = set(history[-i]['numbers'])
        overlap = len(prev & curr)
        prev_repeat_count.append(overlap)

    repeat_dist = Counter(prev_repeat_count)
    print(f"  前後期重複號碼分布 (近200期):")
    for k in sorted(repeat_dist.keys()):
        pct = repeat_dist[k] / len(prev_repeat_count) * 100
        print(f"    {k}個重複: {repeat_dist[k]}次 ({pct:.1f}%)")

    actual_repeat = len(set(history[-1]['numbers']) & ACTUAL)
    print(f"  本期重複{actual_repeat}個 (02) → 常見模式")

    # === Feature 3: Sum regime analysis ===
    print("\n  ━━━ FEATURE 3: 和值分區分析 (Regime) ━━━")
    sums = [sum(d['numbers']) for d in history[-50:]]
    sum_mean = np.mean(sums)
    sum_std = np.std(sums)
    last_sum = sum(history[-1]['numbers'])
    actual_sum = sum(ACTUAL_LIST)

    print(f"  近50期和值: mean={sum_mean:.1f}, std={sum_std:.1f}")
    print(f"  上期和值: {last_sum} ({'LOW' if last_sum < sum_mean - 0.5*sum_std else 'HIGH' if last_sum > sum_mean + 0.5*sum_std else 'MID'})")
    print(f"  本期和值: {actual_sum} ({'LOW' if actual_sum < sum_mean - 0.5*sum_std else 'HIGH' if actual_sum > sum_mean + 0.5*sum_std else 'MID'})")

    # After LOW sum, what happens?
    sum_after_low = []
    for i in range(1, len(history)-1):
        s = sum(history[i]['numbers'])
        if s < sum_mean - 0.5 * sum_std:
            next_s = sum(history[i+1]['numbers'])
            sum_after_low.append(next_s)

    if sum_after_low:
        print(f"  低和值後次期和值: mean={np.mean(sum_after_low):.1f}, 回歸率={np.mean([1 for s in sum_after_low if s > sum_mean - 0.5*sum_std]) / len(sum_after_low) * 100:.1f}%")

    # === Feature 4: Zone momentum ===
    print("\n  ━━━ FEATURE 4: 區間動量分析 ━━━")
    zone_momentum = {'Z1': [], 'Z2': [], 'Z3': []}
    for d in history[-20:]:
        nums = d['numbers']
        zone_momentum['Z1'].append(sum(1 for n in nums if 1 <= n <= 13))
        zone_momentum['Z2'].append(sum(1 for n in nums if 14 <= n <= 26))
        zone_momentum['Z3'].append(sum(1 for n in nums if 27 <= n <= 39))

    for z, vals in zone_momentum.items():
        trend = "↑" if vals[-3:] > vals[:3] else ("↓" if vals[-3:] < vals[:3] else "→")
        print(f"  {z} 近20期: {vals} → 趨勢{trend}, mean={np.mean(vals):.1f}")

    actual_zones = {'Z1': 2, 'Z2': 1, 'Z3': 2}
    print(f"  本期: Z1={actual_zones['Z1']}, Z2={actual_zones['Z2']}, Z3={actual_zones['Z3']}")

    # === Feature 5: Gap pattern cluster ===
    print("\n  ━━━ FEATURE 5: 遺漏模式聚類 ━━━")
    # For the actual numbers, what was their gap pattern before drawing?
    for n in ACTUAL_LIST:
        gaps_before = []
        last_hit = None
        for i, d in enumerate(reversed(history)):
            if n in d['numbers']:
                if last_hit is not None:
                    gaps_before.append(last_hit - i if last_hit > i else i - last_hit)
                last_hit = i
                if len(gaps_before) >= 5:
                    break
        current_gap = next((i for i, d in enumerate(reversed(history)) if n in d['numbers']), -1)
        print(f"  {n:02d}: 最近5次間隔={gaps_before[:5]}, 當前gap={current_gap}")

    # === Feature 6: Co-occurrence matrix analysis ===
    print("\n  ━━━ FEATURE 6: 共現對分析 ━━━")
    pair_freq = Counter()
    for d in history[-500:]:
        nums = sorted(d['numbers'])
        for pair in combinations(nums, 2):
            pair_freq[pair] += 1

    # Check co-occurrence of actual pairs
    actual_pairs = list(combinations(sorted(ACTUAL_LIST), 2))
    print(f"  實際開獎號碼配對共現次數 (近500期):")
    for pair in actual_pairs:
        f = pair_freq.get(pair, 0)
        expected = 500 * 10 / (39*38)  # Expected pair frequency
        lift = f / expected if expected > 0 else 0
        print(f"    ({pair[0]:02d}, {pair[1]:02d}): {f}次, Lift={lift:.2f}")

    # === Feature 7: Boundary number tendency ===
    print("\n  ━━━ FEATURE 7: 邊界號碼傾向 ━━━")
    boundary = set(range(1, 6)) | set(range(35, 40))
    boundary_counts = []
    for d in history[-200:]:
        bc = sum(1 for n in d['numbers'] if n in boundary)
        boundary_counts.append(bc)
    actual_boundary = sum(1 for n in ACTUAL_LIST if n in boundary)
    print(f"  近200期邊界號碼(1-5,35-39)平均: {np.mean(boundary_counts):.2f}")
    print(f"  本期邊界號碼數: {actual_boundary} ({[n for n in ACTUAL_LIST if n in boundary]})")

    # === Feature 8: Modular pattern ===
    print("\n  ━━━ FEATURE 8: Mod-3/Mod-5 模式 ━━━")
    mod3_counts = Counter(n % 3 for n in ACTUAL_LIST)
    mod5_counts = Counter(n % 5 for n in ACTUAL_LIST)
    print(f"  Mod-3分布: {dict(mod3_counts)}")
    print(f"  Mod-5分布: {dict(mod5_counts)}")

    # Historical mod3 patterns
    mod3_patterns = []
    for d in history[-100:]:
        pattern = tuple(sorted(Counter(n % 3 for n in d['numbers']).items()))
        mod3_patterns.append(pattern)
    mod3_dist = Counter(mod3_patterns)
    actual_mod3_pattern = tuple(sorted(mod3_counts.items()))
    rank_mod3 = sorted(mod3_dist.items(), key=lambda x: -x[1])
    pos = next((i+1 for i, (p, _) in enumerate(rank_mod3) if p == actual_mod3_pattern), -1)
    print(f"  本期Mod-3模式排名: 第{pos}名")

    # === Feature 9: Temperature classification ===
    print("\n  ━━━ FEATURE 9: 號碼溫度全景 ━━━")
    freq_100 = Counter()
    for d in history[-100:]:
        for n in d['numbers']:
            freq_100[n] += 1
    expected = 100 * 5 / 39

    hot = sorted([n for n in range(1,40) if freq_100.get(n,0) > expected * 1.2], key=lambda n: -freq_100[n])
    warm = sorted([n for n in range(1,40) if expected * 0.8 <= freq_100.get(n,0) <= expected * 1.2], key=lambda n: -freq_100[n])
    cold = sorted([n for n in range(1,40) if freq_100.get(n,0) < expected * 0.8], key=lambda n: freq_100[n])

    print(f"  HOT (>{expected*1.2:.0f}): {hot}")
    print(f"  WARM ({expected*0.8:.0f}-{expected*1.2:.0f}): {warm}")
    print(f"  COLD (<{expected*0.8:.0f}): {cold}")

    actual_temp = {}
    for n in ACTUAL_LIST:
        if n in hot: actual_temp[n] = 'HOT'
        elif n in cold: actual_temp[n] = 'COLD'
        else: actual_temp[n] = 'WARM'
    print(f"  本期號碼溫度: {actual_temp}")

    # === Analysis: 2-bet and 3-bet strategy design ===
    print("\n" + "=" * 70)
    print("  2注/3注策略設計可行性分析")
    print("=" * 70)

    # Optimal 2-bet: what combination of 2 methods would have caught more?
    print("\n  ━━━ OPTIMAL 2注覆蓋分析 ━━━")

    # Strategy A: HOT追蹤 + ACB冷號
    hot_bet = sorted(hot[:5])
    acb_bet = [9, 14, 20, 21, 39]  # ACB result
    hot_match = len(set(hot_bet) & ACTUAL)
    acb_match = len(set(acb_bet) & ACTUAL)
    combined_match = len((set(hot_bet) | set(acb_bet)) & ACTUAL)
    print(f"  方案A-HOT+ACB: Hot={hot_bet}({hot_match}), ACB={acb_bet}({acb_match}), 合計={combined_match}")

    # Strategy B: Repeat + Zone balance
    repeat_bet = sorted(list(set(history[-1]['numbers'])) + sorted([n for n in hot if n not in history[-1]['numbers']])[:5-len(history[-1]['numbers'])])[:5]
    repeat_match = len(set(repeat_bet) & ACTUAL)
    print(f"  方案B-延續注: {repeat_bet}({repeat_match})")

    # Strategy C: Frequency mid-range (not too hot, not too cold)
    mid_range = sorted([n for n in range(1,40)],
                       key=lambda n: abs(freq_100.get(n,0) - expected))[:10]
    mid_bet = sorted(mid_range[:5])
    mid_match = len(set(mid_bet) & ACTUAL)
    print(f"  方案C-中間頻率注: {mid_bet}({mid_match})")

    # What would ideal 2-bet look like?
    print(f"\n  本期理想2注覆蓋:")
    # Find best 2 combination of 5 from all numbers
    best_2bet = None
    best_2bet_match = 0
    # Try: bet1=hot oriented, bet2=cold/gap oriented
    # actually let's look at which single-method combinations would work
    print(f"  如果 注1=[02,08,15,XX,XX] + 注2=[29,31,XX,XX,XX] → 完美覆蓋")
    print(f"  關鍵問題: 02是上期延續, 08是近期熱號, 15是中性, 29/31是質數+Z3")

    # === Cross-lottery signal analysis ===
    print("\n" + "=" * 70)
    print("  跨彩種信號分析")
    print("=" * 70)

    try:
        bl_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
        bl_history = sorted(bl_draws, key=lambda x: (x['date'], x['draw']))
        pw_draws = db.get_all_draws(lottery_type='POWER_LOTTO')
        pw_history = sorted(pw_draws, key=lambda x: (x['date'], x['draw']))

        if bl_history:
            last_bl = bl_history[-1]
            bl_nums = set(n for n in last_bl['numbers'] if n <= 39)
            bl_overlap = len(bl_nums & ACTUAL)
            print(f"  大樂透最新: {last_bl['draw']} - {last_bl['numbers']}")
            print(f"  與539開獎重疊(<=39): {sorted(bl_nums & ACTUAL) if bl_overlap else '無'}")

        if pw_history:
            last_pw = pw_history[-1]
            pw_nums = set(n for n in last_pw['numbers'] if n <= 39)
            pw_overlap = len(pw_nums & ACTUAL)
            print(f"  威力彩最新: {last_pw['draw']} - {last_pw['numbers']}")
            print(f"  與539開獎重疊(<=39): {sorted(pw_nums & ACTUAL) if pw_overlap else '無'}")
    except Exception as e:
        print(f"  跨彩種分析失敗: {e}")

    # === Autocorrelation analysis ===
    print("\n" + "=" * 70)
    print("  自相關分析")
    print("=" * 70)

    for n in ACTUAL_LIST:
        # Build binary time series for this number
        binary = [1 if n in d['numbers'] else 0 for d in history[-200:]]
        binary = np.array(binary)
        mean_b = np.mean(binary)
        autocorr = []
        for lag in range(1, 11):
            if len(binary) > lag:
                c = np.corrcoef(binary[:-lag], binary[lag:])[0, 1]
                autocorr.append(round(c, 3))
            else:
                autocorr.append(0)
        significant_lags = [i+1 for i, c in enumerate(autocorr) if abs(c) > 0.15]
        print(f"  {n:02d}: lag1-10 autocorr={autocorr[:5]}... 顯著lag={significant_lags if significant_lags else '無'}")

    # === Markov transition from previous draw ===
    print("\n" + "=" * 70)
    print("  馬可夫轉移分析 (從上期號碼)")
    print("=" * 70)

    prev_nums = history[-1]['numbers']
    transitions = defaultdict(Counter)
    for i in range(len(history)-1):
        for pn in history[i]['numbers']:
            for nn in history[i+1]['numbers']:
                transitions[pn][nn] += 1

    for pn in sorted(prev_nums):
        trans = transitions.get(pn, Counter())
        top5 = trans.most_common(5)
        matched = [n for n, _ in top5 if n in ACTUAL]
        print(f"  {pn:02d} → Top5轉移: {[(n,c) for n,c in top5]}")
        if matched:
            print(f"       命中: {matched}")

    print()


if __name__ == '__main__':
    main()
