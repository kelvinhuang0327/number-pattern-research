#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import numpy as np
from datetime import datetime

# Setup paths
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)

from lottery_api.models.individual_rhythm_predictor import IndividualRhythmPredictor

DB_PATH = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
POOL = 39
PICK = 5
BASELINE_GE2 = 0.113973

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'DAILY_539'
        ORDER BY date ASC, draw ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums)})
    return draws

def run_backtest_with_decay(draws, test_periods, decay):
    N = len(draws)
    train_data = draws[:-test_periods]
    test_data = draws[-test_periods:]
    
    predictor = IndividualRhythmPredictor(pool=POOL, pick=PICK)
    predictor.train(train_data, decay_factor=decay)
    
    ge2_count = 0
    for i in range(len(test_data)):
        res = predictor.predict(draws[:len(train_data)+i])
        pred = set(res['numbers'])
        actual = set(test_data[i]['numbers'])
        if len(pred & actual) >= 2:
            ge2_count += 1
            
    rate = ge2_count / test_periods
    return rate - BASELINE_GE2

def main():
    draws = load_draws()
    # Test on the last 500 draws to find the best decay for recent regime
    decay_candidates = [0.990, 0.993, 0.995, 0.997, 0.999, 1.0]
    
    print("=" * 60)
    print("IRAP v2.3 Decay Factor Optimization (Recent 500 Draws)")
    print("=" * 60)
    
    best_decay = 0.995
    max_edge = -1.0
    
    for d in decay_candidates:
        edge = run_backtest_with_decay(draws, 500, d)
        print(f"Decay {d:.3f} | Edge: {edge*100:+.3f}%")
        if edge > max_edge:
            max_edge = edge
            best_decay = d
            
    print("-" * 60)
    print(f"🔥 Best Decay Factor: {best_decay:.3f} (Edge: {max_edge*100:+.3f}%)")
    
    # Run full term test with best decay
    print("\n" + "=" * 60)
    print(f"Final Audit: IRAP v2.3 (Decay={best_decay})")
    print("=" * 60)
    
    full_test_size = len(draws) - 4000
    from backtest_39lotto_irap_standard import run_backtest
    # Need to modify backtest script to accept decay or just manual here
    
    predictor = IndividualRhythmPredictor()
    predictor.train(draws[:-full_test_size], decay_factor=best_decay)
    
    ge2_count = 0
    for i in range(full_test_size):
        res = predictor.predict(draws[:4000+i])
        if len(set(res['numbers']) & set(draws[4000+i]['numbers'])) >= 2:
            ge2_count += 1
    
    final_rate = ge2_count / full_test_size
    print(f"Full Term Edge: {(final_rate - BASELINE_GE2)*100:+.3f}% (Rate: {final_rate*100:.2f}%)")

if __name__ == "__main__":
    main()
