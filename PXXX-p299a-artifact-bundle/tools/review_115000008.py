#!/usr/bin/env python3
"""
威力彩 115000008 期檢討分析腳本
開獎號碼：03 08 12 26 32 38 + 特別號 04
"""
import os
import sys
import json
import sqlite3
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

# 實際開獎號碼
ACTUAL_NUMBERS = [3, 8, 12, 26, 32, 38]
ACTUAL_SPECIAL = 4
DRAW_NUMBER = "115000008"

def get_history_from_json():
    """從 JSON 檔案讀取歷史數據"""
    json_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_history.json')
    with open(json_path, 'r') as f:
        data = json.load(f)

    power_lotto = data.get('data_by_type', {}).get('POWER_LOTTO', [])
    # 按期號排序（舊→新）
    power_lotto.sort(key=lambda x: x['draw'])
    return power_lotto

def get_history_before_target(all_draws, target_draw="115000008"):
    """獲取目標期號之前的歷史數據（防止數據洩漏）"""
    history = []
    for d in all_draws:
        if d['draw'] >= target_draw:
            break
        history.append(d)
    return history

# ==================== 各種預測方法 ====================

def frequency_predict(history, n=6, window=50):
    """頻率法：選近期出現最多的號碼"""
    recent = history[-window:]
    freq = Counter()
    for d in recent:
        for n_ in d['numbers']:
            freq[n_] += 1
    return [n for n, _ in freq.most_common(n)]

def cold_number_predict(history, n=6, window=100):
    """冷號法：選近期出現最少的號碼"""
    recent = history[-window:]
    freq = Counter()
    for d in recent:
        for n_ in d['numbers']:
            freq[n_] += 1

    all_nums = list(range(1, 39))
    sorted_nums = sorted(all_nums, key=lambda x: freq.get(x, 0))
    return sorted_nums[:n]

def deviation_predict(history, n=6, window=100):
    """偏差法：選偏離期望值最多的號碼"""
    recent = history[-window:]
    freq = Counter()
    for d in recent:
        for n_ in d['numbers']:
            freq[n_] += 1

    expected = len(recent) * 6 / 38
    deviations = {}
    for num in range(1, 39):
        actual = freq.get(num, 0)
        deviations[num] = expected - actual

    sorted_nums = sorted(deviations.items(), key=lambda x: x[1], reverse=True)
    return [n for n, _ in sorted_nums[:n]]

def markov_predict(history, n=6, window=50):
    """馬可夫法：基於轉移機率"""
    recent = history[-window:]

    # 計算號碼出現後，下一期出現的機率
    transition = {}
    for i in range(len(recent) - 1):
        current = set(recent[i]['numbers'])
        next_nums = set(recent[i + 1]['numbers'])
        for num in current:
            if num not in transition:
                transition[num] = Counter()
            for next_num in next_nums:
                transition[num][next_num] += 1

    # 基於上一期的號碼預測
    last_nums = set(recent[-1]['numbers'])
    scores = Counter()
    for num in last_nums:
        if num in transition:
            for next_num, count in transition[num].items():
                scores[next_num] += count

    return [n for n, _ in scores.most_common(n)]

def apriori_predict(history, n=6, window=100):
    """關聯規則法：找經常一起出現的號碼對"""
    recent = history[-window:]
    pair_freq = Counter()
    for d in recent:
        nums = d['numbers']
        for pair in combinations(sorted(nums), 2):
            pair_freq[pair] += 1

    # 用最高頻的 pair 來擴展
    top_pairs = pair_freq.most_common(3)
    result = set()
    for pair, _ in top_pairs:
        result.add(pair[0])
        result.add(pair[1])

    # 補足到 n 個
    freq = Counter()
    for d in recent:
        for num in d['numbers']:
            freq[num] += 1

    for num, _ in freq.most_common():
        if len(result) >= n:
            break
        result.add(num)

    return sorted(list(result))[:n]

def zone_balance_predict(history, n=6, window=100):
    """區間平衡法：確保各區間都有覆蓋"""
    recent = history[-window:]

    # 分成 4 個區間
    zones = {
        1: list(range(1, 11)),    # 1-10
        2: list(range(11, 21)),   # 11-20
        3: list(range(21, 31)),   # 21-30
        4: list(range(31, 39))    # 31-38
    }

    # 計算每區頻率
    zone_freq = {i: Counter() for i in range(1, 5)}
    for d in recent:
        for num in d['numbers']:
            for z, nums in zones.items():
                if num in nums:
                    zone_freq[z][num] += 1
                    break

    # 每區選最高頻的
    result = []
    zone_picks = [2, 1, 2, 1]  # 從各區選 2, 1, 2, 1 個
    for z, pick_count in enumerate(zone_picks, 1):
        top_nums = [n for n, _ in zone_freq[z].most_common(pick_count)]
        result.extend(top_nums)

    return sorted(result)[:n]

def consecutive_analysis_predict(history, n=6, window=50):
    """連號分析法"""
    recent = history[-window:]

    # 統計連號出現頻率
    consecutive_freq = Counter()
    for d in recent:
        nums = sorted(d['numbers'])
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] == 1:
                consecutive_freq[(nums[i], nums[i + 1])] += 1

    # 用最高頻的連號作為種子
    result = set()
    for pair, _ in consecutive_freq.most_common(2):
        result.add(pair[0])
        result.add(pair[1])

    # 補足
    freq = Counter()
    for d in recent:
        for num in d['numbers']:
            freq[num] += 1

    for num, _ in freq.most_common():
        if len(result) >= n:
            break
        result.add(num)

    return sorted(list(result))[:n]

def gap_analysis_predict(history, n=6, window=100):
    """遺漏值分析法：選遺漏期數最長的號碼"""
    recent = history[-window:]

    # 計算每個號碼的遺漏期數
    gaps = {}
    for num in range(1, 39):
        last_appear = -1
        for i, d in enumerate(recent):
            if num in d['numbers']:
                last_appear = i
        gaps[num] = len(recent) - 1 - last_appear if last_appear >= 0 else len(recent)

    sorted_nums = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
    return [n for n, _ in sorted_nums[:n]]

def predict_special_v3(history, top_n=1):
    """V3 特別號預測"""
    recent = history[-50:]
    special_freq = Counter()
    for d in recent:
        if 'special' in d and d['special']:
            special_freq[d['special']] += 1

    expected = len(recent) / 8
    bias_scores = {}
    for n in range(1, 9):
        actual = special_freq.get(n, 0)
        bias_scores[n] = expected - actual + 1

    sorted_nums = sorted(bias_scores.items(), key=lambda x: x[1], reverse=True)
    return [n for n, _ in sorted_nums[:top_n]]

def fourier_rhythm_predict(history, n=6, window=500):
    """傅立葉節奏法"""
    from scipy.fft import fft, fftfreq

    h_slice = history[-window:] if len(history) > window else history
    actual_window = len(h_slice)

    bitstreams = {i: np.zeros(actual_window) for i in range(1, 39)}
    for idx, d in enumerate(h_slice):
        for num in d['numbers']:
            if num <= 38:
                bitstreams[num][idx] = 1

    scores = np.zeros(39)
    for num in range(1, 39):
        if sum(bitstreams[num]) < 2:
            continue
        yf = fft(bitstreams[num] - np.mean(bitstreams[num]))
        xf = fftfreq(actual_window, 1)
        idx_ = np.where(xf > 0)
        pos_xf = xf[idx_]
        pos_yf = np.abs(yf[idx_])

        if len(pos_yf) == 0:
            continue

        peak_idx = np.argmax(pos_yf)
        freq = pos_xf[peak_idx]

        if freq == 0:
            continue

        period = 1 / freq
        if 2 < period < actual_window / 2:
            last_hit = np.where(bitstreams[num] == 1)[0][-1]
            gap = (actual_window - 1) - last_hit
            dist_to_peak = abs(gap - period)
            scores[num] = 1.0 / (dist_to_peak + 1.0)

    sorted_nums = np.argsort(scores[1:])[::-1] + 1
    return sorted_nums[:n].tolist()

def ensemble_predict(history, n=6, methods=None):
    """集成預測：多方法投票"""
    if methods is None:
        methods = [
            ('frequency', frequency_predict),
            ('cold', cold_number_predict),
            ('deviation', deviation_predict),
            ('markov', markov_predict),
            ('zone', zone_balance_predict),
        ]

    votes = Counter()
    for name, method in methods:
        try:
            nums = method(history, n=10)
            for num in nums:
                votes[num] += 1
        except:
            pass

    return [n for n, _ in votes.most_common(n)]

# ==================== 分析函數 ====================

def calculate_match(predicted, actual):
    """計算命中數"""
    return len(set(predicted) & set(actual))

def analyze_number_features(nums):
    """分析號碼特徵"""
    features = {
        'sum': sum(nums),
        'avg': sum(nums) / len(nums),
        'odd_count': len([n for n in nums if n % 2 == 1]),
        'even_count': len([n for n in nums if n % 2 == 0]),
        'zone_distribution': {},
        'consecutive_pairs': 0,
        'max_gap': max([nums[i+1] - nums[i] for i in range(len(nums)-1)]),
        'min_gap': min([nums[i+1] - nums[i] for i in range(len(nums)-1)]),
    }

    # 區間分佈
    zones = {1: (1, 10), 2: (11, 20), 3: (21, 30), 4: (31, 38)}
    for z, (low, high) in zones.items():
        features['zone_distribution'][z] = len([n for n in nums if low <= n <= high])

    # 連號
    sorted_nums = sorted(nums)
    for i in range(len(sorted_nums) - 1):
        if sorted_nums[i + 1] - sorted_nums[i] == 1:
            features['consecutive_pairs'] += 1

    return features

def main():
    print("=" * 70)
    print("🎯 威力彩第 115000008 期 檢討會議")
    print("=" * 70)
    print(f"\n📊 開獎號碼: {ACTUAL_NUMBERS}")
    print(f"🎱 特別號: {ACTUAL_SPECIAL}")
    print()

    # 讀取歷史數據
    all_draws = get_history_from_json()
    history = get_history_before_target(all_draws, DRAW_NUMBER)

    print(f"📈 分析基準: 使用 {len(history)} 期歷史數據 (到 115000007)")
    print("-" * 70)

    # 開獎號碼特徵分析
    print("\n【一】開獎號碼特徵分析")
    print("-" * 40)
    features = analyze_number_features(sorted(ACTUAL_NUMBERS))
    print(f"  總和: {features['sum']} (期望 117, 偏差 {features['sum'] - 117:+d})")
    print(f"  平均: {features['avg']:.1f}")
    print(f"  奇偶比: {features['odd_count']}:{features['even_count']}")
    print(f"  區間分佈: Z1={features['zone_distribution'][1]}, Z2={features['zone_distribution'][2]}, Z3={features['zone_distribution'][3]}, Z4={features['zone_distribution'][4]}")
    print(f"  連號對數: {features['consecutive_pairs']}")
    print(f"  號碼間距: 最大={features['max_gap']}, 最小={features['min_gap']}")

    # 各方法預測結果
    print("\n【二】各預測方法結果比較")
    print("-" * 70)

    methods = [
        ('頻率法 (W50)', lambda h: frequency_predict(h, window=50)),
        ('頻率法 (W100)', lambda h: frequency_predict(h, window=100)),
        ('冷號法 (W50)', lambda h: cold_number_predict(h, window=50)),
        ('冷號法 (W100)', lambda h: cold_number_predict(h, window=100)),
        ('偏差法 (W100)', lambda h: deviation_predict(h, window=100)),
        ('馬可夫法', markov_predict),
        ('關聯規則 (Apriori)', apriori_predict),
        ('區間平衡法', zone_balance_predict),
        ('遺漏值分析', gap_analysis_predict),
        ('連號分析', consecutive_analysis_predict),
        ('集成投票', ensemble_predict),
    ]

    # 嘗試加載傅立葉
    try:
        methods.append(('傅立葉節奏', fourier_rhythm_predict))
    except:
        pass

    results = []
    for name, method in methods:
        try:
            predicted = method(history)
            match = calculate_match(predicted, ACTUAL_NUMBERS)
            results.append((name, predicted, match))
            match_indicator = "⭐" * match if match > 0 else "❌"
            print(f"  {name:20s}: {predicted} -> 命中 {match}/6 {match_indicator}")
        except Exception as e:
            print(f"  {name:20s}: 錯誤 - {e}")

    # 找最佳方法
    print("\n【三】最佳預測方法")
    print("-" * 40)
    results.sort(key=lambda x: x[2], reverse=True)
    best = results[0]
    print(f"  🏆 最佳方法: {best[0]}")
    print(f"  📊 預測號碼: {best[1]}")
    print(f"  ✅ 命中數: {best[2]}/6")

    # 命中的號碼
    hit_nums = set(best[1]) & set(ACTUAL_NUMBERS)
    miss_nums = set(ACTUAL_NUMBERS) - set(best[1])
    print(f"  🎯 命中號碼: {sorted(hit_nums)}")
    print(f"  ❌ 遺漏號碼: {sorted(miss_nums)}")

    # 特別號預測
    print("\n【四】特別號預測分析")
    print("-" * 40)
    special_pred = predict_special_v3(history, top_n=3)
    special_match = "✅" if ACTUAL_SPECIAL in special_pred else "❌"
    print(f"  V3 預測 Top-3: {special_pred}")
    print(f"  實際特別號: {ACTUAL_SPECIAL} {special_match}")

    # 分析近期特別號
    recent_specials = [d['special'] for d in history[-20:] if 'special' in d]
    print(f"  近 20 期特別號: {recent_specials}")

    # 未命中號碼分析
    print("\n【五】未命中號碼分析")
    print("-" * 40)

    for num in sorted(ACTUAL_NUMBERS):
        # 計算近期頻率
        freq_50 = sum(1 for d in history[-50:] if num in d['numbers'])
        freq_100 = sum(1 for d in history[-100:] if num in d['numbers'])

        # 計算遺漏期數
        gap = 0
        for d in reversed(history):
            if num in d['numbers']:
                break
            gap += 1

        freq_rank = "熱號" if freq_50 > 7 else "冷號" if freq_50 < 5 else "中性"
        print(f"  號碼 {num:02d}: W50頻率={freq_50:2d}, W100頻率={freq_100:2d}, 遺漏={gap:2d}期, [{freq_rank}]")

    # 統計未被預測到的原因
    print("\n【六】遺漏原因分析")
    print("-" * 40)

    # 檢查每個未命中號碼
    all_predicted = set()
    for _, pred, _ in results:
        all_predicted.update(pred)

    never_predicted = set(ACTUAL_NUMBERS) - all_predicted
    if never_predicted:
        print(f"  ⚠️ 所有方法都未預測到的號碼: {sorted(never_predicted)}")
        for num in never_predicted:
            freq_50 = sum(1 for d in history[-50:] if num in d['numbers'])
            gap = 0
            for d in reversed(history):
                if num in d['numbers']:
                    break
                gap += 1
            print(f"     {num:02d}: 近50期出現{freq_50}次, 遺漏{gap}期")
    else:
        print("  ✅ 所有開獎號碼至少被一種方法預測到")

    # 雙注分析
    print("\n【七】雙注策略分析")
    print("-" * 40)

    # 組合最佳雙注
    bet1 = frequency_predict(history, n=6, window=50)
    bet2 = cold_number_predict(history, n=6, window=100)

    combined_coverage = set(bet1) | set(bet2)
    combined_match = len(combined_coverage & set(ACTUAL_NUMBERS))

    print(f"  注1 (熱號 W50): {bet1} -> 命中 {calculate_match(bet1, ACTUAL_NUMBERS)}/6")
    print(f"  注2 (冷號 W100): {bet2} -> 命中 {calculate_match(bet2, ACTUAL_NUMBERS)}/6")
    print(f"  雙注覆蓋: {len(combined_coverage)} 個號碼")
    print(f"  雙注命中: {combined_match}/6")

    # 最佳雙注組合搜索
    print("\n  🔍 最佳雙注組合搜索:")
    best_combo = None
    best_combo_match = 0

    for i, (name1, pred1, _) in enumerate(results):
        for j, (name2, pred2, _) in enumerate(results):
            if i >= j:
                continue
            combined = set(pred1) | set(pred2)
            match = len(combined & set(ACTUAL_NUMBERS))
            if match > best_combo_match:
                best_combo_match = match
                best_combo = (name1, pred1, name2, pred2, match)

    if best_combo:
        print(f"     組合: {best_combo[0]} + {best_combo[2]}")
        print(f"     注1: {best_combo[1]}")
        print(f"     注2: {best_combo[3]}")
        print(f"     命中: {best_combo[4]}/6")

    # 總結
    print("\n" + "=" * 70)
    print("【總結】")
    print("=" * 70)

    # 列出本期特殊特徵
    print("\n📌 本期特殊特徵:")
    if features['consecutive_pairs'] > 0:
        print(f"  - 出現連號 ({features['consecutive_pairs']} 組)")
    if features['zone_distribution'][1] >= 2:
        print(f"  - 小號區 (1-10) 集中: {[n for n in ACTUAL_NUMBERS if 1<=n<=10]}")
    if features['sum'] < 100 or features['sum'] > 140:
        print(f"  - 總和偏離正常範圍: {features['sum']}")

    print("\n📌 改進建議:")
    print("  1. 加強連號預測邏輯")
    print("  2. 考慮區間覆蓋的動態調整")
    print("  3. 結合多窗口分析提高穩定性")

if __name__ == '__main__':
    main()
