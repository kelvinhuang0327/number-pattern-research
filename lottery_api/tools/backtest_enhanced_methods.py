#!/usr/bin/env python3
"""
P2: 新預測方法研究
回測 enhanced_predictor 的各種方法，與基準比較
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager
from common import get_lottery_rules
from models.enhanced_predictor import EnhancedPredictor
from models.unified_predictor import prediction_engine
from collections import Counter
import json
from datetime import datetime


def quick_backtest(method_func, method_name, all_draws, test_draws, rules, window=100):
    """快速回測單一方法"""
    win_count = 0
    total_matches = 0
    test_count = 0
    match_distribution = Counter()

    for target in test_draws:
        target_idx = None
        for i, d in enumerate(all_draws):
            if d['draw'] == target['draw']:
                target_idx = i
                break

        if target_idx is None:
            continue

        available = all_draws[target_idx + 1:]
        if len(available) < window:
            continue

        history = available[:window]

        try:
            result = method_func(history, rules)
            predicted = set(result['numbers'])
            actual = set(target['numbers'])
            matches = len(predicted & actual)

            total_matches += matches
            match_distribution[matches] += 1
            if matches >= 3:
                win_count += 1
            test_count += 1
        except Exception as e:
            continue

    if test_count > 0:
        win_rate = win_count / test_count
        avg_matches = total_matches / test_count
        periods_per_win = test_count / win_count if win_count > 0 else float('inf')
        return {
            'method': method_name,
            'win_rate': win_rate,
            'win_count': win_count,
            'test_count': test_count,
            'avg_matches': avg_matches,
            'periods_per_win': periods_per_win,
            'match_distribution': dict(match_distribution)
        }
    return None


def main():
    db = DatabaseManager()
    lottery_type = 'BIG_LOTTO'

    draws = db.get_all_draws(lottery_type)
    rules = get_lottery_rules(lottery_type)

    print("=" * 70)
    print("P2: 新預測方法研究 - 增強型預測器回測")
    print("=" * 70)
    print(f"彩種: {lottery_type}")
    print(f"總數據: {len(draws)} 期")
    print(f"最新: {draws[0]['draw']} ({draws[0]['date']})")

    # 2025年測試數據
    test_draws = [d for d in draws if d['date'].startswith('2025') or d['date'].startswith('114')]
    print(f"2025年測試數據: {len(test_draws)} 期")

    # 初始化預測器
    enhanced = EnhancedPredictor()

    # 基準方法 (zone_balance at 4.31%)
    baseline_methods = {
        'zone_balance (基準)': prediction_engine.zone_balance_predict,
        'ensemble (基準)': prediction_engine.ensemble_predict,
        'bayesian (基準)': prediction_engine.bayesian_predict,
    }

    # 增強型方法
    enhanced_methods = {
        'consecutive_friendly': enhanced.consecutive_friendly_predict,
        'cold_comeback': enhanced.cold_number_comeback_predict,
        'constrained': enhanced.constrained_predict,
        'multi_window': enhanced.multi_window_fusion_predict,
        'coverage_opt': enhanced.coverage_optimized_predict,
        'enhanced_ensemble': enhanced.enhanced_ensemble_predict,
    }

    all_methods = {**baseline_methods, **enhanced_methods}
    results = []

    print(f"\n測試 {len(all_methods)} 個方法...")
    print("-" * 70)

    for name, func in all_methods.items():
        print(f"測試 {name}...", end=" ", flush=True)
        result = quick_backtest(func, name, draws, test_draws, rules, window=100)
        if result:
            results.append(result)
            print(f"{result['win_rate']*100:.2f}% ({result['win_count']}/{result['test_count']})")
        else:
            print("失敗")

    # 排序結果
    results.sort(key=lambda x: -x['win_rate'])

    print("\n" + "=" * 70)
    print("回測結果排名")
    print("=" * 70)
    print(f"{'排名':<4} {'方法':<25} {'中獎率':<10} {'平均匹配':<10} {'每N期中1次':<12}")
    print("-" * 70)

    baseline_rate = 0.0431  # zone_balance 基準
    for i, r in enumerate(results, 1):
        improvement = ((r['win_rate'] / baseline_rate) - 1) * 100 if baseline_rate > 0 else 0
        marker = "⭐" if r['win_rate'] > baseline_rate else ""
        print(f"{i:<4} {r['method']:<25} {r['win_rate']*100:.2f}%{marker:<4} "
              f"{r['avg_matches']:.2f}        {r['periods_per_win']:.1f}")

    # 分析最佳方法
    print("\n" + "=" * 70)
    print("分析摘要")
    print("=" * 70)

    best = results[0]
    print(f"最佳方法: {best['method']}")
    print(f"中獎率: {best['win_rate']*100:.2f}%")
    print(f"對比基準提升: {((best['win_rate']/0.0431)-1)*100:.1f}%")
    print(f"\n匹配分佈:")
    for matches, count in sorted(best['match_distribution'].items()):
        print(f"  {matches} 個匹配: {count} 次 ({count/best['test_count']*100:.1f}%)")

    # 保存結果
    output = {
        'lottery_type': lottery_type,
        'test_year': 2025,
        'test_periods': len(test_draws),
        'baseline_rate': 0.0431,
        'results': results,
        'generated_at': datetime.now().isoformat()
    }

    output_path = 'data/enhanced_methods_backtest.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n結果已保存到: {output_path}")

    return results


if __name__ == '__main__':
    main()
