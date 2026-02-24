#!/usr/bin/env python3
"""
Evolutionary GUM Predictor (Frontier Discovery System)
=====================================================
1. Frontier Library: Maintains multiple high-alpha recipes.
2. Adaptive Stacking: Dynamically switches based on 10-period Regime Velocity.
3. Hybrid Fallback: Gracefully reverts to stable anchors if uncertainty is too high.
4. Exhaustive Search: Accesses 60+ theoretical models.
"""
import os
import sys
import argparse
import json
import logging
from collections import Counter
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard
from lottery_api.models.special_predictor import PowerLottoSpecialPredictor
from lottery_api.common import get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class EvolutionaryGUM:
    def __init__(self, lottery_type='POWER_LOTTO'):
        self.lb = StrategyLeaderboard(lottery_type=lottery_type)
        self.lottery_type = lottery_type
        self.max_num = self.lb.max_num
        self.history = self.lb.draws
        self.frontier_library = self.load_frontier_library()
        self.stable_recipe = self.get_stable_recipe()
        
    def load_frontier_library(self):
        """Load multiple high-performance recipes if available."""
        # Check for frontier_library_{lottery_type}.json
        file_path = os.path.join(project_root, 'tools', 'data', f"frontier_library_{self.lottery_type}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load frontier library: {e}")
        
        # Fallback to best_config if no library exists
        best_config_path = os.path.join(project_root, 'tools', 'data', f"best_config_{self.lottery_type}.json")
        if os.path.exists(best_config_path):
            with open(best_config_path, 'r', encoding='utf-8') as f:
                return [json.load(f)]
        
        return []

    def get_stable_recipe(self):
        """Define a verified stable recipe as a safety anchor."""
        if self.lottery_type == 'POWER_LOTTO':
            return {"components": [{"name": "strat_twin_strike", "weight": 1, "window": 150}]}
        else: # BIG_LOTTO
            return {"components": [{"name": "strat_cluster_pivot", "weight": 1, "window": 150}]}

    def get_consensus_scores(self, recipe):
        """Calculate weighted consensus scores for a specific recipe."""
        scores = np.zeros(self.max_num + 1)
        if not recipe or "components" not in recipe:
            return scores
            
        for comp in recipe["components"]:
            strat_name = comp["name"]
            weight = comp["weight"]
            window = comp["window"]
            
            if hasattr(self.lb, strat_name):
                func = getattr(self.lb, strat_name)
                bets = func(self.history, n_bets=4, window=window)
                for b in bets:
                    for n in b:
                        scores[n] += (weight / 4.0)
        return scores

    def get_regime_metrics(self):
        """Analyze current market regime with multiple metrics (Entropy, Velocity, Stability)."""
        recent_10 = self.history[-10:]
        
        # 1. Stability metric (Duplicates in last 10)
        counts_10 = Counter([n for d in recent_10 for n in d['numbers']])
        stability_score = sum(1 for n, c in counts_10.items() if c > 1) / 5.0
        
        # 2. Velocity (How fast the 'Internal Leaderboard' is shifting)
        top_nums_window = []
        for i in range(5):
            h_slice = self.history[:-(i+1)]
            all_n = [n for d in h_slice[-20:] for n in d['numbers']]
            top_5 = [item[0] for item in Counter(all_n).most_common(5)]
            top_nums_window.append(set(top_5))
        
        overlaps = []
        for i in range(len(top_nums_window)-1):
            overlap = len(top_nums_window[i] & top_nums_window[i+1]) / 5.0
            overlaps.append(overlap)
        avg_velocity = 1.0 - np.mean(overlaps)
        
        if stability_score >= 1.0 and avg_velocity < 0.4:
            return "STABLE (Trend Regime)", stability_score, avg_velocity
        elif avg_velocity > 0.7:
            return "CHAOTIC (Flash Regime)", stability_score, avg_velocity
        return "VOLATILE (Chaos Regime)", stability_score, avg_velocity

    def _calculate_frontier_synergy(self, recipes):
        """Find recipes with low correlation (Diverse possibilities)."""
        if len(recipes) < 2: return recipes
            
        selected = [recipes[0]]
        for r in recipes[1:]:
            set1 = set([c['name'] for c in selected[0]['components']])
            set2 = set([c['name'] for c in r['components']])
            overlap = len(set1 & set2) / max(len(set1), len(set2))
            if overlap < 0.5:
                selected.append(r)
                if len(selected) >= 3: break
        return selected

    def validate_combination(self, nums):
        """Rigorous statistical pruning filters."""
        s = sum(nums)
        if self.lottery_type == 'BIG_LOTTO':
            if not (100 <= s <= 200): return False
        else:
            if not (80 <= s <= 160): return False
            
        evens = len([n for n in nums if n % 2 == 0])
        if evens < 1 or evens > 5: return False
        
        nums_sorted = sorted(nums)
        consecutive_groups = 0
        for i in range(len(nums_sorted)-1):
            if nums_sorted[i+1] - nums_sorted[i] == 1:
                consecutive_groups += 1
        if consecutive_groups > 2: return False
        
        return True

    def predict(self, num_bets=2):
        regime, stability, velocity = self.get_regime_metrics()
        
        logger.info(f"📡 Regime: {regime} | Stability: {stability:.2f} | Velocity: {velocity:.2f}")
        
        # Decision Logic
        if regime == "STABLE (Trend Regime)":
            active_recipes = self.frontier_library[:1] if self.frontier_library else [self.stable_recipe]
        elif regime == "CHAOTIC (Flash Regime)":
            logger.info("⚡ Flash Regime detected. Using strict stable fallback.")
            active_recipes = [self.stable_recipe]
        else: # VOLATILE
            logger.info("🧪 Volatile state. Engaging Possibility Explorer (Synergy Stacking).")
            active_recipes = self._calculate_frontier_synergy(self.frontier_library)
            if not active_recipes: active_recipes = [self.stable_recipe]
            
        # Composite Scoring
        composite_scores = np.zeros(self.max_num + 1)
        for i, recipe in enumerate(active_recipes):
            recipe_weight = 1.0 / len(active_recipes)
            composite_scores += self.get_consensus_scores(recipe) * recipe_weight
            
        # Selection Logic
        all_indices = np.arange(1, self.max_num + 1)
        sorted_indices = all_indices[np.argsort(composite_scores[1:])[::-1]]
        
        bets = []
        next_start_idx = 0
        for b_idx in range(num_bets):
            found = False
            for offset in range(30):
                if found: break
                base_ptr = next_start_idx
                if base_ptr + 6 > len(sorted_indices): break
                
                candidate = sorted(sorted_indices[base_ptr : base_ptr+6].tolist())
                if self.validate_combination(candidate):
                    bets.append(candidate)
                    next_start_idx += 6
                    found = True
                else:
                    for swap_idx in range(base_ptr+6, min(base_ptr+50, len(sorted_indices))):
                        alt_candidate = sorted(sorted_indices[base_ptr:base_ptr+5].tolist() + [sorted_indices[swap_idx]])
                        if self.validate_combination(alt_candidate):
                            bets.append(alt_candidate)
                            next_start_idx = base_ptr + 6
                            found = True
                            break
            if not found:
                bets.append(sorted(sorted_indices[next_start_idx:next_start_idx+6].tolist()))
                next_start_idx += 6
                
        return bets, composite_scores, regime, active_recipes

def main():
    parser = argparse.ArgumentParser(description='Evolutionary GUM Predictor')
    parser.add_argument('--lottery', default='POWER_LOTTO', choices=['POWER_LOTTO', 'BIG_LOTTO'])
    parser.add_argument('--num', type=int, default=2)
    args = parser.parse_args()
    
    engine = EvolutionaryGUM(lottery_type=args.lottery)
    bets, scores, regime, recipes = engine.predict(num_bets=args.num)
    
    print(f"\n📡 Current Regime: {regime}")
    print(f"🧬 Active Evolution Recipes: {len(recipes)}")
    for r in recipes:
        comps = [c['name'].replace('strat_', '') for c in r.get('components', [])]
        print(f"   - Mix: {', '.join(comps)}")
    
    print(f"\n📊 Heatmap Analysis (Top 5 Alpha):")
    all_indices = np.arange(1, engine.max_num + 1)
    top_5 = all_indices[np.argsort(scores[1:])[::-1]][:5]
    for n in top_5:
        print(f"   - Number {n:02d}: Score {scores[n]:.2f}")
        
    print("\n" + "="*70)
    print(f"🎯 EVOLUTIONARY GUM RECOMMENDATION (Draw: {int(engine.history[-1]['draw'])+1})")
    print("-" * 70)
    
    special_nums = []
    if args.lottery == 'POWER_LOTTO':
        rules = get_lottery_rules(args.lottery)
        sp_predictor = PowerLottoSpecialPredictor(rules)
        special_nums = sp_predictor.predict_top_n(engine.history, n=args.num)
    
    for i, b in enumerate(bets):
        num_str = ", ".join(f"{n:02d}" for n in b)
        spec = f" | 特別號: {special_nums[i]:02d}" if i < len(special_nums) else ""
        print(f"注 {i+1}: [{num_str}]{spec}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
