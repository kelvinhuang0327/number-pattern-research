#!/usr/bin/env python3
import sys
import os
import logging

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import create_optimized_ensemble_predictor
from common import get_lottery_rules

def main():
    lottery_type = 'BIG_LOTTO'
    lottery_rules = get_lottery_rules(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    
    print("-" * 50)
    print(f"🔮 PREDICTING DRAW 114000115 (Current DB Latest: {all_draws[0]['draw']})")
    print("-" * 50)
    
    # Configuration 1: Ensemble with W=200 (Stable Best Choice)
    print("\n[Strategy A] Ensemble Predictor (Window=200)")
    history_200 = all_draws[:200]
    ensemble = create_optimized_ensemble_predictor(prediction_engine)
    ens_result = ensemble.predict(history_200, lottery_rules)
    
    print(f"➜ Bet 1: {', '.join(map(lambda x: f'{x:02d}', ens_result['bet1']['numbers']))}")
    print(f"➜ Bet 2: {', '.join(map(lambda x: f'{x:02d}', ens_result['bet2']['numbers']))}")
    
    # Configuration 2: Frequency Analysis with W=100 (Highest Peak in Benchmark)
    print("\n[Strategy B] Frequency Analysis (Window=100)")
    history_100 = all_draws[:100]
    freq_result = prediction_engine.frequency_predict(history_100, lottery_rules)
    print(f"➜ Recommended: {', '.join(map(lambda x: f'{x:02d}', freq_result['numbers']))}")
    
    print("-" * 50)

if __name__ == '__main__':
    main()
