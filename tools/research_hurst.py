import sys
import os
import numpy as np
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws, build_binary_matrix

# ==========================================
# 策略發現引擎：Hurst Exponent (長程記憶) 研究
# ==========================================

def calculate_hurst(ts):
    """
    計算時間序列的 Hurst 指數。
    H < 0.5: Mean Reverting (抗持續性)
    H = 0.5: Random Walk (布朗運動)
    H > 0.5: Trending (持續性)
    """
    if len(ts) < 10: return 0.5
    
    lags = range(2, 20)
    tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
    
    # 避免 std 為 0 的情況
    tau = [t if t > 0 else 1e-6 for t in tau]
    
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    return poly[0] * 2.0

def run_hurst_discovery(draws, n_test=500):
    print(f"🔍 [Engine] Hurst Exponent Discovery (N={len(draws)})")
    
    bmat = build_binary_matrix(draws)
    N, K = bmat.shape
    
    hits = 0
    plays = 0
    
    # 執行 Walk-forward 測試
    for i in range(N - n_test, N):
        actual = np.where(bmat[i] == 1)[0] + 1
        
        # 針對每一顆球，計算其 Hurst 指數
        hurst_indices = np.zeros(K)
        for j in range(K):
            # 使用累積和序列來計算 Hurst (Random Walk 形式)
            ts = np.cumsum(bmat[i-150:i, j] - np.mean(bmat[i-150:i, j]))
            hurst_indices[j] = calculate_hurst(ts)
            
        # 策略：選取 Hurst 最偏離 0.5 (最強規律) 的球
        # 或者針對 H < 0.4 (強冷反轉) 的球進行佈局
        scores = np.abs(hurst_indices - 0.5)
        pred = np.argsort(scores)[-6:] + 1
        
        correct = len(set(pred) & set(actual))
        hits += correct
        plays += 6
        
    rate = (hits / plays) if plays > 0 else 0
    edge = rate - (6/49)
    
    print(f"\n📊 [Hurst Results]")
    print(f"   M1+ Hit Rate: {rate*100:.2f}%")
    print(f"   Edge vs Random: {edge*100:+.2f}%")
    
    return edge

if __name__ == "__main__":
    t0 = time.time()
    try:
        draws, _ = load_big_lotto_draws()
        if len(draws) > 200:
            run_hurst_discovery(draws)
        else:
            print("Data too short.")
    except Exception as e:
        print(f"Error: {e}")
    print(f"\n⏱️ Elapsed: {time.time()-t0:.1f}s")
