import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

def analyze_draw(target_draw_nums, max_history=115000020):
    draws, meta = load_big_lotto_draws()
    # Assume target_draw is the next one, but we only use history up to the last draw
    target_set = set(target_draw_nums)
    
    # 1. Triple Strike
    phases, mags = FeatureLibrary.fourier_phase(draws, top_k=3)
    fourier_scores = np.zeros(49)
    for j in range(49):
        fourier_scores[j] = sum(mags[j, k] * max(0, np.cos(phases[j, k])) for k in range(3))
    try:
        lag2 = FeatureLibrary.lag_autocorrelation(draws[-50:], lag=2)
    except:
        lag2 = np.zeros(49)
    dev = FeatureLibrary.deviation_score(draws, window=100)
    
    def norm(x):
        std = np.std(x)
        return (x - np.mean(x)) / std if std > 0 else x
        
    ts_score = norm(fourier_scores) + norm(lag2) - norm(dev)
    ts_pred = list(np.argsort(ts_score)[::-1][:6] + 1)
    
    # 2. Markov
    markov_probs = FeatureLibrary.markov_transition(draws[-30:], order=1)
    last_draw_binary = np.zeros(49)
    for n in draws[-1]: last_draw_binary[n-1] = 1
    markov_scores = np.zeros(49)
    for j in range(49):
        prev_state = int(last_draw_binary[j])
        markov_scores[j] = markov_probs[j, prev_state]
    markov_pred = list(np.argsort(markov_scores)[::-1][:6] + 1)
    
    # 3. Freq Cold
    freq_cold = -FeatureLibrary.frequency(draws, window=30)
    cold_pred = list(np.argsort(freq_cold)[::-1][:6] + 1)
    
    # 4. Freq Hot
    freq_hot = FeatureLibrary.frequency(draws, window=100)
    hot_pred = list(np.argsort(freq_hot)[::-1][:6] + 1)
    
    # 5. Lag2 Echo
    lag2_pred = list(np.argsort(lag2)[::-1][:6] + 1)
    
    predictions = {
        "Triple Strike": ts_pred,
        "Markov (w=30)": markov_pred,
        "Freq Cold (w=30)": cold_pred,
        "Freq Hot (w=100)": hot_pred,
        "Lag2 Echo": lag2_pred
    }
    
    print(f"🎯 Target Draw: {target_draw_nums}")
    print("-" * 50)
    for name, pred in predictions.items():
        hits = set(pred) & target_set
        print(f"[{name}]")
        print(f"  Pred: {sorted(pred)}")
        print(f"  Hits: {len(hits)} {list(hits)}")

    return predictions

if __name__ == "__main__":
    analyze_draw([13, 15, 18, 24, 33, 49])
