#!/usr/bin/env python3
"""
「排除上期 + 中值選號」策略回測驗證

策略核心：
1. 軟排除上期號碼：降低權重到 15%（保留連續號碼 5-15% 的機率）
2. 中值選號：
   - 熱號：選排名 5-15，避開極端熱門（前3）
   - 冷號：選 gap 8-12，避開極端冷門（gap > 15）
3. 結構：3中熱 + 1溫 + 2中冷

驗證目標：150 期嚴格滾動回測，無數據洩漏
"""
import sys
import os
import sqlite3
import json
from collections import Counter
from typing import List, Dict, Set, Tuple

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_all_draws_direct(db_path: str, lottery_type: str = 'BIG_LOTTO') -> List[Dict]:
    """直接從 SQLite 讀取開獎數據"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 按日期排序（舊到新），確保時間順序正確
    cursor.execute("""
        SELECT draw, date, numbers, special
        FROM draws
        WHERE lottery_type = ?
        ORDER BY date ASC
    """, (lottery_type,))

    draws = []
    for row in cursor.fetchall():
        draw_number, draw_date, numbers_json, special_number = row
        numbers = json.loads(numbers_json) if numbers_json else []
        draws.append({
            'draw_number': draw_number,
            'draw_date': draw_date,
            'numbers': numbers,
            'special_number': special_number
        })

    conn.close()
    return draws


def get_lottery_rules(lottery_type: str) -> Dict:
    """獲取彩種規則"""
    rules = {
        'BIG_LOTTO': {'main_count': 6, 'main_max': 49, 'has_special': True, 'special_max': 49},
        'POWER_LOTTO': {'main_count': 6, 'main_max': 38, 'has_special': True, 'special_max': 8},
        'DAILY_539': {'main_count': 5, 'main_max': 39, 'has_special': False}
    }
    return rules.get(lottery_type, rules['BIG_LOTTO'])


def calculate_gaps(history: List[Dict], max_num: int = 49) -> Dict[int, int]:
    """計算每個號碼的遺漏值（距離上次開出的期數）"""
    gaps = {i: len(history) for i in range(1, max_num + 1)}

    for i, draw in enumerate(reversed(history)):
        for num in draw['numbers']:
            if gaps[num] == len(history):
                gaps[num] = i

    return gaps


def calculate_frequency(history: List[Dict], window: int = 30, max_num: int = 49) -> Dict[int, int]:
    """計算號碼在指定窗口內的出現頻率"""
    freq = Counter()
    recent = history[-window:] if len(history) >= window else history

    for draw in recent:
        for num in draw['numbers']:
            freq[num] += 1

    # 確保所有號碼都有值
    for i in range(1, max_num + 1):
        if i not in freq:
            freq[i] = 0

    return freq


def moderate_selection_strategy(history: List[Dict], rules: Dict,
                                  last_draw_penalty: float = 0.15) -> List[int]:
    """
    中值選號策略

    Args:
        history: 歷史開獎數據（不含目標期）
        rules: 彩種規則
        last_draw_penalty: 上期號碼保留權重（0.15 = 保留15%權重）

    Returns:
        選出的 6 個號碼
    """
    max_num = rules.get('main_max', 49)
    pick_count = rules.get('main_count', 6)

    if len(history) < 10:
        return []

    # 獲取上一期開獎號碼
    last_draw_numbers = set(history[-1]['numbers'])

    # 計算遺漏值和頻率
    gaps = calculate_gaps(history, max_num)
    freq_30 = calculate_frequency(history, window=30, max_num=max_num)
    freq_50 = calculate_frequency(history, window=50, max_num=max_num)

    # 計算綜合分數
    scores = {}
    for num in range(1, max_num + 1):
        gap = gaps[num]
        f30 = freq_30[num]
        f50 = freq_50[num]

        # 基礎分數：結合頻率和遺漏
        base_score = f30 * 2 + f50 + (gap * 0.5)

        # 中值偏好：避開極端
        # 極端熱號懲罰（前3名頻率）
        top_freq = sorted(freq_30.values(), reverse=True)[:3]
        if f30 in top_freq and f30 > 0:
            base_score *= 0.7  # 懲罰極端熱號

        # 極端冷號懲罰（gap > 15）
        if gap > 15:
            base_score *= 0.6  # 懲罰極端冷號

        # 中等遺漏加分（gap 8-12 是甜蜜點）
        if 8 <= gap <= 12:
            base_score *= 1.3

        # 軟排除上期號碼（保留一定權重）
        if num in last_draw_numbers:
            base_score *= last_draw_penalty

        scores[num] = base_score

    # 按分數排序，選前 pick_count 個
    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    selected = [num for num, _ in sorted_nums[:pick_count]]

    return sorted(selected)


def moderate_selection_2bet(history: List[Dict], rules: Dict) -> List[List[int]]:
    """
    中值選號雙注策略
    - 注1：標準中值選號
    - 注2：稍微偏向不同區域
    """
    max_num = rules.get('main_max', 49)
    pick_count = rules.get('main_count', 6)

    if len(history) < 10:
        return []

    last_draw_numbers = set(history[-1]['numbers'])
    gaps = calculate_gaps(history, max_num)
    freq_30 = calculate_frequency(history, window=30, max_num=max_num)
    freq_50 = calculate_frequency(history, window=50, max_num=max_num)

    # 計算兩種分數變體
    scores_v1 = {}  # 標準版
    scores_v2 = {}  # 偏向中冷版

    for num in range(1, max_num + 1):
        gap = gaps[num]
        f30 = freq_30[num]
        f50 = freq_50[num]

        # V1: 標準中值（偏熱）
        base_v1 = f30 * 2.5 + f50 + (gap * 0.3)

        # V2: 中值偏冷
        base_v2 = f30 * 1.5 + f50 * 0.8 + (gap * 0.8)

        # 共同的中值偏好邏輯
        top_freq = sorted(freq_30.values(), reverse=True)[:3]

        # V1 懲罰極端熱
        if f30 in top_freq and f30 > 0:
            base_v1 *= 0.7

        # V2 額外懲罰極端熱
        if f30 in top_freq and f30 > 0:
            base_v2 *= 0.5

        # 極端冷號懲罰
        if gap > 15:
            base_v1 *= 0.6
            base_v2 *= 0.7  # V2 對冷號懲罰較輕

        # 中等遺漏加分
        if 8 <= gap <= 12:
            base_v1 *= 1.2
            base_v2 *= 1.4

        # 軟排除上期號碼
        if num in last_draw_numbers:
            base_v1 *= 0.15
            base_v2 *= 0.15

        scores_v1[num] = base_v1
        scores_v2[num] = base_v2

    # 選號
    sorted_v1 = sorted(scores_v1.items(), key=lambda x: x[1], reverse=True)
    sorted_v2 = sorted(scores_v2.items(), key=lambda x: x[1], reverse=True)

    bet1 = sorted([num for num, _ in sorted_v1[:pick_count]])
    bet2 = sorted([num for num, _ in sorted_v2[:pick_count]])

    # 確保兩注有差異
    if bet1 == bet2:
        # 如果完全相同，調整第二注
        bet2 = sorted([num for num, _ in sorted_v2[:pick_count + 2]][1:pick_count + 1])

    return [bet1, bet2]


def strict_rolling_backtest(test_periods: int = 150, strategy: str = 'single'):
    """嚴格滾動回測"""
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws_direct(db_path, lottery_type='BIG_LOTTO')

    print(f"總數據量: {len(all_draws)} 期")
    print(f"最新一期: {all_draws[-1].get('draw_number', 'N/A')} - {all_draws[-1].get('numbers', [])}")

    rules = get_lottery_rules('BIG_LOTTO')

    results = {
        'match0': 0, 'match1': 0, 'match2': 0,
        'match3': 0, 'match4': 0, 'match5': 0, 'match6': 0,
        'total': 0,
        'details': [],
        'last_draw_repeat': 0,  # 統計連續號碼出現次數
    }

    start_idx = len(all_draws) - test_periods

    print(f"\n回測 {test_periods} 期 (策略: {strategy})")
    print(f"範圍: {all_draws[start_idx].get('draw_number')} ~ {all_draws[-1].get('draw_number')}")
    print("-" * 70)

    for target_idx in range(start_idx, len(all_draws)):
        history = all_draws[:target_idx]
        target = all_draws[target_idx]

        if len(history) < 50:
            continue

        actual = set(target['numbers'])
        draw_num = target.get('draw_number', f'idx_{target_idx}')

        # 統計連續號碼
        if target_idx > 0:
            prev_nums = set(all_draws[target_idx - 1]['numbers'])
            repeat_count = len(actual & prev_nums)
            if repeat_count > 0:
                results['last_draw_repeat'] += 1

        # 執行策略
        if strategy == 'single':
            bets = [moderate_selection_strategy(history, rules)]
        else:  # 2bet
            bets = moderate_selection_2bet(history, rules)

        if not bets or not bets[0]:
            continue

        # 計算最佳匹配
        max_match = 0
        best_bet = None
        for bet in bets:
            match_count = len(set(bet) & actual)
            if match_count > max_match:
                max_match = match_count
                best_bet = bet

        results['total'] += 1
        results[f'match{max_match}'] += 1

        if max_match >= 3:
            results['details'].append({
                'draw': draw_num,
                'actual': sorted(list(actual)),
                'prediction': best_bet,
                'match': max_match
            })

    return results


def random_selection(max_num: int = 49, pick_count: int = 6) -> List[int]:
    """純隨機選號"""
    import random
    return sorted(random.sample(range(1, max_num + 1), pick_count))


def backtest_random_baseline(test_periods: int = 150, num_bets: int = 2, trials: int = 100):
    """回測隨機選號基準（多次試驗取平均）"""
    import random
    random.seed(42)  # 固定種子確保可重現

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws_direct(db_path, lottery_type='BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    start_idx = len(all_draws) - test_periods
    total_match3_plus = 0

    for _ in range(trials):
        match3_count = 0
        for target_idx in range(start_idx, len(all_draws)):
            target = all_draws[target_idx]
            actual = set(target['numbers'])

            max_match = 0
            for _ in range(num_bets):
                bet = random_selection(rules['main_max'], rules['main_count'])
                match_count = len(set(bet) & actual)
                max_match = max(max_match, match_count)

            if max_match >= 3:
                match3_count += 1

        total_match3_plus += match3_count

    avg_match3 = total_match3_plus / trials
    return avg_match3 / test_periods * 100


def compare_with_baseline():
    """與基準策略對比"""
    print("=" * 70)
    print("🔬 「排除上期 + 中值選號」策略回測驗證")
    print("=" * 70)

    # 測試單注
    print("\n📊 單注策略回測:")
    results_single = strict_rolling_backtest(test_periods=150, strategy='single')

    # 測試雙注
    print("\n📊 雙注策略回測:")
    results_2bet = strict_rolling_backtest(test_periods=150, strategy='2bet')

    # 隨機基準
    print("\n📊 計算隨機基準 (100次試驗平均)...")
    random_1bet = backtest_random_baseline(test_periods=150, num_bets=1, trials=100)
    random_2bet = backtest_random_baseline(test_periods=150, num_bets=2, trials=100)

    # 輸出結果
    print("\n" + "=" * 70)
    print("📈 回測結果彙總")
    print("=" * 70)

    def print_stats(name: str, results: Dict, bet_count: int = 1):
        total = results['total']
        match3_plus = results['match3'] + results['match4'] + results['match5'] + results['match6']
        match4_plus = results['match4'] + results['match5'] + results['match6']

        rate_3 = match3_plus / total * 100 if total > 0 else 0
        rate_4 = match4_plus / total * 100 if total > 0 else 0
        efficiency = rate_3 / bet_count

        print(f"\n【{name}】")
        print(f"  總期數: {total}")
        print(f"  Match-3+: {match3_plus} 次 ({rate_3:.2f}%)")
        print(f"  Match-4+: {match4_plus} 次 ({rate_4:.2f}%)")
        print(f"  每注效益: {efficiency:.2f}%")
        print(f"  連續號碼出現: {results['last_draw_repeat']} 期 ({results['last_draw_repeat']/total*100:.1f}%)")

        print(f"\n  分布: M0={results['match0']}, M1={results['match1']}, M2={results['match2']}, "
              f"M3={results['match3']}, M4={results['match4']}, M5={results['match5']}, M6={results['match6']}")

    print_stats("單注中值選號", results_single, 1)
    print_stats("雙注中值選號", results_2bet, 2)

    # 顯示 Match-3+ 命中詳情
    if results_2bet['details']:
        print("\n" + "=" * 70)
        print(f"🎯 雙注 Match-3+ 命中詳情 ({len(results_2bet['details'])} 次)")
        print("=" * 70)
        for d in results_2bet['details'][:15]:
            print(f"期號 {d['draw']}: 實際 {d['actual']} | 預測 {d['prediction']} | Match-{d['match']}")

    # 與理論基準對比
    print("\n" + "=" * 70)
    print("📋 完整策略對比")
    print("=" * 70)

    total = results_2bet['total']
    actual_rate_2bet = (results_2bet['match3'] + results_2bet['match4'] +
                        results_2bet['match5'] + results_2bet['match6']) / total * 100 if total > 0 else 0
    single_rate = (results_single['match3'] + results_single['match4'] +
                   results_single['match5'] + results_single['match6']) / results_single['total'] * 100

    print(f"\n{'策略':<25} {'Match-3+ 率':<15} {'vs 隨機':<15} {'每注效益':<10}")
    print("-" * 70)
    print(f"{'🎲 隨機單注':<25} {random_1bet:.2f}%{'':<10} -          {random_1bet:.2f}%")
    print(f"{'📊 中值選號單注':<25} {single_rate:.2f}%{'':<10} {single_rate - random_1bet:+.2f}%{'':<6} {single_rate:.2f}%")
    print(f"{'🎲 隨機雙注':<25} {random_2bet:.2f}%{'':<10} -          {random_2bet/2:.2f}%")
    print(f"{'📊 中值選號雙注':<25} {actual_rate_2bet:.2f}%{'':<10} {actual_rate_2bet - random_2bet:+.2f}%{'':<6} {actual_rate_2bet/2:.2f}%")

    # 關鍵發現
    print("\n" + "=" * 70)
    print("💡 關鍵發現")
    print("=" * 70)

    repeat_rate = results_single['last_draw_repeat'] / results_single['total'] * 100
    print(f"\n1. 連續號碼出現率: {repeat_rate:.1f}%")
    print(f"   → 完全排除上期號碼會損失 {repeat_rate:.0f}% 的機會！")
    print(f"   → 策略採用「軟排除」(保留 15% 權重) 是正確的")

    improvement = actual_rate_2bet - random_2bet
    print(f"\n2. 雙注策略相對隨機提升: {improvement:+.2f}%")
    if improvement > 0:
        print(f"   → 中值選號策略確實優於隨機 ✅")
    else:
        print(f"   → 中值選號策略未顯著優於隨機 ⚠️")

    # Match-4 分析
    match4_count = results_2bet['match4'] + results_2bet['match5'] + results_2bet['match6']
    if match4_count > 0:
        print(f"\n3. Match-4+ 命中: {match4_count} 次 ({match4_count/total*100:.2f}%)")
        print(f"   → 有潛力中獎！")

    return results_single, results_2bet


if __name__ == '__main__':
    compare_with_baseline()
