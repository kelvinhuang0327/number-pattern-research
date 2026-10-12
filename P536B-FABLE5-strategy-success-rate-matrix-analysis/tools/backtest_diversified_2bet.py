#!/usr/bin/env python3
"""
真正多樣化的雙注策略回測

問題：參數調整對結果影響不大（都是 2.67%）
解決：使用兩種完全不同的選號邏輯

策略設計：
- 注1（中熱策略）：選中等熱門號碼，軟排除上期
- 注2（回歸策略）：選即將回歸的冷號 + 穩定溫號

目標：兩注形成互補，提高整體命中率
"""
import sys
import os
import sqlite3
import json
import random
from collections import Counter
from typing import List, Dict, Set

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_all_draws_direct(db_path: str, lottery_type: str = 'BIG_LOTTO') -> List[Dict]:
    """直接從 SQLite 讀取開獎數據"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers, special
        FROM draws WHERE lottery_type = ? ORDER BY date ASC
    """, (lottery_type,))
    draws = []
    for row in cursor.fetchall():
        draw_number, draw_date, numbers_json, special_number = row
        numbers = json.loads(numbers_json) if numbers_json else []
        draws.append({
            'draw_number': draw_number,
            'numbers': numbers,
        })
    conn.close()
    return draws


def calculate_gaps(history: List[Dict], max_num: int = 49) -> Dict[int, int]:
    """計算遺漏值"""
    gaps = {i: len(history) for i in range(1, max_num + 1)}
    for i, draw in enumerate(reversed(history)):
        for num in draw['numbers']:
            if gaps[num] == len(history):
                gaps[num] = i
    return gaps


def calculate_frequency(history: List[Dict], window: int, max_num: int = 49) -> Dict[int, int]:
    """計算頻率"""
    freq = Counter()
    recent = history[-window:] if len(history) >= window else history
    for draw in recent:
        for num in draw['numbers']:
            freq[num] += 1
    for i in range(1, max_num + 1):
        if i not in freq:
            freq[i] = 0
    return freq


def strategy_moderate_hot(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """
    注1：中熱策略
    - 選擇中等熱門號碼（排名 5-15）
    - 軟排除上期號碼（保留 15%）
    - 避開極端冷號
    """
    if len(history) < 30:
        return []

    last_draw = set(history[-1]['numbers'])
    gaps = calculate_gaps(history, max_num)
    freq = calculate_frequency(history, window=30, max_num=max_num)

    # 按頻率排名
    freq_sorted = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    freq_rank = {num: rank for rank, (num, _) in enumerate(freq_sorted, 1)}

    scores = {}
    for num in range(1, max_num + 1):
        rank = freq_rank[num]
        gap = gaps[num]

        # 基礎分：中等排名加分
        if 5 <= rank <= 15:
            score = 100 + (15 - rank) * 5  # 排名 5 得分最高
        elif rank < 5:
            score = 60  # 太熱，降低
        else:
            score = 80 - rank  # 排名越後越低

        # 遺漏調整
        if gap > 15:
            score *= 0.6  # 極端冷號懲罰
        elif 6 <= gap <= 12:
            score *= 1.2  # 中等遺漏加分

        # 軟排除上期
        if num in last_draw:
            score *= 0.15

        scores[num] = score

    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted([num for num, _ in sorted_nums[:pick_count]])


def strategy_comeback(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """
    注2：回歸策略
    - 選擇中等遺漏的「即將回歸」號碼（gap 8-14）
    - 搭配穩定溫號（頻率中等）
    - 完全排除上期號碼（回歸邏輯）
    """
    if len(history) < 30:
        return []

    last_draw = set(history[-1]['numbers'])
    gaps = calculate_gaps(history, max_num)
    freq = calculate_frequency(history, window=50, max_num=max_num)

    scores = {}
    for num in range(1, max_num + 1):
        gap = gaps[num]
        f = freq[num]

        # 回歸分數：中等遺漏最高
        if 8 <= gap <= 14:
            gap_score = 100 + (14 - abs(gap - 11)) * 10  # gap=11 最佳
        elif 5 <= gap <= 7:
            gap_score = 70
        elif gap > 14:
            gap_score = 50  # 太冷
        else:
            gap_score = 40  # 太熱

        # 頻率穩定性加分
        avg_freq = sum(freq.values()) / len(freq)
        if abs(f - avg_freq) < 2:
            freq_score = 30  # 穩定
        else:
            freq_score = 10

        score = gap_score + freq_score

        # 完全排除上期（回歸邏輯不期望連續）
        if num in last_draw:
            score = 0

        scores[num] = score

    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted([num for num, _ in sorted_nums[:pick_count]])


def strategy_zone_balance(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """
    注3：區域平衡策略
    - 確保各區域（1-16, 17-33, 34-49）都有號碼
    - 每區選 2 個中等表現的號碼
    """
    if len(history) < 30:
        return []

    last_draw = set(history[-1]['numbers'])
    freq = calculate_frequency(history, window=30, max_num=max_num)
    gaps = calculate_gaps(history, max_num)

    zones = [
        list(range(1, 17)),    # 低區
        list(range(17, 34)),   # 中區
        list(range(34, 50)),   # 高區
    ]

    selected = []
    for zone in zones:
        zone_scores = {}
        for num in zone:
            f = freq[num]
            gap = gaps[num]
            score = f * 2 + gap * 0.5

            if num in last_draw:
                score *= 0.2

            zone_scores[num] = score

        # 每區選 2 個
        sorted_zone = sorted(zone_scores.items(), key=lambda x: x[1], reverse=True)
        selected.extend([num for num, _ in sorted_zone[:2]])

    return sorted(selected)


def diversified_2bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """生成多樣化雙注"""
    bet1 = strategy_moderate_hot(history, max_num, pick_count)
    bet2 = strategy_comeback(history, max_num, pick_count)

    # 確保有效
    if not bet1:
        bet1 = sorted(random.sample(range(1, max_num + 1), pick_count))
    if not bet2:
        bet2 = sorted(random.sample(range(1, max_num + 1), pick_count))

    return [bet1, bet2]


def diversified_3bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """生成多樣化三注"""
    bet1 = strategy_moderate_hot(history, max_num, pick_count)
    bet2 = strategy_comeback(history, max_num, pick_count)
    bet3 = strategy_zone_balance(history, max_num, pick_count)

    if not bet1:
        bet1 = sorted(random.sample(range(1, max_num + 1), pick_count))
    if not bet2:
        bet2 = sorted(random.sample(range(1, max_num + 1), pick_count))
    if not bet3:
        bet3 = sorted(random.sample(range(1, max_num + 1), pick_count))

    return [bet1, bet2, bet3]


def run_backtest(test_periods: int = 300):
    """執行回測"""
    print("=" * 80)
    print("🔬 多樣化雙注策略回測")
    print("=" * 80)

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws_direct(db_path, lottery_type='BIG_LOTTO')

    print(f"總數據量: {len(all_draws)} 期")
    print(f"回測期數: {test_periods}")
    print(f"範圍: {all_draws[-test_periods]['draw_number']} ~ {all_draws[-1]['draw_number']}")

    start_idx = len(all_draws) - test_periods

    # 測試不同策略
    strategies = {
        '單注-中熱策略': lambda h: [strategy_moderate_hot(h)],
        '單注-回歸策略': lambda h: [strategy_comeback(h)],
        '單注-區域平衡': lambda h: [strategy_zone_balance(h)],
        '雙注-多樣化': diversified_2bet,
        '三注-多樣化': diversified_3bet,
    }

    results = {name: {'m0': 0, 'm1': 0, 'm2': 0, 'm3': 0, 'm4': 0, 'm5': 0, 'm6': 0, 'total': 0, 'details': []}
               for name in strategies}

    # 統計連續號碼
    repeat_stats = {'count': 0, 'total': 0}

    for target_idx in range(start_idx, len(all_draws)):
        history = all_draws[:target_idx]
        target = all_draws[target_idx]

        if len(history) < 50:
            continue

        actual = set(target['numbers'])
        draw_num = target['draw_number']

        # 統計連續號碼
        if target_idx > 0:
            prev = set(all_draws[target_idx - 1]['numbers'])
            repeat_stats['total'] += 1
            if len(actual & prev) > 0:
                repeat_stats['count'] += 1

        for name, strategy_fn in strategies.items():
            bets = strategy_fn(history)
            if not bets or not bets[0]:
                continue

            max_match = 0
            best_bet = None
            for bet in bets:
                match_count = len(set(bet) & actual)
                if match_count > max_match:
                    max_match = match_count
                    best_bet = bet

            results[name]['total'] += 1
            results[name][f'm{max_match}'] += 1

            if max_match >= 3:
                results[name]['details'].append({
                    'draw': draw_num,
                    'actual': sorted(list(actual)),
                    'bet': best_bet,
                    'match': max_match
                })

    # 輸出結果
    print("\n" + "=" * 80)
    print("📊 回測結果")
    print("=" * 80)

    print(f"\n連續號碼出現率: {repeat_stats['count']}/{repeat_stats['total']} = {repeat_stats['count']/repeat_stats['total']*100:.1f}%")

    print(f"\n{'策略':<20} {'Match-3+':<12} {'Match-4+':<12} {'M3率':<10} {'每注效益':<10}")
    print("-" * 70)

    for name, r in results.items():
        total = r['total']
        m3_plus = r['m3'] + r['m4'] + r['m5'] + r['m6']
        m4_plus = r['m4'] + r['m5'] + r['m6']
        rate3 = m3_plus / total * 100 if total > 0 else 0
        rate4 = m4_plus / total * 100 if total > 0 else 0

        # 計算注數
        if '單注' in name:
            bet_count = 1
        elif '雙注' in name:
            bet_count = 2
        else:
            bet_count = 3

        efficiency = rate3 / bet_count

        print(f"{name:<20} {m3_plus:<12} {m4_plus:<12} {rate3:.2f}%{'':<5} {efficiency:.2f}%")

    # 詳細分析最佳策略
    best_name = max(results.keys(), key=lambda n: (results[n]['m3'] + results[n]['m4'] + results[n]['m5'] + results[n]['m6']) / max(results[n]['total'], 1))
    best = results[best_name]

    print("\n" + "=" * 80)
    print(f"🏆 最佳策略: {best_name}")
    print("=" * 80)

    m3_plus = best['m3'] + best['m4'] + best['m5'] + best['m6']
    print(f"Match-3+: {m3_plus} 次 ({m3_plus/best['total']*100:.2f}%)")
    print(f"Match-4+: {best['m4'] + best['m5'] + best['m6']} 次")

    if best['details']:
        print(f"\n命中詳情 (前 10 個):")
        for d in best['details'][:10]:
            print(f"  {d['draw']}: {d['actual']} → 預測 {d['bet']} (Match-{d['match']})")

    # 策略重疊分析
    print("\n" + "=" * 80)
    print("📈 策略分析")
    print("=" * 80)

    # 比較單注策略
    single_strategies = ['單注-中熱策略', '單注-回歸策略', '單注-區域平衡']
    print("\n單注策略對比:")
    for name in single_strategies:
        r = results[name]
        m3 = r['m3'] + r['m4'] + r['m5'] + r['m6']
        print(f"  {name}: {m3/r['total']*100:.2f}% Match-3+")

    # 分析多注策略的提升
    single_best = max(single_strategies, key=lambda n: (results[n]['m3'] + results[n]['m4'] + results[n]['m5'] + results[n]['m6']) / results[n]['total'])
    single_rate = (results[single_best]['m3'] + results[single_best]['m4'] + results[single_best]['m5'] + results[single_best]['m6']) / results[single_best]['total'] * 100

    dual_rate = (results['雙注-多樣化']['m3'] + results['雙注-多樣化']['m4'] + results['雙注-多樣化']['m5'] + results['雙注-多樣化']['m6']) / results['雙注-多樣化']['total'] * 100
    triple_rate = (results['三注-多樣化']['m3'] + results['三注-多樣化']['m4'] + results['三注-多樣化']['m5'] + results['三注-多樣化']['m6']) / results['三注-多樣化']['total'] * 100

    print(f"\n多注策略提升:")
    print(f"  最佳單注基準: {single_rate:.2f}%")
    print(f"  雙注多樣化:   {dual_rate:.2f}% (+{dual_rate - single_rate:.2f}%)")
    print(f"  三注多樣化:   {triple_rate:.2f}% (+{triple_rate - single_rate:.2f}%)")

    return results


if __name__ == '__main__':
    run_backtest(test_periods=300)
