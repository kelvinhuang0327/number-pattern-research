import os
import sys
import random
import numpy as np
import logging
import argparse
from typing import List, Dict

# Set path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import db_manager
from common import get_lottery_rules

# Disable noisy logs
logging.basicConfig(level=logging.ERROR)

def calculate_matches(predicted, actual):
    return len(set(predicted) & set(actual))

def main():
    parser = argparse.ArgumentParser(description='Fast Power Lotto Backtest')
    parser.add_argument('--periods', type=int, default=500, help='Number of periods to test')
    parser.add_argument('--bets', type=int, default=1, help='Number of bets per draw')
    args = parser.parse_args()

    lottery_type = 'POWER_LOTTO'
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    db_manager.db_path = db_path
    
    rules = get_lottery_rules(lottery_type)
    engine = UnifiedPredictionEngine()
    
    # Static Optimized Weights (Based on previous audits)
    weights = {
        'statistical_predict': 0.15,
        'smart_markov_predict': 0.15,
        'anomaly_detection_predict': 0.20,
        'ai_lstm_predict': 0.20,
        'community_predict': 0.15,
        'adaptive_weight_predict': 0.15
    }
    
    all_draws = sorted(db_manager.get_all_draws(lottery_type), key=lambda x: x['draw'])
    test_draws = all_draws[-args.periods:]
    
    print(f"⚡ FAST BACKTEST (STATIC WEIGHTS): {len(test_draws)} PERIODS")
    
    win_count = 0
    special_hits = 0
    match_counts = {i: 0 for i in range(7)}
    
    for idx, target in enumerate(test_draws):
        draw_id = target['draw']
        actual_main = set(target['numbers'])
        actual_special = target.get('special')
        
        target_pos = next(i for i, d in enumerate(all_draws) if d['draw'] == draw_id)
        history = list(reversed(all_draws[:target_pos]))
        
        # Weighted Ensemble Prediction
        number_scores = {}
        for num in range(1, 39): number_scores[num] = 0.0
        
        for strat, weight in weights.items():
            if hasattr(engine, strat):
                try:
                    res = getattr(engine, strat)(history, rules)
                    for n in res.get('numbers', []):
                        number_scores[n] += weight * res.get('confidence', 0.5)
                except: continue
        
        # Simple Multi-Bet Generation (Top N sets of 6)
        # For simplicity, we'll just take top 6, next top 6, etc. or top 6 with different specials
        top_nums_all = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        
        best_m = 0
        s_hit = False
        
        # Predicted specials (Top N)
        from models.unified_predictor import predict_special_number
        valid_specials = []
        # Get top-N special recommendation
        # Here we just use a simple frequency + bias for speed
        for s_idx in range(1, 9):
             valid_specials.append(s_idx)
        random.shuffle(valid_specials) # Placeholder for diversified specials
        
        for b_idx in range(args.bets):
            # Beta: Just use top 6 for all bets but different specials to test special hit rate
            # In real system we diversify main numbers too
            predicted_main = [n for n, s in top_nums_all[:6]]
            
            # Special: Cycle through or use top-N
            # Actually, let's use the real predictor's top-N
            # (In fast mode, we just take 1, 2, 3...)
            # For 4-bet, we ideally cover 4/8 specials.
            predicted_special = (b_idx % 8) + 1 
            
            m = calculate_matches(predicted_main, actual_main)
            if m > best_m: best_m = m
            if predicted_special == actual_special: s_hit = True
        
        if s_hit: special_hits += 1
        if s_hit or best_m >= 3: win_count += 1
        match_counts[best_m] += 1
        
        if (idx + 1) % 100 == 0:
            print(f"Progress: {idx+1}/{len(test_draws)}")

    print("\n" + "=" * 50)
    print(f"🏆 FAST SUMMARY ({len(test_draws)} PERIODS)")
    print(f"Overall Prize Hit Rate: {(win_count / len(test_draws))*100:.2f}%")
    print(f"Special Hits: {special_hits} ({(special_hits/len(test_draws))*100:.2f}%)")
    print("=" * 50)

if __name__ == "__main__":
    main()
