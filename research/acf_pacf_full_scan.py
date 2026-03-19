#!/usr/bin/env python3
"""
S1: ACF/PACF 全掃描 — 三彩種號碼週期信號分析
==============================================
對每個號碼計算自相關 (ACF) 和偏自相關 (PACF)，
發現隱藏週期信號。

分析維度:
  1. 個別號碼 ACF (lag=1~30) — 號碼自身的週期性
  2. 個別號碼 PACF (lag=1~20) — 排除中間 lag 後的直接相關
  3. Sum 序列 ACF — 開獎總和的自相關
  4. Zone 分布 ACF — Zone 佔比的自相關
  5. 跨號碼相關 — 號碼 A 出現是否預測號碼 B 下期出現

Seed: 42
Anti-leakage: 純分析，無預測
"""
import os
import sys
import json
import numpy as np
from collections import Counter, defaultdict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

DB_PATH = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')

LOTTERY_CONFIGS = {
    'BIG_LOTTO': {'max_num': 49, 'pick': 6, 'zones': [(1,16), (17,32), (33,49)]},
    'POWER_LOTTO': {'max_num': 38, 'pick': 6, 'zones': [(1,13), (14,25), (26,38)]},
    'DAILY_539': {'max_num': 39, 'pick': 5, 'zones': [(1,13), (14,26), (27,39)]},
}

MAX_LAG_ACF = 30
MAX_LAG_PACF = 20
SIGNIFICANCE_MULTIPLIER = 2.0  # 2/sqrt(N) 門檻


def compute_acf(series, max_lag):
    """計算自相關函數 (Pearson)"""
    n = len(series)
    mean = np.mean(series)
    var = np.var(series)
    if var == 0:
        return np.zeros(max_lag + 1)
    acf = np.zeros(max_lag + 1)
    acf[0] = 1.0
    for lag in range(1, max_lag + 1):
        if lag >= n:
            break
        cov = np.mean((series[:n-lag] - mean) * (series[lag:] - mean))
        acf[lag] = cov / var
    return acf


def compute_pacf(series, max_lag):
    """計算偏自相關函數 (Durbin-Levinson)"""
    n = len(series)
    acf = compute_acf(series, max_lag)
    pacf = np.zeros(max_lag + 1)
    pacf[0] = 1.0
    if max_lag == 0:
        return pacf

    # Durbin-Levinson recursion
    phi = np.zeros((max_lag + 1, max_lag + 1))
    phi[1, 1] = acf[1]
    pacf[1] = acf[1]

    for k in range(2, max_lag + 1):
        num = acf[k] - sum(phi[k-1, j] * acf[k-j] for j in range(1, k))
        den = 1.0 - sum(phi[k-1, j] * acf[j] for j in range(1, k))
        if abs(den) < 1e-12:
            break
        phi[k, k] = num / den
        pacf[k] = phi[k, k]
        for j in range(1, k):
            phi[k, j] = phi[k-1, j] - phi[k, k] * phi[k-1, k-j]

    return pacf


def analyze_single_number(series, n_draws, num_id, threshold):
    """分析單一號碼的 ACF/PACF"""
    acf = compute_acf(series, MAX_LAG_ACF)
    pacf = compute_pacf(series, MAX_LAG_PACF)

    sig_acf = []
    for lag in range(1, MAX_LAG_ACF + 1):
        if abs(acf[lag]) > threshold:
            sig_acf.append({
                'lag': lag,
                'acf': round(float(acf[lag]), 4),
                'strength': 'strong' if abs(acf[lag]) > threshold * 1.5 else 'moderate'
            })

    sig_pacf = []
    for lag in range(1, MAX_LAG_PACF + 1):
        if abs(pacf[lag]) > threshold:
            sig_pacf.append({
                'lag': lag,
                'pacf': round(float(pacf[lag]), 4),
                'strength': 'strong' if abs(pacf[lag]) > threshold * 1.5 else 'moderate'
            })

    return {
        'number': num_id,
        'freq': float(np.mean(series)),
        'acf_values': [round(float(v), 4) for v in acf[1:11]],  # lag 1~10
        'pacf_values': [round(float(v), 4) for v in pacf[1:11]],
        'significant_acf': sig_acf,
        'significant_pacf': sig_pacf,
        'n_sig_acf': len(sig_acf),
        'n_sig_pacf': len(sig_pacf),
        'max_abs_acf': round(float(np.max(np.abs(acf[1:]))), 4),
        'max_abs_pacf': round(float(np.max(np.abs(pacf[1:]))), 4),
    }


def analyze_cross_correlation(draws, max_num, top_k=20):
    """跨號碼相關分析: 號碼 A 本期出現 → 號碼 B 下期出現的 Lift"""
    n = len(draws)
    # 建立二元矩陣
    matrix = np.zeros((n, max_num), dtype=np.int8)
    for i, d in enumerate(draws):
        for num in d['numbers']:
            if 1 <= num <= max_num:
                matrix[i, num - 1] = 1

    # 計算 cross-lag-1 相關
    cross_lifts = []
    base_freq = matrix.mean(axis=0)  # 每個號碼的基準頻率

    for a in range(max_num):
        if base_freq[a] == 0:
            continue
        # 當 A 在 t 期出現時，B 在 t+1 期出現的頻率
        a_appeared = matrix[:-1, a] == 1
        n_a = a_appeared.sum()
        if n_a < 20:  # 最少出現 20 次才計算
            continue

        for b in range(max_num):
            if a == b:
                continue
            cond_freq = matrix[1:, b][a_appeared].mean()
            lift = cond_freq / base_freq[b] if base_freq[b] > 0 else 1.0
            if abs(lift - 1.0) > 0.15:  # 只記錄 Lift > 1.15 或 < 0.85
                cross_lifts.append({
                    'from': a + 1,
                    'to': b + 1,
                    'lift': round(float(lift), 3),
                    'cond_freq': round(float(cond_freq), 4),
                    'base_freq': round(float(base_freq[b]), 4),
                    'n_samples': int(n_a),
                })

    # 按 |lift - 1| 排序，取 top_k
    cross_lifts.sort(key=lambda x: abs(x['lift'] - 1.0), reverse=True)
    return cross_lifts[:top_k]


def analyze_sum_series(draws):
    """Sum 序列的 ACF 分析"""
    sums = np.array([sum(d['numbers']) for d in draws], dtype=float)
    acf = compute_acf(sums, MAX_LAG_ACF)
    threshold = SIGNIFICANCE_MULTIPLIER / np.sqrt(len(sums))

    sig_lags = []
    for lag in range(1, MAX_LAG_ACF + 1):
        if abs(acf[lag]) > threshold:
            sig_lags.append({'lag': lag, 'acf': round(float(acf[lag]), 4)})

    return {
        'mean': round(float(np.mean(sums)), 2),
        'std': round(float(np.std(sums)), 2),
        'acf_lag1_10': [round(float(v), 4) for v in acf[1:11]],
        'significant_lags': sig_lags,
        'max_abs_acf': round(float(np.max(np.abs(acf[1:]))), 4),
    }


def analyze_zone_series(draws, zones, max_num):
    """Zone 分布的 ACF 分析"""
    n = len(draws)
    zone_counts = np.zeros((n, len(zones)))
    for i, d in enumerate(draws):
        for num in d['numbers']:
            for z_idx, (lo, hi) in enumerate(zones):
                if lo <= num <= hi:
                    zone_counts[i, z_idx] += 1
                    break

    results = {}
    threshold = SIGNIFICANCE_MULTIPLIER / np.sqrt(n)
    for z_idx, (lo, hi) in enumerate(zones):
        series = zone_counts[:, z_idx]
        acf = compute_acf(series, MAX_LAG_ACF)
        sig_lags = [{'lag': lag, 'acf': round(float(acf[lag]), 4)}
                    for lag in range(1, MAX_LAG_ACF + 1) if abs(acf[lag]) > threshold]
        results[f'Z{z_idx+1}({lo}-{hi})'] = {
            'mean': round(float(np.mean(series)), 2),
            'acf_lag1_5': [round(float(v), 4) for v in acf[1:6]],
            'significant_lags': sig_lags,
        }
    return results


def analyze_repeat_rate_series(draws):
    """重複號碼率的 ACF"""
    repeats = []
    for i in range(1, len(draws)):
        prev = set(draws[i-1]['numbers'])
        curr = set(draws[i]['numbers'])
        repeats.append(len(prev & curr))
    series = np.array(repeats, dtype=float)
    acf = compute_acf(series, MAX_LAG_ACF)
    threshold = SIGNIFICANCE_MULTIPLIER / np.sqrt(len(series))
    sig_lags = [{'lag': lag, 'acf': round(float(acf[lag]), 4)}
                for lag in range(1, MAX_LAG_ACF + 1) if abs(acf[lag]) > threshold]
    return {
        'mean_repeats': round(float(np.mean(series)), 3),
        'acf_lag1_10': [round(float(v), 4) for v in acf[1:11]],
        'significant_lags': sig_lags,
    }


def analyze_lag_echo_rates(draws, max_num, max_echo_lag=10):
    """Lag-K 回聲率分析 (擴展至 lag-10)"""
    n = len(draws)
    echo_rates = {}
    for lag in range(1, max_echo_lag + 1):
        hits = 0
        total = 0
        for i in range(lag, n):
            prev = set(draws[i - lag]['numbers'])
            curr = set(draws[i]['numbers'])
            overlap = len(prev & curr)
            hits += overlap
            total += len(curr)
        rate = hits / total if total > 0 else 0
        expected = len(draws[0]['numbers']) / max_num  # 隨機期望
        echo_rates[f'lag_{lag}'] = {
            'rate': round(rate, 4),
            'expected': round(expected, 4),
            'lift': round(rate / expected, 3) if expected > 0 else 0,
        }
    return echo_rates


def run_lottery_analysis(lottery_type, config):
    """對單一彩種執行完整 ACF/PACF 掃描"""
    db = DatabaseManager(DB_PATH)
    draws = sorted(db.get_all_draws(lottery_type), key=lambda x: (x['date'], x['draw']))
    n_draws = len(draws)
    max_num = config['max_num']

    print(f"\n{'=' * 72}")
    print(f"  {lottery_type} — ACF/PACF 全掃描")
    print(f"  期數: {n_draws}, 號碼池: 1~{max_num}, 選 {config['pick']} 個")
    print(f"{'=' * 72}")

    threshold = SIGNIFICANCE_MULTIPLIER / np.sqrt(n_draws)
    print(f"  顯著性門檻: |ACF| > {threshold:.4f} (2/√N)")

    # 1. 個別號碼 ACF/PACF
    print(f"\n  [1/6] 個別號碼 ACF/PACF 掃描...")
    matrix = np.zeros((n_draws, max_num), dtype=np.int8)
    for i, d in enumerate(draws):
        for num in d['numbers']:
            if 1 <= num <= max_num:
                matrix[i, num - 1] = 1

    number_results = []
    for num in range(1, max_num + 1):
        series = matrix[:, num - 1].astype(float)
        result = analyze_single_number(series, n_draws, num, threshold)
        number_results.append(result)

    # 統計
    n_with_sig_acf = sum(1 for r in number_results if r['n_sig_acf'] > 0)
    n_with_sig_pacf = sum(1 for r in number_results if r['n_sig_pacf'] > 0)
    print(f"    有顯著 ACF 信號的號碼: {n_with_sig_acf}/{max_num}")
    print(f"    有顯著 PACF 信號的號碼: {n_with_sig_pacf}/{max_num}")

    # Top 信號
    top_acf = sorted(number_results, key=lambda x: x['max_abs_acf'], reverse=True)[:10]
    print(f"\n    Top-10 最強 ACF 信號:")
    for r in top_acf:
        sig_str = ', '.join(f"lag{s['lag']}={s['acf']:+.4f}" for s in r['significant_acf'][:3])
        marker = '★' if r['n_sig_acf'] > 0 else ' '
        print(f"      {marker} 號碼 {r['number']:>2}: max|ACF|={r['max_abs_acf']:.4f}  "
              f"freq={r['freq']:.4f}  sig: {sig_str or '(none)'}")

    top_pacf = sorted(number_results, key=lambda x: x['max_abs_pacf'], reverse=True)[:10]
    print(f"\n    Top-10 最強 PACF 信號:")
    for r in top_pacf:
        sig_str = ', '.join(f"lag{s['lag']}={s['pacf']:+.4f}" for s in r['significant_pacf'][:3])
        marker = '★' if r['n_sig_pacf'] > 0 else ' '
        print(f"      {marker} 號碼 {r['number']:>2}: max|PACF|={r['max_abs_pacf']:.4f}  "
              f"sig: {sig_str or '(none)'}")

    # 顯著 lag 的分布
    lag_counter = Counter()
    for r in number_results:
        for s in r['significant_acf']:
            lag_counter[s['lag']] += 1
    if lag_counter:
        print(f"\n    ACF 顯著 lag 分布 (哪些 lag 最常出現):")
        for lag, count in lag_counter.most_common(10):
            print(f"      lag={lag}: {count}/{max_num} 號碼有顯著信號 ({count/max_num*100:.1f}%)")

    # 2. Sum 序列 ACF
    print(f"\n  [2/6] Sum 序列 ACF...")
    sum_result = analyze_sum_series(draws)
    print(f"    Sum 均值={sum_result['mean']}, 標準差={sum_result['std']}")
    print(f"    ACF lag1~10: {sum_result['acf_lag1_10']}")
    print(f"    max|ACF|={sum_result['max_abs_acf']}")
    if sum_result['significant_lags']:
        print(f"    ★ 顯著 lags: {sum_result['significant_lags']}")
    else:
        print(f"    (無顯著 lag)")

    # 3. Zone ACF
    print(f"\n  [3/6] Zone 分布 ACF...")
    zone_result = analyze_zone_series(draws, config['zones'], max_num)
    for zname, zdata in zone_result.items():
        sig_str = f" ★ sig: {zdata['significant_lags']}" if zdata['significant_lags'] else ""
        print(f"    {zname}: mean={zdata['mean']}, ACF1~5={zdata['acf_lag1_5']}{sig_str}")

    # 4. 重複號碼率 ACF
    print(f"\n  [4/6] 重複號碼率 ACF...")
    repeat_result = analyze_repeat_rate_series(draws)
    print(f"    平均重複數: {repeat_result['mean_repeats']}")
    print(f"    ACF lag1~10: {repeat_result['acf_lag1_10']}")
    if repeat_result['significant_lags']:
        print(f"    ★ 顯著: {repeat_result['significant_lags']}")

    # 5. Lag-K 回聲率
    print(f"\n  [5/6] Lag-K 回聲率 (lag 1~10)...")
    echo_result = analyze_lag_echo_rates(draws, max_num)
    for k, v in echo_result.items():
        marker = '★' if v['lift'] > 1.05 else ' '
        print(f"    {marker} {k}: rate={v['rate']:.4f}, expected={v['expected']:.4f}, "
              f"lift={v['lift']:.3f}x")

    # 6. 跨號碼相關
    print(f"\n  [6/6] 跨號碼 Cross-Lag-1 Lift (|lift-1| > 0.15)...")
    cross_result = analyze_cross_correlation(draws, max_num, top_k=15)
    if cross_result:
        for c in cross_result[:10]:
            direction = '→' if c['lift'] > 1.0 else '⊘'
            print(f"    {direction} {c['from']:>2} → {c['to']:>2}: lift={c['lift']:.3f}x  "
                  f"(cond={c['cond_freq']:.4f} vs base={c['base_freq']:.4f}, n={c['n_samples']})")
    else:
        print(f"    (無超過門檻的跨號碼相關)")

    return {
        'lottery_type': lottery_type,
        'n_draws': n_draws,
        'max_num': max_num,
        'threshold': round(threshold, 4),
        'numbers': number_results,
        'n_with_sig_acf': n_with_sig_acf,
        'n_with_sig_pacf': n_with_sig_pacf,
        'sum_acf': sum_result,
        'zone_acf': zone_result,
        'repeat_acf': repeat_result,
        'echo_rates': echo_result,
        'cross_correlations': cross_result,
    }


def print_summary(all_results):
    """全彩種總結"""
    print(f"\n{'=' * 72}")
    print(f"  === 三彩種 ACF/PACF 掃描總結 ===")
    print(f"{'=' * 72}")

    for r in all_results:
        lt = r['lottery_type']
        print(f"\n  {lt} ({r['n_draws']} 期, 門檻 |ACF|>{r['threshold']}):")
        print(f"    號碼信號: {r['n_with_sig_acf']}/{r['max_num']} ACF顯著, "
              f"{r['n_with_sig_pacf']}/{r['max_num']} PACF顯著")
        print(f"    Sum ACF: max|ACF|={r['sum_acf']['max_abs_acf']}")

        # 回聲率亮點
        echo_highlights = [(k, v) for k, v in r['echo_rates'].items() if v['lift'] > 1.03]
        if echo_highlights:
            echo_str = ', '.join(f"{k} lift={v['lift']:.3f}x" for k, v in echo_highlights[:3])
            print(f"    回聲亮點: {echo_str}")

        # 跨號碼亮點
        if r['cross_correlations']:
            top_cross = r['cross_correlations'][0]
            print(f"    最強跨號碼: {top_cross['from']}→{top_cross['to']} "
                  f"lift={top_cross['lift']:.3f}x (n={top_cross['n_samples']})")

    # 結論
    print(f"\n  {'─' * 60}")
    total_sig_acf = sum(r['n_with_sig_acf'] for r in all_results)
    total_nums = sum(r['max_num'] for r in all_results)
    random_expected = sum(r['max_num'] * 0.05 * MAX_LAG_ACF for r in all_results)
    # 在 30 個 lag 中, 隨機下約 5% 會通過門檻 → 每號碼 ~1.5 個 false positive
    print(f"  顯著 ACF 號碼: {total_sig_acf}/{total_nums}")
    print(f"  隨機預期 (5% false positive per lag): ~{random_expected:.0f} 個號碼×lag 組合")
    print(f"  (若顯著數 ≈ 隨機預期 → 無真實週期信號)")


def main():
    all_results = []
    for lt, config in LOTTERY_CONFIGS.items():
        result = run_lottery_analysis(lt, config)
        all_results.append(result)

    print_summary(all_results)

    # 儲存完整結果
    out_path = os.path.join(project_root, 'research', 'acf_pacf_scan_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n  完整結果已存至: {out_path}")


if __name__ == '__main__':
    main()
