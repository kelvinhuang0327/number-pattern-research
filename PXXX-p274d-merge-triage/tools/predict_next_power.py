#!/usr/bin/env python3
import os
import sys
import json
import logging

# Setup paths
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.common import load_backend_history

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def predict_next():
    lottery_type = 'POWER_LOTTO'
    
    # Change CWD to lottery_api to ensure relative paths for database work correctly
    original_cwd = os.getcwd()
    os.chdir(os.path.join(project_root, 'lottery_api'))
    
    try:
        history, rules = load_backend_history(lottery_type)
        print(f"Loaded {len(history)} draws. Latest: {history[0]['draw']}")
        
        # history should be descending (already handled by load_backend_history usually, but verified in benchmark script)
        if int(history[0]['draw']) < int(history[-1]['draw']):
            history = list(reversed(history))
            
        engine = UnifiedPredictionEngine()
        optimizer = MultiBetOptimizer()
        
        # Generate 3 diversified bets using the validated Orthogonal strategy
        print("\n🔮 Generating Orthogonal 3-Bet Prediction for draw 115000012...")
        res = optimizer.generate_diversified_bets(history, rules, num_bets=3)
        
        print("\n============================================================")
        print(f"🎯 PREDICTION RESULTS: {lottery_type} (Next: 115000012)")
        print(f"Method: {res.get('method', 'Orthogonal Strategy')}")
        if res.get('is_extreme_alert'):
            print("⚠️ ALERT: Extreme Regime Transition Detected! Recovery Flow Boosted.")
        print("------------------------------------------------------------")
        
        for idx, bet in enumerate(res['bets']):
            nums_str = ", ".join([f"{n:02d}" for n in bet['numbers']])
            special = bet.get('special')
            if isinstance(special, list):
                special_val = special[0]
            else:
                special_val = special
            tag = bet.get('tag', f'Bet {idx+1}')
            print(f"[{tag}] Numbers: {nums_str} | Special (區二): {special_val if special_val is not None else '?'}")
            
        print("============================================================\n")
        
    finally:
        os.chdir(original_cwd)

if __name__ == "__main__":
    predict_next()
