import sys
import os
import numpy as np
import time
import itertools
from sklearn.mixture import GaussianMixture

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

# ==========================================
# 策略發現引擎：Regime-Specific Symbolic Discovery
# ==========================================

def get_atoms(d):
    freq = FeatureLibrary.frequency(d, window=100)
    gap = FeatureLibrary.gap_current(d).astype(float)
    markov = FeatureLibrary.markov_transition(d, order=1)[:, 1]
    return {
        'freq': (freq - np.mean(freq)) / (np.std(freq) + 1e-9),
        'gap_neg': (-gap - np.mean(-gap)) / (np.std(gap) + 1e-9),
        'markov': (markov - np.mean(markov)) / (np.std(markov) + 1e-9)
    }

def discover_regime_specific_signals(draws):
    print(f"🔍 [Engine] Searching for Regime-Specific Signals in {len(draws)} draws...")
    
    # 1. 提取 Regime 特徵並分組
    regime_features = []
    eval_horizon = 500
    start_idx = len(draws) - eval_horizon
    
    for i in range(100, len(draws)):
        hist = draws[:i]
        curr_gaps = FeatureLibrary.gap_current(hist)
        bins = np.histogram(curr_gaps, bins=[0, 5, 10, 20, 50])[0]
        probs = bins / np.sum(bins) if np.sum(bins) > 0 else [0.25]*4
        entropy = -np.sum([p * np.log(p) for p in probs if p > 0])
        avg_gap = np.mean(curr_gaps)
        hot = np.mean(FeatureLibrary.frequency(hist, window=10))
        regime_features.append([entropy, avg_gap, hot])
        
    X = np.array(regime_features)
    gmm = GaussianMixture(n_components=3, n_init=5)
    states_all = gmm.fit_predict(X)
    states = states_all[-(eval_horizon+1):-1] # Match the eval window
    
    # 2. 預計算原子特徵 (Speed up)
    print("⚡ [Engine] Pre-calculating atomic features...")
    atoms_cache = []
    for i in range(start_idx, len(draws)):
        atoms_cache.append(get_atoms(draws[:i]))
    
    atoms_keys = ['freq', 'gap_neg', 'markov']
    operators = [
        ('add', lambda a, b: a + b),
        ('sub', lambda a, b: a - b),
        ('mul', lambda a, b: a * b),
    ]
    
    results_by_state = {0: [], 1: [], 2: []}
    
    # 3. 測試每種公式在不同狀態下的表現
    print("🚀 [Engine] Testing formulas across 3 regimes...")
    
    for (k1, k2) in itertools.combinations(atoms_keys, 2):
        for op_name, op_func in operators:
            formula_hits = {0: 0, 1: 0, 2: 0}
            formula_plays = {0: 0, 1: 0, 2: 0}
            
            for idx in range(eval_horizon):
                i = start_idx + idx
                s = states[idx]
                actual = set(draws[i])
                atoms = atoms_cache[idx]
                
                score = op_func(atoms[k1], atoms[k2])
                pred = np.argsort(score)[-6:] + 1
                
                formula_hits[s] += len(set(pred) & actual)
                formula_plays[s] += 6
                
            for s in range(3):
                rate = (formula_hits[s] / formula_plays[s]) if formula_plays[s] > 0 else 0
                edge = rate - (6/49)
                results_by_state[s].append({
                    'formula': f"{k1} {op_name} {k2}",
                    'edge': edge,
                    'plays': formula_plays[s]
                })
                
    print("\n🏆 [Engine] Best Formulas by Regime:")
    for s in range(3):
        if not results_by_state[s]: continue
        results_by_state[s].sort(key=lambda x: x['edge'], reverse=True)
        top = results_by_state[s][0]
        print(f"   State {s} | Best: {top['formula']:<20} | Edge: {top['edge']*100:+.2f}% | Sample: {top['plays']//6} draws")

if __name__ == "__main__":
    t0 = time.time()
    try:
        draws, _ = load_big_lotto_draws()
        if len(draws) > 600:
            discover_regime_specific_signals(draws)
    except Exception as e:
        print(f"Error: {e}")
    print(f"\n⏱️ Elapsed: {time.time()-t0:.1f}s")
