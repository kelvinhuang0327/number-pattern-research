
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import logging
from datetime import datetime

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('V7Generator')

def generate_predictions(lottery_type: str):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    
    # Load Data
    history = db.get_all_draws(lottery_type)
    if not history:
        logger.error(f"No history found for {lottery_type}")
        return
        
    # Standard Rules
    rules = get_lottery_rules(lottery_type)
    
    # Initialize Optimizer
    optimizer = MultiBetOptimizer()
    
    # Generate 7 bets
    logger.info(f"🔮 Generating v7 Predictions for {lottery_type}...")
    result = optimizer.generate_diversified_bets(
        draws=history,
        lottery_rules=rules,
        num_bets=7
    )
    
    print(f"\n==================================================")
    print(f"🚀 v7 PREDICTIONS: {lottery_type}")
    print(f"==================================================")
    for i, bet in enumerate(result['bets']):
        print(f"Bet {i+1}: {bet['numbers']} (Source: {bet['source']})")
    print(f"==================================================\n")
    
    return result

if __name__ == "__main__":
    generate_predictions('BIG_LOTTO')
    generate_predictions('POWER_LOTTO')
