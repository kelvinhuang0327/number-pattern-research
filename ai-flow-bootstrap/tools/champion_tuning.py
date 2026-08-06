#!/usr/bin/env python3
import os
import sys
import argparse
from tqdm import tqdm

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tools.strategy_leaderboard import StrategyLeaderboard

def run_tuning(lottery_type, strategy_name, param_name, values, periods=500):
    lb = StrategyLeaderboard(lottery_type=lottery_type)
    
    # Map friendly names to LB methods
    registry = {
        'Cluster Pivot': lb.strat_cluster_pivot,
        'GUM Consensus': lb.strat_gum,
        'Markov Transition': lb.strat_markov,
        'Frequency (Hot)': lb.strat_frequency_hot
    }
    
    if strategy_name not in registry:
        print(f"Error: Strategy {strategy_name} not found.")
        return

    func = registry[strategy_name]
    baseline = lb.baselines.get(2, 0.0369) # Default to 2-bet baseline
    
    print(f"\n🔍 Tuning {strategy_name} on {lottery_type} (N={periods})")
    print("-" * 60)
    print(f"{param_name:<10} | {'Win Rate':<10} | {'True Edge':<15}")
    print("-" * 60)
    
    results = []
    for val in tqdm(values, desc=f"Sweeping {param_name}"):
        # Run backtest
        args = {param_name: val, 'n_bets': 2}
        rate = lb.run_backtest(func, periods=periods, **args)
        edge = rate - baseline
        results.append((val, rate, edge))
        
    results.sort(key=lambda x: x[2], reverse=True)
    for val, rate, edge in results:
        print(f"{val:<10} | {rate*100:8.2f}% | {edge*100:+8.2f}% (vs {baseline*100:.2f}%)")
    
    print(f"\n🏆 Best {param_name} for {strategy_name}: {results[0][0]} ({results[0][2]*100:+.2f}% Edge)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', choices=['BIG_LOTTO', 'POWER_LOTTO'], required=True)
    parser.add_argument('--strat', default='Cluster Pivot')
    parser.add_argument('--param', default='window')
    args = parser.parse_args()
    
    windows = [50, 100, 150, 200, 250, 300]
    if args.lottery == 'POWER_LOTTO' and args.strat == 'Cluster Pivot':
        # Power Lotto usually better with consensus, but we can sweep Cluster Pivot too
        pass
    elif args.lottery == 'POWER_LOTTO' and args.strat == 'GUM Consensus':
        pass
        
    run_tuning(args.lottery, args.strat, args.param, windows)
