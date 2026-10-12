import os
import sys
import logging
import numpy as np
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.unified_predictor import predict_special_number
from lottery_api.database import DatabaseManager

def run_special_backtest(periods=300):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws('POWER_LOTTO')))
    
    rules = {'name': 'POWER_LOTTO', 'hasSpecialNumber': True, 'specialMinNumber': 1, 'specialMaxNumber': 8}
    
    hits = 0
    total = 0
    
    print(f"🚀 Running Zone 2 (Special Number) Optimization Backtest: {periods} periods")
    
    for i in range(periods):
        target_idx = i
        target_draw = all_draws[target_idx]
        history = all_draws[target_idx+1 : target_idx+201]
        
        actual_special = target_draw.get('special')
        if not actual_special: continue
        
        # Predict
        predicted = predict_special_number(history, rules)
        
        if predicted == actual_special:
            hits += 1
        total += 1
        
        if (i+1) % 50 == 0:
            print(f"Progress: {i+1}/{periods} | Hit Rate: {(hits/total)*100:.2f}%")
            
    print("-" * 60)
    print(f"FINAL SPECIAL HIT RATE: {(hits/total)*100:.2f}%")
    print(f"Baseline: 12.50% (Random) | Pre-optimization targeted: ~15%")
    print("=" * 60)

if __name__ == "__main__":
    run_special_backtest(300)
