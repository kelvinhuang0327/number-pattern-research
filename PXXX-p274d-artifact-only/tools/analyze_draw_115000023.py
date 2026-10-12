import sys
import os
import numpy as np
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

def analyze_draw(target_draw_nums, max_history=115000022):
    draws, meta = load_big_lotto_draws()
    target_set = set(target_draw_nums)
    
    valid_draws = []
    for d, m in zip(draws, meta):
        try:
            draw_id = int(m['draw'])
            if draw_id <= max_history:
                valid_draws.append(d)
        except:
            pass
            
    if not valid_draws:
        valid_draws = draws # Fallback
        
    draws = np.array(valid_draws, dtype=np.int32)
    print(f"Using {len(draws)} past draws. Last draw in training: {draws[-1] if len(draws) > 0 else 'None'}")
    
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
    
    # 6. Gap
    gaps = FeatureLibrary.gap_current(draws)
    gap_pred = list(np.argsort(gaps)[::-1][:6] + 1)
    
    predictions = {
        "Triple Strike": ts_pred,
        "Fourier Base": list(np.argsort(fourier_scores)[::-1][:6] + 1),
        "Markov (w=30)": markov_pred,
        "Freq Cold (w=30)": cold_pred,
        "Freq Hot (w=100)": hot_pred,
        "Lag2 Echo": lag2_pred,
        "Gap Current": gap_pred
    }
    
    print(f"\n🎯 Target Draw: {target_draw_nums}")
    print("-" * 50)
    for name, pred in predictions.items():
        hits = set(pred) & target_set
        print(f"[{name}]")
        print(f"  Pred: {sorted(pred)}")
        print(f"  Hits: {len(hits)} {list(hits)}")
        
    print("\n--------------------------------------------------")
    print("5-Bet Orthogonal Configuration:")
    signals = [
        norm(fourier_scores),
        norm(lag2),
        -norm(dev),
        norm(markov_scores),
        -norm(freq_hot)
    ]
    pools = [np.argsort(s)[::-1] for s in signals]
    bets = [[] for _ in range(5)]
    used = set()
    pt = [0] * 5
    while any(len(b) < 6 for b in bets):
        for i in range(5):
            if len(bets[i]) < 6:
                while pt[i] < 49:
                    idx = pools[i][pt[i]]
                    pt[i] += 1
                    if idx not in used:
                        bets[i].append(int(idx) + 1)
                        used.add(idx)
                        break
                        
    for i in range(5):
        hits = set(bets[i]) & target_set
        print(f"  [Bet {i+1}]: {sorted(bets[i])} -> Hits: {len(hits)} {list(hits)}")
        
    print("\n--------------------------------------------------")
    print("Traits of the winning numbers:")
    flat = draws[-100:].flatten()
    freq_100_all = collections.Counter(flat)
    flat30 = draws[-30:].flatten()
    freq_30_all = collections.Counter(flat30)
    
    in_last = set(draws[-1])
    in_lag2_draw = set(draws[-2]) if len(draws) > 1 else set()
    
    for n in target_draw_nums:
        f30 = freq_30_all[n]
        f100 = freq_100_all[n]
        gap_val = gaps[n-1]
        is_last = n in in_last
        is_lag2 = n in in_lag2_draw
        print(f"Num {n:2d}: Freq(30)={f30:2d} | Freq(100)={f100:2d} | Gap={gap_val:2d} | InLast={is_last} | InLag2={is_lag2}")

if __name__ == "__main__":
    analyze_draw([5, 7, 17, 22, 24, 47])
