#!/usr/bin/env python3
import os
import sys
import argparse
import numpy as np
from tqdm import tqdm
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tools.strategy_leaderboard import StrategyLeaderboard

class GUMTuner(StrategyLeaderboard):
    def strat_gum_tuned(self, history, n_bets=2, window=50, w_m=0.75, w_c=0.75, w_k=0.5):
        scores = np.zeros(self.max_num + 1)
        m_bets = self.strat_markov(history, n_bets=4, window=window)
        for b in m_bets:
            for n in b: scores[n] += w_m
        c_bets = self.strat_cluster_pivot(history, n_bets=4, window=window)
        for b in c_bets:
            for n in b: scores[n] += w_c
        k_bets = self.strat_cold_numbers(history, n_bets=4, window=window)
        for b in k_bets:
            for n in b: scores[n] += w_k
            
        all_indices = np.arange(1, self.max_num + 1)
        sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
        return [sorted(sorted_indices[i*6:(i+1)*6].tolist()) for i in range(n_bets)]

def run_grid_search(lottery_type):
    tuner = GUMTuner(lottery_type=lottery_type)
    baseline = tuner.baselines.get(2, 0.0369)
    periods = 500
    
    print(f"\n📊 Tuning GUM Weights on {lottery_type} (N={periods})")
    print("-" * 60)
    
    weight_options = [0.25, 0.5, 0.75, 1.0]
    best_rate = -1
    best_params = None
    
    results = []
    
    # Nested loops for w_m, w_c (w_k fixed at 0.5 to reduce search space, or sweep it too)
    for w_m in weight_options:
        for w_c in weight_options:
            for w_k in [0.25, 0.5]:
                rate = tuner.run_backtest(tuner.strat_gum_tuned, periods=periods, n_bets=2, window=50, w_m=w_m, w_c=w_c, w_k=w_k)
                edge = rate - baseline
                results.append(((w_m, w_c, w_k), rate, edge))
                if rate > best_rate:
                    best_rate = rate
                    best_params = (w_m, w_c, w_k)
    
    results.sort(key=lambda x: x[2], reverse=True)
    print(f"{'W_Markov':<8} | {'W_Cluster':<10} | {'W_Cold':<8} | {'Win Rate':<10} | {'Edge'}")
    print("-" * 60)
    for params, rate, edge in results[:10]:
        print(f"{params[0]:<8} | {params[1]:<10} | {params[2]:<8} | {rate*100:8.2f}% | {edge*100:+8.2f}%")
        
    print(f"\n🏆 Best Weights: Markov={best_params[0]}, Cluster={best_params[1]}, Cold={best_params[2]} ({best_rate*100:.2f}% Win Rate)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='BIG_LOTTO')
    args = parser.parse_args()
    run_grid_search(args.lottery)
