#!/usr/bin/env python3
"""
大乐透双注组合测试
测试所有双注组合，找出成功率最高的方案
"""
import sys
import os
import io
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.ensemble_stacking import EnsembleStackingPredictor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_2bet_combination(combo_name, func1, func2, history, rules, test_periods):
    """测试双注组合"""
    wins = 0
    match_3_plus = 0
    total = 0
    
    for i in range(test_periods):
        target_idx = len(history) - test_periods + i
        if target_idx <= 0:
            continue
        
        target_draw = history[target_idx]
        hist = history[:target_idx]
        
        if len(hist) < 10:
            continue
        
        actual = set(target_draw['numbers'])
        
        # 生成两注预测
        period_win = False
        period_match3 = False
        
        for func in [func1, func2]:
            try:
                result = func(hist, rules)
                if not result or 'numbers' not in result:
                    continue
                
                predicted = set(result['numbers'])
                match_count = len(predicted & actual)
                
                # 大乐透只看主号码，不看特别号
                if match_count >= 3:
                    period_match3 = True
                    period_win = True
                elif match_count >= 1:
                    period_win = True
            except:
                continue
        
        if period_match3:
            match_3_plus += 1
        if period_win:
            wins += 1
        
        total += 1
    
    if total == 0:
        return None
    
    return {
        'combination': combo_name,
        'win_rate': wins / total * 100,
        'match_3_plus_rate': match_3_plus / total * 100,
        'total_periods': total,
        'cost_efficiency': (match_3_plus / total * 100) / 2  # 除以2注
    }

def run_biglotto_2bet_tests():
    """运行大乐透双注测试"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    test_periods = min(150, len(all_draws) - 50)
    
    engine = UnifiedPredictionEngine()
    ensemble = EnsembleStackingPredictor()
    
    # 定义所有方法
    methods = {
        'deviation': lambda h, r: engine.deviation_predict(h, r),
        'markov': lambda h, r: engine.markov_predict(h, r),
        'statistical': lambda h, r: engine.statistical_predict(h, r),
        'bayesian': lambda h, r: engine.bayesian_predict(h, r),
        'frequency': lambda h, r: engine.frequency_predict(h, r),
        'trend': lambda h, r: engine.trend_predict(h, r),
        'ensemble': lambda h, r: ensemble.predict_with_features(h, r, use_lstm=False),
    }
    
    print("=" * 80)
    print(f"🔬 大乐透双注组合测试 (最近 {test_periods} 期)")
    print("=" * 80)
    print(f"测试配置: 所有双注组合 (21种)")
    print("-" * 80)
    
    results = []
    
    # 1. 先测试单注基准
    print("\n📍 单注基准测试:")
    single_results = []
    for name, func in methods.items():
        wins = 0
        match_3 = 0
        total = 0
        
        for i in range(test_periods):
            target_idx = len(all_draws) - test_periods + i
            if target_idx <= 0:
                continue
            
            target_draw = all_draws[target_idx]
            hist = all_draws[:target_idx]
            
            if len(hist) < 10:
                continue
            
            actual = set(target_draw['numbers'])
            
            try:
                result = func(hist, rules)
                if result and 'numbers' in result:
                    predicted = set(result['numbers'])
                    match_count = len(predicted & actual)
                    
                    if match_count >= 3:
                        match_3 += 1
                    
                    total += 1
            except:
                continue
        
        if total > 0:
            match_3_rate = match_3 / total * 100
            single_results.append((name, match_3_rate))
            print(f"  {name:<15} Match-3+: {match_3_rate:>5.2f}%")
    
    # 2. 测试所有双注组合
    print("\n📍 双注组合测试:")
    two_combos = list(combinations(methods.items(), 2))
    
    for (name1, func1), (name2, func2) in two_combos:
        combo_name = f"{name1} + {name2}"
        result = test_2bet_combination(combo_name, func1, func2, all_draws, rules, test_periods)
        if result:
            results.append(result)
    
    # 排序并显示结果
    results.sort(key=lambda x: x['match_3_plus_rate'], reverse=True)
    
    print(f"\n{'排名':<5} {'组合':<40} {'Match-3+':<10} {'总胜率':<10} {'效益':<10}")
    print("-" * 80)
    
    for i, result in enumerate(results, 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"{emoji} {i:<3} {result['combination']:<40} {result['match_3_plus_rate']:>8.2f}% {result['win_rate']:>8.2f}% {result['cost_efficiency']:>8.2f}%")
    
    # 详细分析 Top 3
    print("\n" + "=" * 80)
    print("🏆 Top 3 详细分析")
    print("=" * 80)
    
    for i, result in enumerate(results[:3], 1):
        print(f"\n第{i}名: {result['combination']}")
        print(f"  Match-3+ 率: {result['match_3_plus_rate']:.2f}%")
        print(f"  总胜率: {result['win_rate']:.2f}%")
        print(f"  成本: 2 注")
        print(f"  效益: {result['cost_efficiency']:.2f}% per 注")
    
    # 与之前V1方案对比
    print("\n" + "=" * 80)
    print("📊 与优化方案对比")
    print("=" * 80)
    print(f"{'方案':<45} {'Match-3+':<12} {'成本':<8}")
    print("-" * 80)
    print(f"{'单注偏差分析 (基准)':<45} {'2.67%':<12} {'1注':<8}")
    print(f"{'双注优化 V1 (之前测试)':<45} {'4.00%':<12} {'2注':<8}")
    
    if results:
        best = results[0]
        combo_str = f"🎯 {best['combination']} (新测试)"
        rate_str = f"{best['match_3_plus_rate']:.2f}%"
        print(f"{combo_str:<45} {rate_str:<12} {'2注':<8}")
    
    # 最终推荐
    print("\n" + "=" * 80)
    print("💡 最终推荐")
    print("=" * 80)
    
    if results:
        best = results[0]
        print(f"✅ 大乐透双注最佳组合: {best['combination']}")
        print(f"   Match-3+ 率: {best['match_3_plus_rate']:.2f}%")
        print(f"   总胜率: {best['win_rate']:.2f}%")
        print(f"   性价比: {best['cost_efficiency']:.2f}% per 注")
        
        # 提升幅度
        baseline = 2.67
        improvement = best['match_3_plus_rate'] - baseline
        print(f"\n   提升幅度: +{improvement:.2f}% (vs 单注基准)")
        
        if improvement >= 5.0:
            print(f"   🎉 达成目标！提升 {improvement:.2f}% >= 5%")
        else:
            print(f"   ⚠️ 未达 +5% 目标，实际提升 {improvement:.2f}%")

if __name__ == '__main__':
    run_biglotto_2bet_tests()
