#!/usr/bin/env python3
"""
今彩539 3注覆蓋回測
目標：找出達到33%中獎率的最佳3注組合
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from itertools import combinations
from collections import defaultdict
from database import db_manager
from common import get_lottery_rules
from models.daily539_predictor import Daily539Predictor
from models.unified_predictor import prediction_engine

# 初始化
predictor = Daily539Predictor()
rules = get_lottery_rules('DAILY_539')

# Top 方法列表 (基於之前回測結果)
TOP_METHODS = [
    ('sum_range', 300, prediction_engine.sum_range_predict),
    ('tail', 100, predictor.tail_number_predict),
    ('bayesian', 300, prediction_engine.bayesian_predict),
    ('zone_balance', 200, prediction_engine.zone_balance_predict),
    ('zone_opt', 200, predictor.zone_optimized_predict),
    ('hot_cold_mix', 100, prediction_engine.hot_cold_mix_predict),
    ('consecutive', 100, predictor.consecutive_predict),
]

def run_triple_bet_backtest(methods, history_all, test_year=2025):
    """
    執行3注覆蓋滾動回測

    Args:
        methods: [(name, window, func), ...]
        history_all: 全部歷史數據 (最新在前)
        test_year: 測試年份

    Returns:
        dict: 回測結果
    """
    # 台灣民國年 = 西元年 - 1911
    taiwan_year = test_year - 1911  # 2025 -> 114

    # 分割訓練和測試數據
    test_draws = []

    for i, draw in enumerate(history_all):
        draw_id = str(draw.get('draw', ''))
        date_str = draw.get('date', '')

        # 檢查是否為目標年份 (民國114年 = 2025年)
        is_target_year = (
            draw_id.startswith(str(taiwan_year)) or
            str(test_year) in date_str
        )

        if is_target_year:
            test_draws.append((i, draw))

    if not test_draws:
        print(f"警告: 找不到 {test_year} 年數據")
        return None

    # 反轉測試數據 (按時間順序)
    test_draws = list(reversed(test_draws))

    print(f"\n測試數據: {len(test_draws)} 期")
    print(f"方法組合: {[m[0] for m in methods]}")

    wins = 0
    total = 0
    details = []

    for test_idx, (orig_idx, target_draw) in enumerate(test_draws):
        # 訓練數據 = 目標期之後的所有數據
        train_data = history_all[orig_idx + 1:]

        if len(train_data) < 300:
            continue

        target_numbers = set(target_draw['numbers'])

        # 執行3注預測
        all_predictions = []
        bet_hit = False

        for name, window, func in methods:
            try:
                window_data = train_data[:window]
                result = func(window_data, rules)
                pred_numbers = set(result['numbers'])
                matches = len(pred_numbers & target_numbers)
                all_predictions.append({
                    'method': name,
                    'numbers': sorted(result['numbers']),
                    'matches': matches
                })

                if matches >= 2:
                    bet_hit = True

            except Exception as e:
                print(f"  方法 {name} 錯誤: {e}")
                continue

        if bet_hit:
            wins += 1
        total += 1

        # 記錄詳情 (僅前10期和中獎期)
        if test_idx < 10 or bet_hit:
            details.append({
                'draw': target_draw['draw'],
                'actual': sorted(target_draw['numbers']),
                'predictions': all_predictions,
                'hit': bet_hit
            })

    win_rate = wins / total if total > 0 else 0

    return {
        'methods': [m[0] for m in methods],
        'wins': wins,
        'total': total,
        'win_rate': win_rate,
        'periods_per_win': total / wins if wins > 0 else float('inf'),
        'details': details[:5]  # 只保留前5期詳情
    }


def main():
    print("=" * 60)
    print("今彩539 3注覆蓋回測")
    print("目標: 找出達到 33% 中獎率的最佳組合")
    print("=" * 60)

    # 載入數據
    history = db_manager.get_all_draws('DAILY_539')
    print(f"\n總數據量: {len(history)} 期")

    # 測試所有3注組合
    results = []

    # C(7,3) = 35 種組合
    for combo in combinations(TOP_METHODS, 3):
        print(f"\n測試組合: {[m[0] for m in combo]}", end=" ")
        result = run_triple_bet_backtest(combo, history, test_year=2025)

        if result:
            results.append(result)
            print(f"→ 中獎率: {result['win_rate']*100:.2f}%")

    # 排序結果
    results.sort(key=lambda x: x['win_rate'], reverse=True)

    print("\n" + "=" * 60)
    print("3注覆蓋回測結果排名")
    print("=" * 60)

    print(f"\n{'排名':<4} {'方法組合':<45} {'中獎率':<10} {'每N期中1次':<12} {'狀態'}")
    print("-" * 85)

    for i, r in enumerate(results, 1):
        methods_str = ' + '.join(r['methods'])
        win_rate_str = f"{r['win_rate']*100:.2f}%"
        periods_str = f"{r['periods_per_win']:.1f}期"

        if r['win_rate'] >= 0.33:
            status = "✅ 達標"
        elif r['win_rate'] >= 0.30:
            status = "⚠️ 接近"
        else:
            status = ""

        print(f"{i:<4} {methods_str:<45} {win_rate_str:<10} {periods_str:<12} {status}")

    # 最佳結果
    if results:
        best = results[0]
        print("\n" + "=" * 60)
        print("🏆 最佳3注組合")
        print("=" * 60)
        print(f"方法: {' + '.join(best['methods'])}")
        print(f"中獎率: {best['win_rate']*100:.2f}%")
        print(f"每N期中1次: {best['periods_per_win']:.1f}期")
        print(f"測試期數: {best['total']}期")
        print(f"中獎次數: {best['wins']}次")

        if best['win_rate'] >= 0.33:
            print("\n🎉 成功達到33%目標！")
        else:
            print(f"\n⚠️ 未達33%目標，差距: {(0.33 - best['win_rate'])*100:.2f}%")
            print("建議: 嘗試4注覆蓋策略")

    return results


if __name__ == '__main__':
    results = main()
