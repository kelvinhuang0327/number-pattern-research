#!/usr/bin/env python3
"""
務實優化方法的150期回測驗證
對比: Baseline vs Simplified vs Markov2nd
"""
import sys
import os
import json
import numpy as np
from collections import Counter
from scipy.stats import binomtest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.simplified_bayesian_predictor import SimplifiedBayesianPredictor
from models.markov_2nd_special_predictor import  MarkovChain2ndOrderPredictor


def evaluate_prediction(pred_nums, pred_special, actual_nums, actual_special):
    """評估預測"""
    main_hits = len(set(pred_nums) & set(actual_nums))
    special_hit = (pred_special == actual_special)
    return {'main_hits': main_hits, 'special_hit': special_hit}


def backtest_150(method_name, predict_func, history, test_size=150):
    """150期回測"""
    results = []
    rules = get_lottery_rules('POWER_LOTTO')
    
    print(f"  回測 {method_name}...", end='', flush=True)
    
    for i in range(test_size):
        train = history[i+1:]
        test = history[i]
        
        try:
            pred = predict_func(train, rules)
            eval_r = evaluate_prediction(
                pred.get('numbers', []),
                pred.get('special', 0),
                test.get('numbers', []),
                test.get('special', 0)
            )
            results.append(eval_r)
        except Exception as e:
            pass
    
    print(f" ✓ ({len(results)}/{test_size})")
    return results


def main():
    print("=" * 100)
    print("務實優化 150期回測驗證")
    print("=" * 100)
    
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    test_size = min(150, len(all_history) - 20)
    history = all_history[:test_size + 20]
    
    print(f"\n測試期數: {test_size} 期")
    print(f"期數範圍: {history[test_size-1]['draw']} ~ {history[0]['draw']}\n")
    
    # 定義方法
    baseline = UnifiedPredictionEngine()
    simplified = SimplifiedBayesianPredictor()
    
    methods = [
        ('Baseline_Bayesian', baseline.bayesian_predict),
        ('Simplified_Bayesian', simplified.predict),
    ]
    
    # 回測
    all_results = {}
    for method_name, func in methods:
        all_results[method_name] = backtest_150(method_name, func, history, test_size)
    
    # 統計分析
    print("\n" + "=" * 100)
    print("統計結果")
    print("=" * 100)
    
    # 第二區
    print("\n【第二區命中率】")
    for method, results in all_results.items():
        hits = sum(1 for r in results if r['special_hit'])
        total = len(results)
        rate = hits / total if total > 0 else 0
        
        # 二項檢驗
        if total > 0:
            result = binomtest(hits, total, 0.125, alternative='greater')
            p_val = result.pvalue
            sig = "✓" if p_val < 0.05 else "✗"
            
            print(f"  {method:<25}: {rate:.1%} ({hits}/{total}) p={p_val:.4f} {sig}")
    
    # 第一區
    print("\n【第一區平均命中】")
    for method, results in all_results.items():
        hits = [r['main_hits'] for r in results]
        mean = np.mean(hits)
        std = np.std(hits, ddof=1)
        se = std / np.sqrt(len(hits))
        ci = (mean - 1.96*se, mean + 1.96*se)
        
        print(f"  {method:<25}: {mean:.3f}/6  95%CI=[{ci[0]:.3f}, {ci[1]:.3f}]")
    
    # 3+命中率
    print("\n【3+命中率】")
    for method, results in all_results.items():
        hits3plus = sum(1 for r in results if r['main_hits'] >= 3)
        total = len(results)
        rate = hits3plus / total if total > 0 else 0
        
        print(f"  {method:<25}: {rate:.1%} ({hits3plus}/{total})")
    
    print("\n" + "=" * 100)


if __name__ == '__main__':
    main()
