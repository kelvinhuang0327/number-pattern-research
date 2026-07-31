#!/usr/bin/env python3
"""
Consensus Ensemble Predictor (Grand Unified Model - GUM)
======================================================
1. 多維度評分：結合 Markov (時間)、Cluster (空間)、Cold (統計)。
2. 權重疊加：找出受多個模型共同推薦的「高信心」號碼。
3. 自動篩選：排除單一模型特有的噪音。
"""
import os
import sys
import argparse
import json
from collections import Counter
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard
from lottery_api.models.special_predictor import PowerLottoSpecialPredictor
from lottery_api.common import get_lottery_rules

class ConsensusEngine:
    def __init__(self, lottery_type='POWER_LOTTO'):
        self.lb = StrategyLeaderboard(lottery_type=lottery_type)
        self.lottery_type = lottery_type
        self.max_num = self.lb.max_num
        self.history = self.lb.draws
        self.config = self.load_best_config()
        
    def load_best_config(self):
        file_path = os.path.join(project_root, 'tools', 'data', f"best_config_{self.lottery_type}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def get_consensus_scores(self, recipe=None):
        if recipe is None or "components" not in recipe:
            # Fallback to default GUM configuration if no ASD recipe exists
            recipe = {
                "components": [
                    {"name": "strat_markov", "weight": 3, "window": 100},
                    {"name": "strat_cluster_pivot", "weight": 3, "window": 150},
                    {"name": "strat_cold_numbers", "weight": 2, "window": 100}
                ]
            }
            
        scores = np.zeros(self.max_num + 1)
        
        for comp in recipe["components"]:
            strat_name = comp["name"]
            weight = comp["weight"]
            window = comp["window"]
            
            if hasattr(self.lb, strat_name):
                func = getattr(self.lb, strat_name)
                # Use n_bets=4 for broader scoring signal
                bets = func(self.history, n_bets=4, window=window)
                for b in bets:
                    for n in b:
                        scores[n] += (weight / 4.0)
            
        return scores

    def validate_combination(self, nums):
        """統計剪枝過濾器：排除機率極低的組合"""
        # 1. 和值過濾 (Sum Range)
        s = sum(nums)
        if self.lottery_type == 'BIG_LOTTO':
            if not (100 <= s <= 200): return False
        else:
            if not (80 <= s <= 160): return False
            
        # 2. 奇偶平衡 (Parity Check)
        evens = len([n for n in nums if n % 2 == 0])
        if evens < 1 or evens > 5: return False # 排除全奇或全偶
        
        # 3. 連號控制 (Consecutive Check)
        nums_sorted = sorted(nums)
        consecutive_groups = 0
        for i in range(len(nums_sorted)-1):
            if nums_sorted[i+1] - nums_sorted[i] == 1:
                consecutive_groups += 1
        if consecutive_groups > 2: return False # 排除 3 個以上連號組 (如 1,2, 5,6, 10,11)
        
        return True

    def get_regime(self):
        """盤勢偵測：檢測最近 10 期的規律性 (由熵值估計)"""
        recent = self.history[-10:]
        all_nums = [n for d in recent for n in d['numbers']]
        counts = Counter(all_nums)
        # 簡單規律性指標：重複出現的號碼越多，盤勢越趨勢化 (Stable)
        duplicates = sum(1 for n, c in counts.items() if c > 1)
        if duplicates >= 5:
            return "STABLE (Trend Regime)"
        return "VOLATILE (Chaos Regime)"

    def predict(self, num_bets=2, window=None):
        recipe = self.config
        if window and recipe:
            for comp in recipe["components"]:
                comp["window"] = window
                
        scores = self.get_consensus_scores(recipe=recipe)
        
        # Sorting numbers by score
        all_indices = np.arange(1, self.max_num + 1)
        sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
        
        bets = []
        bets = []
        # Rank-Aware Search: Try to stay as close to the top-ranked numbers as possible
        next_start_idx = 0
        for b_idx in range(num_bets):
            # Try combinations starting from the best available numbers
            found = False
            for offset in range(30): # Look ahead up to 30 spots
                if found: break
                # Base candidate: current top 6 from this starting point
                base_ptr = next_start_idx
                if base_ptr + 6 > len(sorted_indices): break
                
                # We try small variations to satisfy pruning
                # (This is a simplified rank-priority search)
                candidate = sorted(sorted_indices[base_ptr : base_ptr+6].tolist())
                if self.validate_combination(candidate):
                    bets.append(candidate)
                    next_start_idx += 6
                    found = True
                else:
                    # Try swapping the last number with something slightly further down
                    for swap_idx in range(base_ptr+6, min(base_ptr+12, len(sorted_indices))):
                        alt_candidate = sorted(sorted_indices[base_ptr:base_ptr+5].tolist() + [sorted_indices[swap_idx]])
                        if self.validate_combination(alt_candidate):
                            bets.append(alt_candidate)
                            next_start_idx = base_ptr + 6 # Still consume the block
                            found = True
                            break
            
            # Absolute fallback if search fails
            if not found:
                bets.append(sorted(sorted_indices[next_start_idx:next_start_idx+6].tolist()))
                next_start_idx += 6
                
        return bets, scores, self.get_regime()

def main():
    parser = argparse.ArgumentParser(description='共識集成預測器 (GUM)')
    parser.add_argument('--lottery', default='POWER_LOTTO', choices=['POWER_LOTTO', 'BIG_LOTTO'])
    parser.add_argument('--num', type=int, default=2)
    parser.add_argument('--window', type=int, default=50)
    args = parser.parse_args()
    
    engine = ConsensusEngine(lottery_type=args.lottery)
    
    if engine.config:
        print(f"🧠 [ASD RECIPE] Discovered Components:")
        for comp in engine.config.get("components", []):
            print(f"   - {comp['name']}: Weight={comp['weight']}, Window={comp['window']}")
    else:
        print(f"⚠️ [DEFAULT] No ASD recipe found. Using standard parameters.")
        
    bets, scores, regime = engine.predict(num_bets=args.num, window=args.window)
    
    print(f"\n📡 Current Regime: {regime}")
    print(f"🛡️  Status: Statistical Pruning Active (Sum/Parity/Consecutive Filters)")
    
    print("\n" + "╔" + "═"*68 + "╗")
    print("║" + " "*15 + f"🧠  CONSENSUS ENSEMBLE (GUM): {args.lottery:<11}  🧠" + " "*15 + "║")
    print("╚" + "═"*68 + "╝")
    
    print(f"\n📊 Heatmap Analysis (Top 10 Scores):")
    all_indices = np.arange(1, engine.max_num + 1)
    top_10 = all_indices[np.argsort(scores[1:])[::-1]][:10]
    for n in top_10:
        print(f"   - Number {n:02d}: Score {scores[n]:.2f}")
        
    print("\n" + "="*70)
    print(f"🎯 FINAL CONSENSUS RECOMMENDATION (Draw: {int(engine.history[-1]['draw'])+1})")
    print("-" * 70)
    
    # Special Number for Power Lotto
    special_nums = []
    if args.lottery == 'POWER_LOTTO':
        rules = get_lottery_rules(args.lottery)
        sp_predictor = PowerLottoSpecialPredictor(rules)
        special_nums = sp_predictor.predict_top_n(engine.history, n=args.num)
    
    for i, b in enumerate(bets):
        num_str = ", ".join(f"{n:02d}" for n in b)
        spec = f" | 特別號: {special_nums[i]:02d}" if i < len(special_nums) else ""
        print(f"注 {i+1}: [{num_str}]{spec}")
        
    print("=" * 70)
    print(f"💡 Logic: Aggregated signals from Markov, Cluster, and Cold models.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
