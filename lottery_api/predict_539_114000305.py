#!/usr/bin/env python3
import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules

def main():
    lottery_type = 'DAILY_539'
    lottery_rules = get_lottery_rules(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    
    # Use W=100 as it was the best performing window in benchmark
    history = all_draws[:100]
    
    print("-" * 60)
    print(f"🔮 PREDICTING DAILY_539 DRAW 114000305 (Latest in DB: {all_draws[0]['draw']})")
    print(f"📊 Using Optimal Window size: 100 draws")
    print("-" * 60)
    
    # Method 1: Monte Carlo (Stable 2-match at W=100)
    mc_res = prediction_engine.monte_carlo_predict(history, lottery_rules)
    print(f"➜ [Monte Carlo Prediction]: {', '.join(map(lambda x: f'{x:02d}', mc_res['numbers']))}")
    
    # Method 2: Zone Balance (Stable 2-match at W=100)
    zb_res = prediction_engine.zone_balance_predict(history, lottery_rules)
    print(f"➜ [Zone Balance Prediction]: {', '.join(map(lambda x: f'{x:02d}', zb_res['numbers']))}")
    
    # Method 3: Hot-Cold Mixed (Stable 2-match at W=100)
    hc_res = prediction_engine.hot_cold_mix_predict(history, lottery_rules)
    print(f"➜ [Hot-Cold Mixed Prediction]: {', '.join(map(lambda x: f'{x:02d}', hc_res['numbers']))}")
    
    print("-" * 60)

if __name__ == '__main__':
    main()
