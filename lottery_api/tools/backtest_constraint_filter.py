#!/usr/bin/env python3
"""
組合約束過濾策略回測

比較不同約束配置的效果
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import DatabaseManager
from common import get_lottery_rules
from models.constraint_filter_predictor import ConstraintFilterPredictor
from collections import defaultdict
import json


def run_constraint_backtest(lottery_type: str = 'BIG_LOTTO',
                             test_year: str = '2025'):
    """執行約束過濾策略回測"""
    print("=" * 80)
    print(f"組合約束過濾策略回測 - {lottery_type} ({test_year}年)")
    print("=" * 80)

    db = DatabaseManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type)
    rules = get_lottery_rules(lottery_type)

    # 找出測試數據
    test_draws = []
    for i, draw in enumerate(all_draws):
        date = draw.get('date', '')
        draw_id = draw.get('draw', '')
        if date.startswith(test_year) or draw_id.startswith('114'):
            test_draws.append((i, draw))

    test_draws = list(reversed(test_draws))
    print(f"測試數據: {len(test_draws)} 期")

    predictor = ConstraintFilterPredictor()

    # 單注回測
    print("\n" + "=" * 60)
    print("單注策略回測")
    print("=" * 60)

    results = []
    win_count = 0
    total_matches = 0
    match_dist = defaultdict(int)

    for test_idx, (orig_idx, target_draw) in enumerate(test_draws):
        train_data = all_draws[orig_idx + 1:]

        if len(train_data) < 100:
            continue

        target_numbers = set(target_draw['numbers'])

        try:
            prediction = predictor.predict(train_data, rules)
            predicted = set(prediction['numbers'])

            matches = len(predicted & target_numbers)
            total_matches += matches
            match_dist[matches] += 1

            won = matches >= 3
            if won:
                win_count += 1

            results.append({
                'draw': target_draw['draw'],
                'matches': matches,
                'won': won
            })

            if (test_idx + 1) % 30 == 0:
                current_rate = win_count / len(results) * 100
                print(f"  進度 {test_idx+1}/{len(test_draws)}: 中獎率 {current_rate:.2f}%")

        except Exception as e:
            print(f"  錯誤: {e}")

    test_count = len(results)
    if test_count > 0:
        win_rate = win_count / test_count
        avg_match = total_matches / test_count

        print(f"\n單注結果:")
        print(f"  中獎率: {win_rate*100:.2f}%")
        print(f"  平均匹配: {avg_match:.2f}")
        print(f"  每N期中1次: {1/win_rate if win_rate > 0 else 999:.1f}")
        print(f"  匹配分佈: {dict(match_dist)}")

    # 2注回測
    print("\n" + "=" * 60)
    print("2注策略回測")
    print("=" * 60)

    results_2bet = []
    win_count_2bet = 0
    total_best = 0
    match_dist_2bet = defaultdict(int)

    for test_idx, (orig_idx, target_draw) in enumerate(test_draws):
        train_data = all_draws[orig_idx + 1:]

        if len(train_data) < 100:
            continue

        target_numbers = set(target_draw['numbers'])

        try:
            prediction = predictor.predict_multi_bet(train_data, rules, num_bets=2)

            best_match = 0
            for bet in prediction['bets']:
                matches = len(set(bet['numbers']) & target_numbers)
                best_match = max(best_match, matches)

            total_best += best_match
            match_dist_2bet[best_match] += 1

            won = best_match >= 3
            if won:
                win_count_2bet += 1

            results_2bet.append({
                'draw': target_draw['draw'],
                'best_match': best_match,
                'won': won
            })

            if (test_idx + 1) % 30 == 0:
                current_rate = win_count_2bet / len(results_2bet) * 100
                print(f"  進度 {test_idx+1}/{len(test_draws)}: 中獎率 {current_rate:.2f}%")

        except Exception as e:
            print(f"  錯誤: {e}")

    test_count_2bet = len(results_2bet)
    if test_count_2bet > 0:
        win_rate_2bet = win_count_2bet / test_count_2bet
        avg_best = total_best / test_count_2bet

        print(f"\n2注結果:")
        print(f"  中獎率: {win_rate_2bet*100:.2f}%")
        print(f"  最佳匹配平均: {avg_best:.2f}")
        print(f"  每N期中1次: {1/win_rate_2bet if win_rate_2bet > 0 else 999:.1f}")
        print(f"  匹配分佈: {dict(match_dist_2bet)}")

    # 與基準比較
    print("\n" + "=" * 60)
    print("與現有方法比較")
    print("=" * 60)
    print(f"現有最佳單注 (zone_balance): 4.31%")
    print(f"現有最佳2注: ~6.03%")
    print(f"約束過濾單注: {win_rate*100:.2f}%")
    print(f"約束過濾2注: {win_rate_2bet*100:.2f}%")

    return {
        'single': {'win_rate': win_rate, 'avg_match': avg_match},
        '2bet': {'win_rate': win_rate_2bet, 'avg_best': avg_best}
    }


if __name__ == '__main__':
    run_constraint_backtest()
