import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

def generate_orthogonal_bets(draws, n_bets=3):
    """
    使用嚴格驗證的四大信號源，生成最佳正交雙注/三注
    - Triple Strike (Fourier, Echo, Deviation)
    - Markov (w=30)
    - Freq Orthogonal (100)
    - Lag2 Echo (50)
    """
    scores = np.zeros(49)
    
    # 1. Frequency (w=100)
    freq = FeatureLibrary.frequency(draws, window=100)
    
    # 2. Markov (Order 1, simple transition from last draw, w=30)
    # Using window=30 implicitly by truncating draws for markov transition 
    # Since FeatureLibrary hasn't a window arg for markov yet, we pass a sliced draws
    markov_probs = FeatureLibrary.markov_transition(draws[-30:], order=1)
    last_draw_binary = np.zeros(49)
    for n in draws[-1]:
        last_draw_binary[n-1] = 1
    
    markov_scores = np.zeros(49)
    for j in range(49):
        prev_state = int(last_draw_binary[j])
        markov_scores[j] = markov_probs[j, prev_state]
        
    # 3. Lag2 Echo (w=50)
    try:
        lag2 = FeatureLibrary.lag_autocorrelation(draws[-50:], lag=2)
    except:
        lag2 = np.zeros(49)
        
    # 4. Triple Strike approximate (Fourier top 3 phases + deviation)
    phases, mags = FeatureLibrary.fourier_phase(draws, top_k=3)
    fourier_scores = np.zeros(49)
    for j in range(49):
        fourier_scores[j] = sum(mags[j, k] * max(0, np.cos(phases[j, k])) for k in range(3))
        
    dev = FeatureLibrary.deviation_score(draws, window=100) # underperforming
    
    # Normalize features
    def norm(x):
        if np.std(x) == 0: return x
        return (x - np.mean(x)) / np.std(x)
        
    final_scores = (
        norm(freq) * 1.0 +
        norm(markov_scores) * 1.5 + 
        norm(lag2) * 1.0 +
        norm(fourier_scores) * 1.2 -
        norm(dev) * 0.8  # penalize high deviation (revert to mean)
    )
    
    # Get top N * 6 numbers
    total_needed = n_bets * 6
    ranked_indices = np.argsort(final_scores)[::-1]
    top_numbers = [int(i) + 1 for i in ranked_indices[:total_needed]]
    
    # Disjoint splitting (Simple round-robin or variance balancing)
    # We use snake draft to balance the power of the bets
    bets = [[] for _ in range(n_bets)]
    for i, num in enumerate(top_numbers):
        # Snake layout: 0, 1, 2, 2, 1, 0, 0, 1, 2...
        round_idx = i // n_bets
        if round_idx % 2 == 0:
            bet_idx = i % n_bets
        else:
            bet_idx = (n_bets - 1) - (i % n_bets)
        bets[bet_idx].append(num)
        
    for b in bets:
        b.sort()
        
    return top_numbers, bets

if __name__ == '__main__':
    draws, meta = load_big_lotto_draws()
    print("=== 大樂透最佳化雙注/三注 (正交獨立分配) ===")
    
    # 雙注
    top12, bets2 = generate_orthogonal_bets(draws, 2)
    print("\n【2 注最佳解】(涵蓋最強 12 碼, 0重複)")
    print(f"核心 12 碼池: {sorted(top12)}")
    for i, b in enumerate(bets2):
        print(f"注 {i+1}: {b}")
        
    # 三注
    top18, bets3 = generate_orthogonal_bets(draws, 3)
    print("\n【3 注最佳解】(涵蓋最強 18 碼, 0重複)")
    print(f"核心 18 碼池: {sorted(top18)}")
    for i, b in enumerate(bets3):
        print(f"注 {i+1}: {b}")
