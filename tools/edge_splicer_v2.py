import sys
import os
import numpy as np
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

# ==========================================
# 1. 提取原子特徵信號 (Atomic Signals)
# ==========================================

def get_signal_triple_strike(draws):
    """主攻注 1：Triple Strike (長期極端迴圈)"""
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
        
    return norm(fourier_scores) + norm(lag2) - norm(dev)

def get_signal_markov(draws, window=30):
    """快攻注 2：Markov (極度短期狀態轉移)"""
    if len(draws) < window:
        window = len(draws)
    markov_probs = FeatureLibrary.markov_transition(draws[-window:], order=1)
    
    last_draw_binary = np.zeros(49)
    for n in draws[-1]:
        last_draw_binary[n-1] = 1
        
    markov_scores = np.zeros(49)
    for j in range(49):
        prev_state = int(last_draw_binary[j])
        markov_scores[j] = markov_probs[j, prev_state]
        
    return markov_scores

def get_signal_zonal_momentum(draws):
    """防禦注 3：Zonal Density + Gap Momentum (非線性平庸區域)"""
    zonal_scores = FeatureLibrary.zonal_density_score(draws, window=10, zones=5)
    gap_mom_scores = FeatureLibrary.gap_momentum(draws)
    
    def norm(x):
        std = np.std(x)
        return (x - np.mean(x)) / std if std > 0 else x
        
    return norm(zonal_scores) * 1.5 + norm(gap_mom_scores) * 1.0

def normalize_signal(s):
    std = np.std(s)
    if std == 0: return s
    return (s - np.mean(s)) / std

# ==========================================
# 2. 完美防禦矩陣 (0% 重疊正交選號)
# ==========================================

def generate_tri_axis_bets(draws):
    """
    產生 3 注完美零重疊的 18 顆號碼
    """
    s_ts = normalize_signal(get_signal_triple_strike(draws))
    s_mk = normalize_signal(get_signal_markov(draws))
    s_zm = normalize_signal(get_signal_zonal_momentum(draws))
    
    # Sort signals descending to get priority pools
    pool_ts = np.argsort(s_ts)[::-1]
    pool_mk = np.argsort(s_mk)[::-1]
    pool_zm = np.argsort(s_zm)[::-1]
    
    bet_ts, bet_mk, bet_zm = [], [], []
    used = set()
    
    # Round-robin selection to ensure fairness across the 3 dimensions
    # We want 6 numbers for each
    pt_ts, pt_mk, pt_zm = 0, 0, 0
    
    while len(bet_ts) < 6 or len(bet_mk) < 6 or len(bet_zm) < 6:
        # TS turn
        if len(bet_ts) < 6:
            while pt_ts < 49:
                idx = pool_ts[pt_ts]
                pt_ts += 1
                if idx not in used:
                    bet_ts.append(int(idx) + 1)
                    used.add(idx)
                    break
                    
        # MK turn            
        if len(bet_mk) < 6:
            while pt_mk < 49:
                idx = pool_mk[pt_mk]
                pt_mk += 1
                if idx not in used:
                    bet_mk.append(int(idx) + 1)
                    used.add(idx)
                    break
                    
        # ZM turn
        if len(bet_zm) < 6:
            while pt_zm < 49:
                idx = pool_zm[pt_zm]
                pt_zm += 1
                if idx not in used:
                    bet_zm.append(int(idx) + 1)
                    used.add(idx)
                    break
                    
    return [sorted(bet_ts), sorted(bet_mk), sorted(bet_zm)], ["Triple Strike (週期突波)", "Markov w=30 (短期狀態)", "Zonal Momentum (板塊均值)"]

# ==========================================
# 3. 三窗口盲測 (Walk-forward Backtest)
# ==========================================

def run_backtest_tri_axis(draws, windows=[150, 500, 1500]):
    total = len(draws)
    max_w = max(windows)
    start_idx = total - max_w
    
    results = []
    
    for i in range(start_idx, total):
        train = draws[:i]
        actual = set(draws[i])
        bets, _ = generate_tri_axis_bets(train)
        
        hits = [len(set(b) & actual) for b in bets]
        joint_hit = max(hits)
        results.append((hits, joint_hit))
        
    target_results = {}
    for w in windows:
        w_results = results[-w:]
        joint_m3 = sum(1 for r in w_results if r[1] >= 3)
        joint_rate = joint_m3 / max(1, w)
        
        current_dd = 0
        max_dd = 0
        for r in w_results:
            if r[1] < 3:
                current_dd += 1
                max_dd = max(max_dd, current_dd)
            else:
                current_dd = 0
                
        target_results[w] = {
            'rate': joint_rate,
            'max_dd': max_dd
        }
        
    contrib = [0] * 3
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
    print("🛡️ 【神聖三聯星 (Tri-Axis v2.0)】 終極 3 注實戰測評")
    print("==================================================")
    
    bets, sources = generate_tri_axis_bets(draws)
    
    print("\n🔹 注碼分配 (下一期實戰推薦):")
    for i in range(3):
        print(f"   [注 {i+1}]: {bets[i]} ({sources[i]})")
        
    # Check overlapping
    all_nums = sum(bets, [])
    assert len(all_nums) == 18 and len(set(all_nums)) == 18, "ERROR: Overlapping detected!"
        
    print(f"\n🔹 執行嚴苛三窗口 OOS 回測 (150p/500p/1500p)...", flush=True)
    stats, contrib = run_backtest_tri_axis(draws, [150, 500, 1500])
    
    base_3 = 1 - (1 - 0.0186)**3
    edge_1500 = stats[1500]['rate'] - base_3
    
    print("\n🔹 回測報告:")
    print(f"   短期 (150p) : {stats[150]['rate']*100:.2f}%")
    print(f"   中期 (500p) : {stats[500]['rate']*100:.2f}%")
    print(f"   長期 (1500p): {stats[1500]['rate']*100:.2f}%  (理論隨機值: {base_3*100:.2f}%)")
    print(f"   => 聯合 Edge: {edge_1500*100:+.2f}%")
    print(f"\n   最大連續槓龜 (Drawdown): {stats[1500]['max_dd']} 期")
    
    print("\n🔹 各維度防禦佔比 (贏牌貢獻度):")
    for i in range(3):
        print(f"   {sources[i]}: {contrib[i]:.1f}%")
        
    print(f"\n⏱️ 測評總耗時: {time.time()-t0:.1f} 秒")
