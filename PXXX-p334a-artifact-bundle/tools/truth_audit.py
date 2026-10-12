import os
import sys
import random
import numpy as np
import logging
from collections import Counter

# Set path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import db_manager
from common import get_lottery_rules

logging.basicConfig(level=logging.ERROR)

def calculate_matches(predicted, actual):
    return len(set(predicted) & set(actual))

def audit():
    lottery_type = 'POWER_LOTTO'
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    db_manager.db_path = db_path
    
    all_draws = sorted(db_manager.get_all_draws(lottery_type), key=lambda x: x['draw'])
    test_periods = 500
    test_draws = all_draws[-test_periods:]
    
    print(f"📊 TRUTH AUDIT (Last {test_periods} Periods)")
    print("-" * 60)
    
    # Random Baseline calculation
    random.seed(42)
    random_1bet_m3plus = 0
    random_1bet_specials = 0
    random_1bet_union = 0
    
    ai_1bet_m3plus = 0
    ai_1bet_specials = 0
    ai_1bet_union = 0
    
    engine = UnifiedPredictionEngine()
    rules = get_lottery_rules(lottery_type)
    
    print("\nProcessing Periods...")
    
    for idx, target in enumerate(test_draws):
        actual_m = target['numbers']
        actual_s = target['special']
        
        # Random Bet (1-Bet)
        r_m = random.sample(range(1, 39), 6)
        r_s = random.randint(1, 8)
        
        r_match = calculate_matches(r_m, actual_m)
        r_s_hit = (r_s == actual_s)
        
        if r_s_hit: random_1bet_specials += 1
        if r_match >= 3: random_1bet_m3plus += 1
        if r_s_hit or r_match >= 3: random_1bet_union += 1
        
        # AI Bet (1-Bet)
        target_pos = next(i for i, d in enumerate(all_draws) if d['draw'] == target['draw'])
        history = list(reversed(all_draws[:target_pos]))
        
        prediction_map = {}
        for n in range(1, 39): prediction_map[n] = 0.0
        
        strats = ['statistical_predict', 'smart_markov_predict', 'anomaly_detection_predict', 'trend_predict']
        for s in strats:
             try:
                 res = getattr(engine, s)(history, rules)
                 for n in res.get('numbers', []):
                     prediction_map[n] += res.get('confidence', 0.5)
             except: continue
        
        ai_m = [n for n, s in sorted(prediction_map.items(), key=lambda x: -x[1])[:6]]
        from models.unified_predictor import predict_special_number
        ai_s = predict_special_number(history, rules, ai_m)
        
        ai_match = calculate_matches(ai_m, actual_m)
        ai_s_hit = (ai_s == actual_s)
        
        if ai_s_hit: ai_1bet_specials += 1
        if ai_match >= 3: ai_1bet_m3plus += 1
        if ai_s_hit or ai_match >= 3: ai_1bet_union += 1
        
        if (idx + 1) % 100 == 0:
            print(f"  Progress: {idx+1}/{test_periods}")

    print("\n" + "=" * 60)
    print(f"🏆 AUDIT RESULTS (1-BET COMPARISON)")
    print("-" * 60)
    print(f"Metric         | Random Baseline | AI Model | Edge")
    print("-" * 60)
    
    r_m3_rate = (random_1bet_m3plus / test_periods) * 100
    ai_m3_rate = (ai_1bet_m3plus / test_periods) * 100
    
    r_spec_rate = (random_1bet_specials / test_periods) * 100
    ai_spec_rate = (ai_1bet_specials / test_periods) * 100
    
    r_union = (random_1bet_union / test_periods) * 100
    ai_union = (ai_1bet_union / test_periods) * 100
    
    print(f"M3+ Hit Rate   | {r_m3_rate:14.2f}% | {ai_m3_rate:8.2f}% | {ai_m3_rate - r_m3_rate:+6.2f}%")
    print(f"Special Hit %  | {r_spec_rate:14.2f}% | {ai_spec_rate:8.2f}% | {ai_spec_rate - r_spec_rate:+6.2f}%")
    print(f"Prize (Any)    | {r_union:14.2f}% | {ai_union:8.2f}% | {ai_union - r_union:+6.2f}%")
    print("-" * 60)

if __name__ == "__main__":
    audit()
