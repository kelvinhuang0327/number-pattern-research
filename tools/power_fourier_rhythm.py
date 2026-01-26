#!/usr/bin/env python3
"""
Power Lotto Fourier Rhythm Researcher
=====================================
Logic:
1. Treat each ball's appearance history (0/1) as a time-series.
2. Apply Fast Fourier Transform (FFT) to detect dominant frequencies.
3. Predict based on the "Next Strike" phase of the top periodic balls.
"""
import os
import sys
import numpy as np
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

def detect_dominant_period(ball_history):
    # ball_history is an array of 0s and 1s
    n = len(ball_history)
    if sum(ball_history) < 2: return None
    
    # FFT
    yf = fft(ball_history - np.mean(ball_history)) # Detrend
    xf = fftfreq(n, 1)
    
    # Only look at positive frequencies (excluding constant term)
    idx = np.where(xf > 0)
    pos_xf = xf[idx]
    pos_yf = np.abs(yf[idx])
    
    # Target peak
    peak_idx = np.argmax(pos_yf)
    freq = pos_xf[peak_idx]
    
    if freq == 0: return None
    period = 1 / freq
    return period

def fourier_rhythm_predict(history, n_bets=2, window=500):
    h_slice = history[-window:]
    max_num = 38
    
    # 1. Create bitstreams for each ball
    bitstreams = {i: np.zeros(window) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            bitstreams[n][idx] = 1
            
    # 2. Detect periods and phases
    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        period = detect_dominant_period(bitstreams[n])
        if period and 2 < period < window/2:
            # Simple scoring: How many draws since last appearance?
            last_hit = np.where(bitstreams[n] == 1)[0][-1]
            gap = (window - 1) - last_hit
            # If gap is approaching the period, high score
            # Score = Gaussian-like peak around the period
            dist_to_peak = abs(gap - period)
            scores[n] = 1.0 / (dist_to_peak + 1.0)
            
    all_indices = np.arange(1, max_num + 1)
    sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
    
    bets = []
    for i in range(n_bets):
        start = i * 6
        end = (i + 1) * 6
        bets.append(sorted(sorted_indices[start:end].tolist()))
        
    return bets

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=500)
    args = parser.parse_args()
    
    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type='POWER_LOTTO')
    
    def audit_bridge(history, num_bets=2):
        return fourier_rhythm_predict(history, n_bets=num_bets)
        
    auditor.audit(audit_bridge, n=args.n, num_bets=2)
