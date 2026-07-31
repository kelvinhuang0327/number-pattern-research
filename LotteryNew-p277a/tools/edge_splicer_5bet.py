import sys
import os
import numpy as np
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

# ==========================================
# 1. 提取五維原子特徵信號 (Atomic Signals for 5-Bet)
# ==========================================

def get_signal_ts_a(draws):
    """注 1: Triple Strike A (Fourier)"""
    phases, mags = FeatureLibrary.fourier_phase(draws, top_k=3)
    fourier_scores = np.zeros(49)
    for j in range(49):
        fourier_scores[j] = sum(mags[j, k] * max(0, np.cos(phases[j, k])) for k in range(3))
    return fourier_scores

def get_signal_ts_b(draws):
    """注 2: Triple Strike B (Lag Echo)"""
    try:
        lag2 = FeatureLibrary.lag_autocorrelation(draws[-50:], lag=2)
    except:
        lag2 = np.zeros(49)
    return lag2

def get_signal_markov(draws, window=30):
    """注 3: Markov"""
    if len(draws) < window: window = len(draws)
    markov_probs = FeatureLibrary.markov_transition(draws[-window:], order=1)
    last_draw_binary = np.zeros(49)
    for n in draws[-1]: last_draw_binary[n-1] = 1
    markov_scores = np.zeros(49)
    for j in range(49):
        prev_state = int(last_draw_binary[j])
        markov_scores[j] = markov_probs[j, prev_state]
    return markov_scores

def get_signal_zm(draws):
    """注 4: Zonal Momentum (New!)"""
    zonal_scores = FeatureLibrary.zonal_density_score(draws, window=10, zones=5)
    gap_mom_scores = FeatureLibrary.gap_momentum(draws)
    
    def norm(x):
        std = np.std(x)
        return (x - np.mean(x)) / std if std > 0 else x
        
    return norm(zonal_scores) * 1.5 + norm(gap_mom_scores) * 1.0

def get_signal_freq_ortho(draws):
    """注 5: Freq Orthogonal (Hot/Cold Inverse)"""
    # 這是原本 5 注架構中的頻率正交點，結合熱碼與冷碼的變異
    freq = FeatureLibrary.frequency(draws, window=100)
    # Return inverse to prioritize the tails
    return -freq

def normalize_signal(s):
    std = np.std(s)
    if std == 0: return s
    return (s - np.mean(s)) / std

# ==========================================
# 2. 完美的 5 注防禦矩陣 (0% 重疊正交)
# ==========================================

def generate_5_bet_matrix(draws):
    """
    產生 5 注完美零重疊的 30 顆號碼
    """
    signals = [
        ("TS-Fourier (主頻譜)", normalize_signal(get_signal_ts_a(draws))),
        ("TS-Lag2 (滯後共鳴)", normalize_signal(get_signal_ts_b(draws))),
        ("Markov (極端短期)", normalize_signal(get_signal_markov(draws))),
        ("Zonal Momentum (板塊均值)", normalize_signal(get_signal_zm(draws))),
        ("Freq Ortho (長期頻率)", normalize_signal(get_signal_freq_ortho(draws)))
    ]
    
    pools = [np.argsort(s)[::-1] for _, s in signals]
    bets = [[] for _ in range(5)]
    used = set()
    
    # 輪流從各訊號的首選池中挑選不重複的號碼
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
                        
    return [sorted(b) for b in bets], [name for name, _ in signals]

# ==========================================
# 3. 三窗口盲測 (Walk-forward Backtest)
# ==========================================

def run_backtest_5bet(draws, windows=[150, 500, 1500]):
    total = len(draws)
    max_w = max(windows)
    start_idx = total - max_w
    
    results = []
    
    for i in range(start_idx, total):
        train = draws[:i]
        actual = set(draws[i])
        bets, _ = generate_5_bet_matrix(train)
        
        hits = [len(set(b) & actual) for b in bets]
        joint_hit = max(hits)
        results.append((hits, joint_hit))
        
    target_results = {}
    for w in windows:
        w_results = results[-w:]
        joint_m3 = sum(1 for r in w_results if r[1] >= 3)
        joint_rate = joint_m3 / max(1, w)
        
        target_results[w] = {'rate': joint_rate}
        
    contrib = [0] * 5
    for r in results[-1500:]:
        for idx, hit in enumerate(r[0]):
            if hit >= 3: 
                contrib[idx] += 1
                
    total_wins = sum(1 for r in results[-1500:] if r[1] >= 3)
    contrib_pct = [c / total_wins * 100 if total_wins > 0 else 0 for c in contrib]
        
    return target_results, contrib_pct

# ==========================================
# EXECUTION
# ==========================================
if __name__ == "__main__":
    t0 = time.time()
    draws, _ = load_big_lotto_draws()
    
    print("==================================================")
    print("🛡️ 【5 注無雙矩陣 (V2：導入 Zonal Momentum)】 標準 OOS 回測")
    print("==================================================")
    
    bets, sources = generate_5_bet_matrix(draws)
    
    print("\n🔹 注碼分配 (下一期實戰推薦):")
    for i in range(5):
        print(f"   [注 {i+1}]: {bets[i]} ({sources[i]})")
        
    all_nums = sum(bets, [])
    assert len(all_nums) == 30 and len(set(all_nums)) == 30, "ERROR: Overlapping detected!"
        
    print(f"\n🔹 執行嚴苛三窗口 OOS 回測 (150p/500p/1500p)...", flush=True)
    stats, contrib = run_backtest_5bet(draws, [150, 500, 1500])
    
    base_5 = 1 - (1 - 0.0186)**5
    edge_1500 = stats[1500]['rate'] - base_5
    
    print("\n🔹 回測報告:")
    print(f"   短期 (150p) : {stats[150]['rate']*100:.2f}%")
    print(f"   中期 (500p) : {stats[500]['rate']*100:.2f}%")
    print(f"   長期 (1500p): {stats[1500]['rate']*100:.2f}%  (理論隨機值: {base_5*100:.2f}%)")
    print(f"   => 聯合 Edge: {edge_1500*100:+.2f}%")
    
    print("\n🔹 各維度防禦佔比 (贏牌貢獻度):")
    for i in range(5):
        print(f"   {sources[i]}: {contrib[i]:.1f}%")
        
    print(f"\n⏱️ 測評總耗時: {time.time()-t0:.1f} 秒")
