#!/usr/bin/env python3
"""
回測驗證優化方法的效果
對比基線方法 vs 優化方法
"""
import sys
import os
import json
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_bayesian_predictor import OptimizedBayesianPredictor
from models. improved_special_predictor import ImprovedSpecialPredictor


def evaluate_prediction(predicted_nums, predicted_special, actual_nums, actual_special):
    """評估單次預測結果"""
    main_hits = len(set(predicted_nums) & set(actual_nums))
    special_hit = (predicted_special == actual_special)
    
    return {
        'main_hits': main_hits,
        'special_hit': special_hit,
        'total_score': main_hits * 10 + (5 if special_hit else 0)
    }


def backtest_method(method_name, predict_func, history, test_size=30):
    """回測單一方法"""
    results = []
    rules = get_lottery_rules('POWER_LOTTO')
    
    for i in range(test_size):
        # 使用前N期預測第N+1期
        train_history = history[i+1:]
        test_draw = history[i]
        
        try:
            prediction = predict_func(train_history, rules)
            pred_nums = prediction.get('numbers', [])
            pred_special = prediction.get('special', 0)
            
            actual_nums = test_draw.get('numbers', [])
            actual_special = test_draw.get('special', 0)
            
            eval_result = evaluate_prediction(pred_nums, pred_special, actual_nums, actual_special)
            eval_result['draw'] = test_draw.get('draw')
            results.append(eval_result)
            
        except Exception as e:
            print(f"  {method_name} - Draw {test_draw.get('draw')}: Error - {e}")
    
    # 統計
    total_tests = len(results)
    if total_tests == 0:
        return None
    
    main_hit_dist = Counter([r['main_hits'] for r in results])
    special_hit_count = sum(1 for r in results if r['special_hit'])
    avg_main_hits = sum(r['main_hits'] for r in results) / total_tests
    avg_score = sum(r['total_score'] for r in results) / total_tests
    
    # 計算各級別命中率
    hit_3plus = sum(1 for r in results if r['main_hits'] >= 3)
    hit_4plus = sum(1 for r in results if r['main_hits'] >= 4)
    hit_5plus = sum(1 for r in results if r['main_hits'] >= 5)
    hit_6 = sum(1 for r in results if r['main_hits'] == 6)
    
    return {
        'method': method_name,
        'total_tests': total_tests,
        'avg_main_hits': avg_main_hits,
        'avg_score': avg_score,
        'main_hit_distribution': dict(main_hit_dist),
        'special_hit_rate': special_hit_count / total_tests * 100,
        'hit_3plus_rate': hit_3plus / total_tests * 100,
        'hit_4plus_rate': hit_4plus / total_tests * 100,
        'hit_5plus_rate': hit_5plus / total_tests * 100,
        'hit_6_rate': hit_6 / total_tests * 100,
        'results': results
    }


def main():
    print("=" * 100)
    print("優化方法回測驗證")
    print("=" * 100)
    
    # 載入數據
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if not all_history or len(all_history) < 50:
        print("❌ 歷史數據不足")
        return
    
    # 使用最近50期進行回測（前30期用於測試，後20期保留）
    history = all_history[:50]
    test_size = 30
    
    print(f"\n回測設定:")
    print(f"  測試期數: {test_size} 期")
    print(f"  期數範圍: {history[test_size-1]['draw']} ~ {history[0]['draw']}")
    print()
    
    # 定義測試方法
    baseline_engine = UnifiedPredictionEngine()
    optimized_bayesian = OptimizedBayesianPredictor()
    
    methods = [
        ('Baseline_Bayesian', baseline_engine.bayesian_predict),
        ('Optimized_Bayesian', optimized_bayesian.predict),
    ]
    
    # 回測
    all_results = []
    
    for method_name, predict_func in methods:
        print(f"正在回測: {method_name}...")
        result = backtest_method(method_name, predict_func, history, test_size)
        
        if result:
            all_results.append(result)
            
            print(f"  ✓ 完成 - 平均命中: {result['avg_main_hits']:.2f}/6")
            print(f"           第二區命中率: {result['special_hit_rate']:.1f}%")
            print(f"           3+命中率: {result['hit_3plus_rate']:.1f}%")
        else:
            print(f"  ✗ 失敗")
        print()
    
    # 生成比較報告
    print("=" * 100)
    print("回測結果比較")
    print("=" * 100)
    
    # 表格輸出
    header = f"{'方法':<25} | {'平均命中':<10} | {'第二區%':<10} | {'3+%':<8} | {'4+%':<8} | {'5+%':<8} | {'6中%':<8}"
    print(header)
    print("-" * 100)
    
    for result in all_results:
        row = (
            f"{result['method']:<25} | "
            f"{result['avg_main_hits']:>4.2f}/6    | "
            f"{result['special_hit_rate']:>7.1f}%  | "
            f"{result['hit_3plus_rate']:>6.1f}% | "
            f"{result['hit_4plus_rate']:>6.1f}% | "
            f"{result['hit_5plus_rate']:>6.1f}% | "
            f"{result['hit_6_rate']:>6.1f}%"
        )
        print(row)
    
    # 詳細命中分布
    print("\n" + "=" * 100)
    print("命中分布詳細")
    print("=" * 100)
    
    for result in all_results:
        print(f"\n{result['method']}:")
        dist = result['main_hit_distribution']
        for hits in range(7):
            count = dist.get(hits, 0)
            rate = count / result['total_tests'] * 100
            bar = '█' * int(rate / 2)
            print(f"  {hits} 個: {count:3d} 次 ({rate:5.1f}%) {bar}")
    
    # 計算改進幅度
    if len(all_results) >= 2:
        baseline = all_results[0]
        optimized = all_results[1]
        
        print("\n" + "=" * 100)
        print("改進效果分析")
        print("=" * 100)
        
        main_improvement = ((optimized['avg_main_hits'] - baseline['avg_main_hits']) 
                          / baseline['avg_main_hits'] * 100)
        special_improvement = optimized['special_hit_rate'] - baseline['special_hit_rate']
        hit3_improvement = optimized['hit_3plus_rate'] - baseline['hit_3plus_rate']
        
        print(f"\n平均命中數: {baseline['avg_main_hits']:.2f} → {optimized['avg_main_hits']:.2f} "
              f"({main_improvement:+.1f}%)")
        print(f"第二區命中率: {baseline['special_hit_rate']:.1f}% → {optimized['special_hit_rate']:.1f}% "
              f"({special_improvement:+.1f} percentage points)")
        print(f"3+命中率: {baseline['hit_3plus_rate']:.1f}% → {optimized['hit_3plus_rate']:.1f}% "
              f"({hit3_improvement:+.1f} percentage points)")
    
    # 保存結果
    output_file = os.path.join(project_root, 'tools', 'optimization_backtest_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        # 簡化results以便保存
        simplified_results = []
        for r in all_results:
            simplified = r.copy()
            # 只保留摘要，不保留詳細results
            del simplified['results']
            simplified_results.append(simplified)
        
        json.dump(simplified_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 回測結果已保存: {output_file}")
    print("=" * 100)


if __name__ == '__main__':
    main()
