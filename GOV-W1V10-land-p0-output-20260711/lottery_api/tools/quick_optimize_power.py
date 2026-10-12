#!/usr/bin/env python3
"""
快速優化 POWER_LOTTO - 精簡版
只測試核心方法和窗口
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine
from collections import Counter
import json
from datetime import datetime

def quick_backtest(method_func, all_draws, test_draws, rules, window):
    """快速回測"""
    win_count = 0
    total_matches = 0
    test_count = 0

    for target in test_draws:
        # 找到目標期在全數據中的位置
        target_idx = None
        for i, d in enumerate(all_draws):
            if d['draw'] == target['draw']:
                target_idx = i
                break

        if target_idx is None:
            continue

        # 只使用目標期之前的數據
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
            if matches >= 3:
                win_count += 1
            test_count += 1
        except Exception as e:
            continue

    return win_count, total_matches, test_count


def main():
    db = DatabaseManager()
    lottery_type = 'POWER_LOTTO'

    draws = db.get_all_draws(lottery_type)
    rules = get_lottery_rules(lottery_type)

    print("=" * 60)
    print("POWER_LOTTO 快速優化")
    print("=" * 60)
    print(f"總數據: {len(draws)} 期")
    print(f"最新: {draws[0]['draw']} ({draws[0]['date']})")

    # 2025年數據
    test_draws = [d for d in draws if d['date'].startswith('2025') or d['date'].startswith('114')]
    print(f"2025年測試數據: {len(test_draws)} 期")

    # 核心方法
    methods = {
        'zone_balance': prediction_engine.zone_balance_predict,
        'ensemble': prediction_engine.ensemble_predict,
        'bayesian': prediction_engine.bayesian_predict,
        'monte_carlo': prediction_engine.monte_carlo_predict,
        'hot_cold_mix': prediction_engine.hot_cold_mix_predict,
    }

    # 精簡窗口
    windows = [50, 100, 200, 300]

    results = []
    total = len(methods) * len(windows)
    count = 0

    print(f"\n測試 {len(methods)} 方法 × {len(windows)} 窗口 = {total} 組合")
    print("-" * 60)

    for method_name, method_func in methods.items():
        for window in windows:
            count += 1
            print(f"[{count}/{total}] {method_name}({window})...", end=" ", flush=True)

            win_count, total_matches, test_count = quick_backtest(
                method_func, draws, test_draws, rules, window
            )

            if test_count > 0:
                win_rate = win_count / test_count
                avg_matches = total_matches / test_count
                periods_per_win = test_count / win_count if win_count > 0 else float('inf')

                results.append({
                    'method': method_name,
                    'window': window,
                    'win_rate': win_rate,
                    'avg_matches': avg_matches,
                    'test_count': test_count,
                    'win_count': win_count,
                    'periods_per_win': periods_per_win
                })

                print(f"{win_rate*100:.2f}% ({win_count}/{test_count})")
            else:
                print("無有效測試")

    # 排序結果
    results.sort(key=lambda x: -x['win_rate'])

    print("\n" + "=" * 60)
    print("Top 10 配置")
    print("=" * 60)
    for i, r in enumerate(results[:10], 1):
        print(f"{i}. {r['method']}({r['window']}): {r['win_rate']*100:.2f}% "
              f"(平均{r['avg_matches']:.2f}匹配, 每{r['periods_per_win']:.1f}期中1次)")

    # 保存最佳配置
    if results:
        best = results[0]
        config = {
            'POWER_LOTTO': {
                'lottery_type': 'POWER_LOTTO',
                'method_name': best['method'],
                'window_size': best['window'],
                'win_rate': best['win_rate'],
                'avg_matches': best['avg_matches'],
                'periods_per_win': best['periods_per_win'],
                'expected_cost': best['periods_per_win'] * 100,  # 威力彩每注100元
                'test_periods': best['test_count'],
                'last_updated': datetime.now().isoformat()
            }
        }

        # 讀取現有配置
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    'data', 'auto_optimal_configs.json')
        try:
            with open(config_path, 'r') as f:
                existing = json.load(f)
        except:
            existing = {}

        existing.update(config)

        with open(config_path, 'w') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 最佳配置已保存: {best['method']}({best['window']}) = {best['win_rate']*100:.2f}%")

    return results


if __name__ == '__main__':
    main()
