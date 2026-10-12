import os
import sys
import logging
import numpy as np
from datetime import datetime
from itertools import product
import json

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.utils.backtest_safety import validate_chronological_order, get_safe_backtest_slice

logging.basicConfig(level=logging.ERROR)

PRIZE_TABLE = {
    (6, 1): 200000000,
    (6, 0): 20000000,
    (5, 1): 150000,
    (5, 0): 20000,
    (4, 1): 4000,
    (4, 0): 800,
    (3, 1): 400,
    (2, 1): 200,
    (3, 0): 100,
    (1, 1): 100
}

def calculate_prize(main_hits, special_hit):
    return PRIZE_TABLE.get((main_hits, special_hit), 0)

def run_roi_tuning(periods: int = 150):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws('POWER_LOTTO'))
    rules = get_lottery_rules('POWER_LOTTO')
    
    engine = UnifiedPredictionEngine()
    optimizer = MultiBetOptimizer()
    
    # Target periods for tuning (150 is a good trade-off between speed and signal)
    test_data = all_draws[-periods:]
    
    # ROI-Focused Search Space
    w_m_vals = [0.2, 0.4, 0.6]
    w_e_vals = [0.2, 0.4, 0.6]
    wobble_modes = [0.05, 0.1, 0.15] # Secondary bet spread
    
    best_roi = -1
    best_config = None
    results_log = []

    print(f"🚀 Starting ROI-Objective Tuning for {periods} periods...")
    print(f"Sweep Size: {len(w_m_vals) * len(w_e_vals) * len(wobble_modes)}")
    
    for w_m, w_e, wobble in product(w_m_vals, w_e_vals, wobble_modes):
        w_l = 1.0 - w_m - w_e
        if w_l < 0.1: continue
        
        meta_config = {
            'method': 'roi_stacking',
            'w_m': w_m,
            'w_e': w_e,
            'w_l': w_l,
            'wobble': wobble
        }
        
        total_cost = 0
        total_prize = 0
        hits_m3 = 0
        
        for i, target_draw in enumerate(test_data):
            target_idx = all_draws.index(target_draw)
            history = get_safe_backtest_slice(all_draws, target_idx)
            actual_main = set(target_draw['numbers'])
            actual_special = target_draw.get('special_number', target_draw.get('special', 0))
            
            # Prediction
            res = optimizer.generate_diversified_bets(history, rules, num_bets=2, meta_config=meta_config)
            
            total_cost += 200
            bet_specials = res.get('specials', [1, 1])
            
            for b_idx, bet in enumerate(res['bets']):
                nums = set(bet['numbers'])
                main_hits = len(nums & actual_main)
                spec_matched = 1 if (bet_specials[b_idx] == actual_special) else 0
                
                prize = calculate_prize(main_hits, spec_matched)
                total_prize += prize
                if main_hits >= 3: hits_m3 += 1

        roi = (total_prize / total_cost) * 100
        hit_rate = (hits_m3 / (periods * 2)) * 100
        
        print(f"Params: M={w_m}, E={w_e}, L={w_l:.1f}, W={wobble} -> ROI: {roi:.2f}% | Hit%: {hit_rate:.2f}%")
        
        results_log.append({
            'config': meta_config,
            'roi': roi,
            'hit_rate': hit_rate
        })
        
        if roi > best_roi:
            best_roi = roi
            best_config = meta_config
            
    print("\n" + "="*50)
    print(f"🏆 BEST ROI CONFIG FOUND:")
    print(json.dumps(best_config, indent=2))
    print(f"Max ROI: {best_roi:.2f}%")
    print("="*50)

if __name__ == "__main__":
    periods = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    run_roi_tuning(periods)
