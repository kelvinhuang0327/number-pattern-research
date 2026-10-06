#!/usr/bin/env python3
"""
P1: Fourier 2注 + Cold 第3注 的 3注策略回測
==============================================
目的: 驗證以下3注組合是否能通過三窗口驗證:
  注1: Fourier Top6 (不動)
  注2: Fourier 7-12 (不動)
  注3: Cold Top6 (偏差 w=50, 排除注1+注2)

對照組:
  - Fourier Rhythm 2注 (現行)
  - Power Precision 3注 (現行PP3: F2+Echo/Cold)
  - 新: Fourier 2注 + Cold 第3注
"""
import sys, os, time
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager

db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
print(f"Total draws: {len(all_draws)}")

BASELINES = {1: 3.87, 2: 7.59, 3: 11.17}

# ============================================================
# Helper functions
# ============================================================

def get_fourier_rank(hist, window=500):
    """Return sorted array of ball numbers by Fourier score (descending)"""
    h_slice = hist[-window:] if len(hist) >= window else hist
    w = len(h_slice)
    max_num = 38
    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= max_num:
                bitstreams[n][idx] = 1
    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores)[::-1]


def get_cold_top(hist, exclude, window=50, pick=6):
    """Return top cold numbers not in exclude set"""
    recent = hist[-window:] if len(hist) >= window else hist
    expected = len(recent) * 6 / 38
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    candidates = [(n, freq.get(n, 0) - expected) for n in range(1, 39) if n not in exclude]
    candidates.sort(key=lambda x: x[1])  # Most negative deviation first
    return sorted([n for n, _ in candidates[:pick]])


# ============================================================
# Strategy A: Fourier Rhythm 2注 (現行)
# ============================================================
def strategy_fourier_2bet(hist):
    f_rank = get_fourier_rank(hist)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0: idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())
    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0: idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())
    return [bet1, bet2]


# ============================================================
# Strategy B: Power Precision 3注 (現行 PP3)
# ============================================================
def strategy_pp3(hist):
    f_rank = get_fourier_rank(hist)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0: idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())
    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0: idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())
    exclude = set(bet1) | set(bet2)
    # Echo + Cold (PP3 original logic)
    if len(hist) >= 2:
        echo_nums = [n for n in hist[-2]['numbers'] if n <= 38 and n not in exclude]
    else:
        echo_nums = []
    recent = hist[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    remaining = [n for n in range(1, 39) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq.get(x, 0))  # Coldest first
    bet3 = sorted((echo_nums + remaining)[:6])
    return [bet1, bet2, bet3]


# ============================================================
# Strategy C: Fourier 2注 + Cold 第3注 (NEW - 測試多個 cold_window)
# ============================================================
def make_f2_cold_strategy(cold_window):
    def strategy(hist):
        f_rank = get_fourier_rank(hist)
        idx_1 = 0
        while idx_1 < len(f_rank) and f_rank[idx_1] == 0: idx_1 += 1
        bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())
        idx_2 = idx_1 + 6
        while idx_2 < len(f_rank) and f_rank[idx_2] == 0: idx_2 += 1
        bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())
        exclude = set(bet1) | set(bet2)
        bet3 = get_cold_top(hist, exclude, window=cold_window, pick=6)
        return [bet1, bet2, bet3]
    return strategy


# ============================================================
# Backtest engine
# ============================================================
def backtest(predict_func, test_periods, n_bets):
    m3_plus = 0
    m3_per_bet = [0] * n_bets
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
            any_hit = False
            for bi, b in enumerate(bets[:n_bets]):
                if len(set(b) & actual) >= 3:
                    m3_per_bet[bi] += 1
                    any_hit = True
            if any_hit:
                m3_plus += 1
            total += 1
        except Exception as e:
            continue
    rate = m3_plus / total * 100 if total > 0 else 0
    baseline = BASELINES[n_bets]
    edge = rate - baseline
    per_bet_rates = [c/total*100 for c in m3_per_bet] if total > 0 else [0]*n_bets
    return {
        'm3_plus': m3_plus, 'total': total, 'rate': rate,
        'edge': edge, 'baseline': baseline,
        'per_bet': per_bet_rates
    }


def significance_test(m3_hits, total, baseline_rate):
    p0 = baseline_rate / 100
    p_hat = m3_hits / total
    se = np.sqrt(p0 * (1 - p0) / total)
    z = (p_hat - p0) / se if se > 0 else 0
    return z


# ============================================================
# Run all backtests
# ============================================================
print("=" * 80)
print("  P1: Fourier 2注 + Cold 第3注 三窗口回測")
print("=" * 80)
print()

strategies = [
    ("Fourier Rhythm 2注 (現行)", strategy_fourier_2bet, 2),
    ("Power Precision 3注 (現行PP3)", strategy_pp3, 3),
    ("F2+Cold(w=30) 3注", make_f2_cold_strategy(30), 3),
    ("F2+Cold(w=50) 3注", make_f2_cold_strategy(50), 3),
    ("F2+Cold(w=100) 3注", make_f2_cold_strategy(100), 3),
    ("F2+Cold(w=200) 3注", make_f2_cold_strategy(200), 3),
]

# Detailed three-tier validation
print("─" * 80)
print(f"{'策略':<30} {'150p Edge':>10} {'500p Edge':>10} {'1500p Edge':>10} {'判定':>12}")
print("─" * 80)

best_stable = None
best_edge = -999

for name, func, n_bets in strategies:
    results = {}
    for periods in [150, 500, 1500]:
        t0 = time.time()
        r = backtest(func, periods, n_bets)
        dt = time.time() - t0
        results[periods] = r

    edges = [results[p]['edge'] for p in [150, 500, 1500]]
    
    if all(e > 0 for e in edges):
        status = "✅ STABLE"
        if edges[2] > best_edge:
            best_edge = edges[2]
            best_stable = name
    elif edges[2] > 0:
        status = "⚠️ PARTIAL"
    elif edges[0] > 0 and edges[2] <= 0:
        status = "❌ SHORT_MOM"
    else:
        status = "❌ INEFFECTIVE"

    print(f"{name:<30} {edges[0]:>+9.2f}% {edges[1]:>+9.2f}% {edges[2]:>+9.2f}% {status:>12}")

print("─" * 80)
print()

# Detailed results for the best cold window
print("=" * 80)
print("  詳細結果 (1500期)")
print("=" * 80)
print()

for name, func, n_bets in strategies:
    r = backtest(func, 1500, n_bets)
    z = significance_test(r['m3_plus'], r['total'], r['baseline'])
    per_bet_str = " | ".join([f"注{i+1}={pb:.2f}%" for i, pb in enumerate(r['per_bet'])])
    print(f"  {name}")
    print(f"    M3+: {r['m3_plus']}/{r['total']} ({r['rate']:.2f}%) | 基準: {r['baseline']:.2f}% | Edge: {r['edge']:+.2f}% | z={z:.2f}")
    print(f"    各注: {per_bet_str}")
    
    # Marginal contribution of bet3 (for 3-bet strategies)
    if n_bets == 3:
        # Calculate 2-bet rate using only bet1+bet2
        m3_2bet = 0
        total_2bet = 0
        for i in range(1500):
            target_idx = len(all_draws) - 1500 + i
            if target_idx < 100:
                continue
            target = all_draws[target_idx]
            hist = all_draws[:target_idx]
            actual = set(target['numbers'])
            try:
                bets = func(hist)
                hit2 = any(len(set(b) & actual) >= 3 for b in bets[:2])
                if hit2:
                    m3_2bet += 1
                total_2bet += 1
            except:
                continue
        rate2 = m3_2bet / total_2bet * 100 if total_2bet > 0 else 0
        marginal = r['rate'] - rate2
        print(f"    注3邊際貢獻: +{marginal:.2f}% (2注M3+={rate2:.2f}% → 3注M3+={r['rate']:.2f}%)")
    print()

# Final verification on draw 115000016
print("=" * 80)
print("  各策略對 115000016 期的預測")
print("=" * 80)
actual_016 = {4, 10, 13, 24, 31, 35}
hist_016 = all_draws[:-1]  # Exclude 016 itself

for name, func, n_bets in strategies:
    bets = func(hist_016)
    all_nums = set(n for b in bets for n in b)
    total_hits = len(all_nums & actual_016)
    m3 = any(len(set(b) & actual_016) >= 3 for b in bets)
    details = []
    for i, b in enumerate(bets):
        hits = sorted(set(b) & actual_016)
        details.append(f"注{i+1}:{hits}({len(hits)})")
    print(f"  {name}: {' | '.join(details)} | 合計{total_hits} | M3+:{'YES' if m3 else 'NO'}")

print()
if best_stable:
    print(f"★ 三窗口最佳 STABLE 策略: {best_stable} (1500p Edge: {best_edge:+.2f}%)")
else:
    print("⚠️ 沒有策略通過三窗口驗證")
