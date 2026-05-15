#!/usr/bin/env python3
import sys
import os
import json

sys.path.insert(0, os.getcwd())
from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from common import get_lottery_rules

def calculate_match(predicted, target_nums):
    pred_set = set(predicted)
    target_set = set(target_nums)
    return len(pred_set.intersection(target_set))

def main():
    engine = UnifiedPredictionEngine()
    lottery_type = 'POWER_LOTTO'
    target_numbers = [8, 15, 16, 21, 29, 37]
    lottery_rules = get_lottery_rules(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    
    # Test W=1000 Statistical
    history = all_draws[:1000]
    
    print("-" * 60)
    print(f"🧪 TESTING STATISTICAL MODEL W=1000 (Target: {target_numbers})")
    print("-" * 60)
    
    # With Filter
    res_filtered = engine.statistical_predict(history, lottery_rules)
    match_filtered = calculate_match(res_filtered['numbers'], target_numbers)
    print(f"With Filter   | Numbers: {res_filtered['numbers']} | Matches: {match_filtered}")
    
    print("-" * 60)

if __name__ == '__main__':
    main()
