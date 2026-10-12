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
from models.optimized_ensemble import OptimizedEnsemblePredictor
from database import db_manager
from common import get_lottery_rules

logging.basicConfig(level=logging.ERROR)

def calculate_matches(predicted, actual):
    return len(set(predicted) & set(actual))

def main():
    lottery_type = 'POWER_LOTTO'
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    db_manager.db_path = db_path
    
    all_draws = sorted(db_manager.get_all_draws(lottery_type), key=lambda x: x['draw'])
    test_periods = 200 # Faster for verification
    test_draws = all_draws[-test_periods:]
    
    print(f"📊 DEFINITIVE TRUTH AUDIT (Blinded, {test_periods} Periods)")
    print("-" * 60)
    
    random.seed(42)
    np.random.seed(42)
    
    r_hits = 0
    ai_hits = 0
    
    engine = UnifiedPredictionEngine()
    rules = get_lottery_rules(lottery_type)
    
    # Use the same ensemble Claude likely verified
    weights = {
        'maml_predict': 0.12,
        'anomaly_detection_predict': 0.10,
        'sota_predict': 0.08,
        'dynamic_ensemble_predict': 0.12,
        'markov_v2_predict': 0.12,
        'statistical_predict': 0.10
    }
    
    for idx, target in enumerate(test_draws):
        actual_m = set(target['numbers'])
        
        # 1. Random Baseline (2-bet)
        r_hit = False
        for _ in range(2):
            if calculate_matches(random.sample(range(1, 39), 6), actual_m) >= 3:
                r_hit = True
        if r_hit: r_hits += 1
        
        # 2. AI Model (Blinded)
        target_pos = next(i for i, d in enumerate(all_draws) if d['draw'] == target['draw'])
        history = list(reversed(all_draws[:target_pos]))
        
        # Weighted Score Prediction
        scores = {n: 0.0 for n in range(1, 39)}
        for s, w in weights.items():
            try:
                res = getattr(engine, s)(history, rules)
                for n in res.get('numbers', []):
                    scores[n] += w * res.get('confidence', 0.5)
            except: pass
        
        # Top 12 (to represent 2 bets of 6 unique numbers)
        top_nums = [n for n, s in sorted(scores.items(), key=lambda x: -x[1])[:12]]
        
        ai_hit = False
        # Bet 1: Top 1-6
        if calculate_matches(top_nums[:6], actual_m) >= 3: ai_hit = True
        # Bet 2: Top 7-12
        if len(top_nums) >= 12 and calculate_matches(top_nums[6:12], actual_m) >= 3: ai_hit = True
        
        if ai_hit: ai_hits += 1
        
        if (idx + 1) % 50 == 0:
            print(f"  Progress: {idx+1}/{test_periods}")

    print("\n" + "=" * 60)
    print(f"🏆 FINAL VERDICT (M3+ Hit Rate)")
    print("-" * 60)
    r_rate = (r_hits / test_periods) * 100
    ai_rate = (ai_hits / test_periods) * 100
    print(f"Random Baseline (2-Bet) | {r_rate:6.2f}%")
    print(f"AI Model (2-Bet)        | {ai_rate:6.2f}%")
    print(f"Scientific Edge         | {ai_rate - r_rate:+6.2f}%")
    print("=" * 60)

if __name__ == "__main__":
    main()
