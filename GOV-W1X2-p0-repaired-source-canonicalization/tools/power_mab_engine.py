#!/usr/bin/env python3
"""
Power Lotto Multi-Armed Bandit (MAB) Engine
===========================================
Uses Thompson Sampling (Reinforcement Learning) to dynamically select 
the best theoretical model for the current Power Lotto regime.

Arms (Sub-Strategies):
1. Cold Numbers (Long-term regression)
2. Momentum (Short-term bursts)
3. Zonal Balance (Spatial constraints)
4. Markov Transition (Sequence dependency)
5. Companion Analysis (Pairings)
... and more.
"""
import os
import sys
import numpy as np
import json
from scipy.stats import beta

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

class PowerMABEngine:
    def __init__(self, lottery_type='POWER_LOTTO', state_path=None):
        self.lb = StrategyLeaderboard(lottery_type=lottery_type)
        self.lottery_type = lottery_type
        if state_path is None:
            state_path = os.path.join(project_root, 'tools', 'data', f'mab_state_{lottery_type}.json')
        self.state_path = state_path
        
        # Initialize Arms with broader theoretical diversity
        self.arms = [
            {"name": "strat_cold_numbers", "alpha": 1, "beta": 1},
            {"name": "strat_frequency_hot", "alpha": 1, "beta": 1},
            {"name": "strat_markov", "alpha": 1, "beta": 1},
            {"name": "strat_apriori", "alpha": 1, "beta": 1},
            {"name": "strat_cluster_pivot", "alpha": 1, "beta": 1},
            {"name": "strat_entropy_pivot", "alpha": 1, "beta": 1},
            {"name": "strat_gap_reversion", "alpha": 1, "beta": 1}
        ]
        self.load_state()

    def load_state(self):
        if os.path.exists(self.state_path):
            with open(self.state_path, 'r') as f:
                saved_arms = json.load(f)
                # Merge saved states into current arms
                arm_map = {a['name']: a for a in saved_arms}
                for arm in self.arms:
                    if arm['name'] in arm_map:
                        arm['alpha'] = arm_map[arm['name']]['alpha']
                        arm['beta'] = arm_map[arm['name']]['beta']

    def save_state(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, 'w') as f:
            json.dump(self.arms, f)

    def select_arm(self):
        """Thompson Sampling: Sample from Beta distribution for each arm."""
        samples = []
        for arm in self.arms:
            s = np.random.beta(arm['alpha'], arm['beta'])
            samples.append(s)
        best_idx = np.argmax(samples)
        return self.arms[best_idx]

    def update_arm(self, arm_name, success):
        """Update Beta distribution parameters based on outcome."""
        for arm in self.arms:
            if arm['name'] == arm_name:
                if success:
                    arm['alpha'] += 1
                else:
                    arm['beta'] += 1
                break

    def get_zone(self, n):
        if n > 35: return 7
        return (n - 1) // 5

    def predict(self, history, num_bets=2):
        """Pick multiple arms and ensemble their results with Zonal Pruning."""
        samples = []
        for arm in self.arms:
            s = np.random.beta(arm['alpha'], arm['beta'])
            samples.append((arm, s))
            
        sorted_arms = sorted(samples, key=lambda x: x[1], reverse=True)
        
        # Determine Typical Zones (Spatial Bias)
        coverage_counts = {}
        for d in history[-200:]:
            zones = len(set(self.get_zone(n) for n in d['numbers']))
            coverage_counts[zones] = coverage_counts.get(zones, 0) + 1
        typical_zones = sorted(coverage_counts.items(), key=lambda x: x[1], reverse=True)
        top_zones = [z[0] for z in typical_zones[:2]]

        final_bets = []
        chosen_arm_names = []
        
        arm_idx = 0
        while len(final_bets) < num_bets and arm_idx < len(sorted_arms):
            arm = sorted_arms[arm_idx][0]
            strat_func = getattr(self.lb, arm['name'])
            # Generate more candidates to allow pruning
            candidates = strat_func(history, n_bets=4, window=100)
            
            for bet in candidates:
                zones = len(set(self.get_zone(n) for n in bet))
                if zones in top_zones:
                    if bet not in final_bets:
                        final_bets.append(bet)
                        chosen_arm_names.append(arm['name'])
                        if len(final_bets) >= num_bets: break
            arm_idx += 1
            
        # Fallback if pruning is too aggressive
        if not final_bets:
            for i in range(min(num_bets, len(sorted_arms))):
                arm = sorted_arms[i][0]
                strat_func = getattr(self.lb, arm['name'])
                final_bets.extend(strat_func(history, n_bets=1, window=100))
                chosen_arm_names.append(arm['name'])
            
        return final_bets[:num_bets], chosen_arm_names

def run_mab_audit(n=1000):
    engine = PowerMABEngine()
    history_full = engine.lb.draws
    
    # We reset state for clean audit
    for arm in engine.arms:
        arm['alpha'] = 1
        arm['beta'] = 1
        
    hits_3_plus = 0
    total = 0
    
    start_idx = len(history_full) - n
    
    print(f"🚀 MAB WALK-FORWARD AUDIT (N={n})")
    print("-" * 50)
    
    for i in range(n):
        idx = start_idx + i
        target = history_full[idx]['numbers']
        history_slice = history_full[:idx]
        
        if len(history_slice) < 150: continue
        
        # 1. Predict
        bets, chosen_arms = engine.predict(history_slice, num_bets=2)
        
        # 2. Check result
        win = False
        for b in bets:
            if sum(1 for n in b if n in target) >= 3:
                win = True
                break
        
        # 3. Update MAB (Online Learning)
        # We update each chosen arm based on its individual performance
        for arm_name in chosen_arms:
            # Re-predict for that specific arm to see if IT won
            strat_func = getattr(engine.lb, arm_name)
            arm_bets = strat_func(history_slice, n_bets=1, window=100)
            arm_win = sum(1 for n in arm_bets[0] if n in target) >= 3
            engine.update_arm(arm_name, arm_win)
            
        if win: hits_3_plus += 1
        total += 1
        
        if (i+1) % 100 == 0:
            print(f"   ∟ Progress: {i+1}/{n} | Current Hit Rate: {hits_3_plus/total*100:.2f}%")

    win_rate = hits_3_plus / total if total > 0 else 0
    baseline = engine.lb.rand_win_2
    edge = win_rate - baseline
    
    print("-" * 50)
    print(f"MAB Final Results (N={total})")
    print(f"Win Rate (M3+): {win_rate*100:.2f}%")
    print(f"Baseline: {baseline*100:.2f}%")
    print(f"Edge: {edge*100:+.2f}%")
    
    print("\nArm Confidence (Alpha/Total):")
    for arm in engine.arms:
        score = arm['alpha'] / (arm['alpha'] + arm['beta'])
        print(f"   - {arm['name']:<20}: {score:7.4f}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=500)
    args = parser.parse_args()
    
    run_mab_audit(n=args.n)
