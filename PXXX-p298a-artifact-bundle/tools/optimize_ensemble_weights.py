import sys
import os
import io
import random
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from models.unified_predictor import UnifiedPredictionEngine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def evaluate_weights(history, target_draw, engine, weights):
    # This function needs to be fast.
    # But calling engine methods is slow because they re-analyze history.
    # Optimization: Pre-calculate the candidates/scores for each method for each period.
    return 0

def precompute_predictions(history, test_indices, engine):
    """
    Pre-compute the top 15 numbers from each method for the test periods.
    Returns a list of dicts: [{'method_name': [num1, num2...]}, ...] for each period.
    """
    print("⏳ Pre-computing predictions (this may take a minute)...")
    precomputed = [] # List of (target_actual, method_outputs)
    
    methods = ['statistical', 'trend', 'deviation', 'markov', 'hot_cold_mix']
    
    for idx_offset in range(len(test_indices)):
        # Calculate actual index in history
        # hist used for prediction is everything BEFORE target
        target_idx = test_indices[idx_offset]
        target_draw = history[target_idx]
        train_hist = history[:target_idx]
        
        if len(train_hist) < 100: continue
        
        method_outputs = {}
        for m in methods:
            # We need raw scores if possible, but the engine usually returns a list.
            # We will assign rank-based scores.
            # 1st place = 1.0, 15th place = 0.0
            func_name = f"{m}_predict"
            func = getattr(engine, func_name)
            
            # Use top 15 for deep ensemble
            res = func(train_hist, {'pickCount': 15})
            nums = res.get('ranked_list', [])[:20] if 'ranked_list' in res else res.get('numbers', [])
            method_outputs[m] = nums
            
        precomputed.append((set(target_draw['numbers']), method_outputs))
        print(f".", end="", flush=True)
        
    print("\n✅ Pre-computation done.")
    return precomputed

def rank_mixed(candidate_lists, weights):
    """
    Combine lists using weights.
    candidate_lists: {'statistical': [1, 2, ...], ...}
    weights: {'statistical': 1.0, ...}
    """
    scores = {}
    
    for method, nums in candidate_lists.items():
        w = weights.get(method, 0)
        if w <= 0: continue
        
        # Scoring: Top 1 gets 20 pts, Top 20 gets 1 pt
        total_nums = len(nums)
        for rank, n in enumerate(nums):
            # Normalized score 1.0 down to >0
            # score = (total_nums - rank) / total_nums * w
            # Simple linear:
            raw_score = (25 - rank) if rank < 25 else 0
            if raw_score > 0:
                scores[n] = scores.get(n, 0) + raw_score * w
                
    # Sort by score
    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [x[0] for x in sorted_nums[:6]]

def optimize_weights():
    print("=" * 60)
    print("⚖️ Big Lotto Ensemble Weight Optimization (Hill Climbing)")
    print("=" * 60)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    engine = UnifiedPredictionEngine()
    
    # 1. Select Test Period (Recent 100 draws is enough for tuning, 500 takes too long to precompute)
    # Let's do 100 periods.
    TEST_PERIODS = 100
    if len(all_draws) < 200:
        print("Not enough Data")
        return

    # Indices: We want the last 100. 
    # all_draws is Old -> New in my standard logic? 
    # Wait, usually db.get_all_draws returns New->Old in many scripts, but I reversed it above?
    # db.get_all_draws usually returns New->Old (DESC).
    # I did list(reversed(...)), so all_draws is Old -> New.
    # So history[-1] is latest.
    
    start_idx = len(all_draws) - TEST_PERIODS
    test_indices = list(range(start_idx, len(all_draws)))
    
    # 2. Precompute
    data = precompute_predictions(all_draws, test_indices, engine)
    
    # 3. Optimization Loop
    methods = ['statistical', 'trend', 'deviation', 'markov', 'hot_cold_mix']
    
    # Initial Weights (Equal)
    current_weights = {m: 1.0 for m in methods}
    
    def calc_fitness(w):
        score = 0
        hits = 0
        match3plus = 0
        
        for actual_set, method_out in data:
            pred = rank_mixed(method_out, w)
            match = len(set(pred).intersection(actual_set))
            
            # Fitness Function: Focus on Match 3+
            if match >= 3:
                score += 10 + (match - 3) * 5 # 3->10, 4->15, 5->20
                match3plus += 1
            else:
                score += match # Small credit for 1 or 2
                
        return score, match3plus

    best_score, best_m3 = calc_fitness(current_weights)
    print(f"\nBaseline (Equal Weights): Score {best_score}, Match3+ {best_m3}/{TEST_PERIODS} ({best_m3/TEST_PERIODS*100:.1f}%)")
    
    # Random Hill Climbing
    iterations = 1000
    print(f"Optimizing over {iterations} iterations...")
    
    for i in range(iterations):
        # Mutate
        candidate = current_weights.copy()
        
        # Pick a key to change
        key = random.choice(methods)
        change = random.choice([-0.2, -0.1, 0.1, 0.2])
        candidate[key] = max(0.0, min(5.0, candidate[key] + change))
        
        # Evaluate
        new_score, new_m3 = calc_fitness(candidate)
        
        if new_score > best_score:
            best_score = new_score
            best_m3 = new_m3
            current_weights = candidate
            print(f"Iter {i}: New Best! Score {best_score} (M3+ {best_m3}) -> {candidate}")
            
    print("\n" + "="*60)
    print("🏆 Optimization Complete")
    print("="*60)
    print("Optimal Weights:")
    for k, v in current_weights.items():
        print(f"  {k}: {v:.1f}")
        
    print(f"\nFinal Performance: Match3+ Rate {best_m3/TEST_PERIODS*100:.1f}%")

if __name__ == "__main__":
    optimize_weights()
