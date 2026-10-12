#!/usr/bin/env python3
"""
Phase 65: GBM Stacker v2 Verification Backtest
Tests the Meta-Ensemble 2.0 against historical Power Lotto draws.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import logging
import sqlite3
from typing import List, Dict
from collections import Counter
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

from lottery_api.models.meta_stacking_2b import GBMStacker
from lottery_api.models.zone_cluster import ZoneClusterRefiner
from lottery_api.models.fourier_rhythm import FourierRhythmPredictor


def load_power_lotto_history(max_records: int = 2000) -> List[Dict]:
    """Load Power Lotto historical data from SQLite database"""
    db_path = 'lottery_api/data/lottery_v2.db'
    if not os.path.exists(db_path):
        db_path = 'lottery_api/data/lottery.db'
    
    if not os.path.exists(db_path):
        logger.error(f"❌ Database file not found")
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT draw, numbers, special, date 
        FROM draws 
        WHERE lottery_type = 'POWER_LOTTO' 
        ORDER BY draw DESC 
        LIMIT ?
    """, (max_records,))
    
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        draw_number, numbers_str, special, draw_date = row
        if isinstance(numbers_str, str):
            try:
                numbers = json.loads(numbers_str)
            except:
                numbers = []
        else:
            numbers = []
        
        history.append({
            'drawNumber': draw_number,
            'numbers': numbers,
            'special': special,
            'drawDate': draw_date
        })
    
    return history


def get_sub_model_scores(history: List[Dict], max_num: int = 38) -> Dict[str, Dict[int, float]]:
    """Get predictions from sub-models"""
    scores = {}
    
    # 1. Fourier Rhythm
    try:
        fourier = FourierRhythmPredictor()
        scores['fourier'] = fourier.predict_main_numbers(history, max_num)
    except:
        scores['fourier'] = {n: 0.5 for n in range(1, max_num + 1)}
    
    # 2. Simple Frequency (Last 30 draws)
    freq_counter = Counter()
    for d in history[:30]:
        for n in d.get('numbers', []):
            freq_counter[n] += 1
    total = sum(freq_counter.values()) or 1
    scores['frequency'] = {n: freq_counter.get(n, 0) / total * 5 for n in range(1, max_num + 1)}
    
    # 3. Gap Pressure
    last_seen = {n: 999 for n in range(1, max_num + 1)}
    for i, d in enumerate(history):
        for n in d.get('numbers', []):
            if last_seen[n] == 999:
                last_seen[n] = i
    max_gap = max(last_seen.values()) or 1
    scores['gap'] = {n: last_seen[n] / max_gap for n in range(1, max_num + 1)}
    
    # 4. Long-term Bias
    bias_counter = Counter()
    for d in history[:500]:
        for n in d.get('numbers', []):
            bias_counter[n] += 1
    bias_total = sum(bias_counter.values()) or 1
    scores['bias'] = {n: bias_counter.get(n, 0) / bias_total * 5 for n in range(1, max_num + 1)}
    
    return scores


def get_zonal_features(history: List[Dict], max_num: int = 38):
    """Get Zonal Momentum and Entropy"""
    refiner = ZoneClusterRefiner({'maxNumber': max_num})
    momentum = refiner.analyze_momentum(history)
    entropy = refiner.calculate_zonal_entropy(history)
    return momentum, entropy


def run_backtest(periods: int = 500, num_bets: int = 2):
    """Run backtest using GBM Stacker v2"""
    logger.info(f"🚀 Starting GBM Stacker v2 Backtest: {periods} periods, {num_bets}-bet")
    
    # Load history
    history = load_power_lotto_history(periods + 500)
    if len(history) < periods + 100:
        logger.error("❌ Insufficient historical data")
        return
    
    logger.info(f"📂 Loaded {len(history)} draws")
    
    # Load trained stacker
    stacker = GBMStacker()
    if stacker.model is None:
        logger.error("❌ GBM Stacker model not trained")
        return
    
    # Backtest loop
    total_hits = 0
    total_cost = 0
    total_prize = 0
    m3_plus_hits = 0
    
    start_time = time.time()
    
    for i in range(periods):
        # Context: draws AFTER this one (older)
        context = history[i + 1:]
        
        # Actual winning numbers
        actual = set(history[i].get('numbers', []))
        actual_special = history[i].get('special')
        
        if len(actual) < 6 or len(context) < 50:
            continue
        
        # Get sub-model scores
        sub_scores = get_sub_model_scores(context)
        
        # Get zonal features
        z_mom, z_ent = get_zonal_features(context)
        
        # Predict using GBM Stacker
        refined_scores = stacker.predict_scores(sub_scores, z_mom, z_ent, 'CHAOS', 38)
        
        # Generate bets (top 6 numbers for each bet, with diversification)
        sorted_nums = sorted(refined_scores.keys(), key=lambda x: -refined_scores[x])
        
        bets = []
        for bet_idx in range(num_bets):
            # Diversify bets by picking from different score ranges
            start_idx = bet_idx * 3
            bet_nums = sorted(sorted_nums[start_idx:start_idx + 6])
            if len(bet_nums) == 6:
                bets.append(bet_nums)
        
        # Evaluate bets
        for bet_nums in bets:
            total_cost += 100
            hits = len(set(bet_nums) & actual)
            
            # Simple prize calculation
            if hits >= 3:
                m3_plus_hits += 1
                if hits == 3:
                    total_prize += 100
                elif hits == 4:
                    total_prize += 800
                elif hits == 5:
                    total_prize += 20000
                elif hits == 6:
                    total_prize += 500000
        
        if (i + 1) % 100 == 0:
            elapsed = time.time() - start_time
            hit_rate = (m3_plus_hits / ((i + 1) * num_bets)) * 100 if i > 0 else 0
            roi = (total_prize / total_cost * 100) if total_cost > 0 else 0
            logger.info(f"Progress: {i+1}/{periods} | M3+: {hit_rate:.2f}% | ROI: {roi:.2f}% | Elapsed: {elapsed:.1f}s")
    
    # Final results
    final_hit_rate = (m3_plus_hits / (periods * num_bets)) * 100
    final_roi = (total_prize / total_cost * 100) if total_cost > 0 else 0
    
    logger.info("=" * 70)
    logger.info("📊 FINAL GBM STACKER V2 BACKTEST REPORT")
    logger.info("-" * 70)
    logger.info(f"🎯 M3+ Hit Rate: {final_hit_rate:.2f}%  (Baseline: 7.59%)")
    logger.info(f"💰 Total Cost:  {total_cost:,} TWD")
    logger.info(f"🏆 Total Prize: {total_prize:,} TWD")
    logger.info(f"📈 Overall ROI: {final_roi:.2f}%")
    logger.info(f"✨ Edge vs Baseline: {final_hit_rate - 7.59:.2f}%")
    logger.info("=" * 70)
    
    return {
        'hit_rate': final_hit_rate,
        'roi': final_roi,
        'm3_plus_hits': m3_plus_hits,
        'total_cost': total_cost,
        'total_prize': total_prize
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('periods', type=int, nargs='?', default=500, help='Number of periods')
    parser.add_argument('bets', type=int, nargs='?', default=2, help='Number of bets per draw')
    args = parser.parse_args()
    
    run_backtest(args.periods, args.bets)
