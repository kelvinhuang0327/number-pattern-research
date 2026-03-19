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

def comb(n, k):
    import math
    return math.comb(n, k)

def exact_baseline(min_hits):
    total = comb(POOL, PICK)
    p = 0.0
    for k in range(min_hits, PICK + 1):
        p += comb(PICK, k) * comb(POOL - PICK, PICK - k) / total
    return p

BASELINE_GE2 = exact_baseline(2) # 0.113973
BASELINE_GE3 = exact_baseline(3) # 0.010041

def run_backtest(draws, test_periods):
    """
    Backtest IRAP strategy
    TRAIN: Everything before test_periods
    TEST: Last test_periods
    """
    N = len(draws)
    train_data = draws[:-test_periods]
    test_data = draws[-test_periods:]
    
    predictor = IndividualRhythmPredictor(pool=POOL, pick=PICK)
    predictor.train(train_data)
    
    hits_list = []
    ge2_count = 0
    ge3_count = 0
    
    for i in range(len(test_data)):
        # Important: predictor uses FULL available history up to the test draw
        # But for IRAP, we use the PROFILE trained on train_data to see if it sustains
        res = predictor.predict(draws[:len(train_data)+i])
        pred = set(res['numbers'])
        actual = set(test_data[i]['numbers'])
        
        overlap = len(pred & actual)
        hits_list.append(overlap)
        if overlap >= 2: ge2_count += 1
        if overlap >= 3: ge3_count += 1
        
    rate_ge2 = ge2_count / test_periods
    rate_ge3 = ge3_count / test_periods
    
    return {
        'avg_hits': np.mean(hits_list),
        'ge2_rate': rate_ge2,
        'ge2_edge': rate_ge2 - BASELINE_GE2,
        'ge3_rate': rate_ge3,
        'ge3_edge': rate_ge3 - BASELINE_GE3,
        'test_count': test_periods
    }

def main():
    draws = load_draws()
    windows = [150, 500, 1500]
    
    print("=" * 80)
    print("IRAP 標準回測審計報告 (Standard Backtest Audit)")
    print(f"基準期數: {len(draws)} 期")
    print(f"基準 >=2 機率: {BASELINE_GE2*100:.4f}%")
    print(f"基準 >=3 機率: {BASELINE_GE3*100:.6f}%")
    print("=" * 80)
    print(f"{'窗口':<10} {'>=2 Rate':<12} {'>=2 Edge':<12} {'>=3 Edge':<12} {'Avg Hits':<10}")
    print("-" * 80)
    
    for w in windows:
        res = run_backtest(draws, w)
        print(f"{w:<10} {res['ge2_rate']*100:10.2f}% {res['ge2_edge']*100:+11.3f}% {res['ge3_edge']*100:+11.4f}% {res['avg_hits']:10.3f}")

    # Full Backtest (Testing from draw 4000 onwards)
    test_full = len(draws) - 4000
    if test_full > 0:
        res = run_backtest(draws, test_full)
        print("-" * 80)
        print(f"{'Full':<10} {res['ge2_rate']*100:10.2f}% {res['ge2_edge']*100:+11.3f}% {res['ge3_edge']*100:+11.4f}% {res['avg_hits']:10.3f}")

if __name__ == "__main__":
    main()
