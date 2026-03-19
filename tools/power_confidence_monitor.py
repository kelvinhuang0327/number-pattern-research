#!/usr/bin/env python3
"""
Power Lotto Volatility Confidence Monitor
=========================================
Logic:
1. Track the rolling "Match-3+" rate of the system (e.g., Fourier).
2. Measure the Z-score of the current performance vs theoretical baseline.
3. If performance is in a significant "drawdown", flag low confidence.
4. Identify "High Predictability Cycles" where the signal-to-noise ratio is rising.
"""
import os
import sys
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.power_fourier_rhythm import fourier_rhythm_predict

def analyze_confidence(history, window=100):
    baseline = 0.0855 # Power Lotto RAND for 2 bets
    
    # We perform a mini backtest on the LAST 'window' draws of the CURRENT history
    if len(history) < window + 100:
        return 1.0 # Default confidence during warm-up
        
    hits = 0
    test_range = min(window, len(history) - 100)
    for i in range(test_range):
        idx = len(history) - test_range + i
        target = history[idx]['numbers']
        h_prev = history[:idx]
        
        # Use Fourier as the signal generator for monitoring
        bets = fourier_rhythm_predict(h_prev, n_bets=2, window=200)
        win = False
        for b in bets:
            if sum(1 for n in b if n in target) >= 3:
                win = True
                break
        if win: hits += 1
        
    actual_rate = hits / test_range
    # Confidence Score: Ratio of actual vs baseline
    # If 1.0, we are at baseline. If > 1.0, we are in a 'Hot Cycle'.
    confidence = actual_rate / baseline
    return confidence

def confidence_boost_predict(history, n_bets=2):
    # This is a meta-predictor that could eventually skip bets.
    # For now, it just logs confidence and prioritizes numbers.
    conf = analyze_confidence(history, window=50)
    
    # Generate base bets
    base_bets = fourier_rhythm_predict(history, n_bets=n_bets, window=500)
    
    # Optional: If confidence is VERY low (e.g. < 0.5), maybe we switch strategy?
    # Or just return the Fourier signal.
    return base_bets, conf

if __name__ == "__main__":
    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type='POWER_LOTTO')
    
    print(f"🚀 AUDITING: Fourier + Confidence Monitor")
    
    def audit_bridge(history, num_bets=2):
        bets, conf = confidence_boost_predict(history, n_bets=num_bets)
        return bets
        
    auditor.audit(audit_bridge, n=500, num_bets=2)
