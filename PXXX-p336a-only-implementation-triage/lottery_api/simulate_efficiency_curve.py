#!/usr/bin/env python3
"""
Simulate Win Rate Efficiency Curve for Daily 539
Determines how many bets are needed to reach 50% success rate (Match >= 3).
"""
import sys
import os
import logging
import itertools
from collections import defaultdict, Counter
import numpy as np

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)

def get_top_numbers_by_ensemble(history, lottery_rules, top_k=15):
    """
    Get numbers ranked by weighted consensus from multiple basic models.
    (Simplified version of OptimizedEnsemble for speed)
    """
    scores = defaultdict(float)
    
    # 1. Frequency (Weight 0.3)
    try:
        res = prediction_engine.frequency_predict(history, lottery_rules)
        for i, num in enumerate(res['numbers']):
            scores[num] += 0.3 * (1.0 - i/len(res['numbers']))
    except: pass
    
    # 2. Trend (Weight 0.2)
    try:
        res = prediction_engine.trend_predict(history, lottery_rules)
        for i, num in enumerate(res['numbers']):
            scores[num] += 0.2 * (1.0 - i/len(res['numbers']))
    except: pass
    
    # 3. Deviation (Weight 0.2)
    try:
        res = prediction_engine.deviation_predict(history, lottery_rules)
        for i, num in enumerate(res['numbers']):
            scores[num] += 0.2 * (1.0 - i/len(res['numbers']))
    except: pass
    
    # 4. Hot Cold (Weight 0.1)
    try:
        res = prediction_engine.hot_cold_mix_predict(history, lottery_rules)
        for i, num in enumerate(res['numbers']):
            scores[num] += 0.1 * (1.0 - i/len(res['numbers']))
    except: pass

    # Sort
    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [num for num, _ in sorted_nums[:top_k]]

def generate_bets_from_top_numbers(top_numbers, count_needed, pick_count=5):
    """
    Generate bets by combining top numbers.
    Strategy: Ordered combinations based on 'Top N' subset.
    We try to cover combinations of the best numbers first.
    """
    bets = []
    
    # Strategy: Combinations of top X numbers
    # X=5 -> 1 bet
    # X=6 -> 6 bets
    # X=7 -> 21 bets
    # ...
    
    # We generate combinations of top_numbers using itertools
    # But we want to prioritize "Best numbers".
    # So we iterate combination size? No, pick_count is fixed (5).
    # We maximize the "Sum of Ranks" (lower is better, if rank 0 is best).
    # Actually, simplistic approach: Just standard combinations of the top K numbers.
    # Since itertools.combinations emits in lexicographic order of indices if input is sorted, 
    # we just need to pass the top_numbers list in rank order? 
    # No, itertools.combinations('ABCD', 2) -> AB AC AD BC BD CD.
    # AB is rank 0+1. AC is 0+2. BC is 1+2.
    # This is roughly score ordered.
    
    # Generate broad pool of combinations then sort? Too expensive if top_numbers is large.
    # If top_numbers is 12, C(12,5) = 792. Manageable.
    
    pool = top_numbers  # Assuming list is [Best1, Best2, ... BestN]
    
    # Generate all combinations
    combs = list(itertools.combinations(pool, pick_count))
    
    # Determine "Score" for each combination: Sum of indices (lower is better)
    # Map number to rank
    rank_map = {num: i for i, num in enumerate(pool)}
    
    def score_comb(c):
        return sum(rank_map[n] for n in c)
        
    combs.sort(key=score_comb)
    
    return [list(c) for c in combs[:count_needed]]

def run_simulation(lottery_type='DAILY_539'):
    print("=" * 80)
    print(f"🚀 Win Rate Efficiency Simulation: {lottery_type}")
    print("=" * 80)
    
    db_draws = db_manager.get_all_draws(lottery_type)
    if not db_draws: return
    
    # Rules
    normalized_type = 'DAILY_539' if lottery_type in ['今彩539', 'DAILY_539'] else 'BIG_LOTTO'
    pick_count = 5 if normalized_type == 'DAILY_539' else 6
    match_threshold = 3 # Win if match >= 3
    
    rules = get_lottery_rules(normalized_type)
    
    # Backtest setup
    test_draws = 50
    start_idx = 0
    end_idx = min(len(db_draws), test_draws)
    
    print(f"📊 Backtesting last {end_idx} draws...")
    print(f"🎯 Goal: Match >= {match_threshold} numbers")
    print("-" * 80)
    
    # We want to find success rate for N bets, N = 1, 5, 10, 20, 30, 40, 50...
    checkpoints = [1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    wins_at_k = defaultdict(int) 
    
    total_valid_draws = 0
    
    for i in range(start_idx, end_idx):
        target_draw = db_draws[i]
        train_data = db_draws[i+1:]
        
        if len(train_data) < 50: break
        total_valid_draws += 1
        
        target_nums = set(target_draw['numbers'])
        
        # 1. Get Top 12 numbers from ensemble (C(12,5)=792 max bets, enough for our checkpoints)
        top_numbers = get_top_numbers_by_ensemble(train_data, rules, top_k=12)
        
        # 2. Generate bets sequence (up to max checkpoint)
        max_bets = checkpoints[-1]
        bets_sequence = generate_bets_from_top_numbers(top_numbers, max_bets, pick_count)
        
        # 3. Check wins cumulative
        # Checking: Did we win AT LEAST ONCE in the first K bets?
        
        has_won = False
        for k, bet in enumerate(bets_sequence, 1):
            # Check this bet
            match_count = len(target_nums.intersection(set(bet)))
            if match_count >= match_threshold:
                has_won = True
                
            if has_won:
                # If we won by bet k, we definitely "have won" for any pool size >= k
                # Record win for all checkpoints >= k
                for cp in checkpoints:
                    if k <= cp:
                        wins_at_k[cp] += 1
                        
            # Optimization: If we already won for all checkpoints (k > max_checkpoints), break?
            # No, 'wins_at_k' is cumulative. 
            # If win happened at bet 5:
            # CP=1: Lost (k>1)
            # CP=5: Won (k<=5)
            # CP=10: Won (k<=10)
            
            if has_won and k == bets_sequence[-1]: # Just processed last bet
                pass

        if i % 10 == 0:
            print(f"   Processed draw {i+1}...")
            
    # Calculate %
    print("-" * 80)
    print("🏆 EFFICIENCY RESULTS")
    print(f"Results over {total_valid_draws} draws")
    print("-" * 50)
    print(f"{'Bets Bought':<15} | {'Win Rate (Match >= 3)':<25}")
    print("-" * 50)
    
    found_50 = False
    
    for cp in checkpoints:
        wins = wins_at_k[cp]
        rate = wins / total_valid_draws
        print(f"{cp:<15} | {rate:.2%}")
        
        if not found_50 and rate >= 0.5:
            print(f"\n✅ RECOMENDATION: Buy {cp} bets to reach >50% win rate.")
            found_50 = True
            
    if not found_50:
        print("\n⚠️ 100 bets were not sufficient to reach 50% win rate with this strategy.")

if __name__ == '__main__':
    run_simulation('DAILY_539')
