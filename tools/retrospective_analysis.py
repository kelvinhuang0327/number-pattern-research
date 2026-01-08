#!/usr/bin/env python3
import sys
import os
import json
import io
from collections import Counter

# Add project root and lottery-api to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.unified_predictor import UnifiedPredictionEngine, get_advanced_strategies
from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def analyze_matches(predicted, actual, actual_special):
    main_hits = sorted(list(set(predicted['numbers']) & set(actual)))
    special_hit = predicted.get('special') == actual_special
    return {
        'count': len(main_hits),
        'hits': main_hits,
        'special_hit': special_hit,
        'confidence': predicted.get('confidence', 0)
    }

def main():
    print("=" * 80)
    print("大樂透 2026/01/02 (第 115000001 期) 回溯分析")
    print(f"實際號碼: [3, 7, 16, 19, 40, 42] 特別號: 12")
    print("=" * 80)

    db_path = os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    lottery_type = 'BIG_LOTTO'
    rules = get_lottery_rules(lottery_type)
    engine = UnifiedPredictionEngine()
    advanced = get_advanced_strategies()
    
    # Get all draws and filter for history UP TO 115000001
    all_draws_desc = db.get_all_draws(lottery_type=lottery_type)
    all_draws_asc = list(reversed(all_draws_desc))
    
    # 找到 115000001 之前的歷史
    history = []
    target_draw = None
    for d in all_draws_asc:
        if d['draw'] == '115000001':
            target_draw = d
            break
        history.append(d)
    
    if not target_draw:
        print("Error: Target draw 115000001 not found in DB.")
        return

    actual_nums = target_draw['numbers']
    actual_special = target_draw['special']

    # 定義要測試的方法
    methods = [
        ('Frequency', engine.frequency_predict),
        ('Trend', engine.trend_predict),
        ('Bayesian', engine.bayesian_predict),
        ('Deviation', engine.deviation_predict),
        ('Markov', engine.markov_predict),
        ('Entropy Analysis', advanced.entropy_analysis_predict),
        ('Clustering', advanced.clustering_predict),
        ('Dynamic Ensemble', advanced.dynamic_ensemble_predict),
        ('Temporal Enhanced', advanced.temporal_enhanced_predict)
    ]

    results = []
    
    print(f"使用的歷史數據總量: {len(history)} 期 (最後一期: {history[-1]['draw']} {history[-1]['date']})")
    print("-" * 80)

    for name, func in methods:
        try:
            print(f"正在執行 {name} 預測...")
            # UnifiedEngine models take (history, rules)
            # Advanced models were initialized with prediction_engine=None usually, 
            # but let's see if they need it.
            res = func(history, rules)
            analysis = analyze_matches(res, actual_nums, actual_special)
            results.append({
                'method': name,
                'prediction': sorted(res['numbers']),
                'special': res.get('special'),
                'hits': analysis['hits'],
                'hit_count': analysis['count'],
                'special_hit': analysis['special_hit'],
                'confidence': analysis['confidence']
            })
        except Exception as e:
            print(f"❌ {name} 執行失敗: {e}")

    # 排序結果
    results.sort(key=lambda x: (x['hit_count'], x['special_hit']), reverse=True)

    print("\n" + "=" * 80)
    print(f"{'預測方法':<20} | {'命中':<4} | {'號碼':<25} | {'命中號碼'}")
    print("-" * 80)
    for r in results:
        spec_str = f"({r['special']})" if r['special'] else ""
        hit_str = f"{r['hit_count']}" + ("+S" if r['special_hit'] else "")
        print(f"{r['method']:<20} | {hit_str:<4} | {str(r['prediction']):<25} | {r['hits']}")
    
    print("=" * 80)
    
    # Save results for report generation
    with open('tools/retrospective_results.json', 'w') as f:
        json.dump({
            'actual': {'numbers': actual_nums, 'special': actual_special},
            'results': results,
            'history_count': len(history)
        }, f, indent=2)

if __name__ == "__main__":
    main()
