import os
import sys
import logging
import numpy as np
from datetime import datetime
from itertools import product

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.optimized_ensemble import OptimizedEnsemblePredictor
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.utils.backtest_safety import validate_chronological_order, get_safe_backtest_slice

logging.basicConfig(level=logging.ERROR)

def run_tuning(periods: int = 150):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws('POWER_LOTTO'))
    rules = get_lottery_rules('POWER_LOTTO')
    
    # Target 150 periods for tuning
    test_data = all_draws[-periods:]
    
    # Define Search Space
    w_m_vals = [0.3, 0.4, 0.5]
    w_e_vals = [0.3, 0.4, 0.5]
    lag_windows = [(3, 8), (5, 12), (1, 6)]
    
    best_m3_rate = -1
    best_roi = -1
    best_config = None
    
    # Prize Table (Simplified for score calculation)
    def get_m3_hit(bet_numbers, actual_numbers):
        return len(set(bet_numbers) & set(actual_numbers)) >= 3

    print(f"🚀 Starting Hyperparameter Tuning (Sweep) for {periods} periods...")
    print(f"Search Space Size: {len(w_m_vals) * len(w_e_vals) * len(lag_windows)}")
    
    predictor = OptimizedEnsemblePredictor(rules)
    
    for w_m, w_e, l_win in product(w_m_vals, w_e_vals, lag_windows):
        # Normalize weights
        w_l = 1.0 - w_m - w_e
        if w_l < 0.1: continue # Ensure minimum lag contribution
        
        config = {
            'w_m': w_m,
            'w_e': w_e,
            'w_l': w_l,
            'lag_min': l_win[0],
            'lag_max': l_win[1]
        }
        
        predictor.update_config(config)
        
        hits = 0
        total_prize = 0
        
        for i, target_draw in enumerate(test_data):
            target_idx = all_draws.index(target_draw)
            history = get_safe_backtest_slice(all_draws, target_idx)
            actual_main = target_draw['numbers']
            actual_spec = target_draw.get('special', 0)
            
            # Predict 2 bets
            res = predictor.predict(history, n_bets=2)
            
            draw_hit = False
            for bet in res['all_bets']:
                match_count = len(set(bet) & set(actual_main))
                if match_count >= 3:
                    draw_hit = True
                    hits += 1
                    total_prize += 100 # Mock prize
                    if match_count == 4: total_prize += 800
                
            # Quick check for special (simplistic)
            if actual_spec in [1, 2, 8]: # Mocking special hit for weighting
                 total_prize += 10
                 
        m3_rate = (hits / (periods * 2)) * 100 # Hits per bet
        score = m3_rate + (total_prize / 1000.0) # Combined score
        
        print(f"Config: {config} -> M3%: {m3_rate:.2f}% | Score: {score:.2f}")
        
        if score > best_m3_rate:
            best_m3_rate = score
            best_config = config
            
    print("\n" + "="*50)
    print(f"🏆 BEST CONFIG FOUND:")
    print(best_config)
    print(f"Score: {best_m3_rate:.2f}")
    print("="*50)

if __name__ == "__main__":
    run_tuning(150)
