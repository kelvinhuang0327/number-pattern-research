#!/usr/bin/env python3
"""
今彩539最佳方法和訓練窗口優化分析
測試不同預測方法和訓練窗口大小的組合，找出2025年實測表現最佳的配置
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine
from collections import defaultdict
import json

def calculate_matches(predicted, actual):
    """計算匹配數"""
    return len(set(predicted['numbers']) & set(actual['numbers']))

def test_method_window(method_name, window_size, draws_2025, all_draws, rules):
    """測試特定方法和窗口大小的組合"""
    predictor = prediction_engine

    if not hasattr(predictor, method_name):
        return None

    method = getattr(predictor, method_name)

    total_matches = 0
    win_count = 0  # >=3個匹配
    test_count = 0

    for target_draw in draws_2025:
        target_index = all_draws.index(target_draw)

        train_start = min(target_index + 1, len(all_draws))
        train_end = min(target_index + 1 + window_size, len(all_draws))
        history = all_draws[train_start:train_end]

        if len(history) < 30:
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
        'method': method_name,
        'window_size': window_size,
        'test_count': test_count,
        'avg_matches': total_matches / test_count,
        'win_rate': win_count / test_count,
        'win_count': win_count
    }

def main():
    print("="*80)
    print("🎯 今彩539最佳方法和訓練窗口優化分析")
    print("="*80)

    # 載入數據
    db_path = os.path.join(os.path.dirname(__file__), 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = db.get_all_draws('DAILY_539')

    # 篩選2025年數據
    draws_2025 = [d for d in all_draws if d['date'].startswith('2025') or d['date'].startswith('114')]

    print(f"\n📊 數據概況:")
    print(f"  今彩539總期數: {len(all_draws)}")
    print(f"  2025年期數: {len(draws_2025)}")
    print(f"  最新期號: {draws_2025[0]['draw']} ({draws_2025[0]['date']})")

    rules = get_lottery_rules('DAILY_539')

    # 定義要測試的方法
    methods = [
        ('frequency_predict', '頻率預測'),
        ('trend_predict', '趨勢預測'),
        ('deviation_predict', '偏差預測'),
        ('bayesian_predict', 'Bayesian預測'),
        ('monte_carlo_predict', '蒙特卡洛預測'),
        ('markov_predict', 'Markov鏈預測'),
        ('odd_even_balance_predict', '奇偶平衡預測'),
        ('zone_balance_predict', '區域平衡預測'),
        ('hot_cold_mix_predict', '冷熱混合預測'),
        ('sum_range_predict', '總和範圍預測'),
        ('ensemble_predict', '集成預測'),
        ('ensemble_advanced_predict', '進階集成預測'),
    ]

    # 定義要測試的窗口大小
    window_sizes = [50, 100, 150, 200, 300, 400, 500]

    print(f"\n🔬 測試配置:")
    print(f"  預測方法: {len(methods)} 種")
    print(f"  訓練窗口: {window_sizes}")
    print(f"  測試組合: {len(methods) * len(window_sizes)} 個")

    all_results = {}

    for method_name, display_name in methods:
        print(f"\n{'='*80}")
        print(f"📈 測試方法: {display_name}")
        print(f"{'='*80}")

        method_results = []

        for window in window_sizes:
            print(f"  窗口 {window:3d} 期...", end=' ', flush=True)
            result = test_method_window(method_name, window, draws_2025, all_draws, rules)

            if result:
                method_results.append(result)
                print(f"✓ 平均匹配: {result['avg_matches']:.3f}, 中獎率: {result['win_rate']:.2%}")
            else:
                print("✗ 失敗")

        all_results[display_name] = method_results

        # 找出該方法的最佳窗口
        if method_results:
            best = max(method_results, key=lambda x: (x['win_rate'], x['avg_matches']))
            print(f"\n  🏆 最佳窗口: {best['window_size']} 期")
            print(f"     平均匹配: {best['avg_matches']:.3f}")
            print(f"     中獎率: {best['win_rate']:.2%} ({best['win_count']}/{best['test_count']})")

    # 生成總排名
    print(f"\n{'='*80}")
    print(f"🏆 整體最佳配置排名（前10名）")
    print(f"{'='*80}\n")

    # 收集所有結果
    all_configs = []
    for method_name, results in all_results.items():
        for r in results:
            all_configs.append({
                'method': method_name,
                'window': r['window_size'],
                'avg_matches': r['avg_matches'],
                'win_rate': r['win_rate'],
                'win_count': r['win_count'],
                'test_count': r['test_count']
            })

    # 排序（優先中獎率，其次平均匹配）
    all_configs.sort(key=lambda x: (x['win_rate'], x['avg_matches']), reverse=True)

    print(f"{'排名':<6} {'方法':<20} {'窗口':<8} {'平均匹配':<12} {'中獎率':<12} {'中獎次數':<12}")
    print(f"{'-'*80}")

    for i, config in enumerate(all_configs[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        print(f"{medal:<6} "
              f"{config['method']:<18} "
              f"{config['window']:<8} "
              f"{config['avg_matches']:<12.3f} "
              f"{config['win_rate']:<12.2%} "
              f"{config['win_count']}/{config['test_count']}")

    # 儲存完整報告
    report = {
        'test_date': '2025-12-26',
        'lottery_type': 'DAILY_539',
        'year': '2025',
        'total_periods': len(draws_2025),
        'methods_tested': [m[1] for m in methods],
        'window_sizes_tested': window_sizes,
        'all_results': all_results,
        'top_10': all_configs[:10]
    }

    report_file = 'DAILY539_OPTIMIZATION_2025.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 詳細報告已儲存至: {report_file}")

    # 最佳配置建議
    best_config = all_configs[0]
    print(f"\n{'='*80}")
    print(f"💡 今彩539最佳配置建議")
    print(f"{'='*80}\n")
    print(f"🥇 方法: {best_config['method']}")
    print(f"   訓練窗口: {best_config['window']} 期")
    print(f"   平均匹配: {best_config['avg_matches']:.3f} 個號碼")
    print(f"   中獎率: {best_config['win_rate']:.2%} ({best_config['win_count']}/{best_config['test_count']} 期)")
    print(f"\n建議使用此配置進行今彩539預測！")

if __name__ == '__main__':
    main()
