#!/usr/bin/env python3
"""
Power Lotto Synergy Aggregator (Phase 17)
=========================================
Combines multiple verified or high-potential signals:
1. Fourier Rhythm (Global Periodicity) - Weight 0.6
2. Wavelet MRA (Local/Transient Periodicity) - Weight 0.4
3. Zonal Pruning (Spatial Constraint) - Hard Filter
"""
import os
import sys
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

def get_zone(n):
    if n > 35: return 7
    return (n - 1) // 5

def synergy_predict(history, num_bets=2, window=500):
    max_num = 38
    h_slice = history[-window:]
    
    # 1. Fourier Scores
    fourier_scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        bitstream = np.zeros(window)
        for i, d in enumerate(h_slice):
            if n in d['numbers']: bitstream[i] = 1
        if sum(bitstream) < 2: continue
        yf = np.fft.fft(bitstream - np.mean(bitstream))
        xf = np.fft.fftfreq(window, 1)
        idx = np.where(xf > 0)
        pos_xf, pos_yf = xf[idx], np.abs(yf[idx])
        freq = pos_xf[np.argmax(pos_yf)]
        if freq > 0:
            period = 1 / freq
            last_hit = np.where(bitstream == 1)[0][-1]
            gap = (window - 1) - last_hit
            fourier_scores[n] = 1.0 / (abs(gap - period) + 1.0)

    # 2. Wavelet Scores
    import pywt
    wavelet_scores = np.zeros(max_num + 1)
    scales = np.arange(2, 32)
    for n in range(1, max_num + 1):
        bitstream = np.zeros(window)
        for i, d in enumerate(h_slice):
            if n in d['numbers']: bitstream[i] = 1
        if sum(bitstream) < 3: continue
        try:
            coef, _ = pywt.cwt(bitstream, scales, 'mexh')
            current_energy = np.abs(coef[:, -1])
            best_scale = scales[np.argmax(current_energy)]
            last_hit = np.where(bitstream == 1)[0][-1]
            gap = (window - 1) - last_hit
            wavelet_scores[n] = (1.0 / (abs(gap - best_scale) + 1.0)) * (1 + np.log1p(current_energy[np.argmax(current_energy)]))
        except: pass

    # 3. Synergy Aggregation (Weighted Rank)
    f_rank = np.argsort(np.argsort(fourier_scores[1:]))
    w_rank = np.argsort(np.argsort(wavelet_scores[1:]))
    combined_scores = 0.6 * f_rank + 0.4 * w_rank
    
    sorted_indices = np.argsort(combined_scores)[::-1] + 1
    
    # 4. Zonal Pruning Filter
    # Determine typical zones for Power Lotto
    coverage_counts = {}
    for d in history[-200:]:
        zones = len(set(get_zone(n) for n in d['numbers']))
        coverage_counts[zones] = coverage_counts.get(zones, 0) + 1
    top_zones = sorted(coverage_counts.items(), key=lambda x: x[1], reverse=True)
    best_zones = [z[0] for z in top_zones[:2]]
    
    # Generate candidates and filter
    final_bets = []
    # Take top 24 numbers as pool
    pool = sorted_indices[:24].tolist()
    
    import itertools
    # Sample many combinations from the pool
    count = 0
    import random
    while len(final_bets) < num_bets and count < 1000:
        combo = sorted(random.sample(pool, 6))
        zones = len(set(get_zone(n) for n in combo))
        if zones in best_zones:
            if combo not in final_bets:
                final_bets.append(combo)
        count += 1
        
    # Fallback
    if len(final_bets) < num_bets:
        for i in range(num_bets - len(final_bets)):
            final_bets.append(sorted(sorted_indices[i*6:(i+1)*6].tolist()))

    return final_bets[:num_bets]

if __name__ == "__main__":
    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type='POWER_LOTTO')
    
    print(f"🚀 SYNERGY AGGREGATOR AUDIT (Fourier + Wavelet + Zonal)")
    auditor.audit(synergy_predict, n=1000, num_bets=2)
