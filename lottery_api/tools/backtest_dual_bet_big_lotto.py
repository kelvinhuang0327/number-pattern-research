#!/usr/bin/env python3
"""
大樂透雙注策略綜合回測

測試多種2注組合策略，找出最佳配置
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import DatabaseManager
from common import get_lottery_rules
from models.big_lotto_dual_bet_optimizer import BigLottoDualBetOptimizer
from models.unified_predictor import prediction_engine
from models.concentrated_pool_predictor import ConcentratedPoolPredictor
from models.constraint_filter_predictor import ConstraintFilterPredictor
from collections import defaultdict
import json
from datetime import datetime


def run_single_method_backtest(draws, rules, test_draws, method_name, method_func, window):
    """執行單一方法回測"""
    results = []
    win_count = 0
    total_matches = 0

    for test_idx, (orig_idx, target_draw) in enumerate(test_draws):
        train_data = draws[orig_idx + 1:]

        if len(train_data) < window:
            continue

        target_numbers = set(target_draw['numbers'])

        try:
            history = train_data[:window]
            prediction = method_func(history, rules)
            predicted = set(prediction['numbers'])

            matches = len(predicted & target_numbers)
            total_matches += matches

            won = matches >= 3
            if won:
                win_count += 1

            results.append({'matches': matches, 'won': won})
        except Exception as e:
            pass

    test_count = len(results)
    if test_count > 0:
        return {
            'method': method_name,
            'window': window,
            'win_rate': win_count / test_count,
            'avg_match': total_matches / test_count,
            'test_count': test_count
        }
    return None


def run_dual_bet_backtest(draws, rules, test_draws, name, bet1_func, bet2_func):
    """執行雙注組合回測"""
    results = []
    win_count = 0
    total_best = 0
    match_dist = defaultdict(int)

    for test_idx, (orig_idx, target_draw) in enumerate(test_draws):
        train_data = draws[orig_idx + 1:]

        if len(train_data) < 100:
            continue

        target_numbers = set(target_draw['numbers'])

        try:
            # 第一注
            pred1 = bet1_func(train_data, rules)
            nums1 = set(pred1['numbers'])
            match1 = len(nums1 & target_numbers)

            # 第二注
            pred2 = bet2_func(train_data, rules)
            nums2 = set(pred2['numbers'])
            match2 = len(nums2 & target_numbers)

            best_match = max(match1, match2)
            total_best += best_match
            match_dist[best_match] += 1

            won = best_match >= 3
            if won:
                win_count += 1

            results.append({
                'match1': match1,
                'match2': match2,
                'best': best_match,
                'won': won
            })
        except Exception as e:
            pass

    test_count = len(results)
    if test_count > 0:
        return {
            'name': name,
            'win_count': win_count,
            'win_rate': win_count / test_count,
            'avg_best': total_best / test_count,
            'test_count': test_count,
            'match_dist': dict(match_dist)
        }
    return None


def main():
    print("=" * 80)
    print("大樂透雙注策略綜合回測")
    print("=" * 80)

    db = DatabaseManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'))
    draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    print(f"\n數據總量: {len(draws)} 期")

    # 找出2025年測試數據
    test_draws = []
    for i, draw in enumerate(draws):
        date = draw.get('date', '')
        draw_id = draw.get('draw', '')
        if date.startswith('2025') or draw_id.startswith('114'):
            test_draws.append((i, draw))

    test_draws = list(reversed(test_draws))
    print(f"2025年測試數據: {len(test_draws)} 期")

    # ========================================
    # 階段1：單一方法回測 (確認基準)
    # ========================================
    print("\n" + "=" * 60)
    print("階段1：單一方法基準測試")
    print("=" * 60)

    single_methods = [
        ('zone_balance', prediction_engine.zone_balance_predict, 500),
        ('bayesian', prediction_engine.bayesian_predict, 300),
        ('hot_cold', prediction_engine.hot_cold_mix_predict, 100),
        ('trend', prediction_engine.trend_predict, 300),
        ('ensemble', prediction_engine.ensemble_predict, 200),
        ('monte_carlo', prediction_engine.monte_carlo_predict, 200),
        ('sum_range', prediction_engine.sum_range_predict, 100),
    ]

    single_results = []
    for method_name, method_func, window in single_methods:
        result = run_single_method_backtest(draws, rules, test_draws, method_name, method_func, window)
        if result:
            single_results.append(result)
            print(f"  {method_name}({window}期): {result['win_rate']*100:.2f}%, avg={result['avg_match']:.2f}")

    # 排序
    single_results.sort(key=lambda x: -x['win_rate'])
    print(f"\n最佳單注: {single_results[0]['method']} = {single_results[0]['win_rate']*100:.2f}%")

    # ========================================
    # 階段2：雙注組合回測
    # ========================================
    print("\n" + "=" * 60)
    print("階段2：雙注組合測試")
    print("=" * 60)

    # 初始化優化器
    dual_optimizer = BigLottoDualBetOptimizer()
    conc_predictor = ConcentratedPoolPredictor(pool_size=28)
    constraint_predictor = ConstraintFilterPredictor()

    # 定義雙注組合策略
    dual_strategies = [
        # 策略名稱, 第一注函數, 第二注函數
        (
            'dual_optimizer (consensus + gap)',
            lambda h, r: {'numbers': dual_optimizer.select_consensus_numbers(h, r)},
            lambda h, r: {'numbers': dual_optimizer.select_gap_regression_numbers(h, r)}
        ),
        (
            'zone_balance + bayesian',
            lambda h, r: prediction_engine.zone_balance_predict(h[:500], r),
            lambda h, r: prediction_engine.bayesian_predict(h[:300], r)
        ),
        (
            'zone_balance + hot_cold',
            lambda h, r: prediction_engine.zone_balance_predict(h[:500], r),
            lambda h, r: prediction_engine.hot_cold_mix_predict(h[:100], r)
        ),
        (
            'zone_balance + monte_carlo',
            lambda h, r: prediction_engine.zone_balance_predict(h[:500], r),
            lambda h, r: prediction_engine.monte_carlo_predict(h[:200], r)
        ),
        (
            'zone_balance + trend',
            lambda h, r: prediction_engine.zone_balance_predict(h[:500], r),
            lambda h, r: prediction_engine.trend_predict(h[:300], r)
        ),
        (
            'bayesian + hot_cold',
            lambda h, r: prediction_engine.bayesian_predict(h[:300], r),
            lambda h, r: prediction_engine.hot_cold_mix_predict(h[:100], r)
        ),
        (
            'concentrated_pool + zone_balance',
            lambda h, r: conc_predictor.predict(h, r, strategy='weighted_random'),
            lambda h, r: prediction_engine.zone_balance_predict(h[:500], r)
        ),
        (
            'ensemble + monte_carlo',
            lambda h, r: prediction_engine.ensemble_predict(h[:200], r),
            lambda h, r: prediction_engine.monte_carlo_predict(h[:200], r)
        ),
        (
            'constraint_filter dual',
            lambda h, r: constraint_predictor.predict(h, r),
            lambda h, r: constraint_predictor.predict(h, r)  # 有隨機性
        ),
    ]

    dual_results = []

    for name, bet1_func, bet2_func in dual_strategies:
        print(f"\n測試: {name}")
        result = run_dual_bet_backtest(draws, rules, test_draws, name, bet1_func, bet2_func)
        if result:
            dual_results.append(result)
            print(f"  中獎率: {result['win_rate']*100:.2f}%")
            print(f"  平均最佳匹配: {result['avg_best']:.2f}")
            print(f"  匹配分佈: {result['match_dist']}")

    # ========================================
    # 階段3：結果排名
    # ========================================
    print("\n" + "=" * 80)
    print("雙注組合結果排名")
    print("=" * 80)

    dual_results.sort(key=lambda x: -x['win_rate'])

    print(f"\n{'排名':<4} {'策略':<40} {'中獎率':<10} {'平均匹配':<10}")
    print("-" * 70)

    for rank, result in enumerate(dual_results, 1):
        print(f"{rank:<4} {result['name']:<40} {result['win_rate']*100:.2f}%      {result['avg_best']:.2f}")

    # ========================================
    # 階段4：與基準比較
    # ========================================
    print("\n" + "=" * 80)
    print("與基準比較")
    print("=" * 80)

    best_single = single_results[0]
    best_dual = dual_results[0] if dual_results else None

    print(f"最佳單注: {best_single['method']} = {best_single['win_rate']*100:.2f}%")
    if best_dual:
        print(f"最佳雙注: {best_dual['name']} = {best_dual['win_rate']*100:.2f}%")
        improvement = (best_dual['win_rate'] / best_single['win_rate'] - 1) * 100
        print(f"提升幅度: {improvement:+.1f}%")

    # 保存結果
    output = {
        'test_year': '2025',
        'test_count': len(test_draws),
        'timestamp': datetime.now().isoformat(),
        'single_best': best_single,
        'dual_results': dual_results,
        'conclusion': {
            'best_dual_strategy': best_dual['name'] if best_dual else None,
            'best_dual_win_rate': best_dual['win_rate'] if best_dual else 0,
            'vs_single_improvement': improvement if best_dual else 0
        }
    }

    output_file = os.path.join(os.path.dirname(__file__), '..', 'data',
                               'big_lotto_dual_bet_backtest_2025.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n結果已保存: {output_file}")

    return dual_results


if __name__ == '__main__':
    main()
