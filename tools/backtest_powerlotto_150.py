#!/usr/bin/env python3
"""
威力彩 ML 方法全面回测 - 150期
测试所有实作的机器学习方法
"""
import sys
import os
import io
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.ensemble_stacking import EnsembleStackingPredictor

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def backtest_method(method_name, predict_func, history, rules, test_periods):
    """回测单一方法"""
    wins = 0
    match_3_plus = 0
    match_2_special = 0
    special_hits = 0
    total = 0
    
    match_distribution = Counter()
    
    for i in range(test_periods):
        target_idx = len(history) - test_periods + i
        if target_idx <= 0:
            continue
        
        target_draw = history[target_idx]
        hist = history[:target_idx]
        
        if len(hist) < 10:
            continue
        
        try:
            result = predict_func(hist, rules)
            
            if not result or 'numbers' not in result:
                continue
            
            predicted = set(result['numbers'])
            actual = set(target_draw['numbers'])
            
            match_count = len(predicted & actual)
            special_match = result.get('special') == target_draw.get('special')
            
            match_distribution[match_count] += 1
            
            if special_match:
                special_hits += 1
            
            # 威力彩中奖判定
            if match_count >= 3:
                match_3_plus += 1
                wins += 1
            elif match_count >= 2 and special_match:
                match_2_special += 1
                wins += 1
            elif match_count >= 1 and special_match:
                wins += 1
            
            total += 1
            
        except Exception as e:
            continue
    
    if total == 0:
        return None
    
    return {
        'method': method_name,
        'win_rate': wins / total * 100,
        'match_3_plus_rate': match_3_plus / total * 100,
        'match_2_special_rate': match_2_special / total * 100,
        'special_hit_rate': special_hits / total * 100,
        'total_periods': total,
        'match_distribution': dict(match_distribution)
    }

def run_powerlotto_150_backtest():
    """执行威力彩150期全面回测"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    # 测试最近150期
    test_periods = min(150, len(all_draws) - 50)
    
    print("=" * 80)
    print(f"🔬 威力彩 ML 模型全面回测 (最近 {test_periods} 期)")
    print("=" * 80)
    print(f"总历史数据: {len(all_draws)} 期")
    print(f"测试期数: {test_periods} 期")
    print(f"号码池: {rules['minNumber']}-{rules['maxNumber']} (共 {rules['maxNumber']} 个号码)")
    print(f"选号数: {rules['pickCount']} 个")
    print(f"特别号池: 1-8")
    print("-" * 80)
    
    # 初始化预测引擎
    engine = UnifiedPredictionEngine()
    ensemble = EnsembleStackingPredictor()
    
    # 定义测试方法
    test_methods = {
        '频率分析 (Frequency)': lambda h, r: engine.frequency_predict(h, r),
        '贝叶斯推论 (Bayesian)': lambda h, r: engine.bayesian_predict(h, r),
        '马可夫链 (Markov)': lambda h, r: engine.markov_predict(h, r),
        '趋势回归 (Trend)': lambda h, r: engine.trend_predict(h, r),
        '偏差分析 (Deviation)': lambda h, r: engine.deviation_predict(h, r),
        '冷热混合 (Hot-Cold Mix)': lambda h, r: engine.hot_cold_mix_predict(h, r),
        '统计综合 (Statistical)': lambda h, r: engine.statistical_predict(h, r),
        'Ensemble Stacking (Top3)': lambda h, r: ensemble.predict_with_features(h, r, use_lstm=False),
    }
    
    # 执行回测
    results = []
    
    for method_name, predict_func in test_methods.items():
        print(f"\n🧪 测试方法: {method_name}")
        result = backtest_method(method_name, predict_func, all_draws, rules, test_periods)
        
        if result:
            results.append(result)
            print(f"  ✅ 总胜率: {result['win_rate']:.2f}%")
            print(f"  📊 Match-3+: {result['match_3_plus_rate']:.2f}%")
            print(f"  🎯 特别号: {result['special_hit_rate']:.2f}%")
        else:
            print(f"  ❌ 测试失败")
    
    # 排序结果
    results.sort(key=lambda x: x['win_rate'], reverse=True)
    
    # 显示排行榜
    print("\n" + "=" * 80)
    print("🏆 方法排行榜 (依总胜率)")
    print("=" * 80)
    
    print(f"\n{'排名':<5} {'方法':<35} {'总胜率':<10} {'Match-3+':<10} {'特别号':<10}")
    print("-" * 80)
    
    for i, result in enumerate(results, 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"{emoji} {i:<3} {result['method']:<35} {result['win_rate']:>8.2f}% {result['match_3_plus_rate']:>8.2f}% {result['special_hit_rate']:>8.2f}%")
    
    # 详细分析最佳方法
    if results:
        best = results[0]
        print("\n" + "=" * 80)
        print(f"🎯 最佳方法详细分析: {best['method']}")
        print("=" * 80)
        print(f"总胜率: {best['win_rate']:.2f}%")
        print(f"Match-3+ 率: {best['match_3_plus_rate']:.2f}%")
        print(f"Match-2+S 率: {best['match_2_special_rate']:.2f}%")
        print(f"特别号命中率: {best['special_hit_rate']:.2f}%")
        print(f"测试期数: {best['total_periods']}")
        
        print("\n命中分布:")
        for match_count in sorted(best['match_distribution'].keys(), reverse=True):
            count = best['match_distribution'][match_count]
            pct = count / best['total_periods'] * 100
            bar = "█" * int(pct / 2)
            print(f"  Match-{match_count}: {count:3d} 次 ({pct:5.1f}%) {bar}")
    
    # Top 3 对比分析
    print("\n" + "=" * 80)
    print("📊 Top 3 方法详细对比")
    print("=" * 80)
    
    print(f"\n{'指标':<20} {'第1名':<25} {'第2名':<25} {'第3名':<25}")
    print("-" * 80)
    
    if len(results) >= 3:
        print(f"{'方法':<20} {results[0]['method']:<25} {results[1]['method']:<25} {results[2]['method']:<25}")
        print(f"{'总胜率':<20} {results[0]['win_rate']:>23.2f}% {results[1]['win_rate']:>23.2f}% {results[2]['win_rate']:>23.2f}%")
        print(f"{'Match-3+':<20} {results[0]['match_3_plus_rate']:>23.2f}% {results[1]['match_3_plus_rate']:>23.2f}% {results[2]['match_3_plus_rate']:>23.2f}%")
        print(f"{'Match-2+S':<20} {results[0]['match_2_special_rate']:>23.2f}% {results[1]['match_2_special_rate']:>23.2f}% {results[2]['match_2_special_rate']:>23.2f}%")
        print(f"{'特别号命中':<20} {results[0]['special_hit_rate']:>23.2f}% {results[1]['special_hit_rate']:>23.2f}% {results[2]['special_hit_rate']:>23.2f}%")
    
    # 推荐配置
    print("\n" + "=" * 80)
    print("💡 威力彩优化建议")
    print("=" * 80)
    
    if results:
        top_3 = [r['method'] for r in results[:3]]
        print(f"1. 建议使用 Top 3 方法: {top_3}")
        
        if results[0]['win_rate'] > 20:
            print(f"2. 最佳方法 '{results[0]['method']}' 表现优异 (>{results[0]['win_rate']:.1f}%)，建议作为主要策略")
        else:
            print(f"2. 当前最佳方法胜率为 {results[0]['win_rate']:.1f}%")
        
        avg_special = sum(r['special_hit_rate'] for r in results) / len(results)
        if avg_special > 15:
            print(f"3. 特别号平均命中率 {avg_special:.1f}%，表现良好")
        else:
            print(f"3. 特别号平均命中率 {avg_special:.1f}%，建议加强 Sum-Bias 逻辑")
        
        # 判断是否需要组合策略
        if results[0]['match_3_plus_rate'] < 5:
            print(f"4. Match-3+ 率 {results[0]['match_3_plus_rate']:.2f}% 偏低，建议使用多注组合策略")
        else:
            print(f"4. Match-3+ 率 {results[0]['match_3_plus_rate']:.2f}% 表现良好")
    
    # 生成预测建议
    print("\n" + "=" * 80)
    print("🎯 下期预测建议")
    print("=" * 80)
    
    if results:
        print(f"推荐方法: {results[0]['method']}")
        print(f"预期总胜率: {results[0]['win_rate']:.2f}%")
        print(f"预期 Match-3+ 率: {results[0]['match_3_plus_rate']:.2f}%")
        
        # 生成实际预测
        try:
            best_func = test_methods[results[0]['method']]
            prediction = best_func(all_draws, rules)
            
            print(f"\n预测号码: {prediction['numbers']}")
            print(f"特别号: {prediction['special']}")
            print(f"信心度: {prediction.get('confidence', 0.5):.2%}")
        except:
            print("\n无法生成预测（数据格式问题）")

if __name__ == '__main__':
    run_powerlotto_150_backtest()
