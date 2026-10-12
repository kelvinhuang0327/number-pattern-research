#!/usr/bin/env python3
"""
Power Lotto Wavelet MRA Researcher
==================================
Logic:
1. Apply Continuous Wavelet Transform (CWT) to each ball's 0/1 history.
2. CWT captures localized (transient) frequencies better than Fourier.
3. Identify "Active Rhythms" that are currently peaking in energy.
4. Predict the "Next Pulse" for balls with high local energy.
"""
import os
import sys
import numpy as np
import pywt

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

def detect_wavelet_peak(ball_history, scales=np.arange(2, 32)):
    """
    Detect the localized energy peak using CWT.
    Returns: (best_scale, energy_at_last_step)
    """
    if sum(ball_history) < 3: return 0, 0
    
    # Use Morlet wavelet (cmor) for clear frequency localization
    # Note: cmor1.5-1.0 is a common choice for periodicity detection
    try:
        coef, freqs = pywt.cwt(ball_history, scales, 'mexh') # Mexican Hat is robust for transients
        
        # Energy at the current (last) draw
        current_energy = np.abs(coef[:, -1])
        
        best_idx = np.argmax(current_energy)
        return scales[best_idx], current_energy[best_idx]
    except:
        return 0, 0

def wavelet_mra_predict(history, n_bets=2, window=300):
    if not history: return []
    h_slice = history[-window:]
    # Detect lottery type from max ball in history
    all_nums = [n for d in h_slice for n in d['numbers']]
    max_num = max(all_nums) if all_nums else 38
    if max_num < 38: max_num = 38
    if max_num > 38: max_num = 49
    
    # 1. Create bitstreams
    bitstreams = {i: np.zeros(window) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            bitstreams[n][idx] = 1
            
    # 2. Analyze Current "Pulsing" Energy
    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        scale, energy = detect_wavelet_peak(bitstreams[n])
        
        # We look for balls that are 'Active' (high energy) 
        # but also consider their gap vs the detected scale (local period)
        if scale > 0:
            last_hits = np.where(bitstreams[n] == 1)[0]
            last_hit = last_hits[-1]
            gap = (window - 1) - last_hit
            
            # Phase alignment: Score peaks when gap approaches scale
            # We add a small energy weight to favor 'Strong Rhythms'
            phase_score = 1.0 / (abs(gap - scale) + 1.0)
            scores[n] = phase_score * (1 + np.log1p(energy))
            
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
        return wavelet_mra_predict(history, n_bets=num_bets)
        
    print(f"🚀 WAVELET MRA AUDIT (Mode: Mexican Hat Transient Detection)")
    auditor.audit(audit_bridge, n=args.n, num_bets=2)
