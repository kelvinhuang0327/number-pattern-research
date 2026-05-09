#!/usr/bin/env python3
"""
Phase 65: Strict Walk-Forward Validation for GBM Stacker v2
Ensures NO data leakage by training only on OLD data and testing on NEWER data.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import logging
import sqlite3
from typing import List, Dict, Tuple
from collections import Counter
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

from lottery_api.models.meta_stacking_2b import GBMStacker
from lottery_api.models.zone_cluster import ZoneClusterRefiner
from lottery_api.models.fourier_rhythm import FourierRhythmPredictor


def load_power_lotto_history(max_records: int = 2500) -> List[Dict]:
    """Load Power Lotto historical data from SQLite database"""
    db_path = 'lottery_api/data/lottery_v2.db'
    if not os.path.exists(db_path):
        db_path = 'lottery_api/data/lottery.db'
    
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


def train_fresh_stacker(history: List[Dict], train_start: int = 100, max_num: int = 38) -> GBMStacker:
    """Train a new GBM Stacker from scratch on given history"""
    training_data = []
    
    for i in range(train_start, len(history) - 1):
        context = history[i + 1:]
        actual_numbers = history[i].get('numbers', [])
        
        if len(context) < 50 or len(actual_numbers) < 6:
            continue
        
        sub_scores = get_sub_model_scores(context, max_num)
        z_mom, z_ent = get_zonal_features(context, max_num)
        
        training_data.append((
            sub_scores,
            z_mom,
            z_ent,
            'CHAOS',  # Simplified regime
            actual_numbers,
            max_num
        ))
    
    logger.info(f"   Training on {len(training_data)} samples...")
    stacker = GBMStacker(model_path=None)  # Don't load existing model
    stacker.train(training_data)
    return stacker


def run_walk_forward_validation(test_periods: int = 500, num_bets: int = 2):
    """
    Walk-Forward Validation:
    - Split: Train on OLD data (index 500+), Test on NEWER data (index 0-499)
    - This ensures the model NEVER sees the test data during training.
    """
    logger.info("=" * 70)
    logger.info("🔬 PHASE 65: STRICT WALK-FORWARD VALIDATION")
    logger.info("=" * 70)
    
    # Load all history
    all_history = load_power_lotto_history(2500)
    logger.info(f"📂 Loaded {len(all_history)} total draws")
    
    if len(all_history) < test_periods + 500:
        logger.error(f"❌ Insufficient data: need {test_periods + 500}, have {len(all_history)}")
        return
    
    # STRICT SPLIT:
    # - Test data: draws[0:test_periods] (NEWEST, never seen during training)
    # - Train data: draws[test_periods:] (OLDER, used for training)
    
    test_data = all_history[:test_periods]
    train_data = all_history[test_periods:]
    
    logger.info(f"📊 Split: Train on {len(train_data)} older draws, Test on {test_periods} newer draws")
    logger.info(f"   Train range: draw #{train_data[0]['drawNumber']} to #{train_data[-1]['drawNumber']}")
    logger.info(f"   Test range:  draw #{test_data[0]['drawNumber']} to #{test_data[-1]['drawNumber']}")
    
    # Train fresh model on OLD data only
    logger.info("🎓 Training fresh GBM Stacker on OLD data only...")
    stacker = train_fresh_stacker(train_data, train_start=50)
    
    # Test on NEWER data
    logger.info(f"🧪 Testing on {test_periods} UNSEEN draws...")
    
    total_cost = 0
    total_prize = 0
    m3_plus_hits = 0
    
    start_time = time.time()
    
    for i in range(test_periods):
        # Context: draws AFTER this one in test data + all train data
        context = test_data[i + 1:] if i < test_periods - 1 else []
        context = context + train_data  # Add older history for context
        
        # Actual winning numbers for test draw i
        actual = set(test_data[i].get('numbers', []))
        
        if len(actual) < 6 or len(context) < 50:
            continue
        
        # Get sub-model scores using context
        sub_scores = get_sub_model_scores(context)
        z_mom, z_ent = get_zonal_features(context)
        
        # Predict using trained stacker
        refined_scores = stacker.predict_scores(sub_scores, z_mom, z_ent, 'CHAOS', 38)
        
        # Generate bets
        sorted_nums = sorted(refined_scores.keys(), key=lambda x: -refined_scores[x])
        
        bets = []
        for bet_idx in range(num_bets):
            start_idx = bet_idx * 3
            bet_nums = sorted(sorted_nums[start_idx:start_idx + 6])
            if len(bet_nums) == 6:
                bets.append(bet_nums)
        
        # Evaluate
        for bet_nums in bets:
            total_cost += 100
            hits = len(set(bet_nums) & actual)
            
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
            logger.info(f"   Progress: {i+1}/{test_periods} | M3+: {hit_rate:.2f}% | ROI: {roi:.2f}% | Elapsed: {elapsed:.1f}s")
    
    # Final results
    final_hit_rate = (m3_plus_hits / (test_periods * num_bets)) * 100
    final_roi = (total_prize / total_cost * 100) if total_cost > 0 else 0
    edge = final_hit_rate - 7.59
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("📊 WALK-FORWARD VALIDATION FINAL REPORT")
    logger.info("=" * 70)
    logger.info(f"🎯 M3+ Hit Rate: {final_hit_rate:.2f}%  (Baseline: 7.59%)")
    logger.info(f"✨ Edge vs Baseline: {edge:+.2f}%")
    logger.info(f"💰 Total Cost:  {total_cost:,} TWD")
    logger.info(f"🏆 Total Prize: {total_prize:,} TWD")
    logger.info(f"📈 Overall ROI: {final_roi:.2f}%")
    logger.info("-" * 70)
    
    if edge > 1.0:
        logger.info(f"✅ VALIDATION PASSED: Model shows GENUINE Edge of {edge:.2f}%")
    elif edge > 0:
        logger.info(f"⚠️ MARGINAL: Model shows slight edge of {edge:.2f}%, not statistically significant")
    else:
        logger.info(f"❌ VALIDATION FAILED: Model shows NO edge ({edge:.2f}%), result was likely data leakage")
    
    logger.info("=" * 70)
    
    return {
        'hit_rate': final_hit_rate,
        'edge': edge,
        'roi': final_roi,
        'm3_plus_hits': m3_plus_hits,
        'total_cost': total_cost,
        'total_prize': total_prize
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('periods', type=int, nargs='?', default=500, help='Test periods')
    parser.add_argument('bets', type=int, nargs='?', default=2, help='Bets per draw')
    args = parser.parse_args()
    
    run_walk_forward_validation(args.periods, args.bets)
