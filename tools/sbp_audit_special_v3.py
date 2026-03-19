#!/usr/bin/env python3
"""
Standardized Backtest Protocol (SBP) - Phase 72
Priority 1 Audit: Power Lotto Special Number V3
Claim: 14.70% (vs 12.50% baseline), Edge +2.20% over 1000 periods.
"""

import os
import sys
import json
import sqlite3
import random
import numpy as np
import logging
from collections import Counter
from scipy.stats import binomtest

# Standardized Seed
random.seed(42)
np.random.seed(42)

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.special_predictor import PowerLottoSpecialPredictor
from lottery_api.common import get_lottery_rules

logging.basicConfig(level=logging.ERROR)

def load_power_lotto_history(max_records=1500):
    db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, numbers, special, date FROM draws 
        WHERE lottery_type = 'POWER_LOTTO' 
        ORDER BY draw DESC LIMIT ?
    """, (max_records,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        nums = json.loads(r[1]) if isinstance(r[1], str) else []
        special = r[2]
        if len(nums) == 6 and special is not None:
            history.append({
                'draw': r[0], 
                'numbers': nums, 
                'special': int(special), 
                'date': r[3]
            })
    return history

def run_sbp_audit(periods=1000):
    print("=" * 70)
    print(f"📊 SBP AUDIT: Power Lotto Special V3 (1-bet)")
    print(f"   Periods: {periods} | Seed: 42")
    print("=" * 70)
    
    # 1. Load Data
    all_draws = load_power_lotto_history(periods + 500)
    if len(all_draws) < periods + 100:
        print(f"❌ Error: Not enough data ({len(all_draws)} records).")
        return

    rules = get_lottery_rules('POWER_LOTTO')
    predictor = PowerLottoSpecialPredictor(rules)
    baseline = 0.125 # 1/8
    
    hits = 0
    total = 0
    
    # Audit Loop (Walk-Forward)
    for i in range(periods):
        # Time-split: target is current draw i, history is i+1 onwards
        context = all_draws[i+1:]
        target_special = all_draws[i]['special']
        
        # Predict 1-bet (Top 1)
        # Using predict() which returns the top-1 special number
        try:
            pred_special = predictor.predict(context)
            if pred_special == target_special:
                hits += 1
            total += 1
        except Exception as e:
            # print(f"Error at period {i}: {e}")
            continue
            
        if (i+1) % 100 == 0:
            print(f"Progress: {i+1}/{periods}...")

    # Reporting
    rate = hits / total if total > 0 else 0
    edge = (rate - baseline) * 100
    p_value = binomtest(hits, total, baseline, alternative='greater').pvalue
    
    print("\n" + "=" * 70)
    print(f"{'Metric':<25} {'Value':<15}")
    print("-" * 70)
    print(f"{'Total Test Periods':<25} {total}")
    print(f"{'Actual Hits':<25} {hits}")
    print(f"{'Hit Rate':<25} {rate*100:6.2f}%")
    print(f"{'Baseline Rate':<25} {baseline*100:6.2f}%")
    print(f"{'Edge (Uplift)':<25} {edge:+6.2f}%")
    print(f"{'p-value (Significance)':<25} {p_value:.4f}")
    
    threshold_p = 0.05
    if p_value < threshold_p and edge > 1.0:
        print("\n✅ VERDICT: VALIDATED (Statistically Significant Edge)")
    elif p_value < threshold_p:
        print("\n⚠️ VERDICT: MARGINAL (Significant but low Edge)")
    else:
        print("\n❌ VERDICT: REJECTED (No significant edge over random baseline)")
    print("=" * 70)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--periods", type=int, default=1000)
    args = parser.parse_args()
    run_sbp_audit(args.periods)
