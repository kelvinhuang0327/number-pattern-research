#!/usr/bin/env python3
"""
Backtest New Power Lotto Predictor Methods (2025)
"""
import sys
import os
import io

# Add project root and lottery_api to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.power_lotto_predictor import power_lotto_predictor
from models.backtest_framework import RollingBacktester, StrategyAdapter
from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding for potential Chinese characters in output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    print("================================================================================")
    print("Starting Power Lotto 2025 Backtest (New Methods)")
    print("================================================================================")

    # 1. Load Data
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    lottery_type = 'POWER_LOTTO'
    draws = db.get_all_draws(lottery_type=lottery_type)
    rules = get_lottery_rules(lottery_type)

    if not draws:
        print(f"Error: No data found for {lottery_type}")
        return

    # 2. Define Strategies from PowerLottoPredictor
    strategies = [
        StrategyAdapter(
            name='constraint_satisfaction',
            predict_func=power_lotto_predictor.constraint_satisfaction_predict,
            optimal_window=100
        ),
        StrategyAdapter(
            name='negative_filtering',
            predict_func=power_lotto_predictor.negative_filtering_predict,
            optimal_window=100
        ),
        StrategyAdapter(
            name='number_clustering',
            predict_func=power_lotto_predictor.number_clustering_predict,
            optimal_window=100
        ),
        StrategyAdapter(
            name='adaptive_window',
            predict_func=power_lotto_predictor.adaptive_window_predict,
            optimal_window=100
        ),
        StrategyAdapter(
            name='pattern_matching',
            predict_func=power_lotto_predictor.pattern_matching_predict,
            optimal_window=100
        ),
        StrategyAdapter(
            name='hybrid_optimizer',
            predict_func=power_lotto_predictor.hybrid_optimizer_predict,
            optimal_window=100
        )
    ]

    # 3. Run Backtest
    backtester = RollingBacktester()
    
    # Run comparison
    results = []
    print(f"\nComparing {len(strategies)} strategies for year 2025...")
    
    for strategy in strategies:
        try:
            summary = backtester.run(
                strategy=strategy,
                draws=draws,
                lottery_rules=rules,
                lottery_type=lottery_type,
                test_year=2025,
                min_match=3,  # Standard win threshold for Power Lotto
                verbose=True
            )
            results.append(summary)
        except Exception as e:
            print(f"Error testing {strategy.name}: {e}")

    # 4. Print Summary Report
    print("\n================================================================================")
    print("FINAL SUMMARY REPORT (2025)")
    print("================================================================================")
    print(f"{'Method':<30} | {'Win Rate':<10} | {'Avg Match':<10} | {'Wins/Total':<15}")
    print("-" * 80)
    
    # Sort by win rate descending
    results.sort(key=lambda x: x.win_rate, reverse=True)
    
    for r in results:
        print(f"{r.method_name:<30} | {r.win_rate*100:6.2f}%    | {r.avg_matches:5.2f}      | {r.win_count}/{r.test_periods}")

if __name__ == '__main__':
    main()
