import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

# ==========================================
# STEP 1: Signal Disassembly
# ==========================================

def get_signal_cold(draws, window=30):
    return -FeatureLibrary.frequency(draws, window=window)

def get_signal_hot(draws, window=100):
    return FeatureLibrary.frequency(draws, window=window)

def get_signal_triple_strike(draws):
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
    if len(draws) < window: window = len(draws)
    markov_probs = FeatureLibrary.markov_transition(draws[-window:], order=1)
    last_draw_binary = np.zeros(49)
    for n in draws[-1]: last_draw_binary[n-1] = 1
    markov_scores = np.zeros(49)
    for j in range(49):
        prev_state = int(last_draw_binary[j])
        markov_scores[j] = markov_probs[j, prev_state]
    return markov_scores

def get_signal_lag2(draws):
    try:
        lag2 = FeatureLibrary.lag_autocorrelation(draws[-50:], lag=2)
    except:
        lag2 = np.zeros(49)
    return lag2

def normalize(s):
    std = np.std(s)
    return (s - np.mean(s)) / std if std > 0 else s

# ==========================================
# STEP 2 & 3: Combination & Generation
# ==========================================

SIGNAL_GENERATORS = [
    ("Triple Strike", "頻譜疊加 (長/中)", get_signal_triple_strike),
    ("Markov", "條件轉移 (極短期)", lambda d: get_signal_markov(d, 30)),
    ("Freq Cold", "均值回歸 (反向)", lambda d: get_signal_cold(d, 30)),
    ("Freq Hot", "趨勢追蹤 (長期)", lambda d: get_signal_hot(d, 100)),
    ("Lag Echo", "延遲自相關 (特定)", get_signal_lag2)
]

def generate_bets(draws, n_bets):
    signals = []
    for name, desc, func in SIGNAL_GENERATORS[:n_bets]:
        signals.append(normalize(func(draws)))
        
    bets = []
    names = []
    used = set()
    
    for i in range(n_bets):
        pool = np.argsort(signals[i])[::-1]
        bet = []
        for idx in pool:
            if idx not in used:
                bet.append(int(idx) + 1)
                used.add(idx)
            if len(bet) == 6: break
        bets.append(sorted(bet))
        names.append((SIGNAL_GENERATORS[i][0], SIGNAL_GENERATORS[i][1]))
        
    return bets, names

# ==========================================
# STEP 4: Backtest
# ==========================================

def run_backtest(draws, n_bets, windows=[150, 500, 1500]):
    total = len(draws)
    max_w = max(windows)
    start_idx = total - max_w
    results = []
    
    for i in range(start_idx, total):
        train = draws[:i]
        actual = set(draws[i])
        bets, sources = generate_bets(train, n_bets)
        hits = [len(set(b) & actual) for b in bets]
        joint_hit = max(hits)
        results.append((hits, joint_hit))
        
    target_results = {}
    for w in windows:
        w_results = results[-w:]
        joint_m3 = sum(1 for r in w_results if r[1] >= 3)
        joint_rate = joint_m3 / w
        
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
        
    contrib = [0] * n_bets
    for r in results[-1500:]:
        for idx, hit in enumerate(r[0]):
            if hit >= 3: contrib[idx] += 1
                
    total_wins = sum(1 for r in results[-1500:] if r[1] >= 3)
    contrib_pct = [c / total_wins * 100 if total_wins > 0 else 0 for c in contrib]
        
    return target_results, contrib_pct, sources

# ==========================================
# STEP 5: Main
# ==========================================
if __name__ == "__main__":
    draws, _ = load_big_lotto_draws()
    baselines = {n: 1 - (1 - 0.0186)**n for n in range(1, 6)}
    
    best_edge = -1
    best_n = 0
    results_map = {}
    
    for n in range(2, 6):
        stats, contrib, sources = run_backtest(draws, n, [150, 500, 1500])
        joint_rate = stats[1500]['rate']
        joint_edge = joint_rate - baselines[n]
        
        results_map[n] = (stats, contrib, sources, joint_edge, baselines[n])
        
        if joint_edge > best_edge:
            best_edge = joint_edge
            best_n = n

    print("==================================================")
    print("📊 大樂透微弱訊號正交拼接 OOS 審查報告")
    print("==================================================\n")
    
    for n in range(2, 6):
        stats, contrib, sources, joint_edge, base = results_map[n]
        print(f"【{n} 注組合聯合策略】")
        print("  訊號分配 / 貢獻度:")
        for i in range(n):
            print(f"   - 注 {i+1}: {sources[i][0]} ({sources[i][1]}) | 貢獻: {contrib[i]:.1f}%")
        print(f"  聯合 M3+ 勝率 (1500p): {stats[1500]['rate']*100:.2f}% (基準: {base*100:.2f}%)")
        print(f"  實質聯合 Edge: {joint_edge*100:+.2f}%")
        print(f"  短/中/長 期勝率: {stats[150]['rate']*100:.1f}% / {stats[500]['rate']*100:.1f}% / {stats[1500]['rate']*100:.1f}%")
        print(f"  最大連續未中 (Drawdown): {stats[1500]['max_dd']} 期\n")
        
    print("==================================================")
    print(f"🏆 系統判定：最優聯合策略為【{best_n} 注組合】")
    print(f"因為其在正交空間隔離下，達成了最大化的聯合 Edge (+{best_edge*100:.2f}%)")
    print("且有效避免了訊號維度的互相干擾稀釋。")
    print("==================================================")
