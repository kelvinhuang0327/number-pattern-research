import os
import sys
import numpy as np
import json
import random
import hashlib

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from tools.biglotto_diversified_ensemble import DiversifiedEnsemble

def get_md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def reconcile():
    print("--- ENVIRONMENT CHECK ---")
    files = [
        "tools/backtest_diversified_3bet.py",
        "tools/biglotto_diversified_ensemble.py",
        "lottery_api/models/advanced_strategies.py"
    ]
    for f in files:
        path = os.path.join(project_root, f)
        if os.path.exists(path):
            print(f"{f}: {get_md5(path)}")
        else:
            print(f"{f}: NOT FOUND")

    print("\n--- DATABASE CHECK ---")
    db = DatabaseManager(os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: str(x.get('date', '')).replace('/', '-'))
    print(f"Total BIG_LOTTO draws: {len(all_draws)}")
    if all_draws:
        print(f"Latest 3 draws: {[d['date'] for d in all_draws[-3:]]}")

    print("\n--- REPRODUCIBILITY TEST (Seed 123, 150 Periods) ---")
    seed = 123
    random.seed(seed)
    np.random.seed(seed)
    
    ensemble = DiversifiedEnsemble(seed=seed)
    n_periods = 150
    start_idx = len(all_draws) - n_periods
    
    # Check if slicing matches
    test_draw = all_draws[start_idx]
    print(f"Testing slice starting at: {test_draw['date']} (Draw numbers: {test_draw['numbers']})")
    
    # Run one prediction
    history_before = all_draws[:start_idx]
    # Check history count
    print(f"History count for first prediction: {len(history_before)}")
    
    bets = ensemble.predict_3bets(history=history_before)
    print(f"First Prediction Result: {bets}")

if __name__ == '__main__':
    reconcile()
