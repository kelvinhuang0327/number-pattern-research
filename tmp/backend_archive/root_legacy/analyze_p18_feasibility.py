#!/usr/bin/env python3
"""
P18 可行性研究 - 結構特徵預測能力回測
研究全奇數偵測、Sum反轉、區間預警、間距模式等可否提升預測
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

MAX_NUM = 38

print("=" * 70)
print("  結構特徵預測能力回測 (1500期)")
print("=" * 70)

# Test window
test_start = len(draws) - 1500
test_draws = draws[test_start:]

# ======== Feature 1: Sum反轉 ========
print("\n[Feature 1] Sum 反轉信號 (前期高→下期低)")
sum_reversal_correct = 0
sum_reversal_total = 0
sum_low_threshold = 110
sum_high_threshold = 145

for i in range(test_start + 1, len(draws)):
    prev_sum = sum(draws[i-1]['numbers'])
    curr_sum = sum(draws[i]['numbers'])
    if prev_sum >= sum_high_threshold:
        sum_reversal_total += 1
        if curr_sum <= sum_low_threshold:
            sum_reversal_correct += 1

if sum_reversal_total > 0:
    print(f"  前期 sum >= {sum_high_threshold} 時，下期 sum <= {sum_low_threshold}: "
          f"{sum_reversal_correct}/{sum_reversal_total} = {sum_reversal_correct/sum_reversal_total*100:.1f}%")

# ======== Feature 2: 全奇/全偶 偵測 ========
print("\n[Feature 2] 全奇數出現後的模式")
# After all-odd, next draw odd ratio?
all_odd_indices = []
for i in range(test_start, len(draws)):
    if all(n % 2 == 1 for n in draws[i]['numbers']):
        all_odd_indices.append(i)

if all_odd_indices:
    next_odd_ratios = []
    for idx in all_odd_indices:
        if idx + 1 < len(draws):
            next_nums = draws[idx + 1]['numbers']
            odd_r = sum(1 for n in next_nums if n % 2 == 1) / 6
            next_odd_ratios.append(odd_r)
    print(f"  全奇數出現{len(all_odd_indices)}次")
    print(f"  下一期奇數比例平均: {np.mean(next_odd_ratios):.2f} (基準 0.50)")

# ======== Feature 3: 高奇數比 前兆 ========
print("\n[Feature 3] 高奇數比 (>= 5/6) 作為信號")
high_odd_pct = 0
high_odd_followed_by_high_odd = 0
high_odd_total = 0

for i in range(test_start + 1, len(draws)):
    prev_odd = sum(1 for n in draws[i-1]['numbers'] if n % 2 == 1)
    curr_odd = sum(1 for n in draws[i]['numbers'] if n % 2 == 1)
    if prev_odd >= 5:
        high_odd_total += 1
        if curr_odd >= 5:
            high_odd_followed_by_high_odd += 1

if high_odd_total > 0:
    print(f"  前期奇數 >= 5 時，下期也 >= 5 的比率: "
          f"{high_odd_followed_by_high_odd}/{high_odd_total} = "
          f"{high_odd_followed_by_high_odd/high_odd_total*100:.1f}%")
    # Compare with baseline
    total_high_odd = sum(1 for d in test_draws if sum(1 for n in d['numbers'] if n % 2 == 1) >= 5)
    print(f"  基準 (任意期奇數 >= 5 的比率): {total_high_odd}/{len(test_draws)} = "
          f"{total_high_odd/len(test_draws)*100:.1f}%")

# ======== Feature 4: Zone 缺席→Zone 回歸 ========
print("\n[Feature 4] 區間缺席後的回歸")
for zone_name, zone_range in [("1-9", (1,9)), ("10-19", (10,19)), ("20-29", (20,29)), ("30-38", (30,38))]:
    absent_then_present = 0
    absent_total = 0
    for i in range(test_start + 1, len(draws)):
        prev_has_zone = any(zone_range[0] <= n <= zone_range[1] for n in draws[i-1]['numbers'])
        curr_has_zone = any(zone_range[0] <= n <= zone_range[1] for n in draws[i]['numbers'])
        if not prev_has_zone:
            absent_total += 1
            if curr_has_zone:
                absent_then_present += 1
    if absent_total > 0:
        print(f"  {zone_name} 區缺席後回歸: {absent_then_present}/{absent_total} = "
              f"{absent_then_present/absent_total*100:.1f}%")

# ======== Feature 5: 連續兩期零重複→GAP模式 ========
print("\n[Feature 5] 零重複後的號碼Gap Profile")
zero_repeat_gaps = []
non_zero_gaps = []
for i in range(test_start + 1, len(draws)):
    overlap = set(draws[i]['numbers']) & set(draws[i-1]['numbers'])
    numbers = draws[i]['numbers']
    for n in numbers:
        gap = 0
        for j in range(i-1, max(i-50, test_start), -1):
            gap += 1
            if n in draws[j]['numbers']:
                break
        if len(overlap) == 0:
            zero_repeat_gaps.append(gap)
        else:
            non_zero_gaps.append(gap)

print(f"  零重複時號碼平均間距: {np.mean(zero_repeat_gaps):.1f}")
print(f"  有重複時號碼平均間距: {np.mean(non_zero_gaps):.1f}")

# ======== Feature 6: 跨度偏低信號 ========
print(f"\n[Feature 6] 跨度 (Spread) 偏低的可預測性")
low_spread_cutoff = 22
# When spread is low, what's the zone distribution?
low_spread_zone_dist = Counter()
low_spread_count = 0
for i in range(test_start, len(draws)):
    nums = sorted(draws[i]['numbers'])
    spread = nums[-1] - nums[0]
    if spread <= low_spread_cutoff:
        low_spread_count += 1
        for n in nums:
            if n <= 9: low_spread_zone_dist['1-9'] += 1
            elif n <= 19: low_spread_zone_dist['10-19'] += 1
            elif n <= 29: low_spread_zone_dist['20-29'] += 1
            else: low_spread_zone_dist['30-38'] += 1

print(f"  跨度 <= {low_spread_cutoff} 的期數: {low_spread_count}")
if low_spread_count > 0:
    for zone in ['1-9', '10-19', '20-29', '30-38']:
        avg = low_spread_zone_dist[zone] / low_spread_count
        print(f"    {zone} 區平均個數: {avg:.1f}")

# ======== Feature 7: 2-3注最佳覆蓋策略組合 ========
print(f"\n{'='*70}")
print(f"  2注/3注最佳策略組合回測 (500期)")
print(f"{'='*70}")

# 回測不同策略組合在任意一注命中3+的比例
from tools.power_fourier_rhythm import fourier_rhythm_predict
from tools.predict_power_precision_3bet import generate_power_precision_3bet

test_500_start = len(draws) - 500 - 1  # -1 because P18 is not in DB

def count_matches(predicted_bets, actual_nums):
    """Count max match across all bets"""
    max_match = 0
    any_3plus = False
    for bet in predicted_bets:
        m = len(set(bet) & set(actual_nums))
        max_match = max(max_match, m)
        if m >= 3:
            any_3plus = True
    return max_match, any_3plus

# Method combinations for 2-bet and 3-bet
print("\n  [2注策略] Fourier Rhythm (500期回測):")
fr2_3plus = 0
for i in range(test_500_start, len(draws)):
    history = draws[:i]
    if len(history) < 100:
        continue
    bets = fourier_rhythm_predict(history, n_bets=2, window=500)
    actual_nums = draws[i]['numbers']
    _, hit3 = count_matches(bets, actual_nums)
    if hit3:
        fr2_3plus += 1

total_tests = len(draws) - test_500_start
print(f"    M3+ 率: {fr2_3plus}/{total_tests} = {fr2_3plus/total_tests*100:.2f}%")
print(f"    2注隨機基準: 7.59%")

print("\n  [3注策略] Power Precision (500期回測):")
pp3_3plus = 0
for i in range(test_500_start, len(draws)):
    history = draws[:i]
    if len(history) < 100:
        continue
    bets = generate_power_precision_3bet(history)
    actual_nums = draws[i]['numbers']
    _, hit3 = count_matches(bets, actual_nums)
    if hit3:
        pp3_3plus += 1

print(f"    M3+ 率: {pp3_3plus}/{total_tests} = {pp3_3plus/total_tests*100:.2f}%")
print(f"    3注隨機基準: 11.17%")

# ======== Feature 8: 結構感知附加注 ========
print(f"\n[Feature 8] 結構感知附加注 - 潛在增量")
# Concept: 當偵測到特定結構信號時，生成一注針對性號碼
# Signal: 前期 Sum 偏高 (>= 145) → 生成低號碼為主的注

struct_3plus = 0
struct_total = 0
for i in range(test_500_start + 1, len(draws)):
    prev_sum = sum(draws[i-1]['numbers'])
    if prev_sum >= 145:
        struct_total += 1
        # Generate low-bias bet: pick from 1-25 mostly
        history = draws[:i]
        freq = Counter(n for d in history[-50:] for n in d['numbers'] if n <= 25)
        candidates = sorted(range(1, 26), key=lambda x: freq.get(x, 0))
        # Mix cold and medium
        bet = sorted(candidates[:3] + candidates[6:9])
        actual_nums = draws[i]['numbers']
        match = len(set(bet) & set(actual_nums))
        if match >= 3:
            struct_3plus += 1

if struct_total > 0:
    print(f"  高Sum信號觸發時，結構注 M3+: {struct_3plus}/{struct_total} = "
          f"{struct_3plus/struct_total*100:.1f}%")
    print(f"  單注隨機基準: 3.87%")

# ======== Feature 9: Neighbor cluster detection ========
print(f"\n[Feature 9] 鄰號群聚偵測 (Gap=2 pairs)")
# When we have 2+ numbers in Fourier top 12 that are gap-2 pairs, is hit rate better?
gap2_boost_3plus = 0
gap2_boost_total = 0
no_gap2_3plus = 0
no_gap2_total = 0

for i in range(test_500_start, len(draws)):
    history = draws[:i]
    if len(history) < 100:
        continue
    bets = fourier_rhythm_predict(history, n_bets=2, window=500)
    all_nums = sorted(set(n for b in bets for n in b))
    
    has_gap2 = False
    for j in range(len(all_nums) - 1):
        if all_nums[j+1] - all_nums[j] == 2:
            has_gap2 = True
            break
    
    actual_nums = draws[i]['numbers']
    _, hit3 = count_matches(bets, actual_nums)
    
    if has_gap2:
        gap2_boost_total += 1
        if hit3:
            gap2_boost_3plus += 1
    else:
        no_gap2_total += 1
        if hit3:
            no_gap2_3plus += 1

if gap2_boost_total > 0 and no_gap2_total > 0:
    print(f"  有Gap-2對時 M3+: {gap2_boost_3plus}/{gap2_boost_total} = "
          f"{gap2_boost_3plus/gap2_boost_total*100:.1f}%")
    print(f"  無Gap-2對時 M3+: {no_gap2_3plus}/{no_gap2_total} = "
          f"{no_gap2_3plus/no_gap2_total*100:.1f}%")

print(f"\n{'='*70}")
print(f"  分析完成")
print(f"{'='*70}")
