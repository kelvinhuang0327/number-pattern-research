#!/usr/bin/env python3
import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules

def main():
    lottery_type = 'POWER_LOTTO'
    lottery_rules = get_lottery_rules(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    history = all_draws[:500]
    
    print("-" * 65)
    print(f"🧪 VERIFYING MULTI-POOL PREDICTION FOR {lottery_type}")
    print("-" * 65)
    
    strategies = [
        ('Frequency', prediction_engine.frequency_predict),
        ('Trend', prediction_engine.trend_predict),
        ('Bayesian', prediction_engine.bayesian_predict),
        ('Deviation', prediction_engine.deviation_predict)
    ]
    
    for name, method in strategies:
        res = method(history, lottery_rules)
        print(f"➜ [{name:10s}] Special Prediction: {res.get('special', 'N/A')}")
    
    print("-" * 65)

if __name__ == '__main__':
    main()
