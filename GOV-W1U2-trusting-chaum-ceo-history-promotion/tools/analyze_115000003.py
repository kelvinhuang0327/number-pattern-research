#!/usr/bin/env python3
import sys
import os
import json
import io

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine, get_advanced_strategies
from database import DatabaseManager
from common import get_lottery_rules

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
    print("大樂透 2026/01/09 (第 115000003 期) 回溯分析")
    actual_nums = [1, 7, 13, 14, 34, 45]
    actual_special = 8
    print(f"實際號碼: {actual_nums} 特別號: {actual_special:02d}")
    print("=" * 80)

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    lottery_type = 'BIG_LOTTO'
    rules = get_lottery_rules(lottery_type)
    engine = UnifiedPredictionEngine()
    advanced = get_advanced_strategies()
    
    all_draws_desc = db.get_all_draws(lottery_type=lottery_type)
    all_draws_asc = list(reversed(all_draws_desc))
    
    # 找到 115000003 之前的歷史 (應該截止到 115000002)
    history = []
    for d in all_draws_asc:
        if d['draw'] == '115000003':
            break
        history.append(d)
    
    methods = [
        ('Frequency (100)', lambda h, r: engine.frequency_predict(h[:100], r)),
        ('Frequency (300)', lambda h, r: engine.frequency_predict(h[:300], r)),
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

    results.sort(key=lambda x: (x['hit_count'], x['special_hit']), reverse=True)

    print("\n" + "=" * 80)
    print(f"{'預測方法':<20} | {'命中':<4} | {'號碼':<25} | {'命中號碼'}")
    print("-" * 80)
    for r in results:
        spec_str = f"({r['special']})" if r['special'] else ""
        hit_str = f"{r['hit_count']}" + ("+S" if r['special_hit'] else "")
        print(f"{r['method']:<20} | {hit_str:<4} | {str(r['prediction']):<25} | {r['hits']}")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
