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
from models.multi_bet_optimizer import multi_bet_optimizer
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
    
    print(f"🔬 BLINDED M3+ AUDIT: {test_periods} Periods, 2-Bets")
    print("-" * 60)
    
    random.seed(99) # Fixed seed for baseline reproducibility
    
    r_m3_hits = 0
    ai_m3_hits = 0
    
    rules = get_lottery_rules(lottery_type)
    
    for idx, target in enumerate(test_draws):
        actual_m = set(target['numbers'])
        
        # 1. Random Baseline (2 Bets)
        r_hit = False
        for _ in range(2):
            if calculate_matches(random.sample(range(1, 39), 6), actual_m) >= 3:
                r_hit = True
        if r_hit: r_m3_hits += 1
        
        # 2. AI Model (Blinded - history excluding current)
        target_pos = next(i for i, d in enumerate(all_draws) if d['draw'] == target['draw'])
        history = list(reversed(all_draws[:target_pos]))
        
        # Use MultiBetOptimizer (Power Dual Max logic)
        try:
            res = multi_bet_optimizer.generate_diversified_bets(
                history, rules, num_bets=2, 
                meta_config={'method': 'dual_max'}
            )
            ai_hit = False
            for bet in res['bets']:
                if calculate_matches(bet['numbers'], actual_m) >= 3:
                    ai_hit = True
            if ai_hit: ai_m3_hits += 1
        except: pass
        
        if (idx + 1) % 100 == 0:
            print(f"  Progress: {idx+1}/{test_periods}")

    print("\n" + "=" * 60)
    print(f"🏆 AUDIT RESULTS (M3+ MATCH 3+)")
    print("-" * 60)
    print(f"Random Baseline (2-Bet) | {(r_m3_hits/test_periods)*100:6.2f}%")
    print(f"AI Model (2-Bet)        | {(ai_m3_hits/test_periods)*100:6.2f}%")
    print(f"Truth Edge              | {(ai_m3_hits - r_m3_hits)/test_periods*100:+7.2f}%")
    print("=" * 60)

if __name__ == "__main__":
    audit()
