import sys
import os
import json
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.path.join(os.getcwd(), 'lottery-api'))

from database import DatabaseManager
from models.multi_bet_optimizer import MultiBetOptimizer

def run_benchmark():
    # Use the absolute path or relative path to the correct DB
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    db_path = os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db')
    
    db = DatabaseManager(db_path=db_path)
    optimizer = MultiBetOptimizer()
    
    lottery_type = 'BIG_LOTTO'
    # Use 2025 draws for benchmark (118 draws)
    draws = db.get_all_draws(lottery_type)
    test_periods = 118 
    num_bets_to_test = [6, 8]
    
    lottery_rules = {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49,
        'hasSpecialNumber': True,
        'specialMinNumber': 1,
        'specialMaxNumber': 49
    }

    # Meta-configurations to test
    meta_configs = [
        {'name': 'Current Baseline', 'wobble_ratio': 0.5, 'base_strategy': 'top_score'},
        {'name': 'High Diversity', 'wobble_ratio': 0.2, 'base_strategy': 'top_score'},
        {'name': 'Wobble Focus', 'wobble_ratio': 0.8, 'base_strategy': 'top_score'},
        {'name': 'Markov-Anchored', 'wobble_ratio': 0.5, 'base_strategy': 'markov'},
        {'name': 'Bayesian-Anchored', 'wobble_ratio': 0.5, 'base_strategy': 'bayesian'},
        {'name': 'Bimodal-Anchored', 'wobble_ratio': 0.6, 'base_strategy': 'bimodal_gap'},
    ]

    print("=" * 80)
    print(f"Lottery Prediction Meta-Optimization Benchmark - {lottery_type}")
    print(f"History Size: {len(draws)} draws | Test Periods: {test_periods}")
    print("=" * 80)

    all_results = []

    for num_bets in num_bets_to_test:
        print(f"\n--- Testing {num_bets} Bets Configurations ---")
        for config in meta_configs:
            name = config['name']
            print(f"\nEvaluating: {name} (wobble={config['wobble_ratio']}, base={config['base_strategy']})")
            
            # Remove name from config for the function call
            call_config = {k: v for k, v in config.items() if k != 'name'}
            
            result = optimizer.backtest_multi_bet(
                draws=draws,
                lottery_rules=lottery_rules,
                num_bets=num_bets,
                test_periods=test_periods,
                meta_config=call_config
            )
            
            summary = {
                'num_bets': num_bets,
                'name': name,
                'win_rate': f"{result['win_rate']:.2%}",
                'avg_match': f"{result['avg_best_match']:.2f}",
                'raw_win_rate': result['win_rate']
            }
            all_results.append(summary)
            print(f"Result -> Win Rate: {summary['win_rate']}, Avg Match: {summary['avg_match']}")

    # Final Rankings
    print("\n" + "=" * 80)
    print("FINAL RANKINGS (Sorted by Win Rate)")
    print("=" * 80)
    
    sorted_results = sorted(all_results, key=lambda x: x['raw_win_rate'], reverse=True)
    
    print(f"{'Bets':<6} | {'Configuration Name':<25} | {'Win Rate':<10} | {'Avg Match':<10}")
    print("-" * 60)
    for res in sorted_results:
        print(f"{res['num_bets']:<6} | {res['name']:<25} | {res['win_rate']:<10} | {res['avg_match']:<10}")

if __name__ == "__main__":
    run_benchmark()
