#!/usr/bin/env python3
"""
AI Meta-Optimizer (SMO) - Grand Unified Model Optimizer
======================================================
1. 自動參數尋優：自動掃描不同窗口 (Window) 與各策略權重 (Weights)。
2. 組合配置優化：找出 Markov, Cluster, Cold 的最佳配比。
3. 自動存檔：將最佳配置輸出至 `tools/data/best_config_{lottery}.json`。
"""
import os
import sys
import json
import argparse
import numpy as np
from itertools import product

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

class MetaOptimizer:
    def __init__(self, lottery_type='POWER_LOTTO'):
        self.lb = StrategyLeaderboard(lottery_type=lottery_type)
        self.lottery_type = lottery_type
        
    def get_candidate_strategies(self):
        """自動找出 Leaderboard 中所有可用的 strat_* 方法"""
        methods = [m for m in dir(self.lb) if m.startswith('strat_') and m not in ['strat_random']]
        return methods

    def evaluate_recipe(self, recipe, periods=100):
        """
        評估一個「食譜」的性能
        recipe: {
            "components": [
                {"name": "strat_markov", "weight": 3, "window": 50},
                {"name": "strat_cluster_pivot", "weight": 2, "window": 100}
            ]
        }
        """
        def recipe_func(history, n_bets=2, **kwargs):
            scores = np.zeros(self.lb.max_num + 1)
            for comp in recipe["components"]:
                func = getattr(self.lb, comp["name"])
                # Get 4 bets worth of candidates to score properly
                bets = func(history, n_bets=4, window=comp["window"])
                for b in bets:
                    for n in b: scores[n] += (comp["weight"] / 4.0)
            
            all_indices = np.arange(1, self.lb.max_num + 1)
            sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
            bets = []
            for i in range(n_bets):
                start = i * 6
                end = (i + 1) * 6
                bets.append(sorted(sorted_indices[start:end].tolist()))
            return bets

        rate = self.lb.run_backtest(recipe_func, periods=periods)
        return rate

    def optimize_asd(self, periods=100):
        print(f"🧠 [ASD] Initiating Autonomous Strategy Discovery for {self.lottery_type}...")
        
        # 1. 第一步：單獨測試所有候選策略，找出 Top 3
        candidates = self.get_candidate_strategies()
        print(f"   - Scanning {len(candidates)} theories: {candidates}")
        
        base_results = []
        for strat in candidates:
            # Test each with a standard window
            recipe = {"components": [{"name": strat, "weight": 1, "window": 100}]}
            rate = self.evaluate_recipe(recipe, periods=periods)
            base_results.append((strat, rate))
        
        base_results.sort(key=lambda x: x[1], reverse=True)
        top_strats = [br[0] for br in base_results[:3]]
        print(f"   - Identified Top Performers: {top_strats}")

        # 2. 第二步：嘗試組合配置 (Synergy Search)
        # 嘗試 Top 1, Top 1+2, Top 1+2+3
        best_overall_rate = -1
        best_recipe = None
        
        search_mixes = [
            [top_strats[0]],
            [top_strats[0], top_strats[1]],
            [top_strats[0], top_strats[1], top_strats[2]]
        ]
        
        windows = [50, 100, 150]
        weight_sets = [
            [1, 1, 1],
            [3, 2, 1],
            [1, 2, 3]
        ]

        count = 0
        total_trials = len(search_mixes) * len(windows) * len(weight_sets)
        
        all_results = []
        for mix in search_mixes:
            for window in windows:
                for weights in weight_sets:
                    if len(weights) < len(mix): continue
                    
                    count += 1
                    current_components = []
                    for i, strat_name in enumerate(mix):
                        current_components.append({
                            "name": strat_name,
                            "weight": weights[i],
                            "window": window
                        })
                    
                    recipe = {"components": current_components}
                    rate = self.evaluate_recipe(recipe, periods=periods)
                    all_results.append((recipe, rate))
                    
                    if rate > best_overall_rate:
                        best_overall_rate = rate
                        best_recipe = recipe
                        print(f"   🔥 [New Discovery] Rate: {rate*100:5.2f}% | Mix: {[c['name'] for c in current_components]} | Win: {window}")

        print(f"\n✨ [ASD] Optimization Complete!")
        print(f"🎯 Discovered Recipe Performance: {best_overall_rate*100:.2f}% (M3+)")
        
        # Add metadata
        best_recipe["win_rate"] = best_overall_rate
        best_recipe["lottery_type"] = self.lottery_type
        
        # Save Frontier Library (Top 5 unique results)
        all_results.sort(key=lambda x: x[1], reverse=True)
        unique_frontiers = []
        seen_mixes = set()
        for r, rate in all_results:
            mix_key = tuple(sorted([c['name'] for c in r['components']]))
            if mix_key not in seen_mixes:
                r["win_rate"] = rate
                unique_frontiers.append(r)
                seen_mixes.add(mix_key)
            if len(unique_frontiers) >= 5: break
            
        self.save_config(best_recipe, unique_frontiers)
        return best_recipe

    def save_config(self, config, frontiers=None):
        data_dir = os.path.join(project_root, 'tools', 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # 1. Save Best Config
        file_path = os.path.join(data_dir, f"best_config_{self.lottery_type}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        print(f"💾 Strategic Recipe saved to {file_path}")
        
        # 2. Save Frontier Library
        if frontiers:
            lib_path = os.path.join(data_dir, f"frontier_library_{self.lottery_type}.json")
            with open(lib_path, 'w', encoding='utf-8') as f:
                json.dump(frontiers, f, indent=4, ensure_ascii=False)
            print(f"🧬 Frontier Library (n={len(frontiers)}) saved to {lib_path}")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='POWER_LOTTO', choices=['POWER_LOTTO', 'BIG_LOTTO'])
    parser.add_argument('--n', type=int, default=100, help='訓練回測期數')
    args = parser.parse_args()
    
    opt = MetaOptimizer(lottery_type=args.lottery)
    opt.optimize_asd(periods=args.n)

if __name__ == "__main__":
    main()
