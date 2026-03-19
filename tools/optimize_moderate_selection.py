#!/usr/bin/env python3
"""
「排除上期 + 中值選號」策略參數優化

優化目標：
1. 軟排除權重：測試 0% ~ 40%（找出最佳保留比例）
2. 中值區間：測試不同的「避極端」範圍
3. 回測期數：300 期驗證穩定性
"""
import sys
import os
import sqlite3
import json
from collections import Counter
from typing import List, Dict, Tuple
from itertools import product

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_all_draws_direct(db_path: str, lottery_type: str = 'BIG_LOTTO') -> List[Dict]:
    """直接從 SQLite 讀取開獎數據"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
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


def calculate_gaps(history: List[Dict], max_num: int = 49) -> Dict[int, int]:
    """計算每個號碼的遺漏值"""
    gaps = {i: len(history) for i in range(1, max_num + 1)}
    for i, draw in enumerate(reversed(history)):
        for num in draw['numbers']:
            if gaps[num] == len(history):
                gaps[num] = i
    return gaps


def calculate_frequency(history: List[Dict], window: int = 30, max_num: int = 49) -> Dict[int, int]:
    """計算號碼頻率"""
    freq = Counter()
    recent = history[-window:] if len(history) >= window else history
    for draw in recent:
        for num in draw['numbers']:
            freq[num] += 1
    for i in range(1, max_num + 1):
        if i not in freq:
            freq[i] = 0
    return freq


def moderate_selection_with_params(
    history: List[Dict],
    max_num: int = 49,
    pick_count: int = 6,
    last_draw_penalty: float = 0.15,
    hot_rank_min: int = 4,      # 熱號從排名 4 開始選
    hot_rank_max: int = 15,     # 熱號到排名 15
    cold_gap_min: int = 8,      # 冷號遺漏最小值
    cold_gap_max: int = 12,     # 冷號遺漏最大值
    extreme_cold_penalty: float = 0.6,  # 極端冷號懲罰
) -> List[int]:
    """帶參數的中值選號策略"""
    if len(history) < 10:
        return []

    last_draw_numbers = set(history[-1]['numbers'])
    gaps = calculate_gaps(history, max_num)
    freq_30 = calculate_frequency(history, window=30, max_num=max_num)
    freq_50 = calculate_frequency(history, window=50, max_num=max_num)

    # 計算頻率排名
    freq_sorted = sorted(freq_30.items(), key=lambda x: x[1], reverse=True)
    freq_rank = {num: rank for rank, (num, _) in enumerate(freq_sorted, 1)}

    scores = {}
    for num in range(1, max_num + 1):
        gap = gaps[num]
        f30 = freq_30[num]
        f50 = freq_50[num]
        rank = freq_rank[num]

        # 基礎分數
        base_score = f30 * 2 + f50 + (gap * 0.5)

        # 中值偏好：避開極端熱號（排名太高）
        if rank < hot_rank_min:
            base_score *= 0.7

        # 中值偏好：選擇中等熱號
        if hot_rank_min <= rank <= hot_rank_max:
            base_score *= 1.2

        # 極端冷號懲罰
        if gap > 15:
            base_score *= extreme_cold_penalty

        # 中等遺漏加分
        if cold_gap_min <= gap <= cold_gap_max:
            base_score *= 1.3

        # 軟排除上期號碼
        if num in last_draw_numbers:
            base_score *= last_draw_penalty

        scores[num] = base_score

    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    selected = [num for num, _ in sorted_nums[:pick_count]]
    return sorted(selected)


def backtest_with_params(
    all_draws: List[Dict],
    test_periods: int,
    num_bets: int,
    last_draw_penalty: float,
    hot_rank_min: int,
    hot_rank_max: int,
    cold_gap_min: int,
    cold_gap_max: int,
) -> Dict:
    """使用指定參數進行回測"""
    max_num = 49
    pick_count = 6

    start_idx = len(all_draws) - test_periods
    results = {'match3_plus': 0, 'match4_plus': 0, 'total': 0}

    for target_idx in range(start_idx, len(all_draws)):
        history = all_draws[:target_idx]
        target = all_draws[target_idx]

        if len(history) < 50:
            continue

        actual = set(target['numbers'])

        # 生成多注
        max_match = 0
        for bet_idx in range(num_bets):
            # 對第二注稍微調整參數以產生多樣性
            adjusted_penalty = last_draw_penalty * (1 + bet_idx * 0.1)
            adjusted_hot_min = hot_rank_min + bet_idx * 2

            bet = moderate_selection_with_params(
                history, max_num, pick_count,
                last_draw_penalty=min(adjusted_penalty, 0.5),
                hot_rank_min=adjusted_hot_min,
                hot_rank_max=hot_rank_max,
                cold_gap_min=cold_gap_min,
                cold_gap_max=cold_gap_max,
            )

            if bet:
                match_count = len(set(bet) & actual)
                max_match = max(max_match, match_count)

        results['total'] += 1
        if max_match >= 3:
            results['match3_plus'] += 1
        if max_match >= 4:
            results['match4_plus'] += 1

    return results


def grid_search_optimization():
    """網格搜索最佳參數"""
    print("=" * 80)
    print("🔬 「排除上期 + 中值選號」策略參數優化")
    print("=" * 80)

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws_direct(db_path, lottery_type='BIG_LOTTO')

    print(f"總數據量: {len(all_draws)} 期")
    print(f"最新一期: {all_draws[-1]['draw_number']}")

    # 參數網格
    penalties = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    hot_rank_mins = [3, 4, 5, 6]
    cold_gap_ranges = [(6, 10), (7, 11), (8, 12), (9, 13), (10, 14)]

    test_periods = 300
    num_bets = 2

    print(f"\n回測期數: {test_periods}")
    print(f"測試注數: {num_bets}")
    print(f"參數組合: {len(penalties)} x {len(hot_rank_mins)} x {len(cold_gap_ranges)} = {len(penalties) * len(hot_rank_mins) * len(cold_gap_ranges)}")
    print("\n開始優化...")
    print("-" * 80)

    best_result = None
    best_params = None
    all_results = []

    total_combos = len(penalties) * len(hot_rank_mins) * len(cold_gap_ranges)
    combo_idx = 0

    for penalty in penalties:
        for hot_min in hot_rank_mins:
            for cold_min, cold_max in cold_gap_ranges:
                combo_idx += 1

                result = backtest_with_params(
                    all_draws, test_periods, num_bets,
                    last_draw_penalty=penalty,
                    hot_rank_min=hot_min,
                    hot_rank_max=15,
                    cold_gap_min=cold_min,
                    cold_gap_max=cold_max,
                )

                rate = result['match3_plus'] / result['total'] * 100 if result['total'] > 0 else 0
                rate4 = result['match4_plus'] / result['total'] * 100 if result['total'] > 0 else 0

                all_results.append({
                    'penalty': penalty,
                    'hot_min': hot_min,
                    'cold_range': (cold_min, cold_max),
                    'match3_rate': rate,
                    'match4_rate': rate4,
                    'match3_count': result['match3_plus'],
                    'match4_count': result['match4_plus'],
                })

                if best_result is None or rate > best_result['match3_rate']:
                    best_result = all_results[-1]
                    best_params = (penalty, hot_min, cold_min, cold_max)

                # 進度顯示
                if combo_idx % 20 == 0:
                    print(f"  進度: {combo_idx}/{total_combos} ({combo_idx/total_combos*100:.0f}%)")

    # 輸出結果
    print("\n" + "=" * 80)
    print("📊 優化結果")
    print("=" * 80)

    # Top 10 結果
    sorted_results = sorted(all_results, key=lambda x: x['match3_rate'], reverse=True)

    print(f"\n🏆 Top 10 參數組合（{test_periods} 期回測）:")
    print("-" * 80)
    print(f"{'排名':<4} {'軟排除權重':<12} {'熱號起始':<10} {'冷號區間':<12} {'Match-3+ 率':<12} {'Match-4+':<10}")
    print("-" * 80)

    for i, r in enumerate(sorted_results[:10], 1):
        print(f"{i:<4} {r['penalty']:.0%}{'':<8} {r['hot_min']:<10} {r['cold_range']}{'':<4} "
              f"{r['match3_rate']:.2f}%{'':<7} {r['match4_count']} 次")

    # 最佳參數詳情
    print("\n" + "=" * 80)
    print("🎯 最佳參數組合")
    print("=" * 80)
    print(f"  軟排除權重: {best_result['penalty']:.0%}")
    print(f"  熱號排名區間: {best_result['hot_min']} ~ 15")
    print(f"  冷號遺漏區間: {best_result['cold_range'][0]} ~ {best_result['cold_range'][1]}")
    print(f"  Match-3+ 率: {best_result['match3_rate']:.2f}% ({best_result['match3_count']} 次 / {test_periods} 期)")
    print(f"  Match-4+ 率: {best_result['match4_rate']:.2f}% ({best_result['match4_count']} 次)")

    # 分析軟排除權重的影響
    print("\n" + "=" * 80)
    print("📈 軟排除權重影響分析")
    print("=" * 80)
    print(f"\n{'權重':<10} {'平均 Match-3+ 率':<20} {'最佳 Match-3+ 率':<20}")
    print("-" * 50)

    for penalty in penalties:
        penalty_results = [r for r in all_results if r['penalty'] == penalty]
        avg_rate = sum(r['match3_rate'] for r in penalty_results) / len(penalty_results)
        max_rate = max(r['match3_rate'] for r in penalty_results)
        label = "← 完全排除" if penalty == 0 else ("← 預設" if penalty == 0.15 else "")
        print(f"{penalty:.0%}{'':<6} {avg_rate:.2f}%{'':<15} {max_rate:.2f}%{'':<10} {label}")

    # 最終建議
    print("\n" + "=" * 80)
    print("💡 最終建議")
    print("=" * 80)

    if best_result['penalty'] == 0:
        print("\n⚠️ 最佳結果是完全排除上期號碼！")
        print("   這與「連續號碼 51% 出現率」矛盾，可能是過擬合。")
        print("   建議使用 10%-20% 權重以保持穩健性。")
    elif best_result['penalty'] > 0.3:
        print("\n⚠️ 最佳權重較高，接近不排除。")
        print("   上期號碼的影響可能被高估。")
    else:
        print(f"\n✅ 建議使用軟排除權重: {best_result['penalty']:.0%}")
        print(f"   在 {test_periods} 期回測中表現最佳。")

    return best_result, sorted_results


if __name__ == '__main__':
    grid_search_optimization()
