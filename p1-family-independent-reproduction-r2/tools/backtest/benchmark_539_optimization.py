#!/usr/bin/env python3
import sys
import os
import json
from collections import defaultdict
from datetime import datetime

# Add lottery_api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine

def calculate_matches(predicted, actual):
    pred_set = set(predicted['numbers'])
    actual_set = set(actual['numbers'])
    matches = len(pred_set & actual_set)
    return matches

def backtest_window(method_name, window_size, draws_2025, all_draws, rules):
    match_distribution = defaultdict(int)
    total_matches = 0
    win_count_3plus = 0
    win_count_2plus = 0
    
    method = getattr(prediction_engine, method_name)
    results = []

    for target_draw in draws_2025:
        target_index = all_draws.index(target_draw)
        train_start = target_index + 1
        train_end = min(target_index + 1 + window_size, len(all_draws))
        history = all_draws[train_start:train_end]

        if len(history) < window_size * 0.8: # Ensure enough data
            continue

        try:
            prediction = method(history, rules)
            matches = calculate_matches(prediction, target_draw)
            
            match_distribution[matches] += 1
            total_matches += matches
            if matches >= 3: win_count_3plus += 1
            if matches >= 2: win_count_2plus += 1
            
            results.append(matches)
        except:
            continue

    total_tests = len(results)
    if total_tests == 0: return None
    
    return {
        "window_size": window_size,
        "test_count": total_tests,
        "avg_matches": total_matches / total_tests,
        "win_rate_3plus": win_count_3plus / total_tests,
        "win_rate_2plus": win_count_2plus / total_tests,
        "win_count_3plus": win_count_3plus
    }

def main():
    db_path = os.path.join(os.path.dirname(__file__), 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = db.get_all_draws('DAILY_539')
    
    # Filter 2025 data (around 300 draws)
    draws_2025 = [d for d in all_draws if '2025' in d['date'] or d['draw'].startswith('114')]
    if len(draws_2025) > 100:
        draws_2025 = draws_2025[:100] # Limit to 100 for speed
        
    rules = get_lottery_rules('DAILY_539')
    window_sizes = [50, 100, 200, 300, 500]
    methods = [
        ('zone_balance_predict', '區域平衡預測'),
        ('odd_even_balance_predict', '奇偶平衡預測'),
        ('markov_predict', 'Markov鏈預測'),
        ('statistical_predict', '統計概率預測')
    ]

    final_results = {}

    for m_id, m_name in methods:
        print(f"Testing {m_name}...")
        method_results = []
        for w in window_sizes:
            res = backtest_window(m_id, w, draws_2025, all_draws, rules)
            if res:
                method_results.append(res)
                print(f"  Window {w}: Avg {res['avg_matches']:.3f}, 3+ Win {res['win_rate_3plus']:.2%}")
        final_results[m_name] = method_results

    # Find best for each method
    summary = []
    for m_name, res_list in final_results.items():
        if not res_list: continue
        best_by_win = max(res_list, key=lambda x: x['win_rate_3plus'])
        summary.append({
            "method": m_name,
            "best_window": best_by_win['window_size'],
            "avg_matches": best_by_win['avg_matches'],
            "win_rate_3plus": best_by_win['win_rate_3plus']
        })

    report = {
        "test_date": datetime.now().strftime('%Y-%m-%d'),
        "lottery_type": "DAILY_539",
        "detailed_results": final_results,
        "summary": summary
    }

    with open('BENCHMARK_539_OPTIMIZATION.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50)
    print("🏆 Daily 539 Optimization Summary")
    print("="*50)
    summary.sort(key=lambda x: x['win_rate_3plus'], reverse=True)
    for s in summary:
        print(f"{s['method']:<15} | Best Window: {s['best_window']:3d} | Win Rate 3+: {s['win_rate_3plus']:.2%}")

if __name__ == "__main__":
    main()
