#!/usr/bin/env python3
"""
Standardized Backtest Protocol (SBP) - Phase 72
Big Lotto Triple Strike Audit (Standardized)
Goal: Resolve 7.3% vs 5.4% discrepancy.
"""

import os
import sys
import json
import sqlite3
import random
import numpy as np
import logging
from scipy.stats import binomtest

# Standardized Seed
random.seed(42)
np.random.seed(42)

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.biglotto_triple_strike import fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet
from lottery_api.common import get_lottery_rules

logging.basicConfig(level=logging.ERROR)

def load_history(max_records=1500):
    db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, numbers, date FROM draws 
        WHERE lottery_type = 'BIG_LOTTO' 
        ORDER BY draw DESC LIMIT ?
    """, (max_records,))
    rows = cursor.fetchall()
    conn.close()
    history = []
    for r in rows:
        nums = json.loads(r[1]) if isinstance(r[1], str) else []
        if len(nums) == 6:
            history.append({'draw': r[0], 'numbers': nums, 'date': r[2]})
    return history

def run_sbp_audit(periods=500):
    print("=" * 80)
    print(f"📊 SBP AUDIT: Big Lotto Triple Strike (3-bet)")
    print(f"   Periods: {periods} | Seed: 42")
    print("=" * 80)
    
    all_history = load_history(periods + 500)
    baseline_1bet = 0.018638
    baseline_3bet = 1 - (1 - baseline_1bet)**3 # ~5.48%
    
    hits = 0
    total = 0
    
    for i in range(periods):
        context = all_history[i+1:]
        target = set(all_history[i]['numbers'])
        
        # Triple Strike Logic
        try:
            h_asc = sorted(context, key=lambda x: x['draw'])
            b1 = fourier_rhythm_bet(h_asc)
            b2 = cold_numbers_bet(h_asc, exclude=set(b1))
            b3 = tail_balance_bet(h_asc, exclude=set(b1)|set(b2))
            bets = [b1, b2, b3]
            
            is_win = False
            for bet in bets:
                if len(set(bet) & target) >= 3:
                    is_win = True
                    break
            if is_win:
                hits += 1
            total += 1
        except Exception:
            continue
            
        if (i+1) % 100 == 0:
            print(f"Progress: {i+1}/{periods}...")

    # Reporting
    rate = hits / total if total > 0 else 0
    edge = (rate - baseline_3bet) * 100
    p_value = binomtest(hits, total, baseline_3bet, alternative='greater').pvalue
    
    print("\n" + "=" * 80)
    print(f"{'Metric':<25} {'Value':<15}")
    print("-" * 80)
    print(f"{'Total Test Periods':<25} {total}")
    print(f"{'Actual Hits':<25} {hits}")
    print(f"{'Hit Rate':<25} {rate*100:6.2f}%")
    print(f"{'Baseline Rate':<25} {baseline_3bet*100:6.2f}%")
    print(f"{'Edge (Uplift)':<25} {edge:+6.2f}%")
    print(f"{'p-value (Significance)':<25} {p_value:.4f}")
    print("=" * 80)

if __name__ == "__main__":
    run_sbp_audit(500)
    run_sbp_audit(1000)
