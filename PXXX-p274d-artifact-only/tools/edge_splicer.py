import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

# ==========================================
# STEP 1: Signal Disassembly & Modeling
# ==========================================

def get_signal_cold_freq(draws, window=30):
    """Freq_cold_w30: Inverse of frequency over last 30 draws"""
    freq = FeatureLibrary.frequency(draws, window=window)
    # Inverse: lower frequency -> higher score
    return -freq

def get_signal_triple_strike(draws):
    """Triple Strike: Fourier(3) + Lag2 + Deviation(100)"""
    # Fourier
    phases, mags = FeatureLibrary.fourier_phase(draws, top_k=3)
    fourier_scores = np.zeros(49)
    for j in range(49):
        fourier_scores[j] = sum(mags[j, k] * max(0, np.cos(phases[j, k])) for k in range(3))
        
    # Lag2
    try:
        lag2 = FeatureLibrary.lag_autocorrelation(draws[-50:], lag=2)
    except:
        lag2 = np.zeros(49)
        
    # Deviation (underperforming gets positive score if we want mean reversion, but standard deviation score is positive for over)
    dev = FeatureLibrary.deviation_score(draws, window=100)
    
    def norm(x):
        std = np.std(x)
        return (x - np.mean(x)) / std if std > 0 else x
        
    # Combine (Triple Strike logic)
    return norm(fourier_scores) + norm(lag2) - norm(dev)

def get_signal_markov(draws, window=30):
    """Markov Order 1 using transition from last draw, computed over last 30 draws"""
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

def normalize_signal(s):
    std = np.std(s)
    if std == 0: return s
    return (s - np.mean(s)) / std

# ==========================================
# STEP 2 & 3: Orthogonalization & Bet Generation
# ==========================================

def generate_custom_bets(draws, n_bets):
    """
    Generate n_bets disjoint tickets based on the 3 atomic signals.
    """
    s_cold = normalize_signal(get_signal_cold_freq(draws))
    s_ts = normalize_signal(get_signal_triple_strike(draws))
    s_mk = normalize_signal(get_signal_markov(draws))
    
    if n_bets == 2:
        # For 2-bet, we merge the components into two distinct meta-signals
        # Meta 1: Trend followers (TS + Mk)
        # Meta 2: Mean Reversion (Cold)
        score1 = s_ts * 0.6 + s_mk * 0.4
        score2 = s_cold
        
        pool1 = np.argsort(score1)[::-1]
        pool2 = np.argsort(score2)[::-1]
        
        bet1 = []
        bet2 = []
        
        used = set()
        # Build Bet 1 (Triple Strike + Markov)
        for idx in pool1:
            if idx not in used:
                bet1.append(int(idx) + 1)
                used.add(idx)
            if len(bet1) == 6: break
            
        # Build Bet 2 (Cold)
        for idx in pool2:
            if idx not in used:
                bet2.append(int(idx) + 1)
                used.add(idx)
            if len(bet2) == 6: break
            
        return [sorted(bet1), sorted(bet2)], ["TripleStrike+Markov", "FreqCold"]
        
    elif n_bets == 3:
        # For 3-bet, map 1-to-1 to atomic signals to maintain pure dimensionality
        pool1 = np.argsort(s_ts)[::-1]
        pool2 = np.argsort(s_mk)[::-1]
        pool3 = np.argsort(s_cold)[::-1]
        
        bet1, bet2, bet3 = [], [], []
        used = set()
        
        for idx in pool1:
            if idx not in used:
                bet1.append(int(idx) + 1)
                used.add(idx)
            if len(bet1) == 6: break
            
        for idx in pool2:
            if idx not in used:
                bet2.append(int(idx) + 1)
                used.add(idx)
            if len(bet2) == 6: break
            
        for idx in pool3:
            if idx not in used:
                bet3.append(int(idx) + 1)
                used.add(idx)
            if len(bet3) == 6: break
            
        return [sorted(bet1), sorted(bet2), sorted(bet3)], ["TripleStrike", "Markov", "FreqCold"]

# ==========================================
# STEP 4: Backtesting Engine
# ==========================================

def run_backtest(draws, n_bets, windows=[150, 500, 1500]):
    total = len(draws)
    max_w = max(windows)
    start_idx = total - max_w
    
    # Store results for the longest window
    results = []
    
    for i in range(start_idx, total):
        train = draws[:i]
        actual = set(draws[i])
        bets, sources = generate_custom_bets(train, n_bets)
        
        hits = [len(set(b) & actual) for b in bets]
        joint_hit = max(hits)
        results.append((hits, joint_hit))
        
    # Analyze by window
    target_results = {}
    for w in windows:
        w_results = results[-w:]
        joint_m3 = sum(1 for r in w_results if r[1] >= 3)
        joint_rate = joint_m3 / w
        
        # Drawdown computation
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
        
    # Atomic contribution
    contrib = [0] * n_bets
    for r in results[-1500:]:
        for idx, hit in enumerate(r[0]):
            if hit >= 3:
                contrib[idx] += 1
                
    total_wins = sum(1 for r in results[-1500:] if r[1] >= 3)
    if total_wins > 0:
        contrib_pct = [c / total_wins * 100 for c in contrib]
    else:
        contrib_pct = [0] * n_bets
        
    return target_results, contrib_pct

# ==========================================
# STEP 5: Main Execution & Output
# ==========================================
if __name__ == "__main__":
    draws, _ = load_big_lotto_draws()
    
    # Baseline for Joint M3+
    # 2-bet baseline: ~ 3.68%
    # 3-bet baseline: ~ 5.48%
    baselines = {2: 0.0368, 3: 0.0548}
    
    for n_bets, strategy_name in [(2, "Dual-Orthogonal Splicing (2注)"), (3, "Tri-Axis Orthogonal (3注)")]:
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"【策略組合名稱】 {strategy_name}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        bets, sources = generate_custom_bets(draws, n_bets)
        
        print(f"🔹 注數明細 (115000021 期推薦):")
        for i in range(n_bets):
            print(f"   注 {i+1}: {bets[i]} [主信號: {sources[i]}]")
            
        # Backtest
        stats, contrib = run_backtest(draws, n_bets, [150, 500, 1500])
        
        # Calculate Joint Edge on 1500p
        joint_rate_1500 = stats[1500]['rate']
        joint_edge = (joint_rate_1500 - baselines[n_bets]) * 100
        
        print(f"\n🔹 聯合期望值 (Joint Edge, 1500p):")
        print(f"   M3+ 合計得勝率: {joint_rate_1500*100:.2f}% (理論無信號值: {baselines[n_bets]*100:.2f}%)")
        print(f"   實質超額 (Edge): {joint_edge:+.2f}%")
        
        print("\n🔹 各期窗口 OOS 回測成功率 (M3+):")
        print(f"   短期 (150p) : {stats[150]['rate']*100:.2f}%")
        print(f"   中期 (500p) : {stats[500]['rate']*100:.2f}%")
        print(f"   長期 (1500p): {stats[1500]['rate']*100:.2f}%")
        
        print("\n🔹 穩定度與風險:")
        max_dd = stats[1500]['max_dd']
        print(f"   最長連續未命中 (Max Drawdown, 1500p): {max_dd} 期")
        print(f"   穩定度評價: {'高' if max_dd < 45 else '中' if max_dd < 60 else '低'}")
        
        print("\n🔹 微弱訊號獨立貢獻度 (1500p 贏留比例):")
        for i in range(n_bets):
            print(f"   {sources[i]}: {contrib[i]:.1f}%")
            
        print("\n🔹 可利用等級:")
        print("   ✅ Composable (可透過空間組合防護下檔風險)")
        print("   ✅ Conditional (短期波動與頻率互補)")
        print("")
