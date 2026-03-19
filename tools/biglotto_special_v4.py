#!/usr/bin/env python3
"""
Big Lotto Special Regression (V4)
=================================
Logic:
1. Treat the 7th ball (Special Number) as a distinct sequence.
2. Apply Return-Interval Analysis (RIA) to model its specific "Lag Rhythm".
3. Evaluate the probability of each number (1-49) appearing in the S-position.
"""
import os
import sys
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

class BigLottoSpecialPredictorV4:
    def __init__(self, history):
        self.history = history
        self.max_num = 49

    def predict_top_n(self, n=4, window=500):
        h_slice = self.history[-window:]
        special_sequence = [d['special'] for d in h_slice]
        
        # 1. Calculate Last Seen & Intervals for S-position
        last_seen = {i: -1 for i in range(1, self.max_num + 1)}
        intervals = {i: [] for i in range(1, self.max_num + 1)}
        
        for idx, s_num in enumerate(special_sequence):
            if last_seen[s_num] != -1:
                intervals[s_num].append(idx - last_seen[s_num])
            last_seen[s_num] = idx
            
        # 2. Score based on "Due-ness" (Current Lag vs Median Interval)
        current_idx = len(special_sequence)
        scores = np.zeros(self.max_num + 1)
        
        for i in range(1, self.max_num + 1):
            if last_seen[i] == -1:
                scores[i] = 0.5 # Neutral if never seen in window
                continue
                
            median_int = np.median(intervals[i]) if intervals[i] else 49.0
            current_lag = current_idx - last_seen[i]
            
            # Gaussian-like probability: High score when current_lag approaches median_int
            # But also favor slightly "Overdue" numbers
            z = (current_lag - median_int) / (np.std(intervals[i]) + 1.0) if intervals[i] else 0
            scores[i] = np.exp(-0.5 * (z**2)) * (1 + 0.1 * max(0, z))
            
        # 3. Frequency Adjustment (Long-term Bias)
        overall_freq = Counter(special_sequence)
        for i in range(1, self.max_num + 1):
            scores[i] *= (1 + 0.05 * overall_freq.get(i, 0))

        sorted_indices = np.argsort(scores[1:])[::-1] + 1
        return sorted_indices[:n].tolist()

if __name__ == "__main__":
    from lottery_api.database import DatabaseManager
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    predictor = BigLottoSpecialPredictorV4(history)
    
    # Audit Logic (N=1000)
    print(f"🚀 AUDITING: Big Lotto Special V4 (N=1000)")
    hits = 0
    total = 0
    n_test = 1000
    start_idx = len(history) - n_test
    
    for i in range(n_test):
        idx = start_idx + i
        target = history[idx]['special']
        h_prev = history[:idx]
        
        # We predict top 4 to match the usual 4-bet recommendation
        pred_top_4 = BigLottoSpecialPredictorV4(h_prev).predict_top_n(n=4)
        if target in pred_top_4:
            hits += 1
        total += 1
        
        if (i+1) % 100 == 0:
            print(f"   ∟ Processed {i+1}/{n_test}... Current Hit Rate: {hits/total*100:.2f}%")
            
    win_rate = hits / total
    baseline = 1 - (1 - 1/49)**4 # Probability of hitting with 4 random picks
    edge = win_rate - baseline
    
    print("-" * 50)
    print(f"實測勝率 (Top 4): {win_rate*100:6.2f}%")
    print(f"隨機基準 (RAND): {baseline*100:6.2f}%")
    print(f"理論優勢 (Edge): {edge*100:+6.2f}%")
    print("-" * 50)
