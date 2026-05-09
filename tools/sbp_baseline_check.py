#!/usr/bin/env python3
"""
SBP Safety Check: Random Baseline
Ensures that 3 random bets achieve ~5.48% (theoretical M3+).
If this script returns >6%, the auditing logic is flawed.
"""

import os
import sys
import json
import sqlite3
import random
import numpy as np
from scipy.stats import binomtest

random.seed(42)
np.random.seed(42)

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"

def load_history(max_records=1500):
    db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT numbers FROM draws 
        WHERE lottery_type = 'BIG_LOTTO' 
        ORDER BY draw DESC LIMIT ?
    """, (max_records,))
    rows = cursor.fetchall()
    conn.close()
    return [{'numbers': json.loads(r[0])} for r in rows]

def run_baseline_check(periods=1000):
    all_history = load_history(periods + 50)
    baseline_3bet = 0.0548
    hits = 0
    total = 0
    
    for i in range(periods):
        target = set(all_history[i]['numbers'])
        # Generate 3 random bets
        bets = [random.sample(range(1, 50), 6) for _ in range(3)]
        
        is_win = False
        for bet in bets:
            if len(set(bet) & target) >= 3:
                is_win = True
                break
        if is_win:
            hits += 1
        total += 1

    rate = hits / total
    print(f"Random Baseline (3-bet M3+) over {periods}p: {rate*100:.2f}%")
    print(f"Theoretical Target: {baseline_3bet*100:.2f}%")

if __name__ == "__main__":
    run_baseline_check(1000)
    run_baseline_check(5000)
