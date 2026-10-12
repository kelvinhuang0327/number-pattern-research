#!/usr/bin/env python3
"""
Big Lotto 5-Bet Strategy Optimizer
Specifically searches for the optimal 5-method combination using all historical data.
"""
import os
import sys
from itertools import combinations
from datetime import datetime

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from ai_lab.scripts.automl_strategy_optimizer import AutoMLStrategyOptimizer

def main():
    print("=" * 80)
    print("🔬 Big Lotto 5-Bet Strategy Optimization")
    print("   Searching all 5-method combinations across ALL historical data...")
    print("=" * 80)
    
    # Initialize optimizer
    optimizer = AutoMLStrategyOptimizer('BIG_LOTTO')
    all_methods = list(optimizer.base_methods.keys())
    
    # Generate 5-bet combinations
    combos_5bet = list(combinations(all_methods, 5))
    total_combos = len(combos_5bet)
    
    print(f"   Total combinations to test: {total_combos}")
    print(f"   Historical draws: {len(optimizer.all_draws)}")
    print("-" * 80)
    
    results = []
    
    # We will test with 'None' window (All Data) as it proved most robust
    # Testing multiple windows would triple the time (462 -> 1386), 
    # and previous results showed 'All' or '500' were dominant. 
    # We'll stick to 'All' for the primary search to keep it under 10 mins.
    
    for i, combo in enumerate(combos_5bet, 1):
        if i % 10 == 0:
            print(f"   Progress: {i}/{total_combos} ({(i/total_combos)*100:.1f}%)", end='\r')
            
        res = optimizer.evaluate_combination(combo, periods=None, window=None) # All data
        results.append(res)
        
    print("\n" + "=" * 80)
    print("📊 TOP 10 5-BET STRATEGIES")
    print("=" * 80)
    print(f"{'Rank':<5} {'Methods (Top 3 shown + 2 more)':<45} {'Win%':<8} {'M4+':<5}")
    print("-" * 75)
    
    # Sort by Win Rate then Match-4+
    results.sort(key=lambda x: (x['win_rate'], x['m4_count']), reverse=True)
    
    for i, r in enumerate(results[:10], 1):
        methods = list(r['methods'])
        display_str = f"{methods[0]}+{methods[1]}+{methods[2]}+..." 
        marker = "⭐" if i == 1 else ""
        print(f"{i:<5} {display_str:<45} {r['win_rate']:.2f}%{marker:<3} {r['m4_count']:<5}")
        
    best = results[0]
    print("\n" + "=" * 80)
    print("🏆 BEST 5-BET COMBINATION:")
    print("   Methods:")
    for m in best['methods']:
        print(f"   - {m}")
    print(f"   Win Rate: {best['win_rate']:.2f}%")
    print(f"   Match-4+: {best['m4_count']}")
    
    # Calculate efficiency
    efficiency = best['win_rate'] / 5
    print(f"   Efficiency: {efficiency:.2f}% per bet")
    print("=" * 80)

if __name__ == "__main__":
    main()
