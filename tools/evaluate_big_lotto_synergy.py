#!/usr/bin/env python3
"""
Phase 69: Big Lotto Synergy-Driven Backtest
Prioritizes high-correlation companion pairs in bet generation.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import sqlite3
import numpy as np
from collections import Counter, defaultdict
from scipy.stats import binomtest
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

def load_big_lotto_history(max_records: int = 1500) -> List[Dict]:
    db_path = 'lottery_api/data/lottery_v2.db'
    if not os.path.exists(db_path):
        db_path = 'lottery_api/data/lottery.db'
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, numbers FROM draws 
        WHERE lottery_type = 'BIG_LOTTO' 
        ORDER BY draw DESC LIMIT ?
    """, (max_records,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        nums = json.loads(row[1]) if isinstance(row[1], str) else []
        if len(nums) == 6:
            history.append({'draw': row[0], 'numbers': nums})
    return history

def get_companion_scores(history: List[Dict], max_num: int = 49) -> Dict[tuple, float]:
    """Calculate Z-scores for all pairs in the given history."""
    pair_counts = Counter()
    total_draws = len(history)
    for d in history:
        nums = sorted(d['numbers'])
        for i in range(len(nums)):
            for j in range(i+1, len(nums)):
                pair_counts[(nums[i], nums[j])] += 1
    
    p_exp = (6*5) / (49*48)
    scores = {}
    for pair, count in pair_counts.items():
        # Z-score formula
        z = (count/total_draws - p_exp) / np.sqrt(p_exp * (1-p_exp) / total_draws)
        if z > 1.0: # Only keep positive correlations
            scores[pair] = z
    return scores

from lottery_api.models.fourier_rhythm import FourierRhythmPredictor
from lottery_api.models.zone_cluster import ZoneClusterRefiner

def run_fused_backtest(periods: int = 500, num_bets: int = 5):
    logger.info(f"🚀 Starting Big Lotto Fusion Backtest (Synergy + Fourier + Zonal): {periods} periods")
    
    all_history = load_big_lotto_history(periods + 500)
    if len(all_history) < periods + 300:
        logger.error("❌ Insufficient data")
        return

    fourier = FourierRhythmPredictor()
    refiner = ZoneClusterRefiner({'maxNumber': 49})
    baseline_1bet = 0.018638
    
    total_hits = 0
    total_bets = 0
    
    for i in range(periods):
        context = all_history[i+1:]
        actual = set(all_history[i]['numbers'])
        
        # 1. Base Score: Fourier + Zonal
        base_scores = fourier.predict_main_numbers(context, max_num=49)
        refined_base = refiner.refine(context, base_scores)
        top_base_nums = sorted(refined_base.keys(), key=lambda x: -refined_base[x])[:15]
        
        # 2. Synergy Score: Companion Z-scores
        pair_scores = get_companion_scores(context[:500])
        
        # 3. Generate bets by seeding with high-Z pairs and filling with top_base_nums
        sorted_pairs = sorted(pair_scores.keys(), key=lambda x: -pair_scores[x])
        
        generated_bets = []
        for pair in sorted_pairs[:12]:
            # Seed bet with synergy pair
            bet_set = set(pair)
            
            # Fill with top base nums
            for n in top_base_nums:
                if len(bet_set) >= 6: break
                bet_set.add(n)
            
            if len(bet_set) == 6:
                bet = sorted(list(bet_set))
                if bet not in generated_bets:
                    generated_bets.append(bet)
            
            if len(generated_bets) >= num_bets: break
            
        # 4. Evaluate
        for bet in generated_bets:
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
    print(f"📊 BIG LOTTO FUSION BACKTEST REPORT")
    print("="*60)
    print(f"🎯 M3+ Hit Rate: {observed*100:.2f}% (Baseline: {baseline_1bet*100:.2f}%)")
    print(f"✨ Edge: {edge:+.2f}%")
    print(f"📉 p-value: {p_value:.4f}")
    print(f"💰 Total Bets: {total_bets} | Hits: {total_hits}")
    print("-" * 60)
    
    if p_value < 0.05:
        print("結論: ✅ VALID - Fusion logic achieves statistical significance!")
    else:
        print("結論: ❌ REJECTED - No robust edge found.")
    print("="*60)

if __name__ == "__main__":
    run_fused_backtest(500, 5)
