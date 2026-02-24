#!/usr/bin/env python3
"""
P2: 冷號事件分類器 (Cold Cluster Classifier)
=============================================
目的: 
  1. 定義「冷號事件」— 開獎結果中冷號數量 >= 4
  2. 找出冷號事件的前置特徵 (precursor signals)
  3. 判斷是否可以「提前偵測」冷號集群期
  4. 如果可以，設計自動偵測機制

方法:
  - 冷號定義: 近 W 期頻率低於期望值 2σ 以下的號碼
  - 冷號事件: 開出 >= 4 個冷號的期
  - 前置特徵: 冷號事件前 1-5 期的各統計指標
"""
import sys, os
import numpy as np
from collections import Counter, defaultdict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager

db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
print(f"Total draws: {len(all_draws)}")

MAX_NUM = 38
PICK = 6

# ============================================================
# Step 1: Define cold numbers per draw
# ============================================================
def count_cold_numbers_in_draw(draws, target_idx, window=100):
    """Count how many of the drawn numbers are 'cold' based on prior history"""
    if target_idx < window + 1:
        return None, None
    
    hist = draws[target_idx - window:target_idx]
    target = draws[target_idx]
    
    # Calculate frequency in window
    freq = Counter()
    for d in hist:
        for n in d['numbers']:
            freq[n] += 1
    
    expected = window * PICK / MAX_NUM
    std_freq = np.std([freq.get(n, 0) for n in range(1, MAX_NUM + 1)])
    
    # Cold threshold: below expected - 1σ
    cold_threshold = expected - std_freq
    cold_nums = {n for n in range(1, MAX_NUM + 1) if freq.get(n, 0) < cold_threshold}
    
    # How many drawn numbers are cold?
    actual = set(target['numbers'])
    cold_in_draw = actual & cold_nums
    
    return len(cold_in_draw), cold_in_draw


# ============================================================
# Step 2: Scan all draws for cold events
# ============================================================
print("\n" + "=" * 80)
print("  Step 1: 掃描所有開獎的冷號事件分布")
print("=" * 80)

cold_counts = []
cold_events = []  # idx of draws with >= 4 cold numbers

for idx in range(200, len(all_draws)):
    cnt, cold_set = count_cold_numbers_in_draw(all_draws, idx, window=100)
    if cnt is not None:
        cold_counts.append(cnt)
        if cnt >= 4:
            cold_events.append(idx)

total_scanned = len(cold_counts)
cnt_dist = Counter(cold_counts)
print(f"  掃描期數: {total_scanned}")
print(f"  冷號數量分布 (window=100期):")
for k in sorted(cnt_dist.keys()):
    pct = cnt_dist[k] / total_scanned * 100
    bar = "█" * int(pct)
    print(f"    {k}個冷號: {cnt_dist[k]:>4}期 ({pct:>5.1f}%) {bar}")

print(f"\n  冷號集群事件 (>=4冷號): {len(cold_events)}期 ({len(cold_events)/total_scanned*100:.1f}%)")

# ============================================================
# Step 3: Pre-event analysis — what happens before cold events?
# ============================================================
print("\n" + "=" * 80)
print("  Step 2: 冷號事件的前置特徵分析")
print("=" * 80)

def compute_features(draws, idx, window=100):
    """Compute feature vector for a given draw index (using data before idx)"""
    if idx < window + 5:
        return None
    
    hist = draws[idx - window:idx]
    
    # F1: Number of cold numbers accumulated (偏差累積)
    freq = Counter()
    for d in hist:
        for n in d['numbers']:
            freq[n] += 1
    expected = window * PICK / MAX_NUM
    std_freq = np.std([freq.get(n, 0) for n in range(1, MAX_NUM + 1)])
    cold_threshold = expected - std_freq
    n_cold_pool = sum(1 for n in range(1, MAX_NUM + 1) if freq.get(n, 0) < cold_threshold)
    
    # F2: Average deviation of cold numbers (how cold are they?)
    cold_deviations = [freq.get(n, 0) - expected for n in range(1, MAX_NUM + 1) if freq.get(n, 0) < cold_threshold]
    avg_cold_dev = np.mean(cold_deviations) if cold_deviations else 0
    
    # F3: Recent trend — cold ratio in last 5 draws
    recent5 = draws[idx-5:idx]
    cold_in_recent = 0
    for d in recent5:
        for n in d['numbers']:
            if freq.get(n, 0) < cold_threshold:
                cold_in_recent += 1
    cold_ratio_recent = cold_in_recent / (5 * PICK)
    
    # F4: Zone imbalance in last 20 draws
    recent20 = draws[idx-20:idx]
    zone_freq = defaultdict(int)
    zones = {'Z1': range(1,11), 'Z2': range(11,21), 'Z3': range(21,31), 'Z4': range(31,39)}
    for d in recent20:
        for n in d['numbers']:
            for zn, zr in zones.items():
                if n in zr:
                    zone_freq[zn] += 1
    zone_vals = list(zone_freq.values())
    zone_imbalance = np.std(zone_vals)
    
    # F5: Sum volatility (std of sum over last 10 draws)
    recent10_sums = [sum(d['numbers']) for d in draws[idx-10:idx]]
    sum_volatility = np.std(recent10_sums)
    
    # F6: Max current gap among all numbers
    max_gap = 0
    for n in range(1, MAX_NUM + 1):
        for j in range(idx-1, max(0, idx-100), -1):
            if n in draws[j]['numbers']:
                gap = idx - j
                if gap > max_gap:
                    max_gap = gap
                break
    
    # F7: Entropy of last 30 draws
    recent30 = draws[idx-30:idx]
    freq30 = Counter()
    for d in recent30:
        for n in d['numbers']:
            freq30[n] += 1
    total30 = sum(freq30.values())
    entropy = -sum((c/total30) * np.log2(c/total30) for c in freq30.values() if c > 0)
    
    return {
        'n_cold_pool': n_cold_pool,
        'avg_cold_dev': avg_cold_dev,
        'cold_ratio_recent': cold_ratio_recent,
        'zone_imbalance': zone_imbalance,
        'sum_volatility': sum_volatility,
        'max_gap': max_gap,
        'entropy': entropy,
    }

# Compute features for cold events and normal events
cold_features = []
normal_features = []

for idx in range(200, len(all_draws)):
    feats = compute_features(all_draws, idx, window=100)
    if feats is None:
        continue
    
    cnt, _ = count_cold_numbers_in_draw(all_draws, idx, window=100)
    if cnt is not None and cnt >= 4:
        cold_features.append(feats)
    elif cnt is not None and cnt <= 1:
        normal_features.append(feats)

print(f"  冷號事件 (>=4冷): {len(cold_features)}期")
print(f"  正常事件 (<=1冷): {len(normal_features)}期")
print()

# Compare feature distributions
feature_names = ['n_cold_pool', 'avg_cold_dev', 'cold_ratio_recent', 
                 'zone_imbalance', 'sum_volatility', 'max_gap', 'entropy']
feature_desc = ['冷號池大小', '冷號平均偏差', '近5期冷號比率', 
                '區間不平衡', '和值波動', '最大gap', '號碼熵']

print(f"  {'特徵':<20} {'冷號事件':>12} {'正常事件':>12} {'差距':>8} {'方向':>8}")
print("  " + "─" * 62)

discriminative_features = []
for fname, fdesc in zip(feature_names, feature_desc):
    cold_vals = [f[fname] for f in cold_features]
    norm_vals = [f[fname] for f in normal_features]
    cold_mean = np.mean(cold_vals)
    norm_mean = np.mean(norm_vals)
    cold_std = np.std(cold_vals)
    norm_std = np.std(norm_vals)
    
    # Effect size (Cohen's d)
    pooled_std = np.sqrt((cold_std**2 + norm_std**2) / 2)
    cohen_d = (cold_mean - norm_mean) / pooled_std if pooled_std > 0 else 0
    direction = "↑冷號" if cold_mean > norm_mean else "↓冷號"
    
    effect = ""
    if abs(cohen_d) > 0.5:
        effect = " ★★"
        discriminative_features.append(fname)
    elif abs(cohen_d) > 0.2:
        effect = " ★"
        discriminative_features.append(fname)
    
    print(f"  {fdesc:<20} {cold_mean:>12.3f} {norm_mean:>12.3f} {cohen_d:>+7.3f} {direction:>8}{effect}")

print()

# ============================================================
# Step 4: Build simple classifier
# ============================================================
print("=" * 80)
print("  Step 3: 簡單冷號預警分類器")
print("=" * 80)

# Use discriminative features to build a threshold-based classifier
def cold_alert_classifier(draws, idx, window=100):
    """Simple rule-based cold event alert"""
    feats = compute_features(draws, idx, window)
    if feats is None:
        return 0.0
    
    score = 0.0
    
    # Rule 1: Large cold pool (>= 12 cold numbers available)
    if feats['n_cold_pool'] >= 12:
        score += 0.3
    elif feats['n_cold_pool'] >= 10:
        score += 0.15
    
    # Rule 2: Very cold average deviation
    if feats['avg_cold_dev'] < -5:
        score += 0.25
    elif feats['avg_cold_dev'] < -4:
        score += 0.1
    
    # Rule 3: Recent draws already showing cold numbers
    if feats['cold_ratio_recent'] > 0.3:
        score += 0.2
    elif feats['cold_ratio_recent'] > 0.2:
        score += 0.1
    
    # Rule 4: High max gap
    if feats['max_gap'] > 30:
        score += 0.15
    
    # Rule 5: Zone imbalance
    if feats['zone_imbalance'] > 5:
        score += 0.1
    
    return min(score, 1.0)


# Test classifier on all draws
print()
tp, fp, tn, fn = 0, 0, 0, 0
alert_threshold = 0.4

cold_alert_correct = 0
cold_alert_total = 0
normal_alert_false = 0
normal_total = 0

for idx in range(200, len(all_draws)):
    alert_score = cold_alert_classifier(all_draws, idx)
    cnt, _ = count_cold_numbers_in_draw(all_draws, idx, window=100)
    if cnt is None:
        continue
    
    is_cold_event = (cnt >= 4)
    is_alert = (alert_score >= alert_threshold)
    
    if is_cold_event and is_alert:
        tp += 1
    elif is_cold_event and not is_alert:
        fn += 1
    elif not is_cold_event and is_alert:
        fp += 1
    else:
        tn += 1

total_events = tp + fp + tn + fn
precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
accuracy = (tp + tn) / total_events * 100 if total_events > 0 else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

print(f"  分類器結果 (alert threshold={alert_threshold}):")
print(f"    True Positive:  {tp} (冷號事件+預警)")
print(f"    False Positive: {fp} (非冷號+誤報)")
print(f"    True Negative:  {tn} (非冷號+無警)")
print(f"    False Negative: {fn} (冷號事件+漏報)")
print(f"    Precision: {precision:.1f}%")
print(f"    Recall:    {recall:.1f}%")
print(f"    Accuracy:  {accuracy:.1f}%")
print(f"    F1 Score:  {f1:.1f}%")
print()

# Check multiple thresholds
print(f"  {'閾值':>6} {'Precision':>10} {'Recall':>8} {'F1':>6} {'TP':>5} {'FP':>5} {'FN':>5}")
print("  " + "─" * 50)
for threshold in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
    tp2, fp2, fn2 = 0, 0, 0
    for idx in range(200, len(all_draws)):
        alert_score = cold_alert_classifier(all_draws, idx)
        cnt, _ = count_cold_numbers_in_draw(all_draws, idx, window=100)
        if cnt is None:
            continue
        is_cold = (cnt >= 4)
        is_alert = (alert_score >= threshold)
        if is_cold and is_alert: tp2 += 1
        elif is_cold and not is_alert: fn2 += 1
        elif not is_cold and is_alert: fp2 += 1
    
    pr2 = tp2 / (tp2 + fp2) * 100 if (tp2 + fp2) > 0 else 0
    re2 = tp2 / (tp2 + fn2) * 100 if (tp2 + fn2) > 0 else 0
    f12 = 2 * pr2 * re2 / (pr2 + re2) if (pr2 + re2) > 0 else 0
    print(f"  {threshold:>6.1f} {pr2:>9.1f}% {re2:>7.1f}% {f12:>5.1f}% {tp2:>5} {fp2:>5} {fn2:>5}")

print()

# ============================================================
# Step 5: Test on 115000016
# ============================================================
print("=" * 80)
print("  Step 4: 115000016 期的冷號預警")
print("=" * 80)
target_idx = len(all_draws) - 1  # 016 is now last draw
alert = cold_alert_classifier(all_draws, target_idx)
feats = compute_features(all_draws, target_idx, window=100)
cnt, cold_set = count_cold_numbers_in_draw(all_draws, target_idx, window=100)

print(f"  冷號預警分數: {alert:.2f} {'(ALERT!)' if alert >= 0.4 else '(正常)'}")
print(f"  實際冷號數: {cnt} → {sorted(cold_set) if cold_set else 'N/A'}")
print(f"  特徵:")
for fname, fdesc in zip(feature_names, feature_desc):
    print(f"    {fdesc}: {feats[fname]:.3f}")

print()

# ============================================================
# Step 6: Backtest the adaptive strategy
# ============================================================
print("=" * 80)
print("  Step 5: 自適應策略回測 (alert時切換至Cold注)")
print("=" * 80)
print("  策略: alert >= 0.4 時用 F2+Cold(w=100), 否則用 PP3")
print()

from scipy.fft import fft as scipy_fft, fftfreq as scipy_fftfreq

def get_fourier_rank_func(hist, window=500):
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
        yf = scipy_fft(bh - np.mean(bh))
        xf = scipy_fftfreq(w, 1)
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


def strategy_adaptive_3bet(hist):
    """Adaptive: use Cold注 when cold alert, otherwise use PP3 Echo/Cold"""
    f_rank = get_fourier_rank_func(hist)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0: idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())
    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0: idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())
    exclude = set(bet1) | set(bet2)
    
    # Check cold alert
    # Note: We can only use features computed from hist (no leakage)
    alert = 0.0
    if len(hist) >= 200:
        alert = cold_alert_classifier(hist + [{'numbers': [], 'draw': '0', 'date': '0'}], len(hist))
        # Cheap trick: compute_features needs draws list up to idx, we use all of hist
        # Actually let's compute more correctly
    
    if alert >= 0.4:
        # Cold strategy for bet3
        recent = hist[-100:] if len(hist) >= 100 else hist
        expected = len(recent) * PICK / MAX_NUM
        freq = Counter()
        for d in recent:
            for n in d['numbers']:
                freq[n] += 1
        remaining = [(n, freq.get(n, 0)) for n in range(1, 39) if n not in exclude]
        remaining.sort(key=lambda x: x[1])  # Coldest first
        bet3 = sorted([n for n, _ in remaining[:6]])
    else:
        # PP3 Echo/Cold strategy for bet3
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


# Backtest adaptive strategy
BASELINES_3 = 11.17

# Count how many times each mode was used
cold_mode_count = 0
pp3_mode_count = 0

m3_plus = 0
total = 0
for i in range(1500):
    target_idx = len(all_draws) - 1500 + i
    if target_idx < 200:
        continue
    target = all_draws[target_idx]
    hist = all_draws[:target_idx]
    actual = set(target['numbers'])
    
    # Check which mode
    alert = cold_alert_classifier(hist + [{'numbers': [], 'draw': '0', 'date': '0'}], len(hist)) if len(hist) >= 200 else 0
    if alert >= 0.4:
        cold_mode_count += 1
    else:
        pp3_mode_count += 1
    
    try:
        bets = strategy_adaptive_3bet(hist)
        hit = any(len(set(b) & actual) >= 3 for b in bets)
        if hit:
            m3_plus += 1
        total += 1
    except:
        continue

rate = m3_plus / total * 100 if total > 0 else 0
edge = rate - BASELINES_3
z = (m3_plus/total - BASELINES_3/100) / np.sqrt(BASELINES_3/100 * (1 - BASELINES_3/100) / total) if total > 0 else 0

print(f"  自適應策略 1500期結果:")
print(f"    M3+: {m3_plus}/{total} ({rate:.2f}%)")
print(f"    基準: {BASELINES_3:.2f}%")
print(f"    Edge: {edge:+.2f}%")
print(f"    z-score: {z:.2f}")
print(f"    Cold模式使用: {cold_mode_count}次 ({cold_mode_count/(cold_mode_count+pp3_mode_count)*100:.1f}%)")
print(f"    PP3模式使用: {pp3_mode_count}次 ({pp3_mode_count/(cold_mode_count+pp3_mode_count)*100:.1f}%)")
print()

# Compare
print("  對照:")
print(f"    PP3 固定: Edge +2.23% (z=2.74)")
print(f"    F2+Cold(w=100) 固定: Edge +1.76% (z=2.17)")
print(f"    Adaptive: Edge {edge:+.2f}% (z={z:.2f})")

print()
print("═" * 80)
print("  結論")
print("═" * 80)
