#!/usr/bin/env python3
"""
今彩539 McNemar 配對檢定：ACB vs 現有冠軍方法
================================================
比較 P1_anomaly_capture 與 cold / state_space / markov
確認 ACB 是否真的優於現有方法，或僅是統計等效
"""

import json, sqlite3, sys, os, time
import numpy as np
from collections import Counter

_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_base, '..', 'lottery_api'))
sys.path.insert(0, os.path.join(_base, '..'))

POOL = 39
PICK = 5

# ═══════════════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════════════
DB_PATH = os.path.join(_base, '..', 'lottery_api', 'data', 'lottery_v2.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(_base, '..', 'lottery_v2.db')

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
    return [{'draw': d, 'date': dt, 'numbers': sorted(json.loads(n))} for d, dt, n in rows]

# ═══════════════════════════════════════════════════════════════════
# METHODS (identical to backtest_539_structural_upgrade.py)
# ═══════════════════════════════════════════════════════════════════

def method_state_space(hist, window=300):
    recent = hist[-window:] if len(hist) >= window else hist
    scores = {}
    for n in range(1, POOL + 1):
        series = [1 if n in d['numbers'] else 0 for d in recent]
        trans = {'00': 0, '01': 0, '10': 0, '11': 0}
        for i in range(1, len(series)):
            trans[f"{series[i-1]}{series[i]}"] += 1
        last_state = series[-1]
        total_from = trans[f'{last_state}0'] + trans[f'{last_state}1']
        scores[n] = trans[f'{last_state}1'] / total_from if total_from > 0 else 0.5
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_markov(hist, window=30):
    recent = hist[-window:] if len(hist) >= window else hist
    if len(recent) < 5:
        return list(range(1, PICK + 1))
    transition = np.zeros((POOL, POOL))
    for i in range(len(recent) - 1):
        for a in recent[i]['numbers']:
            for b in recent[i + 1]['numbers']:
                transition[a - 1][b - 1] += 1
    row_sums = transition.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    transition /= row_sums
    scores = np.zeros(POOL)
    for n in recent[-1]['numbers']:
        scores += transition[n - 1]
    ranked = np.argsort(-scores)
    return sorted([int(idx + 1) for idx in ranked[:PICK]])

def method_cold(hist, window=100):
    recent = hist[-window:] if len(hist) >= window else hist
    counter = Counter()
    for n in range(1, POOL + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    bottom = [x[0] for x in counter.most_common()[::-1][:PICK]]
    return sorted(bottom)

def method_fourier(hist, window=500):
    recent = hist[-window:] if len(hist) >= window else hist
    scores = {}
    for n in range(1, POOL + 1):
        series = np.array([1 if n in d['numbers'] else 0 for d in recent], dtype=float)
        fft_vals = np.fft.rfft(series)
        power = np.abs(fft_vals) ** 2
        if len(power) > 1:
            dom = np.argmax(power[1:]) + 1
            phase = np.angle(fft_vals[dom])
            freq = dom / len(series)
            t_next = len(series)
            predicted = np.abs(fft_vals[dom]) * np.cos(2 * np.pi * freq * t_next + phase)
            base = series.mean()
            scores[n] = base + 0.3 * predicted / (len(series) ** 0.5)
        else:
            scores[n] = 0
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_anomaly_capture(hist, window=100):
    recent = hist[-window:] if len(hist) >= window else hist
    counter = Counter()
    for n in range(1, POOL + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, POOL + 1)}
    expected_freq = len(recent) * PICK / POOL
    scores = {}
    for n in range(1, POOL + 1):
        freq_deficit = expected_freq - counter[n]
        gap_score = gaps[n] / (len(recent) / 2)
        boundary_bonus = 1.2 if (n <= 5 or n >= 35) else 1.0
        mod3_bonus = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus
    ranked = sorted(scores, key=lambda x: -scores[x])
    zones_selected = set()
    result = []
    for n in ranked:
        zone = 0 if n <= 13 else (1 if n <= 26 else 2)
        if len(result) < PICK:
            result.append(n)
            zones_selected.add(zone)
        if len(result) >= PICK:
            break
    if len(zones_selected) < 2 and len(result) >= PICK:
        missing_zones = set(range(3)) - zones_selected
        for mz in missing_zones:
            zone_range = range(1, 14) if mz == 0 else (range(14, 27) if mz == 1 else range(27, 40))
            zone_candidates = sorted([n for n in zone_range], key=lambda x: -scores[x])
            if zone_candidates:
                result[-1] = zone_candidates[0]
                break
    return sorted(result[:PICK])

# ═══════════════════════════════════════════════════════════════════
# MULTI-BET STRATEGIES
# ═══════════════════════════════════════════════════════════════════

def strategy_existing_2bet(hist):
    """舊冠軍: state_space + markov"""
    return [method_state_space(hist), method_markov(hist)]

def strategy_new_2bet(hist):
    """新挑戰者: state_space + ACB"""
    return [method_state_space(hist), method_anomaly_capture(hist)]

def strategy_existing_3bet(hist):
    """舊冠軍: state_space + markov + fourier"""
    return [method_state_space(hist), method_markov(hist), method_fourier(hist)]

def strategy_new_3bet(hist):
    """新挑戰者: state_space + markov + ACB"""
    return [method_state_space(hist), method_markov(hist), method_anomaly_capture(hist)]

# ═══════════════════════════════════════════════════════════════════
# McNEMAR TEST
# ═══════════════════════════════════════════════════════════════════

def mcnemar_test(func_a, func_b, all_draws, test_periods=1500, min_train=100, 
                 is_multi=False, name_a="A", name_b="B", min_hits=2):
    """
    McNemar paired test: A vs B
    For each draw: did A hit? did B hit? → 2×2 contingency
    """
    total = len(all_draws)
    start_idx = max(min_train, total - test_periods)
    
    both_hit = 0
    a_only = 0
    b_only = 0
    neither = 0
    test_count = 0
    a_total = 0
    b_total = 0
    
    for i in range(start_idx, total):
        hist = all_draws[:i]
        actual = set(all_draws[i]['numbers'])
        
        if is_multi:
            bets_a = func_a(hist)
            bets_b = func_b(hist)
            a_hit = any(len(set(bet) & actual) >= min_hits for bet in bets_a)
            b_hit = any(len(set(bet) & actual) >= min_hits for bet in bets_b)
        else:
            pred_a = func_a(hist)
            pred_b = func_b(hist)
            a_hit = len(set(pred_a) & actual) >= min_hits
            b_hit = len(set(pred_b) & actual) >= min_hits
        
        if a_hit and b_hit:
            both_hit += 1
        elif a_hit and not b_hit:
            a_only += 1
        elif not a_hit and b_hit:
            b_only += 1
        else:
            neither += 1
        
        if a_hit: a_total += 1
        if b_hit: b_total += 1
        test_count += 1
    
    # McNemar statistic
    b_val = a_only  # A中B未
    c_val = b_only  # B中A未
    
    if b_val + c_val > 0:
        chi2 = (b_val - c_val) ** 2 / (b_val + c_val)
        z = (b_val - c_val) / (b_val + c_val) ** 0.5
        # p-value (two-sided, using chi2 with 1 df)
        import math
        p_value = math.erfc(abs(z) / math.sqrt(2))  # two-sided
    else:
        chi2 = 0
        z = 0
        p_value = 1.0
    
    overlap = both_hit
    overlap_rate = overlap / max(a_total + b_total - overlap, 1)
    
    return {
        'name_a': name_a,
        'name_b': name_b,
        'test_count': test_count,
        'a_total': a_total,
        'b_total': b_total,
        'a_rate': a_total / test_count,
        'b_rate': b_total / test_count,
        'both_hit': both_hit,
        'a_only': a_only,  # b in McNemar
        'b_only': b_only,  # c in McNemar
        'neither': neither,
        'chi2': chi2,
        'z': z,
        'p_value': p_value,
        'significant': p_value < 0.05,
        'overlap_rate': overlap_rate,
        'complementary': a_only + b_only,
    }

def print_mcnemar(r):
    sig = "✅ 顯著" if r['significant'] else "❌ 無顯著差異"
    winner = r['name_a'] if r['a_only'] > r['b_only'] else r['name_b']
    diff = abs(r['a_only'] - r['b_only'])
    
    print(f"\n  McNemar 結果：{sig}")
    print(f"\n  {r['name_a']}: {r['a_total']}中 / {r['test_count']}期 = {r['a_rate']:.2%}")
    print(f"  {r['name_b']}: {r['b_total']}中 / {r['test_count']}期 = {r['b_rate']:.2%}")
    print(f"\n  b ({r['name_a']}中{r['name_b']}未) = {r['a_only']}")
    print(f"  c ({r['name_b']}中{r['name_a']}未) = {r['b_only']}")
    print(f"  差距 = {'+' if r['a_only'] >= r['b_only'] else '-'}{diff} 期 (方向有利 {winner})")
    print(f"\n  McNemar χ²={r['chi2']:.3f}  z={r['z']:.2f}  p={r['p_value']:.4f}")
    print(f"\n  兩者皆中: {r['both_hit']}期")
    print(f"  互補(各自獨有): {r['complementary']}期")
    print(f"  重疊率: {r['overlap_rate']:.1%}")

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    all_draws = load_draws()
    print(f"載入 {len(all_draws)} 期 DAILY_539 數據")
    print()
    
    # ─── 1. 單注: ACB vs Cold (現有冠軍) ─────────────────────
    print("=" * 70)
    print("  1. 單注 McNemar: ACB vs Cold(w=100) [現有單注冠軍]")
    print("=" * 70)
    r1 = mcnemar_test(method_anomaly_capture, method_cold, all_draws, 1500, 
                      name_a="ACB", name_b="Cold(w=100)", min_hits=2)
    print_mcnemar(r1)
    
    # ─── 2. 單注: ACB vs State Space ─────────────────────────
    print("\n" + "=" * 70)
    print("  2. 單注 McNemar: ACB vs State Space [RESEARCH_539 冠軍]")
    print("=" * 70)
    r2 = mcnemar_test(method_anomaly_capture, method_state_space, all_draws, 1500, 
                      name_a="ACB", name_b="StateSpace", min_hits=2)
    print_mcnemar(r2)
    
    # ─── 3. 單注: ACB vs Markov ──────────────────────────────
    print("\n" + "=" * 70)
    print("  3. 單注 McNemar: ACB vs Markov(w=30)")
    print("=" * 70)
    r3 = mcnemar_test(method_anomaly_capture, method_markov, all_draws, 1500, 
                      name_a="ACB", name_b="Markov(w=30)", min_hits=2)
    print_mcnemar(r3)
    
    # ─── 4. 2注: SS+ACB vs SS+MK ────────────────────────────
    print("\n" + "=" * 70)
    print("  4. 2注 McNemar: SS+ACB [新] vs SS+MK [舊]")
    print("=" * 70)
    r4 = mcnemar_test(strategy_new_2bet, strategy_existing_2bet, all_draws, 1500,
                      is_multi=True, name_a="SS+ACB", name_b="SS+MK(舊)", min_hits=2)
    print_mcnemar(r4)
    
    # ─── 5. 3注: SS+MK+ACB vs SS+MK+FR ──────────────────────
    print("\n" + "=" * 70)
    print("  5. 3注 McNemar: SS+MK+ACB [新] vs SS+MK+FR [舊]")
    print("=" * 70)
    r5 = mcnemar_test(strategy_new_3bet, strategy_existing_3bet, all_draws, 1500,
                      is_multi=True, name_a="SS+MK+ACB", name_b="SS+MK+FR(舊)", min_hits=2)
    print_mcnemar(r5)
    
    elapsed = time.time() - t0
    
    # ─── Summary ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"  總結 (耗時 {elapsed:.0f}秒)")
    print("=" * 70)
    
    all_results = [r1, r2, r3, r4, r5]
    any_sig = any(r['significant'] for r in all_results)
    
    if any_sig:
        sig_results = [r for r in all_results if r['significant']]
        print(f"\n  ✅ 有 {len(sig_results)} 組顯著差異:")
        for r in sig_results:
            winner = r['name_a'] if r['a_only'] > r['b_only'] else r['name_b']
            print(f"    {r['name_a']} vs {r['name_b']}: p={r['p_value']:.4f}, 勝方={winner}")
    else:
        print(f"\n  ❌ 所有5組對比均無顯著差異")
        print(f"     ACB 不能取代任何現有冠軍方法")
    
    print(f"\n  互補性分析:")
    for r in all_results:
        print(f"    {r['name_a']} vs {r['name_b']}: "
              f"重疊率={r['overlap_rate']:.1%}, "
              f"互補期數={r['complementary']}")
    
    # 裁定
    print(f"\n  {'─'*60}")
    print(f"  裁定：")
    if not any_sig:
        print(f"  → ACB 與現有方法統計等效，不做替換")
        print(f"  → ACB 降級至 ARCHIVED (非 REJECTED)")
        print(f"  → 保留作 4注組合互補研究參考")
    else:
        for r in sig_results:
            winner = r['name_a'] if r['a_only'] > r['b_only'] else r['name_b']
            loser = r['name_b'] if winner == r['name_a'] else r['name_a']
            print(f"  → {winner} 顯著優於 {loser}")
    
    # Save results
    output = {
        'test_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'lottery': 'DAILY_539',
        'total_periods': len(all_draws),
        'test_periods': 1500,
        'elapsed_seconds': round(elapsed, 1),
        'comparisons': []
    }
    for r in all_results:
        output['comparisons'].append({
            'name_a': r['name_a'], 'name_b': r['name_b'],
            'a_total': r['a_total'], 'b_total': r['b_total'],
            'a_rate': round(r['a_rate'], 6), 'b_rate': round(r['b_rate'], 6),
            'both_hit': r['both_hit'], 'a_only': r['a_only'], 'b_only': r['b_only'],
            'chi2': round(r['chi2'], 3), 'z': round(r['z'], 2), 'p_value': round(r['p_value'], 4),
            'significant': r['significant'], 'overlap_rate': round(r['overlap_rate'], 4),
        })
    
    out_path = os.path.join(_base, '..', 'mcnemar_539_acb_results.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已存: {out_path}")

if __name__ == '__main__':
    main()
