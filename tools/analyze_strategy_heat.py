#!/usr/bin/env python3
"""
策略熱度分析器 (Strategy Heat Map Analyzer)
分析各預測策略的歷史表現，生成熱度評分。
"""
import sys
import os
import json
from collections import defaultdict, Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules

def analyze_strategy_performance(lookback_periods=30):
    """
    分析各策略在過去 N 期的表現
    
    Args:
        lookback_periods: 回顧期數
    """
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    engine = UnifiedPredictionEngine()
    
    # 定義要測試的策略
    strategies = {
        'frequency': engine.frequency_predict,
        'bayesian': engine.bayesian_predict,
        'markov': engine.markov_predict,
        'trend': engine.trend_predict,
        'hot_cold': engine.hot_cold_mix_predict,
        'statistical': engine.statistical_predict,
        'deviation': engine.deviation_predict,
    }
    
    # 統計結果
    strategy_stats = defaultdict(lambda: {
        'total_hits': 0,
        'match_3_plus': 0,
        'special_hits': 0,
        'periods': 0,
        'recent_10': [],
        'recent_30': []
    })
    
    print(f"🔥 策略熱度分析 (最近 {lookback_periods} 期)")
    print("=" * 80)
    
    # 滾動測試
    test_periods = min(lookback_periods, len(all_draws) - 50)
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        
        actual_numbers = set(target_draw['numbers'])
        actual_special = target_draw['special']
        
        for name, func in strategies.items():
            try:
                result = func(history, rules)
                pred_numbers = set(result['numbers'])
                pred_special = result.get('special', 0)
                
                match_count = len(pred_numbers & actual_numbers)
                special_match = (pred_special == actual_special)
                
                # 記錄命中
                if match_count >= 1 or special_match:
                    strategy_stats[name]['total_hits'] += 1
                
                if match_count >= 3:
                    strategy_stats[name]['match_3_plus'] += 1
                
                if special_match:
                    strategy_stats[name]['special_hits'] += 1
                
                strategy_stats[name]['periods'] += 1
                
                # 記錄近期表現
                hit_score = match_count + (1 if special_match else 0)
                if i >= test_periods - 10:
                    strategy_stats[name]['recent_10'].append(hit_score)
                if i >= test_periods - 30:
                    strategy_stats[name]['recent_30'].append(hit_score)
                    
            except Exception as e:
                continue
    
    # 生成熱度表
    print(f"\n{'策略名稱':<15} {'近10期':<10} {'近30期':<10} {'Match-3+':<10} {'特別號':<10} {'熱度':<10} {'狀態':<10}")
    print("-" * 80)
    
    heat_scores = {}
    for name, stats in sorted(strategy_stats.items()):
        if stats['periods'] == 0:
            continue
        
        recent_10_avg = sum(stats['recent_10']) / len(stats['recent_10']) if stats['recent_10'] else 0
        recent_30_avg = sum(stats['recent_30']) / len(stats['recent_30']) if stats['recent_30'] else 0
        match3_rate = stats['match_3_plus'] / stats['periods'] * 100
        special_rate = stats['special_hits'] / stats['periods'] * 100
        
        # 計算熱度評分 (0-100)
        heat_score = (recent_10_avg * 30 + recent_30_avg * 20 + match3_rate * 2 + special_rate) / 2
        heat_scores[name] = heat_score
        
        # 判定狀態
        if heat_score >= 15:
            status = "🔥🔥🔥 HOT"
        elif heat_score >= 10:
            status = "🔥🔥 WARM"
        elif heat_score >= 5:
            status = "🔥 COOL"
        else:
            status = "❄️ COLD"
        
        print(f"{name:<15} {recent_10_avg:>8.2f} {recent_30_avg:>9.2f} {match3_rate:>9.1f}% {special_rate:>9.1f}% {heat_score:>9.1f} {status:<10}")
    
    # 推薦策略白名單
    print("\n" + "=" * 80)
    print("📋 推薦策略白名單 (熱度 Top 5):")
    print("-" * 80)
    
    top_strategies = sorted(heat_scores.items(), key=lambda x: -x[1])[:5]
    whitelist = [name for name, score in top_strategies]
    
    for i, (name, score) in enumerate(top_strategies, 1):
        print(f"{i}. {name:<15} (熱度: {score:.1f})")
    
    print("\n建議在下次預測時使用以下配置:")
    print(f"strategy_whitelist = {whitelist}")
    
    # 儲存結果
    output_file = os.path.join(project_root, 'data', 'strategy_heat_map.json')
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'analysis_date': __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'lookback_periods': test_periods,
            'heat_scores': heat_scores,
            'recommended_whitelist': whitelist,
            'detailed_stats': {k: {
                'match_3_plus_rate': v['match_3_plus'] / v['periods'] * 100 if v['periods'] > 0 else 0,
                'special_hit_rate': v['special_hits'] / v['periods'] * 100 if v['periods'] > 0 else 0,
                'total_periods': v['periods']
            } for k, v in strategy_stats.items()}
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 分析結果已儲存至: {output_file}")

if __name__ == '__main__':
    analyze_strategy_performance(lookback_periods=50)
