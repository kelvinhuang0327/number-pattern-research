#!/usr/bin/env python3
"""
威力彩 115000008 期深度特徵分析
"""
import os
import sys
import json
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 實際開獎號碼
ACTUAL_NUMBERS = [3, 8, 12, 26, 32, 38]
ACTUAL_SPECIAL = 4

def get_history_from_json():
    """從 JSON 檔案讀取歷史數據"""
    json_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_history.json')
    with open(json_path, 'r') as f:
        data = json.load(f)
    power_lotto = data.get('data_by_type', {}).get('POWER_LOTTO', [])
    power_lotto.sort(key=lambda x: x['draw'])
    return power_lotto

def analyze_deep_features():
    """深度特徵分析"""
    all_draws = get_history_from_json()
    history = [d for d in all_draws if d['draw'] < "115000008"]

    print("=" * 70)
    print("🔬 威力彩 115000008 期深度特徵分析")
    print("=" * 70)
    print(f"開獎號碼: {ACTUAL_NUMBERS} + 特別號 {ACTUAL_SPECIAL}")
    print()

    # 1. 奇偶分析
    print("【1】奇偶比分析")
    print("-" * 50)
    odd_count = len([n for n in ACTUAL_NUMBERS if n % 2 == 1])
    even_count = 6 - odd_count
    print(f"  本期: 奇{odd_count}:偶{even_count} (1:5)")

    # 統計歷史奇偶分佈
    odd_even_dist = Counter()
    for d in history[-100:]:
        odd = len([n for n in d['numbers'] if n % 2 == 1])
        odd_even_dist[(odd, 6 - odd)] += 1

    print("  近100期奇偶分佈:")
    for (o, e), cnt in sorted(odd_even_dist.items(), key=lambda x: -x[1]):
        pct = cnt / 100 * 100
        mark = "⬅️" if (o, e) == (odd_count, even_count) else ""
        print(f"    奇{o}:偶{e} = {cnt}次 ({pct:.1f}%) {mark}")

    # 2. 尾數分析
    print("\n【2】尾數分析")
    print("-" * 50)
    tails = [n % 10 for n in ACTUAL_NUMBERS]
    tail_dist = Counter(tails)
    print(f"  本期尾數: {tails}")
    print(f"  尾數分佈: {dict(tail_dist)}")

    # 重複尾數
    repeated_tails = [t for t, c in tail_dist.items() if c > 1]
    if repeated_tails:
        print(f"  ⚠️ 重複尾數: {repeated_tails} (出現 {[tail_dist[t] for t in repeated_tails]} 次)")

    # 3. 大小號分析 (1-19 vs 20-38)
    print("\n【3】大小號分析")
    print("-" * 50)
    small = [n for n in ACTUAL_NUMBERS if n <= 19]
    large = [n for n in ACTUAL_NUMBERS if n >= 20]
    print(f"  小號 (1-19): {small} ({len(small)}個)")
    print(f"  大號 (20-38): {large} ({len(large)}個)")
    print(f"  大小比: {len(large)}:{len(small)}")

    # 4. 質數分析
    print("\n【4】質數分析")
    print("-" * 50)
    primes = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37}
    prime_count = len([n for n in ACTUAL_NUMBERS if n in primes])
    prime_nums = [n for n in ACTUAL_NUMBERS if n in primes]
    print(f"  質數: {prime_nums} ({prime_count}個)")
    print(f"  質數/合數比: {prime_count}:{6-prime_count}")

    # 5. 號碼間距分析
    print("\n【5】號碼間距分析")
    print("-" * 50)
    sorted_nums = sorted(ACTUAL_NUMBERS)
    gaps = [sorted_nums[i+1] - sorted_nums[i] for i in range(5)]
    print(f"  號碼序列: {sorted_nums}")
    print(f"  間距序列: {gaps}")
    print(f"  平均間距: {np.mean(gaps):.1f}")
    print(f"  間距標準差: {np.std(gaps):.1f}")

    # 6. 熱號/冷號平衡
    print("\n【6】熱冷號平衡分析")
    print("-" * 50)
    freq_50 = Counter()
    for d in history[-50:]:
        for n in d['numbers']:
            freq_50[n] += 1

    hot_threshold = 8
    cold_threshold = 5
    hot_nums = [n for n in ACTUAL_NUMBERS if freq_50.get(n, 0) >= hot_threshold]
    cold_nums = [n for n in ACTUAL_NUMBERS if freq_50.get(n, 0) <= cold_threshold]
    mid_nums = [n for n in ACTUAL_NUMBERS if cold_threshold < freq_50.get(n, 0) < hot_threshold]

    print(f"  熱號 (≥{hot_threshold}次): {hot_nums}")
    print(f"  冷號 (≤{cold_threshold}次): {cold_nums}")
    print(f"  中性號: {mid_nums}")
    print(f"  熱:中:冷 = {len(hot_nums)}:{len(mid_nums)}:{len(cold_nums)}")

    # 7. 號碼對共現分析
    print("\n【7】號碼對共現分析")
    print("-" * 50)
    pair_freq = Counter()
    for d in history[-100:]:
        for pair in combinations(sorted(d['numbers']), 2):
            pair_freq[pair] += 1

    # 檢查本期號碼對是否有共現歷史
    actual_pairs = list(combinations(sorted(ACTUAL_NUMBERS), 2))
    print("  本期號碼對共現次數:")
    high_cooccurrence = []
    for pair in actual_pairs:
        cnt = pair_freq.get(pair, 0)
        if cnt >= 3:
            high_cooccurrence.append((pair, cnt))
        if cnt > 0:
            print(f"    {pair}: {cnt}次")

    if high_cooccurrence:
        print(f"  ⚠️ 高共現對 (≥3次): {high_cooccurrence}")
    else:
        print("  ℹ️ 無高共現號碼對")

    # 8. 上期連續號分析
    print("\n【8】與上期關聯分析")
    print("-" * 50)
    last_draw = history[-1]
    last_nums = set(last_draw['numbers'])
    repeat_nums = set(ACTUAL_NUMBERS) & last_nums
    print(f"  上期號碼: {sorted(last_nums)}")
    print(f"  本期號碼: {sorted(ACTUAL_NUMBERS)}")
    print(f"  重複號碼: {sorted(repeat_nums)} ({len(repeat_nums)}個)")

    # 計算歷史重複率
    repeat_counts = []
    for i in range(1, len(history)):
        prev = set(history[i-1]['numbers'])
        curr = set(history[i]['numbers'])
        repeat_counts.append(len(prev & curr))

    avg_repeat = np.mean(repeat_counts) if repeat_counts else 0
    print(f"  歷史平均重複: {avg_repeat:.2f}個")

    # 9. AC值分析 (複雜度指標)
    print("\n【9】AC值分析 (組合複雜度)")
    print("-" * 50)
    # AC = 不同差值數量 - (n-1)，其中 n 是選號數量
    diffs = set()
    for i in range(len(ACTUAL_NUMBERS)):
        for j in range(i+1, len(ACTUAL_NUMBERS)):
            diffs.add(abs(ACTUAL_NUMBERS[i] - ACTUAL_NUMBERS[j]))
    ac_value = len(diffs) - (6 - 1)
    print(f"  不同差值: {sorted(diffs)}")
    print(f"  AC值: {ac_value} (差值數量{len(diffs)} - 5)")
    if ac_value >= 8:
        print("  ✅ 高複雜度組合 (AC≥8)")
    elif ac_value >= 5:
        print("  ⚠️ 中等複雜度 (5≤AC<8)")
    else:
        print("  ❌ 低複雜度 (AC<5)")

    # 10. 特別號深度分析
    print("\n【10】特別號深度分析")
    print("-" * 50)
    special_history = [d['special'] for d in history[-30:] if 'special' in d]
    special_freq = Counter(special_history)
    print(f"  近30期特別號: {special_history}")
    print(f"  頻率分佈: {dict(special_freq)}")

    # 檢查特別號是否有週期性
    if special_history:
        last_4_appearance = []
        for i, s in enumerate(special_history):
            if s == ACTUAL_SPECIAL:
                last_4_appearance.append(30 - i)

        print(f"  特別號 {ACTUAL_SPECIAL} 近30期出現位置: {last_4_appearance}")
        if len(last_4_appearance) >= 2:
            gaps = [last_4_appearance[i] - last_4_appearance[i+1] for i in range(len(last_4_appearance)-1)]
            print(f"  出現間隔: {gaps}")

    # 總結
    print("\n" + "=" * 70)
    print("🎯 特徵總結")
    print("=" * 70)

    features = []
    # 收集特殊特徵
    if odd_count <= 2 or odd_count >= 4:
        features.append(f"極端奇偶比 ({odd_count}:{even_count})")
    if len(repeated_tails) > 0:
        features.append(f"重複尾數 {repeated_tails}")
    if ac_value >= 8:
        features.append(f"高AC值 ({ac_value})")
    if len(repeat_nums) == 0:
        features.append("與上期無重複號")
    if len(cold_nums) >= 2:
        features.append(f"含{len(cold_nums)}個冷號")

    if features:
        print("  本期特殊特徵:")
        for f in features:
            print(f"    • {f}")
    else:
        print("  本期無顯著特殊特徵")

if __name__ == '__main__':
    analyze_deep_features()
