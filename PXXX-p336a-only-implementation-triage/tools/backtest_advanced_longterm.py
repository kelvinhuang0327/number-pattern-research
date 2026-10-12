#!/usr/bin/env python3
"""
Long-term Backtest (500 Periods) for Advanced Power Lotto Methods
"""
import os
import sys
import torch
import numpy as np

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.models.gnn_predictor import GNNLotteryPredictor
from tools.predict_power_zonal_entropy import entropy_predict
from lottery_api.common import get_lottery_rules

def run_backtest(all_draws, method_name, periods, rules):
    print(f"\n🔍 Backtesting {method_name} over {periods} periods...")
    match_3_plus = 0
    total = 0
    
    gnn_predictor = None
    if method_name == 'GNN':
        device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        gnn_predictor = GNNLotteryPredictor(device=device)
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        if method_name == 'GNN':
            if i % 20 == 0: # Retrain every 20 for 500p speed
                gnn_predictor.train_model(history, epochs=30)
            res = gnn_predictor.predict(history, rules)
            predicted = set(res['numbers'])
        else:
            res = entropy_predict(history, n_bets=1)
            predicted = set(res[0])
            
        if len(predicted & actual) >= 3:
            match_3_plus += 1
        total += 1
        
        if (i+1) % 50 == 0:
            print(f"   Progress: {i+1}/{periods}...")

    success_rate = (match_3_plus / total * 100) if total > 0 else 0
    return success_rate

def main():
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws('POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    for method in ['Zonal_Entropy', 'GNN']:
        sr = run_backtest(all_draws, method, 500, rules)
        print(f"✅ {method} (500p) Match-3+ Rate: {sr:.2f}%")

if __name__ == "__main__":
    main()
