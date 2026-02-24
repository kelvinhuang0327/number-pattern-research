#!/usr/bin/env python3
"""
Phase 69: Big Lotto (6/49) Advanced Backtest
Integrates Fourier Rhythm and Zonal Momentum for Big Lotto evaluation.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import sqlite3
import numpy as np
from collections import Counter
from scipy.stats import binomtest
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

from lottery_api.models.fourier_rhythm import FourierRhythmPredictor
from lottery_api.models.zone_cluster import ZoneClusterRefiner

def load_big_lotto_history(max_records: int = 1500) -> List[Dict]:
    db_path = 'lottery_api/data/lottery_v2.db'
    if not os.path.exists(db_path):
        db_path = 'lottery_api/data/lottery.db'
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT draw, numbers, special, date 
        FROM draws 
        WHERE lottery_type = 'BIG_LOTTO' 
        ORDER BY draw DESC 
        LIMIT ?
    """, (max_records,))
    
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        num_str = row[1]
        if isinstance(num_str, str):
            try:
                nums = json.loads(num_str)
            except:
                nums = []
        else:
            nums = []
        
        if len(nums) == 6:
            history.append({
                'draw': row[0],
                'numbers': nums,
                'special': row[2],
                'date': row[3]
            })
    return history

def run_evaluation(periods: int = 500, num_bets: int = 5):
    logger.info(f"🚀 Starting Big Lotto (6/49) Advanced Backtest: {periods} periods")
    
    history = load_big_lotto_history(periods + 500)
    logger.info(f"📂 Loaded {len(history)} valid draws")
    
    if len(history) < periods + 50:
        logger.error("❌ Insufficient data")
        return

    fourier = FourierRhythmPredictor()
    refiner = ZoneClusterRefiner({'maxNumber': 49})
    
    baseline_1bet = 0.018638 # M3+ for 6/49
    total_hits = 0
    total_bets = 0
    
    for i in range(periods):
        context = history[i+1:]
        actual = set(history[i]['numbers'])
        
        # 1. Fourier Main scores
        f_scores = fourier.predict_main_numbers(context, max_num=49)
        
        # 2. Zonal Momentum refactor
        refined_scores = refiner.refine(context, f_scores)
        
        # 3. Pick top numbers
        sorted_nums = sorted(refined_scores.keys(), key=lambda x: -refined_scores[x])
        
        # 4. Generate diversify bets
        for b in range(num_bets):
            start_off = b * 3 # Slight overlap but some diversity
            bet = sorted(sorted_nums[start_off:start_off+6])
            
            if len(bet) == 6:
                total_bets += 1
                hits = len(set(bet) & actual)
                if hits >= 3:
                    total_hits += 1
        
        if (i+1) % 100 == 0:
            logger.info(f"   Progress: {i+1}/{periods} | Hits: {total_hits}/{total_bets}")

    observed = total_hits / total_bets if total_bets > 0 else 0
    edge = (observed - baseline_1bet) * 100
    p_value = binomtest(total_hits, total_bets, baseline_1bet, alternative='greater').pvalue
    
    print("\n" + "="*60)
    print(f"📊 BIG LOTTO ADVANCED BACKTEST REPORT")
    print("="*60)
    print(f"🎯 M3+ Hit Rate: {observed*100:.2f}% (Baseline: {baseline_1bet*100:.2f}%)")
    print(f"✨ Edge: {edge:+.2f}%")
    print(f"📉 p-value: {p_value:.4f}")
    print(f"💰 Total Bets: {total_bets} | Hits: {total_hits}")
    print("-" * 60)
    
    if p_value < 0.05 and edge > 0.5:
        print("結論: ✅ VALID - Signs of predictive edge detected.")
    elif p_value < 0.1:
        print("結論: ⚠️ MARGINAL - Needs more data or refinement.")
    else:
        print("結論: ❌ REJECTED - No significant edge over random baseline.")
    print("="*60)

if __name__ == "__main__":
    run_evaluation(500, 5)
