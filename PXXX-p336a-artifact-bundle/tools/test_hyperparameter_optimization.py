#!/usr/bin/env python3
"""
超参数优化测试脚本

测试流程：
1. 优化Trend λ参数
2. 优化Markov阶数
3. 优化集成权重
4. 对比优化前后效果
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.hyperparameter_optimizer import HyperparameterOptimizer
from models.unified_predictor import UnifiedPredictionEngine


def main():
    print("=" * 100)
    print("🎯 超参数自动优化测试")
    print("=" * 100)
    
    # 加载数据
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    
    # 使用威力彩数据（数据量充足，1875期）
    lottery_type = 'POWER_LOTTO'
    all_draws = list(reversed(db.get_all_draws(lottery_type=lottery_type)))
    rules = get_lottery_rules(lottery_type)
    
    print(f"\n📊 数据集信息:")
    print(f"  彩种: {lottery_type}")
    print(f"  总期数: {len(all_draws)}")
    print(f"  最早: {all_draws[0]['draw']} ({all_draws[0]['date']})")
    print(f"  最新: {all_draws[-1]['draw']} ({all_draws[-1]['date']})")
    
    # 使用最近500期作为优化数据
    history = all_draws[-500:] if len(all_draws) > 500 else all_draws
    validation_periods = 80  # 使用最近80期验证
    
    print(f"\n使用数据: {len(history)} 期")
    print(f"验证期数: {validation_periods} 期")
    
    # 初始化
    engine = UnifiedPredictionEngine()
    optimizer = HyperparameterOptimizer(unified_engine=engine)
    
    # ===== 测试1: 优化Trend λ =====
    print("\n" + "=" * 100)
    print("📊 测试1: 优化Trend λ参数")
    print("=" * 100)
    
    trend_result = optimizer.optimize_trend_lambda(
        history=history,
        lottery_rules=rules,
        lambda_range=[0.01, 0.03, 0.05, 0.07, 0.10],
        validation_periods=validation_periods
    )
    
    print(f"\n✅ 最佳λ: {trend_result['best_lambda']:.3f}")
    print(f"   Match-3+率: {trend_result['best_score']['match_3_plus_rate']:.2f}%")
    print(f"   命中: {trend_result['best_score']['match_count']}/{trend_result['best_score']['total']}")
    
    # ===== 测试2: 优化Markov阶数 =====
    print("\n" + "=" * 100)
    print("📊 测试2: 优化Markov阶数")
    print("=" * 100)
    
    markov_result = optimizer.optimize_markov_order(
        history=history,
        lottery_rules=rules,
        order_range=[1, 2, 3],
        validation_periods=validation_periods
    )
    
    print(f"\n✅ 最佳阶数: {markov_result['best_order']}")
    print(f"   Match-3+率: {markov_result['best_score']['match_3_plus_rate']:.2f}%")
    print(f"   命中: {markov_result['best_score']['match_count']}/{markov_result['best_score']['total']}")
    
    # ===== 测试3: 优化集成权重 =====
    print("\n" + "=" * 100)
    print("📊 测试3: 优化集成权重")
    print("=" * 100)
    
    ensemble_result = optimizer.optimize_ensemble_weights(
        history=history,
        lottery_rules=rules,
        methods=['statistical_predict', 'deviation_predict', 'markov_predict'],
        validation_periods=validation_periods
    )
    
    print(f"\n✅ 最佳权重:")
    for method, weight in ensemble_result['weights_dict'].items():
        print(f"   {method}: {weight:.2f}")
    print(f"   Match-3+率: {ensemble_result['best_score']:.2f}%")
    
    # ===== 总结 =====
    print("\n" + "=" * 100)
    print("📊 优化结果总结")
    print("=" * 100)
    
    print(f"\n1. Trend λ优化:")
    print(f"   默认λ=0.05 → 最佳λ={trend_result['best_lambda']:.3f}")
    print(f"   Match-3+率: {trend_result['best_score']['match_3_plus_rate']:.2f}%")
    
    print(f"\n2. Markov阶数优化:")
    print(f"   默认阶数=1 → 最佳阶数={markov_result['best_order']}")
    print(f"   Match-3+率: {markov_result['best_score']['match_3_plus_rate']:.2f}%")
    
    print(f"\n3. 集成权重优化:")
    print(f"   Match-3+率: {ensemble_result['best_score']:.2f}%")
    
    # 保存结果
    import json
    output_file = os.path.join(project_root, 'tools', 'hyperparameter_optimization_results.json')
    results = {
        'lottery_type': lottery_type,
        'data_periods': len(history),
        'validation_periods': validation_periods,
        'trend_lambda': {
            'best_lambda': trend_result['best_lambda'],
            'match_3_plus_rate': trend_result['best_score']['match_3_plus_rate']
        },
        'markov_order': {
            'best_order': markov_result['best_order'],
            'match_3_plus_rate': markov_result['best_score']['match_3_plus_rate']
        },
        'ensemble_weights': {
            'weights': ensemble_result['weights_dict'],
            'match_3_plus_rate': ensemble_result['best_score']
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 结果已保存: {output_file}")
    print("=" * 100)


if __name__ == '__main__':
    main()
