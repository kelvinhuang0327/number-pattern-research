#!/usr/bin/env python3
import os
import sys
import numpy as np

project_root = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew'
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.biglotto_zonal_pruning import zonal_pruned_predict, get_zone
from lottery_api.database import DatabaseManager

def solve_complementary_bet():
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    # Existing bets from the user's image
    existing_bets = [
        [5, 7, 11, 17, 19, 26],
        [15, 17, 20, 21, 26, 40],
        [22, 25, 35, 38, 41, 46],
        [11, 13, 18, 23, 33, 39],
        [2, 4, 33, 41, 46, 49],
        [1, 14, 20, 41, 45, 49]
    ]
    
    # Analyze Coverage
    all_used_nums = set()
    for b in existing_bets: all_used_nums.update(b)
    
    # Generate many Zonal candidates (n_bets=20)
    candidates = zonal_pruned_predict(history, n_bets=20, window=150)
    
    # Find a bet with the LEAST overlap with current bets but still follows Zonal rules
    best_bet = None
    min_overlap = 999
    
    # Also prioritize bets that cover "under-represented" zones if possible
    # (But Zonal rules are primary)
    
    for cand in candidates:
        if cand in existing_bets: continue
        overlap = len(set(cand).intersection(all_used_nums))
        if overlap < min_overlap:
            min_overlap = overlap
            best_bet = cand
            
    # Get Special
    from collections import Counter
    recent = history[-100:]
    special_freq = Counter([d['special'] for d in recent])
    # Pick a high-frequency special NOT already used if possible (user didn't provide specials, but we recommend one)
    top_special = special_freq.most_common(1)[0][0]
    
    print(f"RESULT_BET: {sorted(best_bet)}")
    print(f"RESULT_SPECIAL: {top_special}")
    print(f"RESULT_OVERLAP: {min_overlap}")
    print(f"RESULT_ZONES: {len(set(get_zone(n) for n in best_bet))}")

if __name__ == "__main__":
    solve_complementary_bet()
