#!/usr/bin/env python3
import sys
import os
import json
import numpy as np
from collections import defaultdict
from datetime import datetime

# Add lottery_api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine

class CVAAPredictor:
    def __init__(self, lottery_rules):
        self.rules = lottery_rules
        self.pick_count = lottery_rules.get('pickCount', 5)
        self.min_num = lottery_rules.get('minNumber', 1)
        self.max_num = lottery_rules.get('maxNumber', 39)

    def predict(self, history):
        if len(history) < 10:
            return None
        
        # 1. Calculate Centroids
        centroids = []
        for draw in history:
            centroids.append(np.mean(draw['numbers']))
        
        # 2. Derive Physics
        velocities = np.diff(centroids)
        accelerations = np.diff(velocities)
        
        # Use last 5 draws for momentum
        v_next = np.mean(velocities[-5:])
        a_next = np.mean(accelerations[-3:]) if len(accelerations) > 3 else 0
        
        c_predicted = centroids[-1] + v_next + a_next
        c_predicted = max(self.min_num + 5, min(self.max_num - 5, c_predicted))
        
        # 3. Calculate target variance (spread)
        historic_stds = [np.std(draw['numbers']) for draw in history[-20:]]
        target_std = np.mean(historic_stds)
        
        # 4. Global statistics for individual weighting
        all_nums = [n for d in history[-100:] for n in d['numbers']]
        counts = defaultdict(int)
        for n in all_nums: counts[n] += 1
        
        # 5. Iterative Search for best combination
        # For speed in simulation, we'll use a semi-random approach to find a set near the centroid
        best_set = []
        min_diff = float('inf')
        
        # Try 500 samples
        for _ in range(500):
            # Sample weighted by frequency
            weights = np.array([counts.get(i, 1) for i in range(self.min_num, self.max_num + 1)])
            weights = weights / weights.sum()
            sample = np.random.choice(range(self.min_num, self.max_num + 1), size=self.pick_count, replace=False, p=weights)
            
            s_mean = np.mean(sample)
            s_std = np.std(sample)
            
            # Merit function: closeness to predicted centroid AND target spread
            diff = abs(s_mean - c_predicted) * 2.0 + abs(s_std - target_std) * 1.0
            
            if diff < min_diff:
                min_diff = diff
                best_set = sorted(sample.tolist())
        
        return {
            "numbers": [int(n) for n in best_set],
            "confidence": 0.65,
            "method": "CVAA (Centroid Velocity & Adaptive Acceleration)",
            "details": {"predicted_centroid": float(c_predicted), "target_std": float(target_std)}
        }

def run_backtest():
    db_path = os.path.join(os.path.dirname(__file__), 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = db.get_all_draws('DAILY_539')
    draws_2025 = [d for d in all_draws if '2025' in d['date'] or d['draw'].startswith('114')][:100]
    rules = get_lottery_rules('DAILY_539')
    
    cvaa = CVAAPredictor(rules)
    baseline_method = prediction_engine.statistical_predict
    
    stats = {
        "CVAA": {"matches": 0, "win3": 0, "win2": 0, "total": 0},
        "Baseline": {"matches": 0, "win3": 0, "win2": 0, "total": 0}
    }
    
    print(f"Starting Backtest on {len(draws_2025)} draws...")
    
    for target_draw in draws_2025:
        idx = all_draws.index(target_draw)
        history = all_draws[idx+1 : idx+501] # 500 period window
        
        if len(history) < 50: continue
        
        # CVAA
        res_cvaa = cvaa.predict(history)
        if res_cvaa:
            m = len(set(res_cvaa['numbers']) & set(target_draw['numbers']))
            stats["CVAA"]["matches"] += m
            if m >= 3: stats["CVAA"]["win3"] += 1
            if m >= 2: stats["CVAA"]["win2"] += 1
            stats["CVAA"]["total"] += 1
            
        # Baseline (Statistical Probability)
        res_base = baseline_method(history, rules)
        if res_base:
            m = len(set(res_base['numbers']) & set(target_draw['numbers']))
            stats["Baseline"]["matches"] += m
            if m >= 3: stats["Baseline"]["win3"] += 1
            if m >= 2: stats["Baseline"]["win2"] += 1
            stats["Baseline"]["total"] += 1
            
    print("\n" + "="*50)
    print("📈 New Method (CVAA) vs Baseline (Statistical)")
    print("="*50)
    for name, s in stats.items():
        if s['total'] == 0: continue
        avg = s['matches'] / s['total']
        wr3 = s['win3'] / s['total']
        wr2 = s['win2'] / s['total']
        print(f"{name:<10} | Avg Matches: {avg:.3f} | Win 3+: {wr3:.2%} | Win 2+: {wr2:.2%}")
    
    return stats

if __name__ == "__main__":
    run_backtest()
