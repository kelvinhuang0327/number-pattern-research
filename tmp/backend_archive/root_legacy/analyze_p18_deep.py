#!/usr/bin/env python3
"""
P18 深度結構分析 - 尋找遺漏的可識別特徵
"""
import sys, os, numpy as np
from collections import Counter
from itertools import combinations

sys.path.insert(0, '.')
sys.path.insert(0, 'lottery_api')
from database import DatabaseManager

db_path = os.path.join('lottery_api', 'data', 'lottery_v2.db')
db = DatabaseManager(db_path)
draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))

actual = [7, 9, 11, 23, 25, 29]
actual_special = 5

print("=" * 70)
print("  P18 結構特徵深度分析")
print("=" * 70)

# ======== 1. All-odd analysis ========
print("\n[1] 全奇數組合歷史分析:")
all_odd_count = 0
total = len(draws)
for d in draws:
    nums = d['numbers']
    if all(n % 2 == 1 for n in nums):
        all_odd_count += 1
print(f"  歷史全奇數出現次數: {all_odd_count}/{total} = {all_odd_count/total*100:.2f}%")
print(f"  理論機率 (38選6): C(19,6)/C(38,6) = {27132/2760681*100:.2f}%")
# Find last few all-odd draws
print(f"  近期全奇數開獎:")
count = 0
for d in reversed(draws):
    if all(n % 2 == 1 for n in d['numbers']):
        print(f"    {d['draw']} {d['date']}: {d['numbers']}")
        count += 1
        if count >= 5:
            break

# ======== 2. Low-sum tendency ========
print(f"\n[2] 總和偏低分析 (P18 sum=104):")
sums = [sum(d['numbers']) for d in draws]
low_sum_count = sum(1 for s in sums if s <= 104)
print(f"  sum <= 104 的比例: {low_sum_count}/{total} = {low_sum_count/total*100:.1f}%")
# Sum after very high sum
high_prev_count = 0
followed_by_low = 0
for i in range(1, len(draws)):
    prev_sum = sum(draws[i-1]['numbers'])
    curr_sum = sum(draws[i]['numbers'])
    if prev_sum >= 150:
        high_prev_count += 1
        if curr_sum <= 110:
            followed_by_low += 1
print(f"  前期 sum >= 150 後，下期 sum <= 110 的比例: {followed_by_low}/{high_prev_count} = {followed_by_low/high_prev_count*100:.1f}% (P17 sum=154)")

# ======== 3. Zone 30-38 absence ========
print(f"\n[3] 30-38區間缺席分析:")
no_high_zone = 0
for d in draws:
    if not any(30 <= n <= 38 for n in d['numbers']):
        no_high_zone += 1
print(f"  30-38區完全缺席: {no_high_zone}/{total} = {no_high_zone/total*100:.1f}%")

# ======== 4. Consecutive pair patterns ========
print(f"\n[4] 連號/近鄰對分析:")
# P18 has (7,9), (9,11), (23,25) - three pairs with gap=2
pair_gap2_count = Counter()
for d in draws:
    nums = sorted(d['numbers'])
    pairs = 0
    for i in range(len(nums) - 1):
        if nums[i+1] - nums[i] == 2:
            pairs += 1
    pair_gap2_count[pairs] += 1
print(f"  間距=2 的對數分布: {dict(sorted(pair_gap2_count.items()))}")

# Triple near-consecutive
triple_near = 0
for d in draws:
    nums = sorted(d['numbers'])
    for i in range(len(nums) - 2):
        if nums[i+2] - nums[i] <= 4:  # 3 numbers within 4 range
            triple_near += 1
            break
print(f"  含3個號碼在4點範圍內: {triple_near}/{total} = {triple_near/total*100:.1f}%")

# ======== 5. P17→P18 zero repeat ========
print(f"\n[5] 零重複分析:")
zero_repeat = 0
for i in range(1, len(draws)):
    if not set(draws[i]['numbers']) & set(draws[i-1]['numbers']):
        zero_repeat += 1
print(f"  連續兩期零重複: {zero_repeat}/{total-1} = {zero_repeat/(total-1)*100:.1f}%")

# ======== 6. Gap clustering ========
print(f"\n[6] 間距群聚分析:")
print(f"  P18 各號碼間距: 7→6期, 9→13期, 11→10期, 23→2期, 25→4期, 29→7期")
print(f"  間距中位數: {np.median([6,13,10,2,4,7]):.0f}")
print(f"  間距分布: 短(<=5): 2個, 中(6-10): 3個, 長(>10): 1個")

# Historical gap analysis for winning numbers
gap_wins = []
for i in range(100, len(draws)):
    for n in draws[i]['numbers']:
        gap = 0
        for j in range(i-1, max(i-50, 0), -1):
            gap += 1
            if n in draws[j]['numbers']:
                break
        gap_wins.append(gap)

gap_counter = Counter()
for g in gap_wins:
    bucket = (g - 1) // 3
    gap_counter[bucket] += 1
print(f"  歷史中獎號碼間距分布 (每3期一桶):")
for k in sorted(gap_counter.keys())[:8]:
    label = f"{k*3+1}-{(k+1)*3}"
    pct = gap_counter[k] / len(gap_wins) * 100
    bar = "█" * int(pct)
    print(f"    {label:>6s}: {pct:5.1f}% {bar}")

# ======== 7. Spread/Range analysis ========
print(f"\n[7] 號碼跨度分析:")
spread = actual[-1] - actual[0]
print(f"  P18 跨度: {spread} (7 → 29)")
spreads = [max(d['numbers']) - min(d['numbers']) for d in draws]
avg_spread = np.mean(spreads)
std_spread = np.std(spreads)
print(f"  歷史平均跨度: {avg_spread:.1f} ± {std_spread:.1f}")
print(f"  P18 z-score: {(spread - avg_spread) / std_spread:.2f}")
small_spread = sum(1 for s in spreads if s <= spread)
print(f"  跨度 <= {spread}: {small_spread}/{total} = {small_spread/total*100:.1f}%")

# ======== 8. Special number pattern ========
print(f"\n[8] 特別號週期分析:")
sp_history = [d.get('special', 0) for d in draws[-50:]]
for target in range(1, 9):
    gaps = []
    last_pos = None
    for i, sp in enumerate(sp_history):
        if sp == target:
            if last_pos is not None:
                gaps.append(i - last_pos)
            last_pos = i
    avg_gap = np.mean(gaps) if gaps else float('inf')
    print(f"  特別號 {target}: 近50期出現{sp_history.count(target)}次, 平均間距={avg_gap:.1f}")

# ======== 9. Tail number uniformity ========
print(f"\n[9] P18 尾數特異性:")
print(f"  P18 尾數: [7,9,1,3,5,9] - 全部為奇數尾!")
print(f"  這等同於全奇數組合，因為尾數奇偶決定號碼奇偶")

# ======== 10. Sum-shift pattern ========
print(f"\n[10] 總和偏移模式:")
last_5_sums = [sum(draws[-(5-i)]['numbers']) for i in range(5)]
print(f"  近5期 sum: {last_5_sums}")
print(f"  P18 sum: 104")
diffs = []
for i in range(1, len(last_5_sums)):
    diffs.append(last_5_sums[i] - last_5_sums[i-1])
print(f"  近5期 sum 差值: {diffs}")
print(f"  P17→P18 差值: {104 - last_5_sums[-1]}")

# ======== 11. Multi-draw coverage potential ========
print(f"\n[11] 多注覆蓋機制分析:")
# If we used 3 bets with different strategies
methods_combined = set()
# FR: 7, 25, 23
# P0: 11, 23
# Markov: 23
# Cold: 23
# Hot: 11
all_predicted = {7, 25, 23, 11}
missing = set(actual) - all_predicted
print(f"  所有方法已覆蓋: {sorted(all_predicted)}")
print(f"  所有方法未覆蓋: {sorted(missing)} → 9, 29")
print(f"  9 和 29 的特徵:")
# Why 9 and 29 were missed
for num in [9, 29]:
    recent = draws[-50:]
    freq = sum(1 for d in recent for n in d['numbers'] if n == num)
    expected = len(recent) * 6 / 38
    dev = freq - expected
    print(f"    號碼{num}: 50期頻率={freq}, 期望={expected:.1f}, 偏差={dev:.1f}")
    # Gap
    for i in range(len(draws)-1, -1, -1):
        if num in draws[i]['numbers']:
            gap = len(draws) - 1 - i
            print(f"    號碼{num}: 間距={gap}期, 上次出現: {draws[i]['draw']}")
            break

# ======== 12. Regime detection ========
print(f"\n[12] 開獎 Regime 偵測:")
recent_50 = draws[-50:]
avg_sums_5 = []
for i in range(0, 50, 5):
    chunk = recent_50[i:i+5]
    avg_sums_5.append(np.mean([sum(d['numbers']) for d in chunk]))
print(f"  近50期每5期 avg sum: {[f'{s:.0f}' for s in avg_sums_5]}")

# Odd/even ratio trend
for window_start in [0, 10, 20, 30, 40]:
    chunk = recent_50[window_start:window_start+10]
    total_odd = sum(sum(1 for n in d['numbers'] if n % 2 == 1) for d in chunk)
    total_nums = len(chunk) * 6
    print(f"  期{window_start+1}-{window_start+10}: 奇數比例={total_odd/total_nums*100:.0f}%")
