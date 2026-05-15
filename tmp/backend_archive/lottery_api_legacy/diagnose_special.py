#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.getcwd())
from database import db_manager
from models.unified_predictor import predict_special_number
from common import get_lottery_rules

def main():
    lottery_type = 'POWER_LOTTO'
    target_special = 5
    lottery_rules = get_lottery_rules(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    
    print("-" * 60)
    print(f"🧪 DIAGNOSING SECTION 2 PREDICTOR (Target: {target_special})")
    print("-" * 60)
    
    windows = [100, 500, 1000]
    for w in windows:
        history = all_draws[:w]
        spec = predict_special_number(history, lottery_rules, strategy_name='statistical')
        print(f"W={w:4d} | Predicted Special: {spec}")
    
    print("-" * 60)

if __name__ == '__main__':
    main()
