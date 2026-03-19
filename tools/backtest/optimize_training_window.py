#!/usr/bin/env python3
"""
測試不同訓練窗口大小對三種方法的影響
找出每種方法的最佳訓練數據量
"""
import sys
import os
from collections import defaultdict
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine

def calculate_matches(predicted, actual):
    """計算匹配數"""
    pred_set = set(predicted['numbers'])
    actual_set = set(actual['numbers'])
    return len(pred_set & actual_set)

def test_window_size(method_name, window_size, draws_2025, all_draws, rules):
    """測試特定窗口大小的效果"""
    predictor = prediction_engine
    method = getattr(predictor, method_name)

    total_matches = 0
    win_count = 0  # >=3個匹配
    test_count = 0

    for target_draw in draws_2025:
        target_index = all_draws.index(target_draw)

        # 使用指定窗口大小
        train_start = min(target_index + 1, len(all_draws))
        train_end = min(target_index + 1 + window_size, len(all_draws))
        history = all_draws[train_start:train_end]

        if len(history) < 30:  # 最低要求
            continue

        try:
            prediction = method(history, rules)
            matches = calculate_matches(prediction, target_draw)

            total_matches += matches
            if matches >= 3:
                win_count += 1
            test_count += 1

        except Exception:
            continue

    if test_count == 0:
        return None

    return {
        'window_size': window_size,
        'test_count': test_count,
        'avg_matches': total_matches / test_count,
        'win_rate': win_count / test_count,
        'win_count': win_count
    }

def main():
    print("="*80)
    print("🔍 訓練窗口大小優化分析")
    print("="*80)

    # 載入數據
    db_path = os.path.join(os.path.dirname(__file__), 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = db.get_all_draws('BIG_LOTTO')
    draws_2025 = [d for d in all_draws if d['date'].startswith('2025') or d['date'].startswith('114')]

    print(f"\n📊 測試數據: 2025年 {len(draws_2025)} 期")

    rules = get_lottery_rules('BIG_LOTTO')

    # 定義要測試的方法和窗口大小
    methods = [
        ('zone_balance_predict', '區域平衡預測'),
        ('markov_predict', 'Markov鏈預測'),
        ('odd_even_balance_predict', '奇偶平衡預測'),
    ]

    window_sizes = [50, 100, 150, 200, 300, 400, 500]

    all_results = {}

    for method_name, display_name in methods:
        print(f"\n{'='*80}")
        print(f"🔬 測試方法: {display_name}")
        print(f"{'='*80}\n")

        method_results = []

        for window in window_sizes:
            print(f"  測試窗口: {window} 期...", end=' ')
            result = test_window_size(method_name, window, draws_2025, all_draws, rules)

            if result:
                method_results.append(result)
                print(f"✓ 平均匹配: {result['avg_matches']:.3f}, 中獎率: {result['win_rate']:.2%}")
            else:
                print("✗ 數據不足")

        all_results[display_name] = method_results

        # 找出最佳窗口
        if method_results:
            best = max(method_results, key=lambda x: (x['win_rate'], x['avg_matches']))
            print(f"\n  🏆 最佳窗口: {best['window_size']} 期")
            print(f"     平均匹配: {best['avg_matches']:.3f}")
            print(f"     中獎率: {best['win_rate']:.2%} ({best['win_count']}/{best['test_count']})")

    # 生成對比報告
    print(f"\n{'='*80}")
    print(f"📊 各方法最佳窗口對比")
    print(f"{'='*80}\n")

    print(f"{'方法':<20} {'最佳窗口':<12} {'平均匹配':<12} {'中獎率':<12} {'中獎次數':<12}")
    print(f"{'-'*80}")

    summary = []
    for display_name, results in all_results.items():
        if results:
            best = max(results, key=lambda x: (x['win_rate'], x['avg_matches']))
            summary.append({
                'method': display_name,
                'best_window': best['window_size'],
                'avg_matches': best['avg_matches'],
                'win_rate': best['win_rate'],
                'win_count': best['win_count']
            })

            print(f"{display_name:<18} "
                  f"{best['window_size']:<12} "
                  f"{best['avg_matches']:<12.3f} "
                  f"{best['win_rate']:<12.2%} "
                  f"{best['win_count']}/{best['test_count']}")

    # 視覺化比較
    print(f"\n{'='*80}")
    print(f"📈 窗口大小對平均匹配數的影響")
    print(f"{'='*80}\n")

    for display_name, results in all_results.items():
        print(f"\n{display_name}:")
        for r in results:
            bar_length = int(r['avg_matches'] * 30)
            bar = '█' * bar_length
            print(f"  {r['window_size']:3d}期: {r['avg_matches']:.3f} {bar}")

    # 儲存結果
    report = {
        'test_date': '2025-12-26',
        'window_sizes_tested': window_sizes,
        'methods_tested': [m[1] for m in methods],
        'detailed_results': all_results,
        'summary': summary
    }

    with open('WINDOW_SIZE_OPTIMIZATION.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 詳細報告已儲存至: WINDOW_SIZE_OPTIMIZATION.json")

    # 結論
    print(f"\n{'='*80}")
    print(f"💡 結論與建議")
    print(f"{'='*80}\n")

    best_overall = max(summary, key=lambda x: (x['win_rate'], x['avg_matches']))
    print(f"🥇 整體最佳配置:")
    print(f"   方法: {best_overall['method']}")
    print(f"   訓練窗口: {best_overall['best_window']} 期")
    print(f"   平均匹配: {best_overall['avg_matches']:.3f}")
    print(f"   中獎率: {best_overall['win_rate']:.2%}")

    print(f"\n建議針對不同方法使用各自的最佳窗口大小！")

if __name__ == '__main__':
    main()
