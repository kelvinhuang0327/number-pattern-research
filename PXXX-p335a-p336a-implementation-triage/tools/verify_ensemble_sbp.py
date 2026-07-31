#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import random
import numpy as np
from collections import Counter
from typing import List, Dict

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

# Import existing methods
from tools.exhaustive_nbet_benchmark import (
    method_zone_balance, method_gap_pressure, method_random_baseline
)

def load_history(lottery_type: str, periods: int) -> List[Dict]:
    db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, numbers, special, date FROM draws 
        WHERE lottery_type = ? 
        ORDER BY draw DESC LIMIT ?
    """, (lottery_type, periods + 100))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        nums = json.loads(r[1]) if isinstance(r[1], str) else []
        history.append({'draw': r[0], 'numbers': nums, 'date': r[3]})
    return history

def run_sbp(periods: int = 500):
    lottery_type = "POWER_LOTTO"
    max_num = 38
    all_history = load_history(lottery_type, periods)
    
    # Baseline for 1-bet (M3+) - Theoretical
    baseline_1bet = 0.0387 
    # Baseline for 2-bet
    baseline_2bet = 1 - (1 - baseline_1bet)**2
    
    stats = {
        'Zone Balance': {'hits': 0, 'matches': []},
        'Gap Pressure': {'hits': 0, 'matches': []},
        'Ensemble (Any Win)': {'hits': 0},
        'Random 2-Bet': {'hits': 0}
    }
    
    for i in range(periods):
        context = all_history[i+1:]
        target = set(all_history[i]['numbers'])
        
        # Predictions
        pred_a = method_zone_balance(context, max_num)
        pred_b = method_gap_pressure(context, max_num)
        rand_a = method_random_baseline([], max_num)
        rand_b = method_random_baseline([], max_num)
        
        # Evaluate
        match_a = len(set(pred_a) & target)
        match_b = len(set(pred_b) & target)
        match_ra = len(set(rand_a) & target)
        match_rb = len(set(rand_b) & target)
        
        if match_a >= 3: stats['Zone Balance']['hits'] += 1
        if match_b >= 3: stats['Gap Pressure']['hits'] += 1
        if match_a >= 3 or match_b >= 3: stats['Ensemble (Any Win)']['hits'] += 1
        if match_ra >= 3 or match_rb >= 3: stats['Random 2-Bet']['hits'] += 1
        
        stats['Zone Balance']['matches'].append(match_a)
        stats['Gap Pressure']['matches'].append(match_b)

    print(f"--- SBP Results (500 Periods) ---")
    for name, data in stats.items():
        rate = data['hits'] / periods
        if name == 'Random 2-Bet':
            edge = 0
        elif name == 'Ensemble (Any Win)':
            edge = (rate - (stats['Random 2-Bet']['hits']/periods)) * 100
        else:
            edge = (rate - baseline_1bet) * 100
        
        print(f"{name:<20}: {data['hits']:>3} hits | {rate*100:>6.2f}% | Edge: {edge:>+6.2f}%")
        
    print(f"\nTheoretical Baseline (2-Bet): {baseline_2bet*100:.2f}%")

if __name__ == "__main__":
    run_sbp(500)
