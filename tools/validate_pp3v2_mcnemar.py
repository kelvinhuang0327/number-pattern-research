#!/usr/bin/env python3
"""
PP3v2 vs PP3v1 正式驗證 — 1500期 + McNemar Test
================================================
目的: 確認 PP3v2 是否統計顯著優於原 PP3v1

回測規格:
  - 1500期滾動式 (start_offset=391, 保留391期暖機)
  - 三窗口: 150p / 500p / 1500p
  - McNemar chi² test (paired comparison)
  - Monte Carlo p-value (200 random strategies)
  - 每期記錄: hit≥1, hit≥2, hit_count
"""
import os
import sys
import math
import random
import numpy as np
from collections import Counter, defaultdict
from scipy.fft import fft, fftfreq
from scipy.stats import chi2

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

MAX_NUM = 38
PICK = 6


# ========== PP3v1 (原版, Fourier w=500) ==========

def pp3v1_fourier_rank(history, window=500):
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM:
                bitstreams[n][idx] = 1
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
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


def generate_pp3v1(history):
    """原版 PP3: Fourier w500 x2 + Echo/Cold"""
    f_rank = pp3v1_fourier_rank(history, window=500)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0:
        idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())

    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0:
        idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())

    exclude = set(bet1) | set(bet2)
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in exclude]
    else:
        echo_nums = []
    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers'] if n <= MAX_NUM])
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq.get(x, 0))
    bet3 = sorted((echo_nums + remaining)[:6])
    return [bet1, bet2, bet3]


# ========== PP3v2 (新版) — 直接從生產碼 import ==========

from tools.predict_power_precision_3bet import generate_power_precision_3bet as generate_pp3v2


# ========== McNemar Test ==========

def mcnemar_test(v1_hits, v2_hits):
    """McNemar test for paired binary outcomes
    
    比較兩策略在相同期數上的配對差異:
      b = v1 hit, v2 miss
      c = v1 miss, v2 hit
      
    H0: b = c (兩策略無差異)
    chi² = (|b-c| - 1)² / (b+c)  (Yates correction)
    """
    n = len(v1_hits)
    assert n == len(v2_hits)
    
    # 2x2: (v1_hit, v2_hit), (v1_hit, v2_miss), (v1_miss, v2_hit), (v1_miss, v2_miss)
    a = sum(1 for i in range(n) if v1_hits[i] and v2_hits[i])
    b = sum(1 for i in range(n) if v1_hits[i] and not v2_hits[i])
    c = sum(1 for i in range(n) if not v1_hits[i] and v2_hits[i])
    d = sum(1 for i in range(n) if not v1_hits[i] and not v2_hits[i])
    
    total_discord = b + c
    if total_discord == 0:
        return {
            'a': a, 'b': b, 'c': c, 'd': d,
            'chi2': 0.0, 'p_value': 1.0,
            'direction': 'IDENTICAL',
        }
    
    # Yates-corrected McNemar
    chi2_val = (abs(b - c) - 1) ** 2 / (b + c)
    p_value = 1.0 - chi2.cdf(chi2_val, df=1)
    
    if b > c:
        direction = 'V1_BETTER'
    elif c > b:
        direction = 'V2_BETTER'
    else:
        direction = 'EQUAL'
    
    return {
        'a': a, 'b': b, 'c': c, 'd': d,
        'chi2': chi2_val, 'p_value': p_value, 'direction': direction,
    }


# ========== 1500期完整回測 ==========

def run_backtest(draws, strategy_fn, label, start_offset=391):
    """1500期滾動回測"""
    total = len(draws)
    results = []
    
    for i in range(start_offset, total):
        history = draws[:i]
        actual = set(draws[i]['numbers'][:6])
        
        bets = strategy_fn(history)
        all_pred = set()
        for bet in bets:
            all_pred.update(bet)
        
        hit_count = len(all_pred & actual)
        results.append({
            'period_idx': i,
            'draw': draws[i]['draw'],
            'hit_count': hit_count,
            'hit_ge1': hit_count >= 1,
            'hit_ge2': hit_count >= 2,
            'hit_ge3': hit_count >= 3,
        })
    
    return results


def analyze_windows(results, label):
    """三窗口分析"""
    n = len(results)
    
    # Baseline for 3-bet (18 unique numbers from 38)
    from math import comb
    p_miss_1 = comb(MAX_NUM - PICK, PICK) / comb(MAX_NUM, PICK)
    bl_1bet = 1 - p_miss_1
    bl_3bet_ge1 = 1 - p_miss_1 ** 3  # P(hit≥1) with 3 bets
    
    # Expected pool for 3 bets ~ 18 numbers
    pool = 18
    bl_avg_hit = pool * PICK / MAX_NUM  # ~2.842
    
    windows = {}
    for wname, wdata in [('150p', results[-150:]), ('500p', results[-500:]), (f'all({n}p)', results)]:
        wn = len(wdata)
        avg_hit = sum(r['hit_count'] for r in wdata) / wn
        rate_ge1 = sum(r['hit_ge1'] for r in wdata) / wn
        rate_ge2 = sum(r['hit_ge2'] for r in wdata) / wn
        rate_ge3 = sum(r['hit_ge3'] for r in wdata) / wn
        edge_ge1 = rate_ge1 - bl_3bet_ge1
        
        windows[wname] = {
            'n': wn,
            'avg_hit': avg_hit,
            'rate_ge1': rate_ge1,
            'rate_ge2': rate_ge2,
            'rate_ge3': rate_ge3,
            'edge_ge1': edge_ge1,
        }
    
    return windows, bl_3bet_ge1, bl_avg_hit


def mc_pvalue_3bet(draws, strategy_fn, start_offset=391, n_sims=200, seed=42):
    """Monte Carlo p-value: 隨機3注策略能達到同樣 hit_ge2 rate 的概率"""
    rng = random.Random(seed)
    total = len(draws)
    n_periods = total - start_offset
    
    # Actual
    actual_ge2 = 0
    for i in range(start_offset, total):
        history = draws[:i]
        actual = set(draws[i]['numbers'][:6])
        bets = strategy_fn(history)
        pool = set()
        for b in bets:
            pool.update(b)
        if len(pool & actual) >= 2:
            actual_ge2 += 1
    actual_rate = actual_ge2 / n_periods
    
    # Random simulations
    count_ge = 0
    for _ in range(n_sims):
        sim_ge2 = 0
        for i in range(start_offset, total):
            actual = set(draws[i]['numbers'][:6])
            pool = set()
            for _ in range(3):
                pool.update(rng.sample(range(1, MAX_NUM + 1), PICK))
            if len(pool & actual) >= 2:
                sim_ge2 += 1
        sim_rate = sim_ge2 / n_periods
        if sim_rate >= actual_rate:
            count_ge += 1
    
    return count_ge / n_sims, actual_rate


def main():
    from lottery_api.database import DatabaseManager
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    total = len(draws)
    start_offset = total - 1500  # 固定1500期
    if start_offset < 100:
        start_offset = 100
    
    print(f"總期數: {total}")
    print(f"回測範圍: 第{start_offset}期 ~ 第{total-1}期 = {total - start_offset}期")
    print(f"暖機期: {start_offset}期")
    print()
    
    # ===== 1. 並排回測 =====
    print("=" * 80)
    print(" STEP 1: PP3v1 vs PP3v2 — 1500期滾動回測")
    print("=" * 80)
    
    v1_results = run_backtest(draws, generate_pp3v1, "PP3v1", start_offset)
    v2_results = run_backtest(draws, generate_pp3v2, "PP3v2", start_offset)
    
    n = len(v1_results)
    print(f"  共 {n} 期回測完成\n")
    
    # ===== 2. 三窗口分析 =====
    print("=" * 80)
    print(" STEP 2: 三窗口分析")
    print("=" * 80)
    
    for label, results, fn in [("PP3v1 (Fourier w500)", v1_results, generate_pp3v1),
                                ("PP3v2 (Fourier w100 + Dev+Echo)", v2_results, generate_pp3v2)]:
        windows, bl_ge1, bl_avg = analyze_windows(results, label)
        print(f"\n  {label}")
        print(f"  {'─'*60}")
        print(f"  Baseline: hit≥1={bl_ge1*100:.2f}%, E[avg_hit]={bl_avg:.3f}")
        for wname, w in windows.items():
            status_ge1 = "+" if w['edge_ge1'] > 0 else "-"
            print(f"  {wname:>10}: avg_hit={w['avg_hit']:.3f}  "
                  f"h≥1={w['rate_ge1']*100:.1f}%({status_ge1})  "
                  f"h≥2={w['rate_ge2']*100:.1f}%  "
                  f"h≥3={w['rate_ge3']*100:.1f}%")
    
    # ===== 3. McNemar Test =====
    print(f"\n{'='*80}")
    print(" STEP 3: McNemar Test (paired comparison)")
    print("=" * 80)
    
    # Test on hit≥1
    v1_ge1 = [r['hit_ge1'] for r in v1_results]
    v2_ge1 = [r['hit_ge1'] for r in v2_results]
    mc_ge1 = mcnemar_test(v1_ge1, v2_ge1)
    
    print(f"\n  McNemar on hit≥1:")
    print(f"    Both hit:  {mc_ge1['a']:>5}")
    print(f"    V1 only:   {mc_ge1['b']:>5}")
    print(f"    V2 only:   {mc_ge1['c']:>5}")
    print(f"    Both miss: {mc_ge1['d']:>5}")
    print(f"    chi²={mc_ge1['chi2']:.3f}, p={mc_ge1['p_value']:.4f}, direction={mc_ge1['direction']}")
    
    # Test on hit≥2
    v1_ge2 = [r['hit_ge2'] for r in v1_results]
    v2_ge2 = [r['hit_ge2'] for r in v2_results]
    mc_ge2 = mcnemar_test(v1_ge2, v2_ge2)
    
    print(f"\n  McNemar on hit≥2:")
    print(f"    Both hit:  {mc_ge2['a']:>5}")
    print(f"    V1 only:   {mc_ge2['b']:>5}")
    print(f"    V2 only:   {mc_ge2['c']:>5}")
    print(f"    Both miss: {mc_ge2['d']:>5}")
    print(f"    chi²={mc_ge2['chi2']:.3f}, p={mc_ge2['p_value']:.4f}, direction={mc_ge2['direction']}")
    
    # Test on hit≥3
    v1_ge3 = [r['hit_ge3'] for r in v1_results]
    v2_ge3 = [r['hit_ge3'] for r in v2_results]
    mc_ge3 = mcnemar_test(v1_ge3, v2_ge3)
    
    print(f"\n  McNemar on hit≥3:")
    print(f"    Both hit:  {mc_ge3['a']:>5}")
    print(f"    V1 only:   {mc_ge3['b']:>5}")
    print(f"    V2 only:   {mc_ge3['c']:>5}")
    print(f"    Both miss: {mc_ge3['d']:>5}")
    print(f"    chi²={mc_ge3['chi2']:.3f}, p={mc_ge3['p_value']:.4f}, direction={mc_ge3['direction']}")
    
    # ===== 4. 150p 窗口 McNemar (近期表現) =====
    print(f"\n{'='*80}")
    print(" STEP 4: 近150期 McNemar (近期穩定性)")
    print("=" * 80)
    
    v1_150_ge2 = [r['hit_ge2'] for r in v1_results[-150:]]
    v2_150_ge2 = [r['hit_ge2'] for r in v2_results[-150:]]
    mc_150 = mcnemar_test(v1_150_ge2, v2_150_ge2)
    
    print(f"\n  McNemar on hit≥2 (recent 150p):")
    print(f"    Both hit:  {mc_150['a']:>5}")
    print(f"    V1 only:   {mc_150['b']:>5}")
    print(f"    V2 only:   {mc_150['c']:>5}")
    print(f"    Both miss: {mc_150['d']:>5}")
    print(f"    chi²={mc_150['chi2']:.3f}, p={mc_150['p_value']:.4f}, direction={mc_150['direction']}")
    
    v1_150_rate = sum(v1_150_ge2) / len(v1_150_ge2)
    v2_150_rate = sum(v2_150_ge2) / len(v2_150_ge2)
    print(f"    V1 hit≥2 rate: {v1_150_rate*100:.1f}%")
    print(f"    V2 hit≥2 rate: {v2_150_rate*100:.1f}%")
    print(f"    差異: {(v2_150_rate - v1_150_rate)*100:+.1f}%")
    
    # ===== 5. Monte Carlo p-value =====
    print(f"\n{'='*80}")
    print(" STEP 5: Monte Carlo p-value (hit≥2, 200 simulations)")
    print("=" * 80)
    
    p_v1, rate_v1 = mc_pvalue_3bet(draws, generate_pp3v1, start_offset, n_sims=200)
    p_v2, rate_v2 = mc_pvalue_3bet(draws, generate_pp3v2, start_offset, n_sims=200)
    
    print(f"\n  PP3v1: hit≥2 rate={rate_v1*100:.2f}%, MC p={p_v1:.3f} {'***' if p_v1 < 0.01 else '**' if p_v1 < 0.05 else '*' if p_v1 < 0.1 else ''}")
    print(f"  PP3v2: hit≥2 rate={rate_v2*100:.2f}%, MC p={p_v2:.3f} {'***' if p_v2 < 0.01 else '**' if p_v2 < 0.05 else '*' if p_v2 < 0.1 else ''}")
    
    # ===== 6. Hit count 分佈比較 =====
    print(f"\n{'='*80}")
    print(" STEP 6: Hit Count 分佈比較")
    print("=" * 80)
    
    for label, results in [("PP3v1", v1_results), ("PP3v2", v2_results)]:
        dist = Counter(r['hit_count'] for r in results)
        total_r = len(results)
        print(f"\n  {label} hit distribution (n={total_r}):")
        for h in sorted(dist.keys()):
            bar = "█" * int(dist[h] / total_r * 100)
            print(f"    hit={h}: {dist[h]:>4} ({dist[h]/total_r*100:5.1f}%) {bar}")
        avg = sum(r['hit_count'] for r in results) / total_r
        print(f"    avg: {avg:.3f}")
    
    # ===== 7. 滾動50期 hit≥2 rate 趨勢 =====
    print(f"\n{'='*80}")
    print(" STEP 7: 滾動50期趨勢 (最近500期, 每50期)")
    print("=" * 80)
    
    recent_500_v1 = v1_results[-500:]
    recent_500_v2 = v2_results[-500:]
    
    print(f"\n  {'窗口':>12} {'V1 h≥2':>8} {'V2 h≥2':>8} {'差異':>8} {'優勢':>6}")
    print(f"  {'─'*48}")
    
    for start in range(0, 500, 50):
        end = min(start + 50, 500)
        chunk_v1 = recent_500_v1[start:end]
        chunk_v2 = recent_500_v2[start:end]
        r1 = sum(r['hit_ge2'] for r in chunk_v1) / len(chunk_v1)
        r2 = sum(r['hit_ge2'] for r in chunk_v2) / len(chunk_v2)
        diff = r2 - r1
        winner = "V2" if diff > 0 else "V1" if diff < 0 else "="
        period_start = chunk_v1[0]['draw'] if chunk_v1 else '?'
        print(f"  {period_start:>12} {r1*100:>7.1f}% {r2*100:>7.1f}% {diff*100:>+7.1f}% {winner:>6}")
    
    # ===== 結論 =====
    print(f"\n{'='*80}")
    print(" 結論")
    print("=" * 80)
    
    # 判定
    passed_criteria = []
    if all(w['edge_ge1'] > 0 for w in analyze_windows(v2_results, "v2")[0].values()):
        passed_criteria.append("三窗口 hit≥1 Edge 全正")
    if mc_ge2['direction'] == 'V2_BETTER' and mc_ge2['p_value'] < 0.05:
        passed_criteria.append(f"McNemar hit≥2 顯著 (p={mc_ge2['p_value']:.4f})")
    elif mc_ge2['direction'] == 'V2_BETTER':
        passed_criteria.append(f"McNemar hit≥2 V2較佳但不顯著 (p={mc_ge2['p_value']:.4f})")
    if p_v2 < 0.05:
        passed_criteria.append(f"MC p-value < 0.05 ({p_v2:.3f})")
    if v2_150_rate > v1_150_rate:
        passed_criteria.append(f"近150期 V2 勝出 ({v2_150_rate*100:.1f}% vs {v1_150_rate*100:.1f}%)")
    
    failed_criteria = []
    if mc_ge2['direction'] == 'V1_BETTER' and mc_ge2['p_value'] < 0.05:
        failed_criteria.append(f"McNemar hit≥2 V1顯著更佳 (p={mc_ge2['p_value']:.4f})")
    if p_v2 >= 0.05:
        failed_criteria.append(f"MC p-value ≥ 0.05 ({p_v2:.3f})")
    
    print(f"\n  通過: {len(passed_criteria)}")
    for c in passed_criteria:
        print(f"    ✓ {c}")
    if failed_criteria:
        print(f"  失敗: {len(failed_criteria)}")
        for c in failed_criteria:
            print(f"    ✗ {c}")
    
    # 最終判定
    if mc_ge2['direction'] != 'V1_BETTER' and p_v2 < 0.05:
        print(f"\n  判定: PP3v2 可部署 — 不遜於 PP3v1 且通過 MC 顯著性")
    elif mc_ge2['direction'] == 'V1_BETTER' and mc_ge2['p_value'] < 0.05:
        print(f"\n  判定: PP3v2 應回退 — V1 顯著更佳")
    else:
        print(f"\n  判定: PP3v2 與 PP3v1 無統計顯著差異 — 需額外數據或換指標判定")


if __name__ == "__main__":
    main()
