#!/usr/bin/env python3
"""
威力彩组合策略测试 - 寻找最优组合
测试不同方法组合（2注、3注、4注）以提升成功率
"""
import sys
import os
import io
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.ensemble_stacking import EnsembleStackingPredictor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_combination(combo_name, predict_funcs, history, rules, test_periods):
    """测试方法组合"""
    wins = 0
    match_3_plus = 0
    total = 0
    max_matches = []
    
    for i in range(test_periods):
        target_idx = len(history) - test_periods + i
        if target_idx <= 0:
            continue
        
        target_draw = history[target_idx]
        hist = history[:target_idx]
        
        if len(hist) < 10:
            continue
        
        actual = set(target_draw['numbers'])
        actual_special = target_draw.get('special')
        
        # 生成所有预测
        period_win = False
        period_match3 = False
        best_match = 0
        
        for func in predict_funcs:
            try:
                result = func(hist, rules)
                if not result or 'numbers' not in result:
                    continue
                
                predicted = set(result['numbers'])
                predicted_special = result.get('special')
                
                match_count = len(predicted & actual)
                special_match = predicted_special == actual_special
                
                best_match = max(best_match, match_count)
                
                # 判断这一注是否中奖
                if match_count >= 3:
                    period_match3 = True
                    period_win = True
                elif match_count >= 2 and special_match:
                    period_win = True
                elif match_count >= 1 and special_match:
                    period_win = True
            except:
                continue
        
        max_matches.append(best_match)
        
        if period_match3:
            match_3_plus += 1
        if period_win:
            wins += 1
        
        total += 1
    
    if total == 0:
        return None
    
    return {
        'combination': combo_name,
        'num_bets': len(predict_funcs),
        'win_rate': wins / total * 100,
        'match_3_plus_rate': match_3_plus / total * 100,
        'total_periods': total,
        'avg_best_match': sum(max_matches) / len(max_matches) if max_matches else 0,
        'cost_efficiency': (match_3_plus / total * 100) / len(predict_funcs) if len(predict_funcs) > 0 else 0
    }

def run_combination_tests():
    """运行所有组合测试"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    test_periods = min(150, len(all_draws) - 50)
    
    engine = UnifiedPredictionEngine()
    ensemble = EnsembleStackingPredictor()
    
    # 定义所有方法
    methods = {
        'trend': lambda h, r: engine.trend_predict(h, r),
        'ensemble': lambda h, r: ensemble.predict_with_features(h, r, use_lstm=False),
        'bayesian': lambda h, r: engine.bayesian_predict(h, r),
        'markov': lambda h, r: engine.markov_predict(h, r),
        'frequency': lambda h, r: engine.frequency_predict(h, r),
        'deviation': lambda h, r: engine.deviation_predict(h, r),
        'statistical': lambda h, r: engine.statistical_predict(h, r),
    }
    
    print("=" * 80)
    print(f"🔬 威力彩组合策略测试 (最近 {test_periods} 期)")
    print("=" * 80)
    print("测试配置:")
    print("  - 单注方法 (7种)")
    print("  - 双注组合 (21种)")
    print("  - 三注组合 (35种)")
    print("  - 四注组合 (35种)")
    print("-" * 80)
    
    results = []
    
    # 1. 测试单注 (基准)
    print("\n📍 第1轮: 测试单注方法 (基准)")
    for name, func in methods.items():
        combo_name = f"单注: {name}"
        result = test_combination(combo_name, [func], all_draws, rules, test_periods)
        if result:
            results.append(result)
            print(f"  {combo_name:<30} Match-3+: {result['match_3_plus_rate']:>5.2f}%  胜率: {result['win_rate']:>5.2f}%")
    
    # 2. 测试双注组合
    print("\n📍 第2轮: 测试双注组合 (Top 10)")
    two_combos = list(combinations(methods.items(), 2))
    two_results = []
    
    for (name1, func1), (name2, func2) in two_combos:
        combo_name = f"双注: {name1}+{name2}"
        result = test_combination(combo_name, [func1, func2], all_draws, rules, test_periods)
        if result:
            two_results.append(result)
    
    # 只显示 Top 10
    two_results.sort(key=lambda x: x['match_3_plus_rate'], reverse=True)
    for result in two_results[:10]:
        results.append(result)
        print(f"  {result['combination']:<40} Match-3+: {result['match_3_plus_rate']:>5.2f}%  效益: {result['cost_efficiency']:>5.2f}%")
    
    # 3. 测试三注组合
    print("\n📍 第3轮: 测试三注组合 (Top 5最优)")
    
    # 预设几个有潜力的组合
    three_combos = [
        ('trend', 'ensemble', 'bayesian'),
        ('trend', 'bayesian', 'markov'),
        ('ensemble', 'bayesian', 'markov'),
        ('trend', 'markov', 'frequency'),
        ('trend', 'ensemble', 'markov'),
    ]
    
    three_results = []
    for combo in three_combos:
        funcs = [methods[name] for name in combo]
        combo_name = f"三注: {'+'.join(combo)}"
        result = test_combination(combo_name, funcs, all_draws, rules, test_periods)
        if result:
            three_results.append(result)
            results.append(result)
            print(f"  {combo_name:<50} Match-3+: {result['match_3_plus_rate']:>5.2f}%  效益: {result['cost_efficiency']:>5.2f}%")
    
    # 4. 测试四注组合
    print("\n📍 第4轮: 测试四注组合 (Top 3精选)")
    
    four_combos = [
        ('trend', 'ensemble', 'bayesian', 'markov'),
        ('trend', 'bayesian', 'markov', 'frequency'),
        ('trend', 'ensemble', 'markov', 'frequency'),
    ]
    
    four_results = []
    for combo in four_combos:
        funcs = [methods[name] for name in combo]
        combo_name = f"四注: {'+'.join(combo)}"
        result = test_combination(combo_name, funcs, all_draws, rules, test_periods)
        if result:
            four_results.append(result)
            results.append(result)
            print(f"  {combo_name:<60} Match-3+: {result['match_3_plus_rate']:>5.2f}%  效益: {result['cost_efficiency']:>5.2f}%")
    
    # 综合分析
    print("\n" + "=" * 80)
    print("📊 综合分析")
    print("=" * 80)
    
    # 按 Match-3+ 率排序
    results.sort(key=lambda x: x['match_3_plus_rate'], reverse=True)
    
    print(f"\n🏆 Match-3+ 率 Top 10:")
    print(f"{'排名':<5} {'组合':<60} {'Match-3+':<10} {'成本':<8} {'效益':<10}")
    print("-" * 80)
    for i, result in enumerate(results[:10], 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"{emoji} {i:<3} {result['combination']:<60} {result['match_3_plus_rate']:>8.2f}% {result['num_bets']:>6}注 {result['cost_efficiency']:>8.2f}%")
    
    # 按成本效益排序
    results.sort(key=lambda x: x['cost_efficiency'], reverse=True)
    
    print(f"\n💰 成本效益 Top 10 (Match-3+ % / 注数):")
    print(f"{'排名':<5} {'组合':<60} {'效益':<10} {'Match-3+':<10} {'成本':<8}")
    print("-" * 80)
    for i, result in enumerate(results[:10], 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"{emoji} {i:<3} {result['combination']:<60} {result['cost_efficiency']:>8.2f}% {result['match_3_plus_rate']:>8.2f}% {result['num_bets']:>6}注")
    
    # 最终推荐
    print("\n" + "=" * 80)
    print("🎯 最终推荐")
    print("=" * 80)
    
    # 找出最佳单注
    single_bets = [r for r in results if r['num_bets'] == 1]
    if single_bets:
        best_single = max(single_bets, key=lambda x: x['match_3_plus_rate'])
        print(f"\n✅ 最佳单注方案: {best_single['combination']}")
        print(f"   Match-3+ 率: {best_single['match_3_plus_rate']:.2f}%")
        print(f"   总胜率: {best_single['win_rate']:.2f}%")
    
    # 找出最佳性价比组合
    best_value = results[0] if results else None
    if best_value:
        print(f"\n💎 最佳性价比方案: {best_value['combination']}")
        print(f"   Match-3+ 率: {best_value['match_3_plus_rate']:.2f}%")
        print(f"   成本: {best_value['num_bets']} 注")
        print(f"   效益: {best_value['cost_efficiency']:.2f}% per 注")
    
    # 找出最高绝对成功率
    results.sort(key=lambda x: x['match_3_plus_rate'], reverse=True)
    best_absolute = results[0] if results else None
    if best_absolute:
        print(f"\n🎯 最高成功率方案: {best_absolute['combination']}")
        print(f"   Match-3+ 率: {best_absolute['match_3_plus_rate']:.2f}%")
        print(f"   成本: {best_absolute['num_bets']} 注")
        print(f"   总胜率: {best_absolute['win_rate']:.2f}%")
    
    # 建议
    print("\n" + "=" * 80)
    print("💡 使用建议")
    print("=" * 80)
    
    if best_single and best_value and best_absolute:
        print(f"1. 预算有限 (1注): 使用 {best_single['combination']}")
        print(f"2. 追求性价比 (2-3注): 使用 {best_value['combination']}")
        print(f"3. 追求最高成功率: 使用 {best_absolute['combination']}")

if __name__ == '__main__':
    run_combination_tests()
