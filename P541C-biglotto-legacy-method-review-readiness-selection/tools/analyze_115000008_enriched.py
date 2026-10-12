#!/usr/bin/env python3
"""
Enriched Analysis for Power Lotto 115000008
===========================================
Runs GNN and Zonal Entropy models specifically for the targets of 115000008.
"""
import os
import sys
import torch

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.models.gnn_predictor import GNNLotteryPredictor
from tools.predict_power_zonal_entropy import entropy_predict

def main():
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws('POWER_LOTTO')
    
    print("\n" + "="*80)
    print("🚀 ADVANCED MODEL EVALUATION (115000008)")
    print("="*80)
    
    # 1. GNN Training & Prediction
    print("\n[Method 1: GNN Attention Model]")
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    predictor = GNNLotteryPredictor(device=device)
    
    # Train heavily on recent 500
    predictor.train_model(history, epochs=50) 
    
    gnn_res = predictor.predict(history, {'pickCount': 6})
    print(f"🎯 GNN Numbers: {gnn_res['numbers']}")
    
    # 2. Zonal Entropy Prediction
    print("\n[Method 2: Standalone Zonal Entropy]")
    entropy_bets = entropy_predict(history, n_bets=2)
    for i, bet in enumerate(entropy_bets):
        print(f"🎯 Entropy Bet {i+1}: {bet}")
        
    print("\n" + "="*80)
    print("Winning Targets: [3, 8, 12, 26, 32, 38]")
    print("="*80)

if __name__ == "__main__":
    main()
