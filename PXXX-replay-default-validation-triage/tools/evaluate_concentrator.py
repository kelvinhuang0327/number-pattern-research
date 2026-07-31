import sys
import os
import numpy as np
import time
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

# ==========================================
# 輔助函式：訊號常規化
# ==========================================
def norm(x):
    std = np.std(x)
    return (x - np.mean(x)) / std if std > 0 else x

# ==========================================
# 核心評估：2-Bet 濃縮聚類器 (Co-occurrence Concentrator)
# ==========================================
def generate_concentrated_2bet(train_draws):
    """
    1. 執行 5 個核心 AI 模型取得分數矩陣
    2. 提取 Top 15 最強候選池 (聯集)
    3. 利用歷史同出機率 (Co-occurrence) 將 15 球濃縮成 2 注 (12球)
    """
    if len(train_draws) < 100:
        return [[1,2,3,4,5,6], [7,8,9,10,11,12]] # Fallback

    # --- Step 1. 五大核心訊號池 --- 
    # 1. TS-Fourier
    phases, mags = FeatureLibrary.fourier_phase(train_draws, top_k=3)
    fourier_scores = np.zeros(49)
    for j in range(49):
        fourier_scores[j] = sum(mags[j, k] * max(0, np.cos(phases[j, k])) for k in range(3))
    
    # 2. TS-Lag2
    try: lag2_scores = FeatureLibrary.lag_autocorrelation(train_draws[-50:], lag=2)
    except: lag2_scores = np.zeros(49)
        
    # 3. TS-Deviation
    dev_scores = -FeatureLibrary.deviation_score(train_draws, window=100)
    
    # 4. Markov (短期轉移)
    markov_probs = FeatureLibrary.markov_transition(train_draws[-30:], order=1)
    last_draw_binary = np.zeros(49)
    if len(train_draws) > 0:
        for n in train_draws[-1]: last_draw_binary[n-1] = 1
    markov_scores = np.zeros(49)
    for j in range(49):
        prev_state = int(last_draw_binary[j])
        markov_scores[j] = markov_probs[j, prev_state]
        
    # 5. Freq Ortho
    freq_scores = -FeatureLibrary.frequency(train_draws, window=100)

    signals = [
        norm(fourier_scores),
        norm(lag2_scores),
        norm(dev_scores),
        norm(markov_scores),
        norm(freq_scores)
    ]
    
    # 整合成混合綜合強勢榜 (Global Momentum Score)
    global_scores = np.sum(signals, axis=0)
    
    # --- Step 2. 建立高潛力候選池 (Top 15 Pool) ---
    pool_indices = np.argsort(global_scores)[::-1][:15]
    pool_nums = [int(idx + 1) for idx in pool_indices]
    
    # --- Step 3. 建立歷史同出機率矩陣 (Co-occurrence) ---
    # 計算這 15 球裡面，哪些球在過去 100 期常常一起開出
    co_matrix = np.zeros((50, 50))
    for draw in train_draws[-100:]:
        for i in draw:
            for j in draw:
                if i != j:
                    co_matrix[i][j] += 1
                    
    # --- Step 4. K-Medoids / 貪婪叢集分組 (Greedy Clustering) ---
    # 目標：選出 2 注 (各 6 球)，這兩注內部的球是高度「同出關聯」的
    bet_1 = []
    bet_2 = []
    available = set(pool_nums)
    
    # 找勢能最強的兩顆做錨點 (Anchor)
    anchor_1 = pool_nums[0]
    available.remove(anchor_1)
    bet_1.append(anchor_1)
    
    # 錨點 2 是與錨點 1 最互斥 (同出最少) 的強勢球
    furthest = None
    min_co = float('inf')
    for n in available:
        co = co_matrix[anchor_1][n]
        if co < min_co:
            min_co = co
            furthest = n
            
    anchor_2 = furthest if furthest else list(available)[0]
    available.remove(anchor_2)
    bet_2.append(anchor_2)
    
    # 輪流吸納與自身最常同出的球
    while len(bet_1) < 6 or len(bet_2) < 6:
        # Bet 1 吸納
        if len(bet_1) < 6 and available:
            best_n = None
            max_affinity = -1
            for n in available:
                affinity = sum(co_matrix[n][b] for b in bet_1)
                if affinity > max_affinity:
                    max_affinity = affinity
                    best_n = n
            if best_n:
                bet_1.append(best_n)
                available.remove(best_n)
                
        # Bet 2 吸納
        if len(bet_2) < 6 and available:
            best_n = None
            max_affinity = -1
            for n in available:
                affinity = sum(co_matrix[n][b] for b in bet_2)
                if affinity > max_affinity:
                    max_affinity = affinity
                    best_n = n
            if best_n:
                bet_2.append(best_n)
                available.remove(best_n)
                
    # 確保補滿
    while len(bet_1) < 6 and available:
        n = available.pop()
        bet_1.append(n)
    while len(bet_2) < 6 and available:
        n = available.pop()
        bet_2.append(n)
        
    return [sorted(bet_1), sorted(bet_2)]

# ==========================================
# 盲測引擎 (Walk-Forward OOS)
# ==========================================
def run_concentrator_backtest(draws, n_test=1500):
    start_idx = len(draws) - n_test
    
    print("\n⏳ 執行 1500 期 Walk-forward 盲測中 (產生 2-Bet 濃縮注碼)...", flush=True)
    
    results = []
    t0 = time.time()
    
    for i in range(start_idx, len(draws)):
        train = draws[:i]
        actual = set(draws[i])
        
        bets = generate_concentrated_2bet(train)
        
        hits = [len(set(b) & actual) for b in bets]
        joint_m3 = max(hits)
        results.append(joint_m3)
        
        if (i - start_idx + 1) % 300 == 0:
            print(f"  ... {i - start_idx + 1}/{n_test} 模擬完成")
            
    time_taken = time.time() - t0
    
    return results, time_taken

# ==========================================
# 主程式：115000023 覆盤與 1500期驗證
# ==========================================
if __name__ == "__main__":
    import math
    draws, meta = load_big_lotto_draws()
    if len(draws) < 1600:
        print(f"資料不足 ({len(draws)} 期)，需 >= 1600 期")
        sys.exit(0)
    
    print("================================================================")
    print("🔬 【大樂透 2-Bet 濃縮聚類器 (Co-occurrence Concentrator)】")
    print("================================================================")
    
    # 1. 115000023 覆盤測試
    target_draw = 115000023
    test_train_draws = []
    actual_nums = None
    for d, m in zip(draws, meta):
        try:
            d_id = int(m['draw'])
            if d_id < target_draw:
                test_train_draws.append(d)
            elif d_id == target_draw:
                actual_nums = set(d)
        except: pass
        
    test_train_draws = np.array(test_train_draws, dtype=np.int32)
    concentrated_bets = generate_concentrated_2bet(test_train_draws)
    
    print(f"\n🎯 覆盤第 {target_draw} 期 (開獎號: {sorted(list(actual_nums)) if actual_nums else '未知'})")
    print("  [原算法 5注 0% 重疊]: 單注最多命中 1 顆 (稀釋嚴重)")
    print("  [新算法 2注 同出壓縮]:")
    for i, b in enumerate(concentrated_bets):
        if actual_nums:
            hits = set(b) & actual_nums
            print(f"   Bet {i+1}: {b} -> 爆發命中 {len(hits)} 顆: {list(hits)}")
        else:
            print(f"   Bet {i+1}: {b}")
            
    # 2. 執行 1500期 OOS 回測
    results, elapsed = run_concentrator_backtest(draws, n_test=1500)
    
    # 3. M3+ 績效統計
    total_m3_plays = 1500
    m3_wins = sum(1 for h in results if h >= 3)
    rate_m3 = m3_wins / total_m3_plays
    
    # 計算 2-Bet (6/49) 理論 M3+ 隨機機率
    def p_m(k): return (math.comb(6, k) * math.comb(43, 6 - k)) / math.comb(49, 6)
    p_geq_3_single = p_m(3) + p_m(4) + p_m(5) + p_m(6)
    base_2bet_m3 = 1 - (1 - p_geq_3_single)**2
    
    print("\n📊 1500期 OOS 回測報告 (M3+ 理論覆核):")
    print(f"   2-Bet 實際勝率: {rate_m3*100:.2f}% ({m3_wins} / {total_m3_plays})")
    print(f"   2-Bet 理論基線: {base_2bet_m3*100:.2f}%")
    
    edge = rate_m3 - base_2bet_m3
    z_score = edge / np.sqrt((base_2bet_m3 * (1 - base_2bet_m3)) / total_m3_plays)
    
    print(f"   優勢 (Edge):    {(edge)*100:+.2f}%")
    print(f"   Z-Score:        {z_score:+.2f}")
    
    from scipy.stats import norm as scipy_norm
    p_val = 1 - scipy_norm.cdf(z_score)
    print(f"   P-Value (單尾): {p_val:.4f}")
    
    # 4. 判定
    print("\n👩‍⚖️ 設計評審裁決:")
    if p_val < 0.05:
         print("   🟢【通過】Z-score > 1.645，優勢具備統計顯著性，成功解決濃度稀釋！")
    else:
         print("   🔴【駁回】未達 95% 信心水準，同出壓縮效應最終敵不過隨機大數法則。維持原 5-Bet 正交。")
         
    print(f"\n⏱️ 測評總耗時: {elapsed:.1f} 秒")
