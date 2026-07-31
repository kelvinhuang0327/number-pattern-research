#!/usr/bin/env python3
"""
驗證 Gemini 發現的「算法隨機性」對回測結果的影響
進行多次運行並統計結果分佈
"""
import sys
import os
import random
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine


def generate_3bet_diversified(engine, history, rules):
    """三注策略"""
    candidates = Counter()

    try:
        result = engine.deviation_predict(history, rules)
        for num in result['numbers']:
            candidates[num] += 2.0
    except:
        pass

    try:
        result = engine.markov_predict(history, rules)
        for num in result['numbers']:
            candidates[num] += 1.5
    except:
        pass

    try:
        result = engine.statistical_predict(history, rules)
        for num in result['numbers']:
            candidates[num] += 1.0
    except:
        pass

    top_18 = [num for num, _ in candidates.most_common(18)]

    if len(top_18) < 14:
        return None

    bet1 = sorted(top_18[0:6])
    bet2 = sorted(top_18[4:10])
    bet3 = sorted(top_18[8:14])

    return [bet1, bet2, bet3]


def single_backtest_run(seed=None):
    """單次回測"""
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: x.get('draw_number', x.get('draw_date', '')))

    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()

    test_periods = 150
    start_idx = len(all_draws) - test_periods

    match3_plus = 0
    match4_plus = 0
    total = 0

    for target_idx in range(start_idx, len(all_draws)):
        history = all_draws[:target_idx]
        target = all_draws[target_idx]

        if len(history) < 50:
            continue

        actual = set(target['numbers'])

        bets = generate_3bet_diversified(engine, history, rules)
        if bets:
            max_match = 0
            for bet in bets:
                match_count = len(set(bet) & actual)
                max_match = max(max_match, match_count)

            total += 1
            if max_match >= 4:
                match4_plus += 1
            if max_match >= 3:
                match3_plus += 1

    return {
        'match3_plus': match3_plus,
        'match4_plus': match4_plus,
        'total': total,
        'rate': match3_plus / total * 100 if total > 0 else 0
    }


def main():
    print("=" * 70)
    print("🔬 驗證算法隨機性對回測結果的影響")
    print("=" * 70)

    # 測試 1: 固定種子 (應該完全一致)
    print("\n📌 測試1: 固定種子模式 (seed=42)")
    print("-" * 50)

    fixed_results = []
    for i in range(3):
        result = single_backtest_run(seed=42)
        fixed_results.append(result)
        print(f"  運行 {i+1}: Match-3+ = {result['match3_plus']}, Match-4+ = {result['match4_plus']}, Rate = {result['rate']:.2f}%")

    # 檢查一致性
    rates = [r['rate'] for r in fixed_results]
    if len(set(rates)) == 1:
        print(f"  ✅ 固定種子結果一致: {rates[0]:.2f}%")
    else:
        print(f"  ⚠️ 固定種子結果不一致: {rates}")

    # 測試 2: 隨機種子 (應該有變化)
    print("\n📌 測試2: 隨機種子模式 (5次運行)")
    print("-" * 50)

    random_results = []
    for i in range(5):
        result = single_backtest_run(seed=None)  # 不固定種子
        random_results.append(result)
        print(f"  運行 {i+1}: Match-3+ = {result['match3_plus']}, Match-4+ = {result['match4_plus']}, Rate = {result['rate']:.2f}%")

    rates = [r['rate'] for r in random_results]
    match3_counts = [r['match3_plus'] for r in random_results]
    match4_counts = [r['match4_plus'] for r in random_results]

    print(f"\n📊 隨機運行統計:")
    print(f"  Match-3+ 範圍: {min(match3_counts)} - {max(match3_counts)} 次")
    print(f"  Match-4+ 範圍: {min(match4_counts)} - {max(match4_counts)} 次")
    print(f"  Rate 範圍: {min(rates):.2f}% - {max(rates):.2f}%")
    print(f"  Rate 平均: {sum(rates)/len(rates):.2f}%")
    print(f"  Rate 標準差: {np.std(rates):.2f}%")

    # 結論
    print("\n" + "=" * 70)
    print("📋 結論")
    print("=" * 70)

    variance = max(rates) - min(rates)
    if variance > 1.0:
        print(f"  ⚠️ 確認存在顯著隨機性波動 (變化範圍: {variance:.2f}%)")
        print(f"  Gemini 的「Lucky Run」解釋是正確的")
    else:
        print(f"  ✅ 隨機性影響較小 (變化範圍: {variance:.2f}%)")

    avg_rate = sum(rates) / len(rates)
    print(f"\n  🎯 推薦報告的 Match-3+ 率: {avg_rate:.2f}% (±{np.std(rates):.2f}%)")
    print(f"  對比 Gemini 原報告: 7.33%")
    print(f"  對比 Gemini 修正後: 6.00%")


if __name__ == '__main__':
    main()
