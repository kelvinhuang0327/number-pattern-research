#!/usr/bin/env python3
"""
39樂合彩 v2 — 自動特徵搜尋 + 假說驗證
======================================
Phase 7: Auto-Discovery Feature Search
Phase 8: Hypothesis Verification (H1-H24)

自動生成特徵 → 篩選 → Bonferroni 修正 → 驗證可否證假說
"""

import json
import math
import sqlite3
import os
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime
from scipy import stats

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'lottery_v2.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_v2.db')

POOL = 39
PICK = 5
BASELINE_1BET_GE2 = sum(math.comb(PICK, k) * math.comb(POOL - PICK, PICK - k) / math.comb(POOL, PICK)
                        for k in range(2, PICK + 1))

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'DAILY_539'
        ORDER BY date ASC, draw ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums)})
    return draws


def main():
    print("=" * 80)
    print("39樂合彩 v2 — 自動特徵搜尋 + 假說驗證")
    print(f"啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    draws = load_draws()
    N = len(draws)
    print(f"📊 載入 {N} 期資料\n")

    results = {}

    # ══════════════════════════════════════════
    # PART A: 假說驗證 (H1-H14 + 關鍵額外假說)
    # ══════════════════════════════════════════

    print("═" * 80)
    print("PART A: 假說驗證")
    print("═" * 80)

    # ── H1: 頻率偏差假說 ──
    print("\n▶ H1: 頻率偏差假說 — χ² 適合度檢驗")
    freq = Counter()
    for d in draws:
        for num in d['numbers']:
            freq[num] += 1
    total_obs = sum(freq.values())
    expected = total_obs / POOL
    observed = [freq.get(i, 0) for i in range(1, POOL + 1)]
    chi2, p_h1 = stats.chisquare(observed, f_exp=[expected] * POOL)
    results['H1_frequency'] = {'chi2': chi2, 'p_value': p_h1, 'df': POOL - 1}
    verdict_h1 = "✅ 存在偏差" if p_h1 < 0.05 else "❌ 均勻分布"
    print(f"  χ²={chi2:.2f}, df={POOL-1}, p={p_h1:.6f} → {verdict_h1}")
    print(f"  最高頻: {max(observed)}次, 最低頻: {min(observed)}次, 期望: {expected:.1f}次")

    # ── H4: 奇偶比失衡假說 ──
    print("\n▶ H4: 奇偶比失衡假說")
    odd_counts = []
    for d in draws:
        odd_counts.append(sum(1 for n in d['numbers'] if n % 2 == 1))
    odd_dist = Counter(odd_counts)

    # 理論分布 (超幾何: 20 個奇數, 19 個偶數, 抽 5 個)
    n_odd = 20  # 1,3,5,...,39
    n_even = 19  # 2,4,6,...,38
    theoretical = {}
    for k in range(PICK + 1):
        if k <= n_odd and (PICK - k) <= n_even:
            theoretical[k] = math.comb(n_odd, k) * math.comb(n_even, PICK - k) / math.comb(POOL, PICK)
        else:
            theoretical[k] = 0

    obs_arr = [odd_dist.get(k, 0) for k in range(PICK + 1)]
    exp_arr = [theoretical.get(k, 0) * N for k in range(PICK + 1)]
    chi2_h4, p_h4 = stats.chisquare(obs_arr, f_exp=exp_arr)
    results['H4_odd_even'] = {'chi2': chi2_h4, 'p_value': p_h4}
    verdict_h4 = "✅ 偏離理論" if p_h4 < 0.05 else "❌ 符合超幾何"
    print(f"  χ²={chi2_h4:.2f}, p={p_h4:.6f} → {verdict_h4}")
    for k in range(PICK + 1):
        print(f"    {k}奇{PICK-k}偶: 實測={odd_dist.get(k, 0)} 期望={exp_arr[k]:.1f} 理論={theoretical[k]*100:.2f}%")

    # ── H5: 區域分布偏移假說 ──
    print("\n▶ H5: 區域分布偏移假說 (三區 1-13/14-26/27-39)")
    zone_counts = [0, 0, 0]
    for d in draws:
        for num in d['numbers']:
            if num <= 13:
                zone_counts[0] += 1
            elif num <= 26:
                zone_counts[1] += 1
            else:
                zone_counts[2] += 1
    # 期望: 每區 13/39 × 5 × N
    expected_z = [13 / POOL * PICK * N, 13 / POOL * PICK * N, 13 / POOL * PICK * N]
    chi2_h5, p_h5 = stats.chisquare(zone_counts, f_exp=expected_z)
    results['H5_zone'] = {'chi2': chi2_h5, 'p_value': p_h5, 'observed': zone_counts, 'expected': expected_z}
    verdict_h5 = "✅ 區域偏差" if p_h5 < 0.05 else "❌ 區域均勻"
    print(f"  χ²={chi2_h5:.2f}, p={p_h5:.6f} → {verdict_h5}")
    for z in range(3):
        print(f"    Zone {z+1}: 實測={zone_counts[z]} 期望={expected_z[z]:.1f}")

    # ── H6: Lag-2 回聲假說 ──
    print("\n▶ H6: Lag-2 回聲假說")
    lag2_overlaps = []
    for i in range(2, N):
        overlap = len(set(draws[i-2]['numbers']) & set(draws[i]['numbers']))
        lag2_overlaps.append(overlap)

    # 理論: 如果獨立，E[overlap] = PICK * PICK / POOL
    expected_overlap = PICK * PICK / POOL
    actual_overlap = np.mean(lag2_overlaps)
    t_stat, p_h6 = stats.ttest_1samp(lag2_overlaps, expected_overlap)
    results['H6_lag2'] = {
        'actual_mean': actual_overlap,
        'expected_mean': expected_overlap,
        't_stat': t_stat,
        'p_value': p_h6
    }
    verdict_h6 = "✅ Lag-2 回聲顯著" if p_h6 < 0.05 else "❌ 與理論無異"
    print(f"  實測均值: {actual_overlap:.4f}, 理論: {expected_overlap:.4f}")
    print(f"  t={t_stat:.3f}, p={p_h6:.6f} → {verdict_h6}")

    # Lag-1 也測
    lag1_overlaps = []
    for i in range(1, N):
        overlap = len(set(draws[i-1]['numbers']) & set(draws[i]['numbers']))
        lag1_overlaps.append(overlap)
    t_stat_l1, p_l1 = stats.ttest_1samp(lag1_overlaps, expected_overlap)
    results['H6_lag1'] = {
        'actual_mean': np.mean(lag1_overlaps),
        'expected_mean': expected_overlap,
        't_stat': t_stat_l1,
        'p_value': p_l1
    }
    print(f"  [Lag-1] 實測均值: {np.mean(lag1_overlaps):.4f}, t={t_stat_l1:.3f}, p={p_l1:.6f}")

    # ── H7: Markov 轉移假說 ──
    print("\n▶ H7: Markov 轉移假說 — 轉移矩陣均勻性檢驗")
    transition = np.zeros((POOL, POOL))
    for i in range(N - 1):
        for a in draws[i]['numbers']:
            for b in draws[i + 1]['numbers']:
                transition[a - 1][b - 1] += 1

    # 每行應該是均勻的 (如果 Markov 不存在)
    # χ² 檢定每行
    markov_p_values = []
    for row in range(POOL):
        row_data = transition[row]
        row_total = row_data.sum()
        if row_total > 0:
            expected_row = [row_total / POOL] * POOL
            chi2_row, p_row = stats.chisquare(row_data, f_exp=expected_row)
            markov_p_values.append(p_row)

    # Bonferroni 修正
    n_tests_markov = len(markov_p_values)
    significant_rows = sum(1 for p in markov_p_values if p < 0.05 / n_tests_markov)

    results['H7_markov'] = {
        'significant_rows_bonferroni': significant_rows,
        'total_rows': n_tests_markov,
        'min_p': min(markov_p_values) if markov_p_values else 1.0,
        'mean_p': np.mean(markov_p_values) if markov_p_values else 1.0
    }
    verdict_h7 = f"✅ {significant_rows}/{n_tests_markov} 行顯著" if significant_rows > 0 else "❌ 無顯著轉移"
    print(f"  Bonferroni 修正後顯著行數: {significant_rows}/{n_tests_markov}")
    print(f"  最小 p-value: {min(markov_p_values):.6f}")
    print(f"  → {verdict_h7}")

    # ── H8: 週期/傅立葉假說 ──
    print("\n▶ H8: 傅立葉頻譜假說 — 是否存在顯著週期")
    # 對隨機取 5 個號碼測試 (取頻率最高的號碼)
    top_num = max(freq, key=freq.get)
    series = np.array([1 if top_num in d['numbers'] else 0 for d in draws], dtype=float)
    fft_vals = np.fft.rfft(series)
    power = np.abs(fft_vals) ** 2

    # 白噪音基準: 功率均值
    mean_power = np.mean(power[1:])  # 排除 DC
    # 99% 信賴帶 (指數分布近似)
    threshold_99 = -mean_power * np.log(0.01)

    # 有多少頻率超過 99% 門檻
    n_significant_freqs = sum(1 for p in power[1:] if p > threshold_99)
    max_power_idx = np.argmax(power[1:]) + 1
    max_period = len(series) / max_power_idx if max_power_idx > 0 else 0

    results['H8_fourier'] = {
        'test_number': int(top_num),
        'n_significant_above_99pct': n_significant_freqs,
        'total_frequencies': len(power) - 1,
        'max_power_period': max_period,
        'mean_power': float(mean_power),
        'max_power': float(max(power[1:])),
        'threshold_99': float(threshold_99)
    }
    verdict_h8 = f"✅ {n_significant_freqs} 頻率顯著" if n_significant_freqs > len(power) * 0.01 else "❌ 與白噪音無異"
    print(f"  測試號碼: {top_num} (最高頻)")
    print(f"  超過 99% 白噪音門檻的頻率: {n_significant_freqs}/{len(power)-1}")
    print(f"  最強週期: {max_period:.1f} 期")
    print(f"  → {verdict_h8}")

    # ── H9: 趨勢漂移假說 ──
    print("\n▶ H9: 趨勢漂移假說 — 分段 KS 檢驗")
    segment_size = 500
    segments = [draws[i:i+segment_size] for i in range(0, N - segment_size, segment_size)]
    ks_results = []

    if len(segments) >= 2:
        for i in range(len(segments) - 1):
            dist_a = Counter()
            dist_b = Counter()
            for d in segments[i]:
                for num in d['numbers']:
                    dist_a[num] += 1
            for d in segments[i + 1]:
                for num in d['numbers']:
                    dist_b[num] += 1

            # KS test 需要連續分布，用 CDFs
            vals_a = []
            for d in segments[i]:
                vals_a.extend(d['numbers'])
            vals_b = []
            for d in segments[i + 1]:
                vals_b.extend(d['numbers'])

            ks_stat, p_ks = stats.ks_2samp(vals_a, vals_b)
            ks_results.append({'segment_pair': f'{i}-{i+1}', 'ks': ks_stat, 'p': p_ks})

    significant_drift = sum(1 for r in ks_results if r['p'] < 0.05)
    results['H9_drift'] = {
        'n_segment_pairs': len(ks_results),
        'significant_pairs': significant_drift,
        'details': ks_results
    }
    verdict_h9 = f"✅ {significant_drift} 對有漂移" if significant_drift > 0 else "❌ 分布穩態"
    print(f"  分段數: {len(segments)}, 顯著漂移對: {significant_drift}")
    for r in ks_results[:5]:
        print(f"    Segment {r['segment_pair']}: KS={r['ks']:.4f}, p={r['p']:.6f}")
    print(f"  → {verdict_h9}")

    # ── H10: Fourier 節奏量化 ──
    print("\n▶ H10: 傅立葉節奏假說 — 全部 39 個號碼的頻譜分析")
    n_nums_with_signal = 0
    for num in range(1, POOL + 1):
        s = np.array([1 if num in d['numbers'] else 0 for d in draws], dtype=float)
        fft_v = np.fft.rfft(s)
        pw = np.abs(fft_v) ** 2
        mean_pw = np.mean(pw[1:])
        thresh = -mean_pw * np.log(0.01)
        n_sig = sum(1 for p in pw[1:] if p > thresh)
        if n_sig > len(pw) * 0.02:  # 超過 2% 的頻率顯著
            n_nums_with_signal += 1

    results['H10_fourier_all'] = {'total': POOL, 'with_signal': n_nums_with_signal}
    verdict_h10 = f"✅ {n_nums_with_signal}/{POOL} 號碼有頻譜訊號" if n_nums_with_signal > 5 else "❌ 無普遍訊號"
    print(f"  有頻譜訊號的號碼: {n_nums_with_signal}/{POOL}")
    print(f"  → {verdict_h10}")

    # ── H11: 號碼對共現假說 ──
    print("\n▶ H11: 號碼對共現假說 — Bonferroni 修正的 Binomial test")
    pair_counter = Counter()
    for d in draws:
        nums = d['numbers']
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                pair_counter[(nums[i], nums[j])] += 1

    total_pairs = math.comb(POOL, 2)  # 741
    expected_pair = N * math.comb(PICK, 2) / total_pairs  # 每對期望出現次數
    alpha_bonf = 0.05 / total_pairs

    significant_pairs = 0
    most_extreme_pair = None
    most_extreme_p = 1.0

    for pair, count in pair_counter.items():
        # Binomial test: 每期出現機率 = C(37,3)/C(39,5) = 7770/575757
        p_pair_per_draw = math.comb(POOL - 2, PICK - 2) / math.comb(POOL, PICK)
        p_binom = stats.binom_test(count, N, p_pair_per_draw) if hasattr(stats, 'binom_test') else 1.0
        try:
            p_binom = stats.binomtest(count, N, p_pair_per_draw).pvalue
        except AttributeError:
            p_binom = stats.binom_test(count, N, p_pair_per_draw)

        if p_binom < alpha_bonf:
            significant_pairs += 1
        if p_binom < most_extreme_p:
            most_extreme_p = p_binom
            most_extreme_pair = (pair, count, p_binom)

    results['H11_pairs'] = {
        'total_pairs': total_pairs,
        'bonferroni_alpha': alpha_bonf,
        'significant_after_bonferroni': significant_pairs,
        'most_extreme': {
            'pair': list(most_extreme_pair[0]) if most_extreme_pair else None,
            'count': most_extreme_pair[1] if most_extreme_pair else None,
            'p_value': most_extreme_pair[2] if most_extreme_pair else None
        },
        'expected_count': expected_pair
    }
    verdict_h11 = f"✅ {significant_pairs} 對顯著" if significant_pairs > 0 else "❌ 無顯著號碼對"
    print(f"  總號碼對: {total_pairs}")
    print(f"  Bonferroni α: {alpha_bonf:.8f}")
    print(f"  通過修正的顯著對: {significant_pairs}")
    if most_extreme_pair:
        print(f"  最極端: {most_extreme_pair[0]} 出現 {most_extreme_pair[1]} 次 (期望 {expected_pair:.1f}), p={most_extreme_pair[2]:.6e}")
    print(f"  → {verdict_h11}")

    # ── H13: 連號模式假說 ──
    print("\n▶ H13: 連號模式假說")
    consec_counts = []
    for d in draws:
        nums = sorted(d['numbers'])
        consec = 0
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] == 1:
                consec += 1
        consec_counts.append(consec)

    # 理論: Monte Carlo 模擬
    rng = np.random.RandomState(42)
    mc_consec = []
    for _ in range(100000):
        sample = sorted(rng.choice(range(1, POOL + 1), size=PICK, replace=False))
        c = sum(1 for i in range(len(sample) - 1) if sample[i + 1] - sample[i] == 1)
        mc_consec.append(c)

    actual_mean = np.mean(consec_counts)
    mc_mean = np.mean(mc_consec)
    t_h13, p_h13 = stats.ttest_1samp(consec_counts, mc_mean)
    results['H13_consecutive'] = {
        'actual_mean': actual_mean,
        'mc_mean': mc_mean,
        't_stat': t_h13,
        'p_value': p_h13
    }
    verdict_h13 = "✅ 連號頻率異常" if p_h13 < 0.05 else "❌ 符合隨機"
    print(f"  實測連號均值: {actual_mean:.4f}")
    print(f"  Monte Carlo 期望: {mc_mean:.4f}")
    print(f"  t={t_h13:.3f}, p={p_h13:.6f} → {verdict_h13}")

    # ── H14: 和值範圍假說 ──
    print("\n▶ H14: 和值範圍假說")
    sums = [sum(d['numbers']) for d in draws]
    # CLT 近似: μ = 5 × 20 = 100, σ² = approx
    mc_sums = []
    for _ in range(100000):
        sample = rng.choice(range(1, POOL + 1), size=PICK, replace=False)
        mc_sums.append(sum(sample))

    ks_sum, p_sum = stats.ks_2samp(sums, mc_sums)
    results['H14_sum_range'] = {
        'actual_mean': np.mean(sums),
        'actual_std': np.std(sums),
        'mc_mean': np.mean(mc_sums),
        'mc_std': np.std(mc_sums),
        'ks_stat': ks_sum,
        'p_value': p_sum
    }
    verdict_h14 = "✅ 和值分布異常" if p_sum < 0.05 else "❌ 符合隨機"
    print(f"  實測均值: {np.mean(sums):.2f}, 標準差: {np.std(sums):.2f}")
    print(f"  MC 均值: {np.mean(mc_sums):.2f}, 標準差: {np.std(mc_sums):.2f}")
    print(f"  KS={ks_sum:.4f}, p={p_sum:.6f} → {verdict_h14}")

    # ── H15: 條件熵下降假說 ──
    print("\n▶ H15: 條件熵下降假說")
    # 用全體號碼的 autocorrelation 來估計
    all_series = {}
    for num in range(1, POOL + 1):
        all_series[num] = np.array([1 if num in d['numbers'] else 0 for d in draws], dtype=float)

    # 計算 lag-1 的互資訊近似
    # MI(X_t, X_{t-1}) for each number
    mi_vals = []
    for num in range(1, POOL + 1):
        s = all_series[num]
        # Lag-1 mutual information
        x = s[:-1]
        y = s[1:]
        # 建構聯合分布
        joint = Counter()
        for xi, yi in zip(x, y):
            joint[(int(xi), int(yi))] += 1
        total_joint = len(x)
        px = Counter(x.astype(int))
        py = Counter(y.astype(int))

        mi = 0.0
        for (xi, yi), count in joint.items():
            p_xy = count / total_joint
            p_x = px[xi] / total_joint
            p_y = py[yi] / total_joint
            if p_xy > 0 and p_x > 0 and p_y > 0:
                mi += p_xy * np.log2(p_xy / (p_x * p_y))
        mi_vals.append(mi)

    avg_mi = np.mean(mi_vals)
    # 比較: shuffled MI
    shuffle_mi_vals = []
    rng2 = np.random.RandomState(42)
    for _ in range(100):
        mi_s = []
        for num in range(1, POOL + 1):
            s = all_series[num].copy()
            rng2.shuffle(s)
            x = s[:-1]
            y = s[1:]
            joint = Counter()
            for xi, yi in zip(x, y):
                joint[(int(xi), int(yi))] += 1
            total_joint = len(x)
            px = Counter(x.astype(int))
            py = Counter(y.astype(int))
            mi = 0.0
            for (xi, yi), count in joint.items():
                p_xy = count / total_joint
                p_x = px[xi] / total_joint
                p_y = py[yi] / total_joint
                if p_xy > 0 and p_x > 0 and p_y > 0:
                    mi += p_xy * np.log2(p_xy / (p_x * p_y))
            mi_s.append(mi)
        shuffle_mi_vals.append(np.mean(mi_s))

    p_mi = np.mean([m >= avg_mi for m in shuffle_mi_vals])
    results['H15_cond_entropy'] = {
        'avg_mi_real': avg_mi,
        'avg_mi_shuffle': np.mean(shuffle_mi_vals),
        'p_value': p_mi
    }
    verdict_h15 = "✅ 條件熵顯著下降" if p_mi < 0.05 else "❌ 無可利用的時序依賴"
    print(f"  真實平均 MI(X_t, X_{{t-1}}): {avg_mi:.6f}")
    print(f"  Shuffle 平均 MI: {np.mean(shuffle_mi_vals):.6f}")
    print(f"  p-value: {p_mi:.4f} → {verdict_h15}")

    # ── H24: 尾數分布假說 ──
    print("\n▶ H24: 尾數分布假說")
    tail_counter = Counter()
    for d in draws:
        for num in d['numbers']:
            tail_counter[num % 10] += 1
    total_tails = sum(tail_counter.values())

    # 理論: 各尾數有多少個號碼
    tail_pool = Counter()
    for num in range(1, POOL + 1):
        tail_pool[num % 10] += 1
    # 期望頻率 ∝ 該尾數的號碼數量
    expected_tails = [tail_pool[t] / POOL * total_tails for t in range(10)]
    observed_tails = [tail_counter.get(t, 0) for t in range(10)]
    chi2_h24, p_h24 = stats.chisquare(observed_tails, f_exp=expected_tails)
    results['H24_tails'] = {'chi2': chi2_h24, 'p_value': p_h24}
    verdict_h24 = "✅ 尾數偏差" if p_h24 < 0.05 else "❌ 符合比例期望"
    print(f"  χ²={chi2_h24:.2f}, p={p_h24:.6f} → {verdict_h24}")
    for t in range(10):
        print(f"    尾數 {t}: 實測={observed_tails[t]} 期望={expected_tails[t]:.1f} (池中{tail_pool[t]}個號碼)")

    # ══════════════════════════════════════════
    # PART B: 自動特徵搜尋
    # ══════════════════════════════════════════

    print("\n" + "═" * 80)
    print("PART B: 自動特徵搜尋 (Auto-Discovery)")
    print("═" * 80)

    # 生成特徵: 每個特徵是一個函數 f(history[:i]) → 分數向量 (39維)
    # 然後衡量 「高分號碼是否更容易命中」

    WINDOWS = [20, 50, 100, 200]
    features_tested = 0
    significant_features = []

    # 特徵生成器
    feature_generators = []

    # F1: 頻率 (多窗口)
    for w in WINDOWS:
        def make_freq(window=w):
            def f(history):
                recent = history[-window:] if len(history) >= window else history
                c = Counter()
                for d in recent:
                    for num in d['numbers']:
                        c[num] += 1
                total = sum(c.values()) or 1
                return {num: c.get(num, 0) / total for num in range(1, POOL + 1)}
            return f
        feature_generators.append((f"freq_w{w}", make_freq(w)))

    # F2: Gap (多窗口)
    for w in WINDOWS:
        def make_gap(window=w):
            def f(history):
                recent = history[-window:] if len(history) >= window else history
                last_seen = {}
                for i, d in enumerate(recent):
                    for num in d['numbers']:
                        last_seen[num] = i
                current = len(recent)
                return {num: (current - last_seen.get(num, -1)) / max(current, 1) for num in range(1, POOL + 1)}
            return f
        feature_generators.append((f"gap_w{w}", make_gap(w)))

    # F3: Lag-k 出現 (k=1,2,3)
    for lag in [1, 2, 3]:
        def make_lag(k=lag):
            def f(history):
                if len(history) < k:
                    return {num: 0 for num in range(1, POOL + 1)}
                lag_nums = set(history[-k]['numbers'])
                return {num: (1.0 if num in lag_nums else 0.0) for num in range(1, POOL + 1)}
            return f
        feature_generators.append((f"lag_{lag}", make_lag(lag)))

    # F4: 偏差 (freq - expected)
    for w in WINDOWS:
        def make_dev(window=w):
            def f(history):
                recent = history[-window:] if len(history) >= window else history
                c = Counter()
                for d in recent:
                    for num in d['numbers']:
                        c[num] += 1
                expected = len(recent) * PICK / POOL
                return {num: (c.get(num, 0) - expected) for num in range(1, POOL + 1)}
            return f
        feature_generators.append((f"dev_w{w}", make_dev(w)))

    # F5: 趨勢 (EMA)
    for lam in [0.01, 0.05, 0.1]:
        def make_ema(decay=lam):
            def f(history):
                scores = {num: 0.0 for num in range(1, POOL + 1)}
                for i, d in enumerate(history[-200:]):
                    weight = np.exp(-decay * (len(history) - 200 + len(history[-200:]) - i))
                    for num in d['numbers']:
                        scores[num] += weight
                return scores
            return f
        feature_generators.append((f"ema_l{lam}", make_ema(lam)))

    # F6: 尾數偏離
    def make_tail_deficit():
        def f(history):
            recent = history[-100:] if len(history) >= 100 else history
            tail_c = Counter()
            for d in recent:
                for num in d['numbers']:
                    tail_c[num % 10] += 1
            total = sum(tail_c.values()) or 1
            tail_pool_count = Counter()
            for num in range(1, POOL + 1):
                tail_pool_count[num % 10] += 1
            return {num: (tail_pool_count[num % 10] / POOL - tail_c[num % 10] / total)
                    for num in range(1, POOL + 1)}
        return f
    feature_generators.append(("tail_deficit", make_tail_deficit()))

    # F7: 區域偏離
    def make_zone_deficit():
        def f(history):
            recent = history[-100:] if len(history) >= 100 else history
            zone_c = [0, 0, 0]
            for d in recent:
                for num in d['numbers']:
                    if num <= 13:
                        zone_c[0] += 1
                    elif num <= 26:
                        zone_c[1] += 1
                    else:
                        zone_c[2] += 1
            total = sum(zone_c) or 1
            return {num: (1/3 - zone_c[(num - 1) // 13] / total)
                    for num in range(1, POOL + 1)}
        return f
    feature_generators.append(("zone_deficit", make_zone_deficit()))

    # F8: 雙號窗口差分 (freq_w20 - freq_w100)
    def make_freq_diff():
        def f(history):
            r20 = history[-20:] if len(history) >= 20 else history
            r100 = history[-100:] if len(history) >= 100 else history
            c20 = Counter()
            c100 = Counter()
            for d in r20:
                for num in d['numbers']:
                    c20[num] += 1
            for d in r100:
                for num in d['numbers']:
                    c100[num] += 1
            t20 = sum(c20.values()) or 1
            t100 = sum(c100.values()) or 1
            return {num: (c20.get(num, 0) / t20 - c100.get(num, 0) / t100)
                    for num in range(1, POOL + 1)}
        return f
    feature_generators.append(("freq_diff_20v100", make_freq_diff()))

    # ── 運行特徵搜尋 ──
    print(f"\n生成 {len(feature_generators)} 個特徵，開始回測評估...")

    TEST_RANGE = 1000  # 使用最後 1000 期測試
    start_idx = max(200, N - TEST_RANGE)

    bonferroni_alpha = 0.05 / len(feature_generators)

    for fname, ffunc in feature_generators:
        # 策略: 每期取特徵分數最高的 5 個號碼做為預測
        ge2_count = 0
        test_count = 0

        for i in range(start_idx, N):
            history = draws[:i]  # 嚴格不含 i
            scores = ffunc(history)
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            prediction = set(x[0] for x in ranked[:PICK])
            actual = set(draws[i]['numbers'])

            if len(prediction & actual) >= 2:
                ge2_count += 1
            test_count += 1

        if test_count == 0:
            continue

        rate = ge2_count / test_count
        edge = rate - BASELINE_1BET_GE2

        # Z-test
        p_0 = BASELINE_1BET_GE2
        se = (p_0 * (1 - p_0) / test_count) ** 0.5
        z = (rate - p_0) / se if se > 0 else 0
        p_value = 1 - stats.norm.cdf(z) if z > 0 else 1.0

        features_tested += 1
        status = ""
        if p_value < bonferroni_alpha:
            status = "🟢 BONFERRONI_PASS"
            significant_features.append({
                'name': fname,
                'rate': rate,
                'edge': edge,
                'z': z,
                'p_value': p_value
            })
        elif p_value < 0.05:
            status = "🟡 nominal_only"
        else:
            status = ""

        if edge > 0 or status:
            print(f"  {fname:25s} | Rate={rate*100:.3f}% | Edge={edge*100:+.3f}% | z={z:.2f} | p={p_value:.4f} {status}")

    print(f"\n{'═'*60}")
    print(f"特徵搜尋結果:")
    print(f"  測試特徵數: {features_tested}")
    print(f"  Bonferroni α: {bonferroni_alpha:.6f}")
    print(f"  通過 Bonferroni: {len(significant_features)}")

    if significant_features:
        print(f"\n  通過 Bonferroni 的特徵:")
        for sf in significant_features:
            print(f"    🟢 {sf['name']}: Edge={sf['edge']*100:+.3f}%, z={sf['z']:.2f}, p={sf['p_value']:.6f}")
    else:
        print(f"\n  ❌ 0/{features_tested} 特徵通過 Bonferroni 修正")
        print(f"     與大樂透/威力彩研究結論一致 (0/54)")

    results['auto_discovery'] = {
        'features_tested': features_tested,
        'bonferroni_alpha': bonferroni_alpha,
        'passed': len(significant_features),
        'significant': significant_features
    }

    # ══════════════════════════════════════════
    # 總結
    # ══════════════════════════════════════════

    print("\n" + "═" * 80)
    print("假說驗證總結")
    print("═" * 80)
    hypothesis_summary = [
        ('H1', '頻率偏差', results.get('H1_frequency', {}).get('p_value', 1)),
        ('H4', '奇偶比失衡', results.get('H4_odd_even', {}).get('p_value', 1)),
        ('H5', '區域偏移', results.get('H5_zone', {}).get('p_value', 1)),
        ('H6', 'Lag-2 回聲', results.get('H6_lag2', {}).get('p_value', 1)),
        ('H7', 'Markov 轉移', 0.05 if results.get('H7_markov', {}).get('significant_rows_bonferroni', 0) > 0 else 1.0),
        ('H8', '傅立葉週期', 0.01 if results.get('H8_fourier', {}).get('n_significant_above_99pct', 0) > 0 else 1.0),
        ('H9', '趨勢漂移', min([r['p'] for r in results.get('H9_drift', {}).get('details', [{'p': 1}])]) if results.get('H9_drift', {}).get('details') else 1.0),
        ('H11', '號碼對共現', results.get('H11_pairs', {}).get('most_extreme', {}).get('p_value', 1) or 1.0),
        ('H13', '連號模式', results.get('H13_consecutive', {}).get('p_value', 1)),
        ('H14', '和值範圍', results.get('H14_sum_range', {}).get('p_value', 1)),
        ('H15', '條件熵下降', results.get('H15_cond_entropy', {}).get('p_value', 1)),
        ('H24', '尾數分布', results.get('H24_tails', {}).get('p_value', 1)),
    ]

    print(f"\n{'假說':<6s} {'描述':<15s} {'p-value':>10s} {'判定'}")
    print(f"{'─'*6} {'─'*15} {'─'*10} {'─'*20}")
    for h_id, desc, p_val in hypothesis_summary:
        if p_val < 0.001:
            verdict = "✅✅✅ 極顯著"
        elif p_val < 0.01:
            verdict = "✅✅ 高度顯著"
        elif p_val < 0.05:
            verdict = "✅ 顯著"
        else:
            verdict = "❌ 不顯著"
        print(f"{h_id:<6s} {desc:<15s} {p_val:10.6f} {verdict}")

    # 保存
    serializable_results = {}
    for k, v in results.items():
        if isinstance(v, dict):
            sr = {}
            for kk, vv in v.items():
                if isinstance(vv, (np.floating, np.integer)):
                    sr[kk] = float(vv)
                elif isinstance(vv, np.ndarray):
                    sr[kk] = vv.tolist()
                elif isinstance(vv, list):
                    sr[kk] = [{kkk: float(vvv) if isinstance(vvv, (np.floating,)) else vvv
                               for kkk, vvv in item.items()} if isinstance(item, dict) else item
                              for item in vv]
                else:
                    sr[kk] = vv
            serializable_results[k] = sr
        else:
            serializable_results[k] = v

    output_path = os.path.join(os.path.dirname(__file__), '..', 'hypothesis_39lotto_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(serializable_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n💾 結果已保存至: {output_path}")


if __name__ == '__main__':
    main()
