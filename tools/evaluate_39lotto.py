import sys
import os
import numpy as np
import time
import json
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.strategy_base import FeatureLibrary

def load_daily_cash_draws():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lottery_api', 'data', 'lottery_v2.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        SELECT draw, date, numbers 
        FROM draws 
        WHERE lottery_type='DAILY_539' 
        ORDER BY id ASC
    """)
    rows = c.fetchall()
    conn.close()
    
    draws = []
    for draw_id, date, nums_str in rows:
        try:
            nums = json.loads(nums_str)
            if len(nums) == 5 and all(1 <= n <= 39 for n in nums):
                draws.append(sorted(nums))
        except:
            continue
            
    return np.array(draws, dtype=np.int32)

# ==========================================
# 1. 39 樂合彩 (5/39) 原子信號
# ==========================================

def get_signal_zm(draws):
    # 39樂合彩 39個號碼，改為4區
    zonal_scores = FeatureLibrary.zonal_density_score(draws, window=10, zones=4)
    gap_mom_scores = FeatureLibrary.gap_momentum(draws)
    
    def norm(x):
        std = np.std(x)
        return (x - np.mean(x)) / std if std > 0 else x
        
    scores = norm(zonal_scores) * 1.5 + norm(gap_mom_scores) * 1.0
    return scores

def get_signal_ts(draws):
    phases, mags = FeatureLibrary.fourier_phase(draws, top_k=3)
    fourier_scores = np.zeros(49)
    for j in range(49):
        fourier_scores[j] = sum(mags[j, k] * max(0, np.cos(phases[j, k])) for k in range(3))
    
    def norm(x):
        std = np.std(x)
        return (x - np.mean(x)) / std if std > 0 else x
        
    return norm(fourier_scores)

def get_signal_markov(draws, window=30):
    if len(draws) < window: window = len(draws)
    markov_probs = FeatureLibrary.markov_transition(draws[-window:], order=1)
    last_draw_binary = np.zeros(49)
    for n in draws[-1]: last_draw_binary[n-1] = 1
    markov_scores = np.zeros(49)
    for j in range(49):
        prev_state = int(last_draw_binary[j])
        markov_scores[j] = markov_probs[j, prev_state]
        
    def norm(x):
        std = np.std(x)
        return (x - np.mean(x)) / std if std > 0 else x
        
    return norm(markov_scores)

def normalize_signal(s):
    std = np.std(s)
    if std == 0: return s
    return (s - np.mean(s)) / std

# ==========================================
# 2. 完美的 3 注防禦矩陣 (0% 重疊正交) - 39 樂合彩
# ==========================================

def generate_39_bets(draws):
    signals = [
        ("TS-Fourier (主頻譜)", normalize_signal(get_signal_ts(draws))),
        ("Markov (極端短期)", normalize_signal(get_signal_markov(draws))),
        ("Zonal Momentum (板塊均值)", normalize_signal(get_signal_zm(draws)))
    ]
    
    # 限制只有前 39 個號碼的分數
    for name, sig in signals:
        sig[39:] = -9999
        
    pools = [np.argsort(s)[::-1] for _, s in signals]
    bets = [[] for _ in range(3)]
    used = set()
    pt = [0] * 3
    
    while any(len(b) < 5 for b in bets):
        for i in range(3):
            if len(bets[i]) < 5:
                while pt[i] < 39:
                    idx = pools[i][pt[i]]
                    pt[i] += 1
                    if idx not in used:
                        bets[i].append(int(idx) + 1)
                        used.add(idx)
                        break
                        
    return [sorted(b) for b in bets], [name for name, _ in signals]

# ==========================================
# 3. 三窗口盲測 (Walk-forward Backtest) for 39 Lotto M2+
# ==========================================

def run_backtest_39(draws, windows=[150, 500, 1500]):
    total = len(draws)
    max_w = max(windows)
    
    if total < max_w + 1:
        max_w = total - 1
        windows = [w for w in windows if w <= max_w]
        
    if len(windows) == 0:
        return {}, [], []
        
    start_idx = total - max_w
    results = []
    
    for i in range(start_idx, total):
        train = draws[:i]
        actual = set(draws[i])
        bets, _ = generate_39_bets(train)
        
        hits = [len(set(b) & actual) for b in bets]
        joint_hit = max(hits)
        results.append((hits, joint_hit))
        
    target_results = {}
    for w in windows:
        w_results = results[-w:]
        joint_m2 = sum(1 for r in w_results if r[1] >= 2)
        joint_rate = joint_m2 / max(1, w)
        
        current_dd = 0
        max_dd = 0
        for r in w_results:
            if r[1] < 2:
                current_dd += 1
                max_dd = max(max_dd, current_dd)
            else:
                current_dd = 0
                
        target_results[w] = {
            'rate': joint_rate,
            'max_dd': max_dd
        }
        
    contrib = [0] * 3
    analyze_w = min(1500, len(results))
    for r in results[-analyze_w:]:
        for idx, hit in enumerate(r[0]):
            if hit >= 2: 
                contrib[idx] += 1
                
    total_wins = sum(1 for r in results[-analyze_w:] if r[1] >= 2)
    contrib_pct = [c / total_wins * 100 if total_wins > 0 else 0 for c in contrib]
        
    return target_results, contrib_pct, windows

# ==========================================
# EXECUTION
# ==========================================
if __name__ == "__main__":
    t0 = time.time()
    try:
         draws = load_daily_cash_draws()
    except Exception as e:
         print(f"Error loading Daily Cash data: {e}")
         sys.exit(1)
         
    if len(draws) < 150:
        print(f"Loaded {len(draws)} draws. Not enough data to run meaningful backtest. Need at least 150 draws.")
        sys.exit(0)

    print("==================================================")
    print("🛡️ 【39樂合彩 (5/39) 3 注無雙矩陣】 標準 OOS 回測")
    print("==================================================")
    
    bets, sources = generate_39_bets(draws)
    
    print("\n🔹 注碼分配 (下一期實戰推薦):")
    for i in range(3):
        print(f"   [注 {i+1}]: {bets[i]} ({sources[i]})")
        
    all_nums = sum(bets, [])
    assert len(all_nums) == 15 and len(set(all_nums)) == 15, "ERROR: Overlapping detected!"
        
    print(f"\n🔹 執行嚴苛三窗口 OOS 回測 (M2+ 二合勝率)...", flush=True)
    stats, contrib, valid_windows = run_backtest_39(draws, [150, 500, 1500])
    
    # 5/39 二合基礎機率
    # M2: 0.1039, M3: 0.0097, M4: 0.0003 -> P(>=2) = 0.1139 per ticket
    p_geq_2 = 0.1139
    base_m2_3bet = 1 - (1 - p_geq_2)**3  # ~ 0.3039 (30.39%)
    
    print(f"\n🔹 回測報告 (聯合 M2+ 二合勝率，理論獨立隨機值約 {base_m2_3bet*100:.2f}%):")
    for w in valid_windows:
        edge = (stats[w]['rate'] - base_m2_3bet) * 100
        print(f"   {w}p: {stats[w]['rate']*100:.2f}% (Edge: {edge:+.2f}%)")
        
    if 1500 in valid_windows:
        print(f"\n   最大連續槓龜 (Drawdown < M2, 1500p): {stats[1500]['max_dd']} 期")
    elif len(valid_windows) > 0:
        w_max = max(valid_windows)
        print(f"\n   最大連續槓龜 (Drawdown < M2, {w_max}p): {stats[w_max]['max_dd']} 期")
    
    print("\n🔹 各維度防禦佔比 (贏牌貢獻度):")
    for i in range(3):
        print(f"   {sources[i]}: {contrib[i]:.1f}%")
        
    print(f"\n⏱️ 測評總耗時: {time.time()-t0:.1f} 秒")
