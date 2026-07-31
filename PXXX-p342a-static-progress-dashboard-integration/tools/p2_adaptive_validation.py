#!/usr/bin/env python3
"""
P2 延續: 自適應策略三窗口驗證 + 10種子穩定性
"""
import sys, os
import numpy as np
from collections import Counter, defaultdict
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager

db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))

MAX_NUM = 38
PICK = 6
BASELINE_3 = 11.17

def compute_features(draws, idx, window=100):
    if idx < window + 5:
        return None
    hist = draws[idx - window:idx]
    freq = Counter()
    for d in hist:
        for n in d['numbers']:
            freq[n] += 1
    expected = window * PICK / MAX_NUM
    std_freq = np.std([freq.get(n, 0) for n in range(1, MAX_NUM + 1)])
    cold_threshold = expected - std_freq
    n_cold_pool = sum(1 for n in range(1, MAX_NUM + 1) if freq.get(n, 0) < cold_threshold)
    cold_deviations = [freq.get(n, 0) - expected for n in range(1, MAX_NUM + 1) if freq.get(n, 0) < cold_threshold]
    avg_cold_dev = np.mean(cold_deviations) if cold_deviations else 0
    recent5 = draws[idx-5:idx]
    cold_in_recent = 0
    for d in recent5:
        for n in d['numbers']:
            if freq.get(n, 0) < cold_threshold:
                cold_in_recent += 1
    cold_ratio_recent = cold_in_recent / (5 * PICK)
    max_gap = 0
    for n in range(1, MAX_NUM + 1):
        for j in range(idx-1, max(0, idx-100), -1):
            if n in draws[j]['numbers']:
                gap = idx - j
                if gap > max_gap:
                    max_gap = gap
                break
    return {
        'n_cold_pool': n_cold_pool,
        'avg_cold_dev': avg_cold_dev,
        'cold_ratio_recent': cold_ratio_recent,
        'max_gap': max_gap,
    }

def cold_alert_classifier(draws, idx):
    feats = compute_features(draws, idx, window=100)
    if feats is None:
        return 0.0
    score = 0.0
    if feats['n_cold_pool'] >= 12:
        score += 0.3
    elif feats['n_cold_pool'] >= 10:
        score += 0.15
    if feats['avg_cold_dev'] < -5:
        score += 0.25
    elif feats['avg_cold_dev'] < -4:
        score += 0.1
    if feats['cold_ratio_recent'] > 0.3:
        score += 0.2
    elif feats['cold_ratio_recent'] > 0.2:
        score += 0.1
    if feats['max_gap'] > 30:
        score += 0.15
    return min(score, 1.0)

def get_fourier_rank(hist, window=500):
    h_slice = hist[-window:] if len(hist) >= window else hist
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx_j, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM:
                bitstreams[n][idx_j] = 1
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = bitstreams[n]
        if sum(bh) < 2: continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx_f = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx_f]
        if freq_val == 0: continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores)[::-1]

# ---- Strategies ----

def strategy_pp3(hist):
    f_rank = get_fourier_rank(hist)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0: idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())
    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0: idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())
    exclude = set(bet1) | set(bet2)
    if len(hist) >= 2:
        echo_nums = [n for n in hist[-2]['numbers'] if n <= 38 and n not in exclude]
    else:
        echo_nums = []
    recent = hist[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    remaining = [n for n in range(1, 39) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq.get(x, 0))
    bet3 = sorted((echo_nums + remaining)[:6])
    return [bet1, bet2, bet3]

def strategy_adaptive(hist):
    f_rank = get_fourier_rank(hist)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0: idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())
    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0: idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())
    exclude = set(bet1) | set(bet2)
    
    alert = cold_alert_classifier(hist, len(hist)) if len(hist) >= 200 else 0
    
    if alert >= 0.4:
        # Cold mode
        recent = hist[-100:] if len(hist) >= 100 else hist
        expected = len(recent) * PICK / MAX_NUM
        freq = Counter()
        for d in recent:
            for n in d['numbers']:
                freq[n] += 1
        remaining = [(n, freq.get(n, 0)) for n in range(1, 39) if n not in exclude]
        remaining.sort(key=lambda x: x[1])
        bet3 = sorted([n for n, _ in remaining[:6]])
    else:
        # PP3 Echo/Cold mode
        if len(hist) >= 2:
            echo_nums = [n for n in hist[-2]['numbers'] if n <= 38 and n not in exclude]
        else:
            echo_nums = []
        recent = hist[-100:]
        freq = Counter([n for d in recent for n in d['numbers']])
        remaining = [n for n in range(1, 39) if n not in exclude and n not in echo_nums]
        remaining.sort(key=lambda x: freq.get(x, 0))
        bet3 = sorted((echo_nums + remaining)[:6])
    
    return [bet1, bet2, bet3]

def backtest(predict_func, test_periods):
    m3_plus = 0
    total = 0
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 200:
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
    edge = rate - BASELINE_3
    z = (m3_plus/total - BASELINE_3/100) / np.sqrt(BASELINE_3/100 * (1 - BASELINE_3/100) / total) if total > 0 else 0
    return {'m3_plus': m3_plus, 'total': total, 'rate': rate, 'edge': edge, 'z': z}

# ============================================================
# Three-tier validation
# ============================================================
print("=" * 80)
print("  三窗口驗證: PP3 vs Adaptive")
print("=" * 80)

strategies = [
    ("PP3 (現行)", strategy_pp3),
    ("Adaptive (PP3+Cold切換)", strategy_adaptive),
]

print(f"\n  {'策略':<30} {'150p':>12} {'500p':>12} {'1500p':>12} {'判定':>12}")
print("  " + "─" * 82)

for name, func in strategies:
    results = {}
    for periods in [150, 500, 1500]:
        results[periods] = backtest(func, periods)
    
    edges = [results[p]['edge'] for p in [150, 500, 1500]]
    zs = [results[p]['z'] for p in [150, 500, 1500]]
    
    if all(e > 0 for e in edges):
        status = "✅ STABLE"
    elif edges[2] > 0:
        status = "⚠️ PARTIAL"
    else:
        status = "❌"
    
    line = f"  {name:<30}"
    for p in [150, 500, 1500]:
        r = results[p]
        line += f" {r['edge']:>+5.2f}%(z={r['z']:.1f})"
    line += f" {status}"
    print(line)

print()

# ============================================================
# 10-seed stability (deterministic check)
# ============================================================
print("=" * 80)
print("  確定性檢查 (策略是否包含隨機成分)")
print("=" * 80)

# Both strategies are deterministic (no random.seed involved)
# So 10-seed check should give variance = 0
print("  PP3 和 Adaptive 策略均為確定性 (無 random 成分)")
print("  10種子檢查: 方差 = 0 (不需要測試)")

print()

# ============================================================
# McNemar test: PP3 vs Adaptive
# ============================================================
print("=" * 80)
print("  McNemar 配對檢驗: PP3 vs Adaptive (1500期)")
print("=" * 80)

# Run both on same periods and compare
pp3_hits = []
adp_hits = []

for i in range(1500):
    target_idx = len(all_draws) - 1500 + i
    if target_idx < 200:
        pp3_hits.append(0)
        adp_hits.append(0)
        continue
    target = all_draws[target_idx]
    hist = all_draws[:target_idx]
    actual = set(target['numbers'])
    
    try:
        bets_pp3 = strategy_pp3(hist)
        hit_pp3 = 1 if any(len(set(b) & actual) >= 3 for b in bets_pp3) else 0
    except:
        hit_pp3 = 0
    
    try:
        bets_adp = strategy_adaptive(hist)
        hit_adp = 1 if any(len(set(b) & actual) >= 3 for b in bets_adp) else 0
    except:
        hit_adp = 0
    
    pp3_hits.append(hit_pp3)
    adp_hits.append(hit_adp)

# Build contingency table
a = sum(1 for p, a2 in zip(pp3_hits, adp_hits) if p == 1 and a2 == 1)  # Both hit
b = sum(1 for p, a2 in zip(pp3_hits, adp_hits) if p == 1 and a2 == 0)  # PP3 only
c = sum(1 for p, a2 in zip(pp3_hits, adp_hits) if p == 0 and a2 == 1)  # Adaptive only
d = sum(1 for p, a2 in zip(pp3_hits, adp_hits) if p == 0 and a2 == 0)  # Neither

print(f"  Contingency table:")
print(f"                    Adaptive HIT  Adaptive MISS")
print(f"    PP3 HIT            {a:>4}          {b:>4}")
print(f"    PP3 MISS           {c:>4}          {d:>4}")
print()
print(f"  PP3 total hits: {sum(pp3_hits)}")
print(f"  Adaptive total hits: {sum(adp_hits)}")
print(f"  Both hit: {a}")
print(f"  PP3 only: {b}")
print(f"  Adaptive only: {c}")
print(f"  Net improvement: {c - b} (Adaptive額外命中)")

if b + c > 0:
    chi2 = (abs(b - c) - 1)**2 / (b + c)
    from scipy.stats import chi2 as chi2_dist
    p_val = 1 - chi2_dist.cdf(chi2, df=1)
    print(f"  McNemar χ²={chi2:.3f}, p={p_val:.4f} {'★顯著' if p_val < 0.05 else '不顯著'}")
else:
    print("  b+c=0, 無法計算McNemar")

print()
print("═" * 80)
print("  最終結論")
print("═" * 80)
print()
print("  如果 Adaptive Edge > PP3 Edge 且 三窗口全正:")
print("  → 建議採納 Adaptive 策略作為威力彩 3注首推")
print("  否則:")
print("  → 維持 PP3 作為 3注首推，Adaptive 作為備選")
