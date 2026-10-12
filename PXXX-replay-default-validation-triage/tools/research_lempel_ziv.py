import sys
import os
import numpy as np
import time
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws, build_binary_matrix

# ==========================================
# 策略發現引擎：Lempel-Ziv 序列複雜度研究
# ==========================================

def lempel_ziv_complexity(sequence):
    """
    計算二進位序列的 Lempel-Ziv 複雜度。
    這衡量了序列的「可壓縮性」或「規律性」。
    """
    if len(sequence) == 0: return 0
    s = "".join(map(str, sequence))
    n = len(s)
    v, w, k = 0, "", 1
    substrings = set()
    
    i = 0
    while i < n:
        sub = s[i:i+k]
        if sub not in substrings:
            substrings.add(sub)
            i += k
            k = 1
        else:
            k += 1
    return len(substrings)

def run_lz_discovery(draws, n_test=500):
    print(f"🔍 [Engine] Lempel-Ziv Complexity Discovery (N={len(draws)})")
    
    bmat = build_binary_matrix(draws)
    N, K = bmat.shape
    
    hits = 0
    plays = 0
    
    # 執行 Walk-forward 測試 (跳躍採樣以節省時間)
    for i in range(N - n_test, N, 10):
        actual = np.where(bmat[i] == 1)[0] + 1
        
        # 針對每一顆球，計算其過去 100 期的 LZ 複雜度
        lz_scores = np.zeros(K)
        for j in range(K):
            seq = bmat[i-100:i, j]
            # 我們尋找「複雜度正在下降」(規律性增加) 的球，或是複雜度極低的球
            lz_scores[j] = -lempel_ziv_complexity(seq) 
            
        # 選取複雜度最低 (規律性最強) 的 6 顆球
        pred = np.argsort(lz_scores)[-6:] + 1
        
        correct = len(set(pred) & set(actual))
        hits += correct
        plays += 6
        
    rate = (hits / plays) if plays > 0 else 0
    edge = rate - (6/49)
    
    print(f"\n📊 [LZ Results]")
    print(f"   M1+ Hit Rate: {rate*100:.2f}%")
    print(f"   Edge vs Random: {edge*100:+.2f}%")
    
    return edge

if __name__ == "__main__":
    t0 = time.time()
    try:
        draws, _ = load_big_lotto_draws()
        if len(draws) > 200:
            run_lz_discovery(draws)
        else:
            print("Data too short.")
    except Exception as e:
        print(f"Error: {e}")
    print(f"\n⏱️ Elapsed: {time.time()-t0:.1f}s")
