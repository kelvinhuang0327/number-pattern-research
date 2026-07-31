#!/usr/bin/env python3
"""
Phase 65: Training Script for GBM Stacker v2
Generates training data from historical draws and trains the Meta-Learner.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import logging
from typing import List, Dict, Tuple
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

from lottery_api.models.meta_stacking_2b import GBMStacker
from lottery_api.models.zone_cluster import ZoneClusterRefiner
from lottery_api.models.regime_detector import RegimeDetector
from lottery_api.models.fourier_rhythm import FourierRhythmPredictor


def load_power_lotto_history(max_records: int = 2000) -> List[Dict]:
    """Load Power Lotto historical data from SQLite database"""
    import sqlite3
    
    db_path = 'lottery_api/data/lottery_v2.db'
    if not os.path.exists(db_path):
        db_path = 'lottery_api/data/lottery.db'
    
    if not os.path.exists(db_path):
        logger.error(f"❌ Database file not found")
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Query Power Lotto draws (lottery_type = 'POWER_LOTTO')
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
        # Parse numbers string (format: "[1, 24, 29, 31, 33, 38]")
        if isinstance(numbers_str, str):
            try:
                numbers = json.loads(numbers_str)
            except:
                # Fallback: try comma-separated
                numbers = [int(n.strip()) for n in numbers_str.split(',') if n.strip().isdigit()]
        else:
            numbers = []
        
        history.append({
            'drawNumber': draw_number,
            'numbers': numbers,
            'special': special,
            'drawDate': draw_date
        })
    
    logger.info(f"📂 Loaded {len(history)} draws from {db_path}")
    return history


def get_sub_model_scores(history: List[Dict], max_num: int = 38) -> Dict[str, Dict[int, float]]:
    """
    Get predictions from multiple sub-models for the NEXT draw.
    Uses the history up to (but not including) the current draw.
    """
    scores = {}
    
    # 1. Fourier Rhythm
    try:
        fourier = FourierRhythmPredictor()
        fourier_scores = fourier.predict_main_numbers(history, max_num)
        scores['fourier'] = fourier_scores
    except Exception as e:
        logger.warning(f"Fourier failed: {e}")
        scores['fourier'] = {n: 0.5 for n in range(1, max_num + 1)}
    
    # 2. Simple Frequency (Last 30 draws)
    freq_counter = Counter()
    for d in history[:30]:
        for n in d.get('numbers', []):
            freq_counter[n] += 1
    total = sum(freq_counter.values()) or 1
    scores['frequency'] = {n: freq_counter.get(n, 0) / total * 5 for n in range(1, max_num + 1)}
    
    # 3. Gap Pressure (Inverse of recency)
    last_seen = {n: 999 for n in range(1, max_num + 1)}
    for i, d in enumerate(history):
        for n in d.get('numbers', []):
            if last_seen[n] == 999:
                last_seen[n] = i
    max_gap = max(last_seen.values()) or 1
    scores['gap'] = {n: last_seen[n] / max_gap for n in range(1, max_num + 1)}
    
    # 4. Long-term Bias (Last 500 draws)
    bias_counter = Counter()
    for d in history[:500]:
        for n in d.get('numbers', []):
            bias_counter[n] += 1
    bias_total = sum(bias_counter.values()) or 1
    scores['bias'] = {n: bias_counter.get(n, 0) / bias_total * 5 for n in range(1, max_num + 1)}
    
    return scores


def get_zonal_features(history: List[Dict], max_num: int = 38) -> Tuple[Dict[int, float], Dict[int, float]]:
    """Get Zonal Momentum and Entropy from Phase 62 logic"""
    refiner = ZoneClusterRefiner({'maxNumber': max_num})
    momentum = refiner.analyze_momentum(history)
    entropy = refiner.calculate_zonal_entropy(history)
    return momentum, entropy


def get_regime(history: List[Dict]) -> str:
    """Detect current regime"""
    try:
        detector = RegimeDetector()
        result = detector.detect_regime(history)
        # Handle dict or string return
        if isinstance(result, dict):
            return result.get('regime', 'CHAOS')
        return str(result) if result else 'CHAOS'
    except Exception:
        return 'CHAOS'


def generate_training_data(history: List[Dict], 
                          train_start: int = 100, 
                          max_num: int = 38) -> List[Tuple]:
    """
    Generate training data from historical draws.
    For each draw i, use history[i+1:] as context to predict draw i.
    """
    training_data = []
    
    for i in range(train_start, len(history) - 1):
        # Context: draws AFTER this one (older in time)
        context = history[i + 1:]
        
        # Actual winning numbers for draw i
        actual_numbers = history[i].get('numbers', [])
        
        if len(context) < 50 or len(actual_numbers) < 6:
            continue
        
        # Get sub-model scores
        sub_scores = get_sub_model_scores(context, max_num)
        
        # Get zonal features
        z_mom, z_ent = get_zonal_features(context, max_num)
        
        # Get regime
        regime = get_regime(context)
        
        training_data.append((
            sub_scores,
            z_mom,
            z_ent,
            regime,
            actual_numbers,
            max_num
        ))
        
        if (i - train_start + 1) % 100 == 0:
            logger.info(f"📊 Generated {i - train_start + 1} training samples...")
    
    return training_data


def main():
    logger.info("🚀 Starting GBM Stacker v2 Training")
    
    # Load history
    history = load_power_lotto_history(2500)
    if len(history) < 500:
        logger.error("❌ Insufficient historical data for training")
        return
    
    # Generate training data
    logger.info("📈 Generating training data from historical draws...")
    train_data = generate_training_data(history, train_start=100)
    logger.info(f"✅ Generated {len(train_data)} training samples")
    
    if len(train_data) < 100:
        logger.error("❌ Insufficient training samples")
        return
    
    # Train the stacker
    stacker = GBMStacker()
    stacker.train(train_data)
    
    # Show feature importance
    importance = stacker.get_feature_importance()
    logger.info("📊 Feature Importance:")
    for name, imp in sorted(importance.items(), key=lambda x: -x[1])[:10]:
        logger.info(f"   {name}: {imp:.4f}")
    
    logger.info("🎯 Training complete!")


if __name__ == '__main__':
    main()
