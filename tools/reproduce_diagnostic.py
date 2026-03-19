import os
import sys
import numpy as np
import json
import random

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from tools.biglotto_diversified_ensemble import DiversifiedEnsemble

def diagnostic():
    seed = 123
    random.seed(seed)
    np.random.seed(seed)
    
    db = DatabaseManager(os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    ensemble = DiversifiedEnsemble(seed=seed)
    
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: str(x.get('date', '')))
    
    n_periods = 150
    start_idx = len(all_draws) - n_periods
    
    print(f"DEBUG: Total Draws: {len(all_draws)}")
    print(f"DEBUG: Backtest Start Index: {start_idx}")
    print(f"DEBUG: First Draw Date: {all_draws[start_idx]['date']}")
    print(f"DEBUG: Last Draw Date: {all_draws[-1]['date']}")
    
    # Test first prediction
    history_before = all_draws[:start_idx]
    bets = ensemble.predict_3bets(history=history_before)
    actual_nums = json.loads(all_draws[start_idx]['numbers']) if isinstance(all_draws[start_idx]['numbers'], str) else all_draws[start_idx]['numbers']
    
    print(f"DEBUG: First Prediction Bets: {bets}")
    print(f"DEBUG: First Draw Result: {actual_nums}")

if __name__ == '__main__':
    diagnostic()
