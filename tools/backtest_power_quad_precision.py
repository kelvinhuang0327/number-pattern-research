#!/usr/bin/env python3
"""
威力彩 Power Quad Precision (4注) 回測工具
=======================================
隨機基準: 14.60% (M3+)
"""
import os
import sys
import numpy as np
from tqdm import tqdm

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lottery_api.database import DatabaseManager
from tools.predict_power_quad_precision import generate_power_quad_precision

def run_backtest(test_periods=1384):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    total = min(len(all_draws) - 500, test_periods)
    hits_count = 0
    baseline = 14.60 # Power Lotto 4-bet random baseline
    
    for i in tqdm(range(len(all_draws) - total, len(all_draws)), desc=f"Backtest {total}"):
        history = all_draws[:i]
        actual = set(all_draws[i]['numbers'])
        predict_bets = generate_power_quad_precision(history)
        
        is_hit = False
        for bet in predict_bets:
            if len(set(bet) & actual) >= 3:
                is_hit = True
                break
        if is_hit: hits_count += 1

    hit_rate = hits_count / total * 100
    edge = hit_rate - baseline
    print(f"  Result (N={total}): {hit_rate:.2f}% | Edge: {edge:+.2f}%")
    return edge

if __name__ == "__main__":
    print(f"📊 Running Power Quad Precision backtests...")
    run_backtest(150)
    run_backtest(500)
    run_backtest(1384)
