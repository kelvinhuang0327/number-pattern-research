
#!/usr/bin/env python3
"""
Banker Accuracy Analyzer (膽碼命中率分析器)
目標：統計各預測方法在「必中 1 碼」與「必中 2 碼」的滾動式預測成功率。

驗證模式：
1. Predict-1 (Banker-1): 取方法排名第 1 的號碼，檢查是否中獎。
2. Predict-2 (Banker-2): 取方法排名第 1、2 的號碼，檢查命中數 (1 or 2)。
   - Success Criteria A (Strict): Hit 2 (中 2 碼)
   - Success Criteria B (Soft): Hit >= 1 (至少中 1 碼)

適用彩種：Big Lotto (大樂透) - 49 選 6
"""
import sys
import os
import argparse
import pandas as pd
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

def analyze_banker_accuracy(year=2025, methods=None, all_period=False):
    if methods is None:
        methods = [
            'trend_predict', 
            'frequency_predict', 
            'deviation_predict', 
            'markov_predict', 
            'bayesian_predict'
        ]

    period_name = "ALL HISTORY (2007-2026)" if all_period else str(year)
    print("=" * 100)
    print(f"🎯 Banker Accuracy Analysis - {period_name}")
    print("=" * 100)
    
    # 1. 準備數據
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: x['date'])
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()

    # 篩選測試範圍
    if all_period:
        # 使用全部數據，但要保留至少 50 期做為歷史窗口 (warm-up)
        # 不然第1期沒歷史無法預測
        test_draws = all_draws[50:] 
    else:
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
    
    if not test_draws:
        print(f"❌ No data for {period_name}")
        return

    print(f"📊 Test Data: {len(test_draws)} draws")
    print("-" * 100)
    print(f"{'Method':<20} | {'Predict-1 (Win Rate)':<25} | {'Predict-2 (Strict Win Rate)':<25} | {'Predict-2 (Soft Win Rate)':<25}")
    print("-" * 100)

    results = []

    for method in methods:
        top1_hits = 0
        top2_strict_hits = 0  # Hit 2
        top2_soft_hits = 0    # Hit >= 1
        total = 0

        # 顯示進度
        print(f"Testing {method:<15} ... ", end="", flush=True)

        for target_draw in test_draws:
            target_idx = all_draws.index(target_draw)
            history = all_draws[:target_idx]
            actual = set(target_draw['numbers'])

            try:
                # 獲取預測 (Top 2)
                func = getattr(engine, method)
                pred_result = func(history, rules)
                # 假設預測結果的 numbers 是按優先級排序的
                # 大多數方法返回的 numbers 是 top N，默認 N=6
                # 我們需要確保它是 ranked list。UnifiedPredictor 大多數方法返回的是 sorted list?
                # 不一定，有些是 sorted by value, 有些是 random selection if equal.
                # 但 UnifiedPredictor 的方法通常返回 top 6。我們假設其順序是有意義的 (Ranked)。
                # 若 engine 方法未明確排序，此處假設 result['numbers'] 前 2 個為最佳推薦。
                
                # 注意: 除了 markov 可能返回無序，其他如 trend/freq 都是 sorted。
                # 我們需要在這裡做一個簡單的假設：使用返回列表的前 N 個。
                
                ranked_nums = pred_result['numbers']
                
                if len(ranked_nums) < 2:
                    continue

                # 1. Predict-1 Evaluation
                banker1 = set(ranked_nums[:1])
                if len(banker1 & actual) == 1:
                    top1_hits += 1

                # 2. Predict-2 Evaluation
                banker2 = set(ranked_nums[:2])
                hits = len(banker2 & actual)
                if hits == 2:
                    top2_strict_hits += 1
                if hits >= 1:
                    top2_soft_hits += 1

                total += 1
            except Exception as e:
                pass
        
        # 計算統計
        if total > 0:
            rate1 = (top1_hits / total) * 100
            rate2_strict = (top2_strict_hits / total) * 100
            rate2_soft = (top2_soft_hits / total) * 100
            
            print(f"Done. ({total} draws)")
            results.append({
                'method': method,
                'p1': rate1,
                'p2_strict': rate2_strict,
                'p2_soft': rate2_soft
            })
        else:
            print("No Data or Error.")

    print("\n" + "=" * 100)
    print("🏆 Ranking Report (Success Rate)")
    print("=" * 100)
    
    # Sort by Predict-1
    results.sort(key=lambda x: x['p1'], reverse=True)
    
    print(f"{'Method':<20} | {'Predict-1 (必中1)':<18} | {'Predict-2 (必中2)':<18} | {'Predict-2 (任中1)':<18}")
    print("-" * 100)
    for res in results:
        print(f"{res['method']:<20} | {res['p1']:6.2f}%            | {res['p2_strict']:6.2f}%            | {res['p2_soft']:6.2f}%")
    print("=" * 100)
    print("Note:")
    print("Predict-1: Top 1 number hits.")
    print("Predict-2 (必中2): Top 2 numbers BOTH hit.")
    print("Predict-2 (任中1): Top 2 numbers contain at least 1 hit.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2025)
    parser.add_argument('--all', action='store_true', help='Test on all historical data')
    args = parser.parse_args()
    
    analyze_banker_accuracy(args.year, all_period=args.all)
