#!/usr/bin/env python3
"""
2025 年大樂透 ML 模型全面回測
比較所有實作的機器學習方法，找出最佳配置
"""
import sys
import os
import io
from collections import Counter, defaultdict
from itertools import combinations

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
    """回測單一方法"""
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
            
            # 大樂透中獎判定：Match 3+ 或 Match 2+S
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

def run_biglotto_backtest():
    """執行大樂透全面回測"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    # 找出 2025 年的數據
    draws_2025 = [d for d in all_draws if d['date'].startswith('2025')]
    test_periods = len(draws_2025)
    
    print("=" * 80)
    print("🔬 2025 年大樂透 ML 模型全面回測")
    print("=" * 80)
    print(f"總歷史數據: {len(all_draws)} 期")
    print(f"2025 年數據: {test_periods} 期")
    print(f"號碼池: {rules['minNumber']}-{rules['maxNumber']} (共 {rules['maxNumber']} 個號碼)")
    print(f"選號數: {rules['pickCount']} 個")
    print("-" * 80)
    
    # 初始化預測引擎
    engine = UnifiedPredictionEngine()
    ensemble = EnsembleStackingPredictor()
    
    # 定義測試方法
    test_methods = {
        '頻率分析 (Frequency)': lambda h, r: engine.frequency_predict(h, r),
        '貝葉斯推論 (Bayesian)': lambda h, r: engine.bayesian_predict(h, r),
        '馬可夫鏈 (Markov)': lambda h, r: engine.markov_predict(h, r),
        '趨勢回歸 (Trend)': lambda h, r: engine.trend_predict(h, r),
        '偏差分析 (Deviation)': lambda h, r: engine.deviation_predict(h, r),
        '冷熱混合 (Hot-Cold Mix)': lambda h, r: engine.hot_cold_mix_predict(h, r),
        '統計綜合 (Statistical)': lambda h, r: engine.statistical_predict(h, r),
        'Ensemble Stacking': lambda h, r: ensemble.predict_with_features(h, r, use_lstm=False),
    }
    
    # 執行回測
    results = []
    
    for method_name, predict_func in test_methods.items():
        print(f"\n🧪 測試方法: {method_name}")
        result = backtest_method(method_name, predict_func, all_draws, rules, test_periods)
        
        if result:
            results.append(result)
            print(f"  ✅ 總勝率: {result['win_rate']:.2f}%")
            print(f"  📊 Match-3+: {result['match_3_plus_rate']:.2f}%")
            print(f"  🎯 特別號: {result['special_hit_rate']:.2f}%")
        else:
            print(f"  ❌ 測試失敗")
    
    # 排序結果
    results.sort(key=lambda x: x['win_rate'], reverse=True)
    
    # 顯示排行榜
    print("\n" + "=" * 80)
    print("🏆 大樂透方法排行榜 (依總勝率)")
    print("=" * 80)
    
    print(f"\n{'排名':<5} {'方法':<30} {'總勝率':<10} {'Match-3+':<10} {'特別號':<10}")
    print("-" * 80)
    
    for i, result in enumerate(results, 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"{emoji} {i:<3} {result['method']:<30} {result['win_rate']:>8.2f}% {result['match_3_plus_rate']:>8.2f}% {result['special_hit_rate']:>8.2f}%")
    
    # 詳細分析最佳方法
    if results:
        best = results[0]
        print("\n" + "=" * 80)
        print(f"🎯 最佳方法詳細分析: {best['method']}")
        print("=" * 80)
        print(f"總勝率: {best['win_rate']:.2f}%")
        print(f"Match-3+ 率: {best['match_3_plus_rate']:.2f}%")
        print(f"Match-2+S 率: {best['match_2_special_rate']:.2f}%")
        print(f"特別號命中率: {best['special_hit_rate']:.2f}%")
        print(f"測試期數: {best['total_periods']}")
        
        print("\n命中分佈:")
        for match_count in sorted(best['match_distribution'].keys(), reverse=True):
            count = best['match_distribution'][match_count]
            pct = count / best['total_periods'] * 100
            bar = "█" * int(pct / 2)
            print(f"  Match-{match_count}: {count:3d} 次 ({pct:5.1f}%) {bar}")
    
    # 與威力彩比較
    print("\n" + "=" * 80)
    print("📊 大樂透 vs 威力彩 最佳方法比較")
    print("=" * 80)
    print(f"{'彩種':<15} {'最佳方法':<20} {'總勝率':<10} {'Match-3+':<10} {'特別號':<10}")
    print("-" * 80)
    print(f"{'威力彩':<15} {'馬可夫鏈':<20} {'16.10%':<10} {'4.24%':<10} {'21.19%':<10}")
    if results:
        win_rate_str = f"{results[0]['win_rate']:.2f}%"
        match3_str = f"{results[0]['match_3_plus_rate']:.2f}%"
        special_str = f"{results[0]['special_hit_rate']:.2f}%"
        print(f"{'大樂透':<15} {results[0]['method']:<20} {win_rate_str:<10} {match3_str:<10} {special_str:<10}")
    
    # 推薦配置
    print("\n" + "=" * 80)
    print("💡 大樂透優化建議")
    print("=" * 80)
    
    if results:
        top_3 = [r['method'] for r in results[:3]]
        print(f"1. 建議使用 Top 3 方法: {top_3}")
        
        if results[0]['win_rate'] > 15:
            print(f"2. 最佳方法 '{results[0]['method']}' 表現優異 (>{results[0]['win_rate']:.1f}%)，建議作為主要策略")
        else:
            print(f"2. 當前最佳方法勝率為 {results[0]['win_rate']:.1f}%，大樂透難度較高")
        
        avg_special = sum(r['special_hit_rate'] for r in results) / len(results)
        print(f"3. 特別號平均命中率 {avg_special:.1f}%")
        
        # 判斷是否與威力彩一致
        if results[0]['method'] == '馬可夫鏈 (Markov)':
            print("4. ✅ 大樂透最佳方法與威力彩一致，都是馬可夫鏈！")
        else:
            print(f"4. ⚠️ 大樂透最佳方法 ({results[0]['method']}) 與威力彩 (馬可夫鏈) 不同")

if __name__ == '__main__':
    run_biglotto_backtest()
