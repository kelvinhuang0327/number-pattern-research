#!/usr/bin/env python3
"""
2注 vs 3注可行性研究 + 冷號增強策略回測
目標: 測試新策略是否能在歷史上產生 Edge > 0
"""
import sys, os
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager

db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))

BASELINES = {1: 3.87, 2: 7.59, 3: 11.17}

def fourier_scores(hist, window=500):
    """Return dict of {num: fourier_score}"""
    h_slice = hist[-window:] if len(hist) >= window else hist
    w = len(h_slice)
    max_num = 38
    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= max_num:
                bitstreams[n][idx] = 1
    scores = {}
    for n in range(1, max_num + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            scores[n] = 0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            scores[n] = 0
            continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores

def cold_scores(hist, window=50):
    """Return dict of {num: cold_score} (higher = colder)"""
    recent = hist[-window:] if len(hist) >= window else hist
    expected = len(recent) * 6 / 38
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    scores = {}
    for n in range(1, 39):
        deviation = freq.get(n, 0) - expected
        scores[n] = -deviation  # Negative deviation = high cold score
    return scores

def gap_ratio_scores(hist):
    """Return dict of {num: gap_ratio_score}"""
    scores = {}
    for n in range(1, 39):
        appearances = [i for i, d in enumerate(hist) if n in d['numbers']]
        if len(appearances) < 5:
            scores[n] = 0
            continue
        gaps_ = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
        avg_gap = np.mean(gaps_)
        current_gap = len(hist) - appearances[-1]
        ratio = current_gap / avg_gap if avg_gap > 0 else 0
        # Score peaks at ratio = 1.0 (due)
        scores[n] = 1.0 / (abs(ratio - 1.0) + 0.5)
    return scores

# ============================================================
# Strategy 1: Fourier Rhythm (current 2-bet) — baseline
# ============================================================
def strategy_fourier_2bet(hist):
    fs = fourier_scores(hist)
    ranked = sorted(fs.items(), key=lambda x: -x[1])
    bet1 = sorted([n for n, _ in ranked[:6]])
    bet2 = sorted([n for n, _ in ranked[6:12]])
    return [bet1, bet2]

# ============================================================
# Strategy 2: Fourier + Cold Hybrid 2-bet (NEW)
# ============================================================
def strategy_fourier_cold_2bet(hist):
    fs = fourier_scores(hist)
    cs = cold_scores(hist, window=50)
    
    # Bet 1: Fourier top 6 (unchanged)
    f_ranked = sorted(fs.items(), key=lambda x: -x[1])
    bet1 = sorted([n for n, _ in f_ranked[:6]])
    
    # Bet 2: Cold numbers NOT in bet1
    used = set(bet1)
    remaining = {n: cs[n] for n in range(1, 39) if n not in used}
    c_ranked = sorted(remaining.items(), key=lambda x: -x[1])
    bet2 = sorted([n for n, _ in c_ranked[:6]])
    
    return [bet1, bet2]

# ============================================================
# Strategy 3: Fourier + Cold + GapRatio 3-bet (NEW)
# ============================================================
def strategy_hybrid_3bet(hist):
    fs = fourier_scores(hist)
    cs = cold_scores(hist, window=50)
    gs = gap_ratio_scores(hist)
    
    # Bet 1: Fourier top 6
    f_ranked = sorted(fs.items(), key=lambda x: -x[1])
    bet1 = sorted([n for n, _ in f_ranked[:6]])
    used = set(bet1)
    
    # Bet 2: Cold numbers
    remaining = {n: cs[n] for n in range(1, 39) if n not in used}
    c_ranked = sorted(remaining.items(), key=lambda x: -x[1])
    bet2 = sorted([n for n, _ in c_ranked[:6]])
    used |= set(bet2)
    
    # Bet 3: Gap ratio
    remaining2 = {n: gs[n] for n in range(1, 39) if n not in used}
    g_ranked = sorted(remaining2.items(), key=lambda x: -x[1])
    bet3 = sorted([n for n, _ in g_ranked[:6]])
    
    return [bet1, bet2, bet3]

# ============================================================
# Strategy 4: Comprehensive Score 2-bet (NEW)
# ============================================================
def strategy_comprehensive_2bet(hist):
    fs = fourier_scores(hist)
    cs = cold_scores(hist, window=50)
    gs = gap_ratio_scores(hist)
    
    # Weighted combination
    combined = {}
    for n in range(1, 39):
        combined[n] = fs.get(n, 0) * 0.4 + cs.get(n, 0) * 0.3 + gs.get(n, 0) * 0.3
    
    ranked = sorted(combined.items(), key=lambda x: -x[1])
    bet1 = sorted([n for n, _ in ranked[:6]])
    bet2 = sorted([n for n, _ in ranked[6:12]])
    return [bet1, bet2]

# ============================================================
# Strategy 5: Comprehensive Score 3-bet (NEW)
# ============================================================
def strategy_comprehensive_3bet(hist):
    fs = fourier_scores(hist)
    cs = cold_scores(hist, window=50)
    gs = gap_ratio_scores(hist)
    
    combined = {}
    for n in range(1, 39):
        combined[n] = fs.get(n, 0) * 0.4 + cs.get(n, 0) * 0.3 + gs.get(n, 0) * 0.3
    
    ranked = sorted(combined.items(), key=lambda x: -x[1])
    bet1 = sorted([n for n, _ in ranked[:6]])
    bet2 = sorted([n for n, _ in ranked[6:12]])
    bet3 = sorted([n for n, _ in ranked[12:18]])
    return [bet1, bet2, bet3]

# ============================================================
# Strategy 6: Cold priority + Fourier supplement 2-bet
# ============================================================
def strategy_cold_first_2bet(hist):
    cs = cold_scores(hist, window=100)
    fs = fourier_scores(hist)
    
    # Bet 1: Top 6 coldest
    c_ranked = sorted(cs.items(), key=lambda x: -x[1])
    bet1 = sorted([n for n, _ in c_ranked[:6]])
    used = set(bet1)
    
    # Bet 2: Fourier top 6 not in bet1
    remaining = {n: fs[n] for n in range(1, 39) if n not in used}
    f_ranked = sorted(remaining.items(), key=lambda x: -x[1])
    bet2 = sorted([n for n, _ in f_ranked[:6]])
    
    return [bet1, bet2]

# ============================================================
# Backtest all strategies
# ============================================================
def backtest(predict_func, test_periods, n_bets):
    m3_plus = 0
    total = 0
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            continue
        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])
        
        try:
            bets = predict_func(hist)
            hit = any(len(set(b) & actual) >= 3 for b in bets)
            if hit:
                m3_plus += 1
            total += 1
        except:
            continue
    
    rate = m3_plus / total * 100 if total > 0 else 0
    baseline = BASELINES[n_bets]
    edge = rate - baseline
    return {'m3_plus': m3_plus, 'total': total, 'rate': rate, 'edge': edge, 'baseline': baseline}

strategies = [
    ("Fourier Rhythm 2注 (current)", strategy_fourier_2bet, 2),
    ("Fourier+Cold 2注 (NEW)", strategy_fourier_cold_2bet, 2),
    ("Cold-First+Fourier 2注 (NEW)", strategy_cold_first_2bet, 2),
    ("Comprehensive 2注 (NEW)", strategy_comprehensive_2bet, 2),
    ("Hybrid F+C+G 3注 (NEW)", strategy_hybrid_3bet, 3),
    ("Comprehensive 3注 (NEW)", strategy_comprehensive_3bet, 3),
]

print("=" * 80)
print("  2注 vs 3注 策略可行性回測 (500期)")
print("=" * 80)
print()

for name, func, n_bets in strategies:
    r = backtest(func, 500, n_bets)
    status = "✅" if r['edge'] > 0 else "❌"
    print(f"  {status} {name}")
    print(f"     M3+: {r['m3_plus']}/{r['total']} ({r['rate']:.2f}%) | 基準: {r['baseline']:.2f}% | Edge: {r['edge']:+.2f}%")
    print()

# 3-tier validation for promising strategies
print("=" * 80)
print("  三窗口驗證 (150/500/1500)")
print("=" * 80)
print()

for name, func, n_bets in strategies:
    results = {}
    for periods in [150, 500, 1500]:
        try:
            r = backtest(func, periods, n_bets)
            results[periods] = r
        except:
            results[periods] = None
    
    edges = []
    line = f"  {name}:"
    for p in [150, 500, 1500]:
        r = results.get(p)
        if r:
            edges.append(r['edge'])
            line += f"  {p}p={r['edge']:+.2f}%"
        else:
            line += f"  {p}p=ERR"
    
    if all(e > 0 for e in edges):
        line += "  → ✅ STABLE"
    elif edges and edges[-1] > 0:
        line += "  → ⚠️ PARTIAL"
    else:
        line += "  → ❌ INEFFECTIVE"
    print(line)

print()

# === For draw 016 specifically, what would each strategy have predicted? ===
print("=" * 80)
print("  各策略對 115000016 的預測結果")
print("=" * 80)
print()
actual_016 = {4, 10, 13, 24, 31, 35}
hist_016 = all_draws  # All data before 016

for name, func, n_bets in strategies:
    bets = func(hist_016)
    all_nums = set(n for b in bets for n in b)
    total_hits = len(all_nums & actual_016)
    m3 = any(len(set(b) & actual_016) >= 3 for b in bets)
    per_bet = [f"注{i+1}:{sorted(set(b) & actual_016)}({len(set(b) & actual_016)})" for i, b in enumerate(bets)]
    print(f"  {name}")
    print(f"    {' | '.join(per_bet)} | 合計覆蓋{len(all_nums)}號命中{total_hits} | M3+: {'YES' if m3 else 'NO'}")
    for i, b in enumerate(bets):
        print(f"    注{i+1}: {sorted(b)}")
    print()
