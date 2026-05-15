#!/usr/bin/env python3
"""
Fast Gate Tests for H003, H004, H006
H003: ΔACB frequency momentum - Ljung-Box on delta signal
H004: Gap Entropy - Ljung-Box on entropy series
H006: Frequency Cluster ACF - Ljung-Box on cluster label series
"""
import json, sys, os, numpy as np
from collections import defaultdict

os.chdir('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

def load_539():
    from database import DatabaseManager
    db = DatabaseManager()
    raw = db.get_all_draws('DAILY_539')
    draws = []
    for d in raw:
        nums = d.get('numbers', [])
        if isinstance(nums, str): nums = json.loads(nums)
        draws.append({'period': d['draw'], 'numbers': sorted(nums)})
    draws.sort(key=lambda x: x['period'])
    print(f"Loaded {len(draws)} draws")
    return draws

def ljung_box(x, max_lag=10):
    from scipy.stats import chi2
    n = len(x)
    x = np.array(x, dtype=float)
    mean = np.mean(x)
    var = np.var(x)
    if var < 1e-12:
        return 0.0, 1.0, [0.0]*max_lag
    acf_vals = []
    for k in range(1, max_lag+1):
        if n > k:
            r = np.corrcoef(x[:n-k], x[k:])[0,1]
            acf_vals.append(float(r) if not np.isnan(r) else 0.0)
        else:
            acf_vals.append(0.0)
    Q = n*(n+2) * sum((r**2)/(n-k) for k,r in enumerate(acf_vals, 1))
    p = float(1 - chi2.cdf(Q, df=max_lag))
    return float(Q), p, acf_vals

def interpret(p, name):
    if p < 0.05:
        print(f"  {name}: Q-stat p={p:.4f} → SIGNIFICANT 有結構 → 進入完整回測")
        return True
    else:
        print(f"  {name}: Q-stat p={p:.4f} → 白噪音 → FAST REJECT")
        return False

# ==========================================
# H003: ΔACB Frequency Momentum
# ==========================================
def h003_delta_acb(draws):
    print("\n=== H003: ΔACB Frequency Momentum ===")
    MAX_NUM = 39
    W_SHORT = 30
    W_LONG = 300
    n = len(draws)
    start = W_LONG

    # For each period t, compute ΔACB for each number
    # ΔACB(n,t) = freq(n, t-W_LONG..t)/W_LONG - freq(n, t-W_SHORT..t)/W_SHORT
    # Use the average ΔACB across all numbers as the series signal
    delta_series = []

    for t in range(start, n):
        long_freq = defaultdict(int)
        short_freq = defaultdict(int)
        for d in draws[t-W_LONG:t]:
            for num in d['numbers']:
                long_freq[num] += 1
        for d in draws[t-W_SHORT:t]:
            for num in d['numbers']:
                short_freq[num] += 1

        expected_long = W_LONG * 5 / MAX_NUM
        expected_short = W_SHORT * 5 / MAX_NUM

        deltas = []
        for num in range(1, MAX_NUM+1):
            f_long = long_freq.get(num, 0) / W_LONG
            f_short = short_freq.get(num, 0) / W_SHORT
            deltas.append(f_long - f_short)  # positive = accelerating cold

        # Use std of deltas as the period-level signal (measure of momentum spread)
        delta_series.append(float(np.std(deltas)))

    print(f"  Series length: {len(delta_series)}")
    print(f"  Mean: {np.mean(delta_series):.4f}, Std: {np.std(delta_series):.4f}")
    Q, p, acf = ljung_box(delta_series)
    print(f"  ACF(lag1-5): {[round(a,4) for a in acf[:5]]}")
    signal_exists = interpret(p, "ΔACB std series")

    # Also test: for each period, does picking top-5 ΔACB numbers improve hit rate?
    top5_hits = []
    for t in range(start, n):
        long_freq = defaultdict(int)
        short_freq = defaultdict(int)
        for d in draws[t-W_LONG:t]:
            for num in d['numbers']:
                long_freq[num] += 1
        for d in draws[t-W_SHORT:t]:
            for num in d['numbers']:
                short_freq[num] += 1
        deltas = {}
        for num in range(1, MAX_NUM+1):
            f_long = long_freq.get(num, 0) / W_LONG
            f_short = short_freq.get(num, 0) / W_SHORT
            deltas[num] = f_long - f_short
        # Top-5 most accelerating cold numbers
        top5 = sorted(deltas, key=lambda x: deltas[x], reverse=True)[:5]
        actual = set(draws[t]['numbers'])
        top5_hits.append(sum(1 for num in top5 if num in actual))

    hit_rate = np.mean(top5_hits) / 5
    baseline = 5/39
    lift = hit_rate / baseline
    from scipy.stats import binomtest
    total_bets = len(top5_hits) * 5
    total_hits = sum(top5_hits)
    bt = binomtest(total_hits, total_bets, baseline)
    print(f"  Top-5 ΔACB hit rate: {hit_rate:.4f} vs baseline {baseline:.4f} → Lift={lift:.4f} p={bt.pvalue:.4f}")

    return {
        'signal_in_series': signal_exists,
        'ljung_box_p': p,
        'acf_lag1_5': [round(a,4) for a in acf[:5]],
        'top5_lift': round(lift, 4),
        'top5_p': round(float(bt.pvalue), 4),
        'verdict': 'PROCEED' if (signal_exists or lift > 1.15) else 'FAST_REJECT'
    }

# ==========================================
# H004: Gap Entropy
# ==========================================
def h004_gap_entropy(draws):
    print("\n=== H004: Gap Entropy ===")
    from scipy.stats import entropy

    entropies = []
    for d in draws:
        nums = sorted(d['numbers'])
        # Compute gaps between consecutive numbers (including boundaries)
        gaps = []
        for i in range(1, len(nums)):
            gaps.append(nums[i] - nums[i-1])
        if gaps:
            # Normalize to probability distribution
            total = sum(gaps)
            probs = [g/total for g in gaps]
            ent = float(entropy(probs, base=2))
            entropies.append(ent)
        else:
            entropies.append(0.0)

    print(f"  Series length: {len(entropies)}")
    print(f"  Mean entropy: {np.mean(entropies):.4f}, Std: {np.std(entropies):.4f}")
    Q, p, acf = ljung_box(entropies)
    print(f"  ACF(lag1-5): {[round(a,4) for a in acf[:5]]}")
    signal_exists = interpret(p, "Gap Entropy series")

    # Does entropy correlate with next-period anything useful?
    # Test: after low entropy (compressed draw), does next draw have predictable structure?
    low_ent_threshold = np.percentile(entropies, 25)
    next_hit_low = []
    next_hit_high = []
    for t in range(len(draws)-1):
        actual = set(draws[t+1]['numbers'])
        # Use ACB-like: frequency deficit top-5
        if entropies[t] < low_ent_threshold:
            next_hit_low.append(1 if len(actual & set(draws[t]['numbers'])) >= 1 else 0)
        else:
            next_hit_high.append(1 if len(actual & set(draws[t]['numbers'])) >= 1 else 0)

    p_low = np.mean(next_hit_low) if next_hit_low else 0
    p_high = np.mean(next_hit_high) if next_hit_high else 0
    print(f"  P(repeat|low_entropy): {p_low:.4f} vs P(repeat|high_entropy): {p_high:.4f}")
    lift_vs_entropy = p_low / p_high if p_high > 0 else 0
    print(f"  Lift: {lift_vs_entropy:.4f}")

    return {
        'signal_in_series': signal_exists,
        'ljung_box_p': p,
        'acf_lag1_5': [round(a,4) for a in acf[:5]],
        'entropy_low_vs_high_lift': round(lift_vs_entropy, 4),
        'verdict': 'PROCEED' if signal_exists else 'FAST_REJECT'
    }

# ==========================================
# H006: Frequency Cluster ACF
# ==========================================
def h006_freq_cluster(draws):
    print("\n=== H006: Frequency Cluster ACF ===")
    try:
        from sklearn.cluster import KMeans
        sklearn_available = True
    except ImportError:
        print("  sklearn not available, using manual binning")
        sklearn_available = False

    MAX_NUM = 39
    WINDOW = 300
    n = len(draws)
    start = WINDOW
    K = 3  # clusters

    cluster_labels_series = []  # dominant cluster per period

    for t in range(start, n):
        freq = defaultdict(int)
        for d in draws[t-WINDOW:t]:
            for num in d['numbers']:
                freq[num] += 1

        freq_vec = np.array([freq.get(i, 0) for i in range(1, MAX_NUM+1)], dtype=float)

        if sklearn_available:
            # Cluster numbers by frequency
            km = KMeans(n_clusters=K, random_state=42, n_init=3)
            labels = km.fit_predict(freq_vec.reshape(-1, 1))
            # Dominant cluster = cluster with highest mean frequency
            cluster_means = [freq_vec[labels==k].mean() for k in range(K)]
            # For each draw in this period, which cluster was dominant?
            actual = draws[t]['numbers']
            draw_cluster_counts = [sum(1 for num in actual if labels[num-1] == k) for k in range(K)]
            dominant = int(np.argmax(draw_cluster_counts))
        else:
            # Simple tertile binning
            tertiles = np.percentile(freq_vec, [33, 67])
            labels = np.digitize(freq_vec, tertiles)  # 0, 1, 2
            actual = draws[t]['numbers']
            draw_cluster_counts = [sum(1 for num in actual if labels[num-1] == k) for k in range(K)]
            dominant = int(np.argmax(draw_cluster_counts))

        cluster_labels_series.append(dominant)

    print(f"  Series length: {len(cluster_labels_series)}")
    cluster_dist = [cluster_labels_series.count(k)/len(cluster_labels_series) for k in range(K)]
    print(f"  Cluster distribution: {[round(c,3) for c in cluster_dist]}")

    Q, p, acf = ljung_box(cluster_labels_series)
    print(f"  ACF(lag1-5): {[round(a,4) for a in acf[:5]]}")
    signal_exists = interpret(p, "Cluster label series")

    return {
        'signal_in_series': signal_exists,
        'ljung_box_p': p,
        'acf_lag1_5': [round(a,4) for a in acf[:5]],
        'cluster_distribution': [round(c, 4) for c in cluster_dist],
        'verdict': 'PROCEED' if signal_exists else 'FAST_REJECT'
    }

# ==========================================
# MAIN
# ==========================================
if __name__ == '__main__':
    draws = load_539()

    results = {}
    results['H003_delta_acb'] = h003_delta_acb(draws)
    results['H004_gap_entropy'] = h004_gap_entropy(draws)
    results['H006_freq_cluster'] = h006_freq_cluster(draws)

    print("\n=== SUMMARY ===")
    for name, r in results.items():
        verdict = r['verdict']
        p = r['ljung_box_p']
        print(f"  {name}: p={p:.4f} → {verdict}")

    out = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/tools/fast_gate_h003_h004_h006_results.json'
    with open(out, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n結果已儲存至 {out}")
