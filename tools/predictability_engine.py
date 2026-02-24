#!/usr/bin/env python3
"""
可預測期識別引擎 (Predictability Period Identification Engine)
=============================================================
目標：不預測號碼，只預測哪些期數存在可利用統計偏差。

特徵體系（全部嚴格向後看，無 look-ahead）：
  A. 隨機性  — entropy, chi2_pval, variance_ratio
  B. Regime  — ewma_drift_mag, hhi_concentration, sum_slope
  C. 異常    — max_gap_ratio, zone_imbalance, extreme_sum_rate
  D. 共識    — signal_agreement, fourier_confidence

Score 建構：
  - 訓練期：個別特徵 quintile 分析 → 篩選顯著特徵
  - 組合分數：存活特徵的標準化 z-score 平均

嚴格驗證：
  1. 時序 OOS（前半訓練 / 後半測試）
  2. Permutation test (n=500)
  3. OOS 內前半/後半穩定性

輸出：
  - 若無特徵通過 → 「不存在可利用期」
  - 若有特徵 → Score time series、Regime intervals、可下注期列表
"""

import os, sys, math, time
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq
from scipy.stats import chi2_contingency, norm, linregress
import copy

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))
from lottery_api.database import DatabaseManager

MAX_NUM = 49
PICK = 6
P1 = 1 - sum(math.comb(6, k) * math.comb(43, 6-k) / math.comb(49, 6) for k in range(3))
BASELINE_5 = (1 - (1 - P1) ** 5) * 100
MIN_HISTORY = 200
SEED = 42

# ══════════════════════════════════════════════════════════════
# TS3+M+FO 5-bet Strategy (for M3+ label computation)
# ══════════════════════════════════════════════════════════════

def fourier_rhythm_bet(history, window=500):
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bits = np.array([1 if n in d['numbers'] else 0 for d in h], dtype=float)
        if bits.sum() < 2: continue
        yf = fft(bits - bits.mean())
        xf = fftfreq(w, 1)
        pos = xf > 0
        if pos.sum() == 0: continue
        peak = np.argmax(np.abs(yf[pos]))
        fv = xf[pos][peak]
        if fv == 0: continue
        period = 1 / fv
        if 2 < period < w / 2:
            lh = np.where(bits == 1)[0]
            if len(lh) == 0: continue
            gap = (w - 1) - lh[-1]
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores[1:])[::-1] + 1


def generate_5bet(history):
    f_rank = fourier_rhythm_bet(history)
    bet1 = sorted(f_rank[:6].tolist())

    excl = set(bet1)
    freq100 = Counter(n for d in history[-100:] for n in d['numbers'][:PICK] if n <= MAX_NUM)
    cands = sorted([n for n in range(1, MAX_NUM+1) if n not in excl], key=lambda x: freq100.get(x, 0))
    bet2 = sorted(cands[:6])

    excl |= set(bet2)
    tail_groups = {i: [] for i in range(10)}
    for n in range(1, MAX_NUM+1):
        if n not in excl:
            tail_groups[n % 10].append((n, freq100.get(n, 0)))
    for t in tail_groups: tail_groups[t].sort(key=lambda x: -x[1])
    sel3 = []
    avail = sorted([t for t in range(10) if tail_groups[t]], key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0, reverse=True)
    idx_g = {t: 0 for t in range(10)}
    while len(sel3) < PICK:
        added = False
        for t in avail:
            if len(sel3) >= PICK: break
            if idx_g[t] < len(tail_groups[t]):
                num, _ = tail_groups[t][idx_g[t]]
                if num not in sel3: sel3.append(num); added = True
                idx_g[t] += 1
        if not added: break
    if len(sel3) < PICK:
        rem = [n for n in range(1, MAX_NUM+1) if n not in excl and n not in sel3]
        rem.sort(key=lambda x: -freq100.get(x, 0))
        sel3.extend(rem[:PICK - len(sel3)])
    bet3 = sorted(sel3[:PICK])

    excl |= set(bet3)
    # Markov w=30
    recent30 = history[-30:] if len(history) >= 30 else history
    trans = Counter()
    for i in range(len(recent30)-1):
        for p in recent30[i]['numbers']:
            for q in recent30[i+1]['numbers']:
                trans[(p,q)] += 1
    last_nums = history[-1]['numbers']
    mk_scores = {}
    for n in range(1, MAX_NUM+1):
        mk_scores[n] = sum(trans.get((p, n), 0) for p in last_nums)
    mk_cands = sorted([n for n in range(1, MAX_NUM+1) if n not in excl], key=lambda x: -mk_scores[x])
    bet4 = sorted(mk_cands[:PICK])

    excl |= set(bet4)
    leftover = sorted([n for n in range(1, MAX_NUM+1) if n not in excl], key=lambda x: -freq100.get(x, 0))
    bet5 = sorted(leftover[:PICK])

    return [bet1, bet2, bet3, bet4, bet5]


# ══════════════════════════════════════════════════════════════
# Feature Computation (strictly backward-looking)
# ══════════════════════════════════════════════════════════════

def compute_features(history):
    """Compute 11 features from history (all backward-looking)."""
    feats = {}
    N = len(history)

    # --- A. 隨機性特徵 ---

    # A1: Shannon Entropy of number frequencies (last 50 draws)
    w = min(50, N)
    recent = history[-w:]
    freq = Counter(n for d in recent for n in d['numbers'][:PICK] if 1 <= n <= MAX_NUM)
    total_nums = sum(freq.values())
    if total_nums > 0:
        probs = np.array([freq.get(n, 0) / total_nums for n in range(1, MAX_NUM+1)])
        probs = probs[probs > 0]
        feats['entropy_w50'] = -np.sum(probs * np.log2(probs))
    else:
        feats['entropy_w50'] = 0

    # A2: Chi-squared uniformity p-value (last 50 draws)
    expected = total_nums / MAX_NUM if total_nums > 0 else 1
    observed = [freq.get(n, 0) for n in range(1, MAX_NUM+1)]
    if expected > 0 and total_nums > 10:
        chi2_stat = sum((o - expected)**2 / expected for o in observed)
        from scipy.stats import chi2
        feats['chi2_pval'] = 1 - chi2.cdf(chi2_stat, MAX_NUM - 1)
    else:
        feats['chi2_pval'] = 0.5

    # A3: Variance ratio (short-term vs long-term sum variance)
    if N >= 100:
        sums_short = [sum(d['numbers'][:PICK]) for d in history[-10:]]
        sums_long = [sum(d['numbers'][:PICK]) for d in history[-100:]]
        var_short = np.var(sums_short) if len(sums_short) > 1 else 1
        var_long = np.var(sums_long) if len(sums_long) > 1 else 1
        feats['variance_ratio'] = var_short / (var_long + 1e-10)
    else:
        feats['variance_ratio'] = 1.0

    # --- B. Regime 特徵 ---

    # B1: EWMA drift magnitude (alpha=0.2)
    base_freq = PICK / MAX_NUM
    ewma_vals = {n: base_freq for n in range(1, MAX_NUM+1)}
    alpha = 0.2
    for d in history:
        nums_set = set(d['numbers'][:PICK])
        for n in range(1, MAX_NUM+1):
            x = 1.0 if n in nums_set else 0.0
            ewma_vals[n] = alpha * x + (1 - alpha) * ewma_vals[n]
    drifts = [abs(ewma_vals[n] - base_freq) for n in range(1, MAX_NUM+1)]
    feats['ewma_drift_mag'] = np.mean(drifts)

    # B2: HHI concentration (last 30 draws)
    w30 = min(30, N)
    freq30 = Counter(n for d in history[-w30:] for n in d['numbers'][:PICK] if 1 <= n <= MAX_NUM)
    total30 = sum(freq30.values())
    if total30 > 0:
        shares = [(freq30.get(n, 0) / total30) for n in range(1, MAX_NUM+1)]
        feats['hhi_w30'] = sum(s**2 for s in shares)
    else:
        feats['hhi_w30'] = 1.0 / MAX_NUM

    # B3: Sum trend slope (last 20 draws)
    if N >= 20:
        sums20 = [sum(d['numbers'][:PICK]) for d in history[-20:]]
        slope, _, _, _, _ = linregress(range(len(sums20)), sums20)
        feats['sum_slope'] = abs(slope)
    else:
        feats['sum_slope'] = 0

    # --- C. 異常特徵 ---

    # C1: Max gap ratio
    last_appear = {}
    for i, d in enumerate(history):
        for n in d['numbers'][:PICK]:
            if 1 <= n <= MAX_NUM:
                last_appear[n] = i
    gaps = [N - 1 - last_appear.get(n, 0) for n in range(1, MAX_NUM+1)]
    if N >= 100:
        hist_gaps = []
        for n in range(1, MAX_NUM+1):
            positions = [i for i, d in enumerate(history[-100:]) if n in d['numbers'][:PICK]]
            if len(positions) >= 2:
                for j in range(1, len(positions)):
                    hist_gaps.append(positions[j] - positions[j-1])
        median_gap = np.median(hist_gaps) if hist_gaps else 8
    else:
        median_gap = 8
    feats['max_gap_ratio'] = max(gaps) / (median_gap + 1e-10)

    # C2: Zone imbalance (last 10 draws)
    w10 = min(10, N)
    zones = [0, 0, 0]  # Z1: 1-16, Z2: 17-32, Z3: 33-49
    for d in history[-w10:]:
        for n in d['numbers'][:PICK]:
            if 1 <= n <= 16: zones[0] += 1
            elif 17 <= n <= 32: zones[1] += 1
            elif 33 <= n <= 49: zones[2] += 1
    feats['zone_imbalance'] = max(zones) - min(zones)

    # C3: Extreme sum rate (last 20 draws, sum beyond 2σ)
    if N >= 100:
        sums100 = [sum(d['numbers'][:PICK]) for d in history[-100:]]
        mu, sigma = np.mean(sums100), np.std(sums100)
        if sigma > 0:
            sums20 = [sum(d['numbers'][:PICK]) for d in history[-20:]]
            extreme_count = sum(1 for s in sums20 if abs(s - mu) > 2 * sigma)
            feats['extreme_sum_rate'] = extreme_count / 20
        else:
            feats['extreme_sum_rate'] = 0
    else:
        feats['extreme_sum_rate'] = 0

    # --- D. 共識特徵 ---

    # D1: Signal agreement (overlap between Fourier/Cold/Markov top6)
    try:
        f_rank = fourier_rhythm_bet(history)
        fourier_top6 = set(f_rank[:6].tolist())
    except:
        fourier_top6 = set()

    cold_top6 = set(sorted(range(1, MAX_NUM+1),
                           key=lambda x: freq.get(x, 0))[:6])

    # Simple Markov top6
    if N >= 30:
        recent30 = history[-30:]
        trans = Counter()
        for i in range(len(recent30)-1):
            for p in recent30[i]['numbers']:
                for q in recent30[i+1]['numbers']:
                    trans[(p,q)] += 1
        last_nums = history[-1]['numbers']
        mk_sc = {n: sum(trans.get((p,n),0) for p in last_nums) for n in range(1, MAX_NUM+1)}
        markov_top6 = set(sorted(range(1, MAX_NUM+1), key=lambda x: -mk_sc[x])[:6])
    else:
        markov_top6 = set()

    pairs = [
        len(fourier_top6 & cold_top6),
        len(fourier_top6 & markov_top6),
        len(cold_top6 & markov_top6),
    ]
    feats['signal_agreement'] = sum(pairs)

    # D2: Fourier confidence (max Fourier score / mean)
    try:
        h500 = history[-500:] if N >= 500 else history
        w = len(h500)
        f_scores = []
        for n in range(1, MAX_NUM+1):
            bits = np.array([1 if n in d['numbers'] else 0 for d in h500], dtype=float)
            if bits.sum() < 2: continue
            yf = fft(bits - bits.mean())
            xf = fftfreq(w, 1)
            pos = xf > 0
            if pos.sum() == 0: continue
            f_scores.append(np.max(np.abs(yf[pos])))
        if f_scores:
            feats['fourier_confidence'] = max(f_scores) / (np.mean(f_scores) + 1e-10)
        else:
            feats['fourier_confidence'] = 1
    except:
        feats['fourier_confidence'] = 1

    return feats

FEATURE_NAMES = [
    'entropy_w50', 'chi2_pval', 'variance_ratio',
    'ewma_drift_mag', 'hhi_w30', 'sum_slope',
    'max_gap_ratio', 'zone_imbalance', 'extreme_sum_rate',
    'signal_agreement', 'fourier_confidence'
]


# ══════════════════════════════════════════════════════════════
# Main Engine
# ══════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"總期數: {len(all_draws)}")

    # ── Phase A: Compute features + M3+ labels ──
    print("\n" + "="*70)
    print("Phase A: 計算特徵 + M3+ 標籤（嚴格向後看）")
    print("="*70)

    feature_matrix = []  # list of dicts
    m3_labels = []       # 1 or 0
    draw_indices = []

    test_range = 1500  # test on last 1500 draws
    start_idx = max(MIN_HISTORY, len(all_draws) - test_range)

    for idx in range(start_idx, len(all_draws)):
        history = all_draws[:idx]
        actual = set(all_draws[idx]['numbers'][:PICK])

        # M3+ label: did 5-bet hit?
        try:
            bets = generate_5bet(history)
            hit = any(len(set(b) & actual) >= 3 for b in bets)
        except:
            continue

        # Features
        feats = compute_features(history)
        feature_matrix.append(feats)
        m3_labels.append(1 if hit else 0)
        draw_indices.append(idx)

        if len(draw_indices) % 200 == 0:
            elapsed = time.time() - t0
            print(f"  已處理 {len(draw_indices)} 期... ({elapsed:.1f}s)")

    N_total = len(m3_labels)
    hit_rate = sum(m3_labels) / N_total * 100
    print(f"\n完成: {N_total} 期, M3+ 命中 {sum(m3_labels)} 次 ({hit_rate:.2f}%)")
    print(f"5注基準: {BASELINE_5:.2f}%")

    # ── Phase B: Temporal Train/Test Split ──
    split = N_total // 2
    train_feats = feature_matrix[:split]
    train_labels = m3_labels[:split]
    test_feats = feature_matrix[split:]
    test_labels = m3_labels[split:]

    print(f"\nTrain: {len(train_labels)} 期, Test: {len(test_labels)} 期")
    print(f"Train M3+: {sum(train_labels)/len(train_labels)*100:.2f}%")
    print(f"Test  M3+: {sum(test_labels)/len(test_labels)*100:.2f}%")

    # ── Phase C: Individual Feature Analysis (Training Only) ──
    print("\n" + "="*70)
    print("Phase C: 個別特徵 Quintile 分析（僅訓練集）")
    print("="*70)
    print(f"{'特徵':>22}  {'Q5 M3+%':>8}  {'Q1 M3+%':>8}  {'Q5-基準':>8}  {'z':>6}  {'p':>8}  {'用Q':>4}")
    print("-"*70)

    surviving_features = []
    feature_directions = {}  # +1 = high is good, -1 = low is good
    bonferroni_alpha = 0.05 / len(FEATURE_NAMES)

    for fname in FEATURE_NAMES:
        vals = [f[fname] for f in train_feats]
        labels = train_labels

        # Sort by feature value → quintile split
        order = np.argsort(vals)
        q_size = len(order) // 5

        # Q1 = lowest quintile, Q5 = highest quintile
        q1_idx = order[:q_size]
        q5_idx = order[-q_size:]

        q1_rate = sum(labels[i] for i in q1_idx) / q_size * 100 if q_size > 0 else 0
        q5_rate = sum(labels[i] for i in q5_idx) / q_size * 100 if q_size > 0 else 0

        # Test Q5 (high quintile)
        q5_edge = q5_rate - BASELINE_5
        se = (BASELINE_5 * (100 - BASELINE_5) / 100 / q_size) ** 0.5 if q_size > 0 else 1
        z5 = q5_edge / se

        # Test Q1 (low quintile)
        q1_edge = q1_rate - BASELINE_5
        z1 = q1_edge / se

        # Which direction is better?
        if z5 > z1:
            best_z, best_q, direction, use_q = z5, 'Q5', +1, 'Q5'
            best_rate = q5_rate
        else:
            best_z, best_q, direction, use_q = z1, 'Q1', -1, 'Q1'
            best_rate = q1_rate

        p_val = 1 - norm.cdf(best_z)
        passed = p_val < bonferroni_alpha

        print(f"{fname:>22}  {q5_rate:8.2f}  {q1_rate:8.2f}  {q5_edge:+8.2f}  "
              f"{best_z:6.2f}  {p_val:8.5f}  {use_q:>4}{'  ★' if passed else ''}")

        if p_val < 0.10:  # relaxed pre-screen (strict test on OOS)
            surviving_features.append(fname)
            feature_directions[fname] = direction

    print(f"\nBonferroni 閾值: p < {bonferroni_alpha:.5f}")
    bonferroni_pass = [f for f in FEATURE_NAMES
                       if any(f == sf for sf in surviving_features)]

    # ── Phase D: Composite Score ──
    print("\n" + "="*70)
    print(f"Phase D: 組合分數（{len(surviving_features)} 個候選特徵）")
    print("="*70)

    if not surviving_features:
        print("\n⚠️  沒有任何特徵通過預篩（p<0.10）。")
        print("仍然建構全特徵組合分數進行 OOS 測試（可能為 null result）。")
        surviving_features = FEATURE_NAMES[:]
        feature_directions = {f: +1 for f in FEATURE_NAMES}  # default: high is good

    # Compute z-scores on TRAINING data
    train_means = {}
    train_stds = {}
    for fname in surviving_features:
        vals = [f[fname] for f in train_feats]
        train_means[fname] = np.mean(vals)
        train_stds[fname] = np.std(vals) + 1e-10

    def compute_score(feat_dict):
        zscores = []
        for fname in surviving_features:
            z = (feat_dict[fname] - train_means[fname]) / train_stds[fname]
            z *= feature_directions[fname]  # flip if low is good
            zscores.append(z)
        return np.mean(zscores)

    # Compute scores for test set
    test_scores = [compute_score(f) for f in test_feats]

    # ── Phase E: OOS Evaluation ──
    print("\n" + "="*70)
    print("Phase E: OOS 時序驗證（測試集）")
    print("="*70)

    # Test at multiple thresholds
    thresholds = [50, 60, 70, 75, 80, 90, 95]  # percentiles of training scores
    train_scores = [compute_score(f) for f in train_feats]

    print(f"\n{'Percentile':>12}  {'閾值':>8}  {'OOS期數':>8}  {'OOS命中':>8}  "
          f"{'M3+%':>7}  {'Edge%':>7}  {'z':>6}  {'p':>8}  {'H1%':>7}  {'H2%':>7}")
    print("-"*100)

    oos_results = []
    for pct in thresholds:
        threshold = np.percentile(train_scores, pct)
        selected = [(i, test_labels[i]) for i in range(len(test_scores))
                     if test_scores[i] >= threshold]

        if len(selected) < 10:
            print(f"P{pct:>3d}         {threshold:8.3f}  {'<10':>8}  {'—':>8}  "
                  f"{'—':>7}  {'—':>7}  {'—':>6}  {'—':>8}")
            oos_results.append(None)
            continue

        n_sel = len(selected)
        n_hits = sum(lab for _, lab in selected)
        rate = n_hits / n_sel * 100
        edge = rate - BASELINE_5
        se = (BASELINE_5 * (100 - BASELINE_5) / 100 / n_sel) ** 0.5
        z = edge / se
        p = 1 - norm.cdf(z)

        # H1/H2 stability
        half = n_sel // 2
        h1_hits = sum(lab for _, lab in selected[:half])
        h2_hits = sum(lab for _, lab in selected[half:])
        h1_n = half
        h2_n = n_sel - half
        h1_rate = h1_hits / h1_n * 100 if h1_n > 0 else 0
        h2_rate = h2_hits / h2_n * 100 if h2_n > 0 else 0

        print(f"P{pct:>3d}         {threshold:8.3f}  {n_sel:8d}  {n_hits:8d}  "
              f"{rate:7.2f}  {edge:+7.2f}  {z:6.2f}  {p:8.5f}  "
              f"{h1_rate - BASELINE_5:+7.2f}  {h2_rate - BASELINE_5:+7.2f}")

        oos_results.append({
            'pct': pct, 'threshold': threshold, 'n': n_sel,
            'rate': rate, 'edge': edge, 'z': z, 'p': p,
            'h1_edge': h1_rate - BASELINE_5, 'h2_edge': h2_rate - BASELINE_5,
        })

    # Find best OOS result
    valid_results = [r for r in oos_results if r is not None and r['p'] < 0.05]

    # ── Phase F: Permutation Test (on best OOS threshold) ──
    print("\n" + "="*70)
    print("Phase F: 排列檢定")
    print("="*70)

    if not valid_results:
        print("\n⚠️  OOS 沒有任何閾值的 p < 0.05。")
        # Still run permutation on best edge threshold
        nonzero = [r for r in oos_results if r is not None]
        if nonzero:
            best_oos = max(nonzero, key=lambda x: x['edge'])
            print(f"以最佳 Edge 閾值 P{best_oos['pct']} 執行排列檢定（預期結果: NO_SIGNAL）")
        else:
            print("完全無有效結果，跳過排列檢定。")
            best_oos = None
    else:
        best_oos = min(valid_results, key=lambda x: x['p'])
        print(f"最佳 OOS: P{best_oos['pct']} Edge={best_oos['edge']:+.2f}% p={best_oos['p']:.5f}")

    if best_oos:
        rng = np.random.RandomState(SEED)
        n_perm = 500
        real_edge = best_oos['edge']
        perm_edges = []

        pct_threshold = best_oos['pct']
        threshold_val = np.percentile(train_scores, pct_threshold)

        print(f"執行 {n_perm} 次排列... ", end="", flush=True)
        for perm_i in range(n_perm):
            # Shuffle M3+ labels in test set
            shuffled_labels = list(test_labels)
            rng.shuffle(shuffled_labels)
            selected = [(i, shuffled_labels[i]) for i in range(len(test_scores))
                         if test_scores[i] >= threshold_val]
            if len(selected) < 5:
                perm_edges.append(0)
                continue
            n_hits = sum(lab for _, lab in selected)
            rate = n_hits / len(selected) * 100
            perm_edges.append(rate - BASELINE_5)

        perm_arr = np.array(perm_edges)
        perm_p = float(np.mean(perm_arr >= real_edge))
        perm_d = float((real_edge - perm_arr.mean()) / (perm_arr.std() + 1e-10))

        if perm_p < 0.001:
            verdict = 'STRONG_SIGNAL'
        elif perm_p < 0.05:
            verdict = 'SIGNAL'
        elif perm_p < 0.10:
            verdict = 'MARGINAL'
        else:
            verdict = 'NO_SIGNAL'

        print(f"完成")
        print(f"\n  Real Edge:    {real_edge:+.2f}%")
        print(f"  Shuffle Mean: {perm_arr.mean():+.4f}%")
        print(f"  Shuffle Std:  {perm_arr.std():.4f}%")
        print(f"  Perm p-value: {perm_p:.4f}")
        print(f"  Cohen's d:    {perm_d:.3f}")
        print(f"  裁定:         {verdict}")

        # Bonferroni for threshold search (7 thresholds)
        bonf_perm = 0.05 / len(thresholds)
        print(f"\n  Bonferroni 校正（{len(thresholds)} 個閾值）: 需要 p < {bonf_perm:.4f}")
        if perm_p < bonf_perm:
            print(f"  ✅ 通過 Bonferroni 校正!")
        else:
            print(f"  ❌ 未通過 Bonferroni 校正 (p={perm_p:.4f} > {bonf_perm:.4f})")

    # ── Phase G: Final Verdict ──
    print("\n" + "="*70)
    print("Phase G: 最終裁定")
    print("="*70)

    has_signal = (best_oos is not None and
                  best_oos.get('p', 1) < 0.05 and
                  'perm_p' in dir() and perm_p < bonf_perm)

    if best_oos and perm_p < bonf_perm:
        print("\n🟢 發現可利用期識別信號!")
        print(f"  閾值: Composite Score P{best_oos['pct']}")
        print(f"  OOS Edge: {best_oos['edge']:+.2f}%")
        print(f"  排列檢定 p: {perm_p:.4f}")
        print(f"  建議：高分期可以增加投注信心。")
    else:
        print("\n🔴 不存在可利用的可預測期識別信號。")
        print("  所有特徵組合在 OOS 排列檢定中均未通過 Bonferroni 校正。")
        print("  結論：彩池的可預測性在各期之間沒有系統性差異。")
        print("  建議：維持每期等額投注策略。")

    elapsed = time.time() - t0
    print(f"\n總耗時: {elapsed:.1f}s")


if __name__ == '__main__':
    main()
