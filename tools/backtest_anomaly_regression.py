#!/usr/bin/env python3
"""
异常检测+回归策略回测脚本

验证异常检测和回归预测的效果
目标: Match-3+ 率从11%提升到12%+
"""
import sys
import os
import numpy as np
from collections import defaultdict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.anomaly_regression import AnomalyRegressionPredictor
from models.unified_predictor import UnifiedPredictionEngine


def backtest_anomaly_regression(
    lottery_type: str = 'BIG_LOTTO',
    validation_periods: int = 200,
    comparison_baseline: bool = True
):
    """
    回测异常检测+回归策略
    
    Args:
        lottery_type: 彩票类型
        validation_periods: 验证期数
        comparison_baseline: 是否与基准策略对比
    """
    print("=" * 100)
    print(f"📊 异常检测+回归策略回测 - {lottery_type}")
    print("=" * 100)
    
    # 加载数据
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type=lottery_type)))
    rules = get_lottery_rules(lottery_type)
    
    if len(all_draws) < validation_periods + 50:
        print(f"❌ 数据不足，需要至少 {validation_periods + 50} 期")
        return
    
    # 初始化
    predictor = AnomalyRegressionPredictor()
    unified_engine = UnifiedPredictionEngine()
    
    # 统计数据
    stats = {
        'total': 0,
        'match_0': 0,
        'match_1': 0,
        'match_2': 0,
        'match_3': 0,
        'match_4': 0,
        'match_5': 0,
        'match_6': 0,
        'regression_used': 0,  # 使用回归策略的次数
        'normal_used': 0,       # 使用标准策略的次数
    }
    
    baseline_stats = defaultdict(int) if comparison_baseline else None
    
    # 滚动回测
    print(f"\n开始滚动回测 (最近 {validation_periods} 期)...")
    print(f"使用数据: 第 {all_draws[0]['draw']} 期到第 {all_draws[-1]['draw']} 期")
    print("-" * 100)
    
    hit_details = []
    
    for i in range(len(all_draws) - validation_periods, len(all_draws)):
        # 训练数据：前面所有期
        history = all_draws[:i]
        # 测试数据：当前期
        target = all_draws[i]
        
        if len(history) < 30:  # 至少需要30期历史（降低要求）
            continue
        
        # 异常检测+回归预测
        try:
            prediction = predictor.predict(history, rules, unified_engine)
            predicted_numbers = sorted(prediction['numbers'])
            is_regression = prediction.get('is_regression', False)
            
            if is_regression:
                stats['regression_used'] += 1
            else:
                stats['normal_used'] += 1
                
        except Exception as e:
            print(f"⚠️ 预测失败 (期号 {target['draw']}): {e}")
            continue
        
        # 计算匹配
        actual_numbers = sorted(target['numbers'])
        matched = set(predicted_numbers) & set(actual_numbers)
        match_count = len(matched)
        
        stats['total'] += 1
        stats[f'match_{match_count}'] += 1
        
        if match_count >= 3:
            hit_details.append({
                'draw': target['draw'],
                'date': target['date'],
                'predicted': predicted_numbers,
                'actual': actual_numbers,
                'matched': sorted(list(matched)),
                'match_count': match_count,
                'is_regression': is_regression,
                'anomaly_info': prediction.get('anomaly_info', {})
            })
        
        # 基准对比（5ME）
        if comparison_baseline:
            baseline_pred = _predict_5me(unified_engine, history, rules)
            baseline_matched = set(baseline_pred) & set(actual_numbers)
            baseline_match_count = len(baseline_matched)
            baseline_stats[f'match_{baseline_match_count}'] += 1
    
    # 显示结果
    print("\n" + "=" * 100)
    print("📊 回测结果")
    print("=" * 100)
    
    if stats['total'] == 0:
        print("❌ 无有效回测数据")
        return
    
    match_3_plus = stats['match_3'] + stats['match_4'] + stats['match_5'] + stats['match_6']
    match_3_plus_rate = (match_3_plus / stats['total']) * 100
    
    print(f"\n总期数: {stats['total']}")
    print(f"回归策略使用: {stats['regression_used']} 次 ({stats['regression_used']/stats['total']*100:.1f}%)")
    print(f"标准策略使用: {stats['normal_used']} 次 ({stats['normal_used']/stats['total']*100:.1f}%)")
    
    print(f"\n匹配分布:")
    for i in range(7):
        count = stats[f'match_{i}']
        pct = (count / stats['total']) * 100
        bar = '█' * int(pct / 2)
        print(f"  Match-{i}: {count:3d} ({pct:5.2f}%) {bar}")
    
    print(f"\n🎯 Match-3+ 率: {match_3_plus_rate:.2f}% ({match_3_plus}/{stats['total']})")
    
    # 显示Match-3+详情
    if hit_details:
        print(f"\n🏆 Match-3+ 命中详情 ({len(hit_details)} 次):")
        print("-" * 100)
        for detail in hit_details[:10]:  # 显示前10次
            regression_tag = "🔄" if detail['is_regression'] else "📊"
            anomaly_str = ""
            if detail['is_regression']:
                anomaly_types = detail['anomaly_info'].get('anomaly_types', [])
                if anomaly_types:
                    anomaly_str = f" | 异常: {', '.join(anomaly_types)}"
            
            print(f"{regression_tag} {detail['draw']} ({detail['date']}) "
                  f"Match-{detail['match_count']}: {detail['matched']}{anomaly_str}")
        
        if len(hit_details) > 10:
            print(f"... (还有 {len(hit_details) - 10} 次)")
    
    # 基准对比
    if comparison_baseline and baseline_stats:
        print("\n" + "=" * 100)
        print("📊 vs 基准策略 (5ME)")
        print("=" * 100)
        
        baseline_match_3_plus = sum(baseline_stats[f'match_{i}'] for i in range(3, 7))
        baseline_rate = (baseline_match_3_plus / stats['total']) * 100
        
        print(f"\n基准 Match-3+ 率: {baseline_rate:.2f}% ({baseline_match_3_plus}/{stats['total']})")
        print(f"新策略 Match-3+ 率: {match_3_plus_rate:.2f}% ({match_3_plus}/{stats['total']})")
        
        improvement = match_3_plus_rate - baseline_rate
        if improvement > 0:
            print(f"\n✅ 提升: +{improvement:.2f}% (绝对值)")
            print(f"   相对提升: +{(improvement/baseline_rate)*100:.1f}%")
        elif improvement < 0:
            print(f"\n⚠️ 下降: {improvement:.2f}%")
        else:
            print(f"\n➖ 持平")
    
    # 评估
    print("\n" + "=" * 100)
    print("🎯 策略评估")
    print("=" * 100)
    
    target_rate = 12.0  # 目标
    baseline_rate_expected = 11.0  # 当前最佳(5ME)
    
    if match_3_plus_rate >= target_rate:
        print(f"✅ 达标！Match-3+ 率 {match_3_plus_rate:.2f}% ≥ 目标 {target_rate}%")
    elif match_3_plus_rate >= baseline_rate_expected:
        print(f"⚠️ 接近目标。Match-3+ 率 {match_3_plus_rate:.2f}%，距离目标还差 {target_rate - match_3_plus_rate:.2f}%")
    else:
        print(f"❌ 未达标。Match-3+ 率 {match_3_plus_rate:.2f}%，需要进一步优化")
    
    print("=" * 100)
    
    return {
        'match_3_plus_rate': match_3_plus_rate,
        'total_periods': stats['total'],
        'regression_usage': stats['regression_used'] / stats['total'] if stats['total'] > 0 else 0,
        'stats': stats
    }


def _predict_5me(engine, history, rules):
    """使用5ME策略预测（作为基准）"""
    methods = [
        'statistical_predict',
        'deviation_predict',
        'markov_predict',
        'hot_cold_mix_predict',
        'trend_predict'
    ]
    
    from collections import Counter
    number_votes = Counter()
    
    for method_name in methods:
        method = getattr(engine, method_name, None)
        if method:
            try:
                result = method(history, rules)
                number_votes.update(result['numbers'])
            except:
                pass
    
    pick_count = rules.get('pickCount', 6)
    return sorted([num for num, _ in number_votes.most_common(pick_count)])


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='异常检测+回归策略回测')
    parser.add_argument('--lottery', default='BIG_LOTTO', 
                       choices=['BIG_LOTTO', 'POWER_LOTTO'],
                       help='彩票类型')
    parser.add_argument('--periods', type=int, default=200,
                       help='验证期数')
    parser.add_argument('--no-baseline', action='store_true',
                       help='不对比基准')
    
    args = parser.parse_args()
    
    backtest_anomaly_regression(
        lottery_type=args.lottery,
        validation_periods=args.periods,
        comparison_baseline=not args.no_baseline
    )
