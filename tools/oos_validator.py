#!/usr/bin/env python3
import os
import sys
import numpy as np
import argparse
from tqdm import tqdm

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tools.strategy_leaderboard import StrategyLeaderboard

class OOSValidator(StrategyLeaderboard):
    def __init__(self, lottery_type):
        super().__init__(lottery_type=lottery_type)
        self.validation_size = 200
        self.train_draws = self.draws[:-self.validation_size]
        self.test_draws = self.draws # Will slice in run_backtest appropriately or just overwrite
        
        # Override self.draws for Training Phase methods
        # But wait, run_backtest usually iterates over self.draws.
        # We need a way to swap data.

    def run_phase(self, phase_name, draws_subset, tuning_func):
        print(f"\n🔵 Running {phase_name} Phase (N={len(draws_subset)})")
        # Temporarily swap data
        original_draws = self.draws
        self.draws = draws_subset
        
        try:
            result = tuning_func(self)
            if len(result) == 2:
                best_params, best_score = result
                best_func = None
            else:
                best_params, best_score, best_func = result
        finally:
            self.draws = original_draws
            
        return best_params, best_score, best_func

    def evaluate_on_test(self, test_subset, strategy_func, params):
        print(f"\n🟠 Running Validation Phase (N={len(test_subset)})")
        # For validation, we need to run backtest specifically on these indices
        # But StrategyLeaderboard.run_backtest runs on the *last* N periods of self.draws
        # So we can set self.draws = training_set + test_set (which is original)
        # And run backtest with periods = len(test_subset)
        
        # However, to be strictly OOS, the strategy prediction at index i must NOT see i+1.
        # Standard backtest does this correctly (uses history[:i]).
        # So setting self.draws = full and periods = 200 works perfectly 
        # as it tests the *last* 200 predictions.
        
        original_draws = self.draws
        self.draws = self.draws # Ensure we are using full data (assuming test_subset is the tail)
        
        # Verify alignment
        if test_subset[-1]['draw'] != self.draws[-1]['draw']:
             print("Warning: Test subset alignment issue.")
             
        try:
            rate = self.run_backtest(strategy_func, periods=len(test_subset), **params)
        finally:
            self.draws = original_draws
            
        return rate

def tune_big_lotto(lb):
    # Tune Window for Cluster Pivot
    best_win = 0
    best_rate = -1
    
    windows = [50, 100, 150, 200, 250, 300]
    
    print(f"Sweeping windows: {windows}")
    baseline = lb.baselines.get(2, 0.0369)
    
    for w in tqdm(windows):
        rate = lb.run_backtest(lb.strat_cluster_pivot, periods=300, n_bets=2, window=w) 
        # Using periods=300 for training stability (tuning on the tail of training set)
        if rate > best_rate:
            best_rate = rate
            best_win = w
            
    print(f"✅ Best Training Params: Window={best_win} (Rate: {best_rate*100:.2f}%)")
    return {'n_bets': 2, 'window': best_win}, best_rate

def tune_power_lotto(lb):
    # Tune GUM Weights
    # Simplified Grid to save time
    weight_sets = [
        (0.75, 0.75, 0.50), # Original
        (0.25, 1.00, 0.50), # Previous Best
        (0.50, 0.50, 0.50), # Balanced
        (0.25, 0.25, 0.50),
        (1.00, 0.25, 0.50)
    ]
    
    # We also need to define the wrapper function inside or use partial
    # StrategyLeaderboard doesn't have a generic weighted GUM, we added it to standard GUM in previous step?
    # No, we modified strat_gum in previous step to use hardcoded defaults based on lottery type.
    # We need a flexible one here. 
    
    # Let's attach a dynamic strategy
    def dynamic_gum(history, n_bets=2, window=150, w_m=0.75, w_c=0.75, w_k=0.5):
        scores = np.zeros(lb.max_num + 1)
        m_bets = lb.strat_markov(history, n_bets=4, window=window)
        for b in m_bets:
            for n in b: scores[n] += w_m
        c_bets = lb.strat_cluster_pivot(history, n_bets=4, window=window)
        for b in c_bets:
            for n in b: scores[n] += w_c
        k_bets = lb.strat_cold_numbers(history, n_bets=4, window=window)
        for b in k_bets:
            for n in b: scores[n] += w_k
            
        all_indices = np.arange(1, lb.max_num + 1)
        sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
        return [sorted(sorted_indices[i*6:(i+1)*6].tolist()) for i in range(n_bets)]
    
    best_params = None
    best_rate = -1
    
    print(f"Sweeping weight sets: {len(weight_sets)} configs")
    
    for ws in tqdm(weight_sets):
        params = {'n_bets': 2, 'window': 150, 'w_m': ws[0], 'w_c': ws[1], 'w_k': ws[2]}
        rate = lb.run_backtest(dynamic_gum, periods=300, **params)
        if rate > best_rate:
            best_rate = rate
            best_params = params
            
    print(f"✅ Best Training Params: {best_params} (Rate: {best_rate*100:.2f}%)")
    return best_params, best_rate, dynamic_gum

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', required=True)
    args = parser.parse_args()
    
    validator = OOSValidator(args.lottery)
    
    # 1. Tuning Phase
    # We use data up to index -200
    # Actually, StrategyLeaderboard.run_backtest(periods=N) runs on the LAST N indices.
    # So if we feed it `draws[:-200]`, and ask for `periods=300`, it tests on `[-500:-200]`.
    # Ideally we maximize data usage.
    
    training_set = validator.draws[:-200]
    test_set = validator.draws[-200:]
    
    print(f"📊 OOS Validation: {args.lottery}")
    print(f"Total Draws: {len(validator.draws)}")
    print(f"Training Set: {len(training_set)} (Ends at {training_set[-1]['date']})")
    print(f"Test Set: {len(test_set)} (Starts at {test_set[0]['date']})")
    
    if args.lottery == 'BIG_LOTTO':
        # Phase 1: Tune
        best_params, _, _ = validator.run_phase("Tuning", training_set, tune_big_lotto)
        
        # Phase 2: Validate
        # Note: best_params is just dict. Strategy is strat_cluster_pivot
        start_rate = validator.evaluate_on_test(test_set, validator.strat_cluster_pivot, best_params)
        
        baseline = validator.baselines.get(2, 0.0369)
        print(f"\n🏁 OOS Result (N=200):")
        print(f"Win Rate: {start_rate*100:.2f}%")
        print(f"Baseline: {baseline*100:.2f}%")
        print(f"True Edge: {(start_rate - baseline)*100:+.2f}%")
        
    elif args.lottery == 'POWER_LOTTO':
        # Phase 1: Tune
        # Note: tune_power_lotto returns (params, rate, func)
        best_params, _, best_func = validator.run_phase("Tuning", training_set, tune_power_lotto)
        
        # Phase 2: Validate
        start_rate = validator.evaluate_on_test(test_set, best_func, best_params)
        
        baseline = validator.baselines.get(2, 0.0759)
        print(f"\n🏁 OOS Result (N=200):")
        print(f"Win Rate: {start_rate*100:.2f}%")
        print(f"Baseline: {baseline*100:.2f}%")
        print(f"True Edge: {(start_rate - baseline)*100:+.2f}%")

if __name__ == "__main__":
    main()
