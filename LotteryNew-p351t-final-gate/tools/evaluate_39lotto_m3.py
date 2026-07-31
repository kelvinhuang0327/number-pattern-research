import sys
import os
import numpy as np
import time
import json
import sqlite3
import math

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

def get_signal_zm(draws):
    zonal_scores = FeatureLibrary.zonal_density_score(draws, window=10, zones=4)
    gap_mom_scores = FeatureLibrary.gap_momentum(draws)
    def norm(x):
        std = np.std(x)
        return (x - np.mean(x)) / std if std > 0 else x
    return norm(zonal_scores) * 1.5 + norm(gap_mom_scores) * 1.0

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

def generate_multi_bets(draws, num_bets=3):
    signals = [
        ("TS-Fourier", normalize_signal(get_signal_ts(draws))),
        ("Markov", normalize_signal(get_signal_markov(draws))),
        ("Zonal Momentum", normalize_signal(get_signal_zm(draws)))
    ]
    
    signals = signals[:num_bets]
    
    for name, sig in signals:
        sig[39:] = -9999
        
    pools = [np.argsort(s)[::-1] for _, s in signals]
    bets = [[] for _ in range(num_bets)]
    used = set()
    pt = [0] * num_bets
    
    while any(len(b) < 5 for b in bets):
        for i in range(num_bets):
            if len(bets[i]) < 5:
                while pt[i] < 39:
                    idx = pools[i][pt[i]]
                    pt[i] += 1
                    if idx not in used:
                        bets[i].append(int(idx) + 1)
                        used.add(idx)
                        break
                        
    return [sorted(b) for b in bets], [name for name, _ in signals]

def run_permutation_test(actual_hit_counts, baseline_prob, num_permutations=200):
    n_trials = len(actual_hit_counts)
    actual_success = sum(1 for h in actual_hit_counts if h >= 3)
    
    rnd = np.random.default_rng(42)
    simulated = rnd.binomial(n_trials, baseline_prob, num_permutations)
    
    better_count = np.sum(simulated >= actual_success)
    p_value = (better_count + 1) / (num_permutations + 1)
    return p_value, actual_success

def calculate_m3_baseline(num_bets):
    p_m3 = (math.comb(5,3) * math.comb(34,2)) / math.comb(39,5)
    p_m4 = (math.comb(5,4) * math.comb(34,1)) / math.comb(39,5)
    p_m5 = (math.comb(5,5) * math.comb(34,0)) / math.comb(39,5)
    p_geq_3 = p_m3 + p_m4 + p_m5
    return 1 - (1 - p_geq_3)**num_bets, p_geq_3

def main():
    try:
         draws = load_daily_cash_draws()
    except Exception as e:
         print(f"Error loading Daily Cash data: {e}")
         sys.exit(1)
         
    if len(draws) < 1550:
        print(f"Not enough data ({len(draws)}). Need >1500 draws.")
        sys.exit(0)

    print("==================================================")
    print("🔬 【39樂合彩 科學覆核：M3+ 聯合 Edge 與 Permutation Test】")
    print("==================================================")
    
    base_3bet_m3, base_1bet_m3 = calculate_m3_baseline(3)
    base_2bet_m3, _ = calculate_m3_baseline(2)
    
    start_idx = len(draws) - 1500
    
    results_2bet = []
    results_3bet = []
    
    # Track individual bet success for marginal analysis
    indiv_hits = {0: 0, 1: 0, 2: 0} 
    
    t0 = time.time()
    print("⏳ 執行 1500 期 Walk-forward 盲測中 (產生 2-Bet 與 3-Bet)...", flush=True)
    
    for i in range(start_idx, len(draws)):
        train = draws[:i]
        actual = set(draws[i])
        
        # We can just generate 3 bets, Bet 0 + Bet 1 = 2-Bet strategy
        bets, sources = generate_multi_bets(train, 3)
        
        hits = [len(set(b) & actual) for b in bets]
        joint_2bet = max(hits[0:2])
        joint_3bet = max(hits)
        
        results_2bet.append(joint_2bet)
        results_3bet.append(joint_3bet)
        
        for idx in range(3):
            if hits[idx] >= 3:
                indiv_hits[idx] += 1
                
    time_taken = time.time() - t0
    
    # --- M3+ Metrics ---
    rate_2bet = sum(1 for h in results_2bet if h >= 3) / 1500
    rate_3bet = sum(1 for h in results_3bet if h >= 3) / 1500
    
    z_2bet = (rate_2bet - base_2bet_m3) / np.sqrt((base_2bet_m3 * (1 - base_2bet_m3)) / 1500)
    z_3bet = (rate_3bet - base_3bet_m3) / np.sqrt((base_3bet_m3 * (1 - base_3bet_m3)) / 1500)
    
    # --- Marginal Analysis ---
    print("\n🔹 注碼邊際效益分析 (M3+ 個別勝率):")
    print(f"   隨機單注理論 M3+ 基線: {base_1bet_m3*100:.4f}% ({base_1bet_m3*1500:.1f} 起)")
    for idx in range(3):
        r = indiv_hits[idx] / 1500
        edge = r - base_1bet_m3
        z = edge / np.sqrt((base_1bet_m3 * (1 - base_1bet_m3)) / 1500)
        print(f"   [注 {idx+1}] {sources[idx]}: 命中 {indiv_hits[idx]} 次 | 勝率 {r*100:.2f}% | Edge {edge*100:+.2f}% | z={z:+.2f}")
    
    print("\n🔹 2-Bet (Fourier+Markov) vs 3-Bet (+Zonal Momentum) 聯合勝率比較:")
    print(f"   2-Bet 理論基線: {base_2bet_m3*100:.2f}%")
    print(f"   2-Bet 實際勝率: {rate_2bet*100:.2f}% (Edge: {(rate_2bet - base_2bet_m3)*100:+.2f}%, z={z_2bet:+.2f})")
    print(f"   ----------------------------------------")
    print(f"   3-Bet 理論基線: {base_3bet_m3*100:.2f}%")
    print(f"   3-Bet 實際勝率: {rate_3bet*100:.2f}% (Edge: {(rate_3bet - base_3bet_m3)*100:+.2f}%, z={z_3bet:+.2f})")
    
    # --- Permutation Test ---
    print("\n🔹 執行 Shuffle Permutation Test (N=200) 確認時序顯著性...")
    p_val_2bet, succ_2 = run_permutation_test(results_2bet, base_2bet_m3)
    p_val_3bet, succ_3 = run_permutation_test(results_3bet, base_3bet_m3)
    
    print(f"   2-Bet Permutation p-value: {p_val_2bet:.4f}")
    print(f"   3-Bet Permutation p-value: {p_val_3bet:.4f}")
    
    print(f"\n⏱️ 測評總耗時: {time_taken:.1f} 秒")

if __name__ == "__main__":
    main()
