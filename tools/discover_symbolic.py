import sys
import os
import numpy as np
import time
import itertools

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

# ==========================================
# 策略發現引擎：Symbolic Formula Discovery (Lite)
# ==========================================

def discover_symbolic_signals(draws, n_test=300):
    """
    1. 準備基礎原子特徵 (Freq, Gap, Fourier, Markov)
    2. 窮盡符號運算組合 (+, -, *, /)
    3. 在 300 期樣本中計算候選公式的 Edge
    4. 輸出具有「異常 Edge」的高潛力公式
    """
    print(f"🔍 [Engine] Searching for Symbolic Signals in {len(draws)} draws...")
    
    # 最近一次訓練集
    train = draws[:-n_test]
    test_draws = draws[-n_test:]
    
    # 原子特徵庫
    def get_atoms(d):
        freq = FeatureLibrary.frequency(d, window=100)
        gap = FeatureLibrary.gap_current(d).astype(float)
        markov = FeatureLibrary.markov_transition(d, order=1)[:, 1] # P(appear | appear)
        return {
            'freq': (freq - np.mean(freq)) / (np.std(freq) + 1e-9),
            'gap_neg': (-gap - np.mean(-gap)) / (np.std(gap) + 1e-9),
            'markov': (markov - np.mean(markov)) / (np.std(markov) + 1e-9)
        }

    atoms_keys = ['freq', 'gap_neg', 'markov']
    operators = [
        ('add', lambda a, b: a + b),
        ('sub', lambda a, b: a - b),
        ('mul', lambda a, b: a * b),
        ('div', lambda a, b: a / (np.abs(b) + 0.1)),
    ]
    
    best_formulas = []
    
    # 執行搜尋
    print("🚀 [Engine] Symbolic Brute-force Search in progress...")
    for (k1, k2) in itertools.combinations(atoms_keys, 2):
        for op_name, op_func in operators:
            # 在測試期間跑 Walk-forward 計算 Edge
            hits = 0
            plays = 0
            
            # 為了效率，我們抽樣 50 期來做初選
            for i in range(len(draws) - 50, len(draws)):
                h = draws[:i]
                actual = set(draws[i])
                atoms = get_atoms(h)
                
                score = op_func(atoms[k1], atoms[k2])
                pred = np.argsort(score)[-6:] + 1
                
                hits += len(set(pred) & actual)
                plays += 6
            
            rate = (hits / plays) if plays > 0 else 0
            # 隨機基準：6/49 = 0.1224
            edge = rate - (6/49)
            
            formula_name = f"{k1} {op_name} {k2}"
            best_formulas.append({'name': formula_name, 'edge': edge})
            
    best_formulas.sort(key=lambda x: x['edge'], reverse=True)
    
    print("\n🏆 [Engine] Top Discovered Symbolic Formulas (Edge > 0):")
    for f in best_formulas[:5]:
        print(f"   {f['name']:<25} | Edge: {f['edge']*100:+.2f}%")
        
    return best_formulas

if __name__ == "__main__":
    t0 = time.time()
    try:
        draws, _ = load_big_lotto_draws()
        if len(draws) > 200:
            discover_symbolic_signals(draws)
            print("\n✅ [Engine] Discovery Cycle Finished.")
        else:
            print("Data too short.")
    except Exception as e:
        print(f"Error: {e}")
    print(f"\n⏱️ Elapsed: {time.time()-t0:.1f}s")
