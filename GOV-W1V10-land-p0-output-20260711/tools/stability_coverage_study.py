#!/usr/bin/env python3
"""
大樂透 / 威力彩 策略穩定性與覆蓋優化研究
==========================================
目標：
  1. 三窗口 Edge 穩定性分析 (150/500/1500期) + Z-score + Bonferroni
  2. 子集組合覆蓋模擬 (2注/3注/5注) + M3+/M4+ 命中率
  3. 獎金結構 ROI 分析 (每種組合的期望收益 vs 成本)
  4. Permutation Test 驗證信號
  5. 科學報告生成

Usage:
    python3 tools/stability_coverage_study.py
    python3 tools/stability_coverage_study.py --lottery POWER_LOTTO
    python3 tools/stability_coverage_study.py --n_perm 500
"""
import os
import sys
import json
import argparse
import time
import numpy as np
from collections import Counter
from itertools import combinations
from scipy import stats
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

# ─────────────────────────────────────────────────────────
# 遊戲參數
# ─────────────────────────────────────────────────────────
GAMES = {
    'BIG_LOTTO': {
        'name': '大樂透',
        'max_num': 49,
        'pick': 6,
        'p_single': 0.0186,
        'cost_per_bet': 50,       # TWD
        'draws_per_year': 104,    # 每週2期
        'prize_table': {
            # (main_matched, has_special) → TWD (固定獎金部分)
            (6, False): 100_000_000,  # 頭獎 (浮動，取估計值)
            (5, True):  1_500_000,    # 貳獎
            (5, False): 40_000,       # 參獎
            (4, True):  10_000,       # 肆獎
            (4, False): 2_000,        # 伍獎
            (3, True):  1_000,        # 陸獎
            (3, False): 400,          # 柒獎 (普獎)
            (2, True):  400,          # 普獎
        },
        'n_bets': 5,   # 已驗證策略注數
    },
    'POWER_LOTTO': {
        'name': '威力彩',
        'max_num': 38,
        'pick': 6,
        'p_single': 0.0387,
        'cost_per_bet': 100,      # TWD
        'draws_per_year': 104,    # 每週2期
        'prize_table': {
            # 威力彩獎金 (第一區匹配, 不含第二區)
            (6, False): 200_000_000,  # 貳獎 (6 main only)
            (5, True):  200_000,      # 參獎
            (5, False): 40_000,       # 肆獎
            (4, True):  5_000,        # 伍獎
            (4, False): 800,          # 陸獎
            (3, True):  400,          # 柒獎
            (2, True):  200,          # 捌獎
            (3, False): 100,          # 玖獎
            (1, True):  100,          # 普獎
        },
        'n_bets': 3,   # 已驗證策略注數
    },
}

SEED = 42
MIN_BUFFER = 500  # 策略需要的最少歷史期數


# ─────────────────────────────────────────────────────────
# 大樂透 5注策略: TS3+M+FO (已驗證)
# ─────────────────────────────────────────────────────────
def fourier_rhythm_bet(history, max_num, window=500):
    """Bet 1: Fourier Rhythm FFT"""
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        bstream = np.array([1.0 if n in d['numbers'] else 0.0 for d in h])
        if bstream.sum() < 2:
            continue
        yf = fft(bstream - bstream.mean())
        xf = fftfreq(w, 1)
        pos = xf > 0
        pos_xf = xf[pos]
        pos_amp = np.abs(yf[pos])
        if len(pos_amp) == 0:
            continue
        peak = np.argmax(pos_amp)
        freq_val = pos_xf[peak]
        if freq_val == 0:
            continue
        period = 1.0 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bstream == 1)[0]
            if len(last_hit) == 0:
                continue
            gap = (w - 1) - last_hit[-1]
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def generate_biglotto_5bet(history):
    """大樂透 5注策略 (TS3+M+FO)"""
    max_num = 49
    pick = 6
    scores = fourier_rhythm_bet(history, max_num)
    f_rank = np.argsort(scores)[::-1]

    # Filter out index 0
    f_rank = [int(n) for n in f_rank if n > 0]

    # Bet 1: Top-6 Fourier
    bet1 = sorted(f_rank[:pick])

    # Bet 2: Next-6 Fourier
    bet2 = sorted(f_rank[pick:2*pick])

    # Bet 3: Echo + Cold
    exclude = set(bet1) | set(bet2)
    echo_nums = []
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= max_num and n not in exclude]
    recent = history[-100:]
    freq = Counter(n for d in recent for n in d['numbers'])
    rem = [n for n in range(1, max_num + 1) if n not in exclude and n not in echo_nums]
    rem.sort(key=lambda x: freq.get(x, 0))  # coldest first
    bet3 = sorted((echo_nums + rem)[:pick])

    # Bet 4-5: Frequency Orthogonal
    used = set(bet1) | set(bet2) | set(bet3)
    leftover = [n for n in range(1, max_num + 1) if n not in used]
    leftover.sort(key=lambda x: freq.get(x, 0), reverse=True)
    bet4 = sorted(leftover[:pick])
    bet5 = sorted(leftover[pick:2*pick])

    return [bet1, bet2, bet3, bet4, bet5]


# ─────────────────────────────────────────────────────────
# 威力彩 3注策略: PP3 (Fourier+Echo/Cold)
# ─────────────────────────────────────────────────────────
def generate_powerlotto_3bet(history):
    """威力彩 3注策略 (PP3 簡化版)"""
    max_num = 38
    pick = 6
    scores = fourier_rhythm_bet(history, max_num)
    f_rank = np.argsort(scores)[::-1]
    f_rank = [int(n) for n in f_rank if n > 0]

    # Bet 1: Top Fourier
    bet1 = sorted(f_rank[:pick])

    # Bet 2: Echo + Cold
    exclude = set(bet1)
    echo_nums = []
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= max_num and n not in exclude]
    recent = history[-100:]
    freq = Counter(n for d in recent for n in d['numbers'])
    rem = [n for n in range(1, max_num + 1) if n not in exclude and n not in echo_nums]
    rem.sort(key=lambda x: freq.get(x, 0))
    bet2 = sorted((echo_nums + rem)[:pick])

    # Bet 3: Gray zone balanced
    used = set(bet1) | set(bet2)
    leftover = [n for n in range(1, max_num + 1) if n not in used]
    leftover.sort(key=lambda x: freq.get(x, 0), reverse=True)
    bet3 = sorted(leftover[:pick])

    return [bet1, bet2, bet3]


# ─────────────────────────────────────────────────────────
# Walk-forward 核心引擎
# ─────────────────────────────────────────────────────────
def walk_forward(draws, game_key, n_periods, verbose=False):
    """
    Walk-forward backtest. Returns per-draw result list.
    Each result: {
        'bet_hits': [int, ...],    # 每注命中數
        'best_hit': int,           # 最佳單注命中數
        'has_special': bool,       # 是否命中特別號
        'prize': int,              # 最高獎金
    }
    """
    game = GAMES[game_key]
    max_num = game['max_num']
    gen_fn = generate_biglotto_5bet if game_key == 'BIG_LOTTO' else generate_powerlotto_3bet

    start_idx = max(MIN_BUFFER, len(draws) - n_periods)
    results = []

    for i in range(start_idx, len(draws)):
        history = draws[:i]
        actual = set(draws[i]['numbers'])
        special = draws[i].get('special', 0)

        bets = gen_fn(history)
        bet_hits = [len(set(b) & actual) for b in bets]
        best_hit = max(bet_hits)
        has_special = any(special in b for b in bets)

        # Calculate prize (best single bet)
        best_prize = 0
        for b in bets:
            m = len(set(b) & actual)
            s = special in b
            key = (m, s)
            p = game['prize_table'].get(key, 0)
            if p > best_prize:
                best_prize = p
            # Also check without special
            key_no_s = (m, False)
            p2 = game['prize_table'].get(key_no_s, 0)
            if p2 > best_prize:
                best_prize = p2

        results.append({
            'bet_hits': bet_hits,
            'best_hit': best_hit,
            'has_special': has_special,
            'prize': best_prize,
        })

    if verbose:
        n = len(results)
        m3 = sum(1 for r in results if r['best_hit'] >= 3)
        print(f"  Walk-forward: {n} 期, M3+={m3} ({m3/n:.2%})")

    return results


# ─────────────────────────────────────────────────────────
# 1. 穩定性分析: 三窗口 + Z-score + 衰減
# ─────────────────────────────────────────────────────────
def stability_analysis(draws, game_key, verbose=True):
    """三窗口穩定性分析 (150/500/1500期)"""
    game = GAMES[game_key]
    n_bets = game['n_bets']
    p_baseline = 1 - (1 - game['p_single']) ** n_bets
    windows = [150, 500, 1500]

    if verbose:
        print(f"\n{'='*60}")
        print(f"  1. 穩定性分析: {game['name']} {n_bets}注")
        print(f"     基準 P(M3+, {n_bets}注) = {p_baseline:.4f} ({p_baseline:.2%})")
        print(f"{'='*60}")

    window_results = {}
    for w in windows:
        results = walk_forward(draws, game_key, w)
        n = len(results)
        m3_count = sum(1 for r in results if r['best_hit'] >= 3)
        m4_count = sum(1 for r in results if r['best_hit'] >= 4)
        rate = m3_count / n
        edge_abs = rate - p_baseline
        edge_rel = edge_abs / p_baseline if p_baseline > 0 else 0

        # Z-score (binomial)
        se = np.sqrt(p_baseline * (1 - p_baseline) / n)
        z = edge_abs / se if se > 0 else 0
        p_val = 1 - stats.norm.cdf(z)  # one-sided

        window_results[w] = {
            'n': n,
            'm3_count': m3_count,
            'm4_count': m4_count,
            'rate': rate,
            'edge_abs': edge_abs,
            'edge_rel': edge_rel,
            'z_score': z,
            'p_value': p_val,
        }

        if verbose:
            sig = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else ("*" if p_val < 0.05 else ""))
            print(f"\n  [{w:4d}期] n={n}")
            print(f"    M3+: {m3_count}/{n} = {rate:.2%} (基準 {p_baseline:.2%})")
            print(f"    M4+: {m4_count}/{n} = {m4_count/n:.2%}")
            print(f"    Edge(絕對): {edge_abs:+.2%} | Edge(相對): {edge_rel:+.2%}")
            print(f"    Z-score: {z:.3f} | p-value: {p_val:.4f} {sig}")

    # Bonferroni (3 windows)
    bonf_alpha = 0.05 / len(windows)
    passes = [w for w in windows if window_results[w]['p_value'] < bonf_alpha]

    # Edge decay pattern
    edges = [window_results[w]['edge_rel'] for w in windows]
    if edges[0] > edges[1] > edges[2]:
        pattern = 'DECAYING'
    elif edges[0] < edges[1] < edges[2]:
        pattern = 'ACCELERATING'
    elif all(e > 0 for e in edges):
        pattern = 'STABLE_POSITIVE'
    elif all(e < 0 for e in edges):
        pattern = 'STABLE_NEGATIVE'
    else:
        pattern = 'MIXED'

    if verbose:
        print(f"\n  Bonferroni α = 0.05/{len(windows)} = {bonf_alpha:.4f}")
        print(f"  通過 Bonferroni 的窗口: {passes if passes else 'None'}")
        print(f"  Edge 趨勢: {pattern}")
        print(f"  Edge(相對): {edges[0]:+.2%} → {edges[1]:+.2%} → {edges[2]:+.2%}")

    return {
        'windows': window_results,
        'bonferroni_passes': passes,
        'pattern': pattern,
    }


# ─────────────────────────────────────────────────────────
# 2. 子集組合覆蓋模擬
# ─────────────────────────────────────────────────────────
def coverage_simulation(draws, game_key, eval_window=1500, verbose=True):
    """
    子集組合覆蓋模擬：測試不同注數子集的 M3+/M4+ 效能

    For BIG_LOTTO 5-bet: test C(5,2)=10, C(5,3)=10, all 5 bets
    For POWER_LOTTO 3-bet: test C(3,1)=3, C(3,2)=3, all 3 bets
    """
    game = GAMES[game_key]
    n_bets = game['n_bets']
    gen_fn = generate_biglotto_5bet if game_key == 'BIG_LOTTO' else generate_powerlotto_3bet

    start_idx = max(MIN_BUFFER, len(draws) - eval_window)
    n_eval = len(draws) - start_idx

    if verbose:
        print(f"\n{'='*60}")
        print(f"  2. 覆蓋模擬: {game['name']} ({n_eval} 期)")
        print(f"{'='*60}")

    # Define subset sizes to test
    if n_bets == 5:
        subset_sizes = [1, 2, 3, 5]
    elif n_bets == 3:
        subset_sizes = [1, 2, 3]
    else:
        subset_sizes = list(range(1, n_bets + 1))

    # Pre-compute all walk-forward predictions
    all_bet_hits = []  # list of (bet_hits_per_draw)
    for i in range(start_idx, len(draws)):
        history = draws[:i]
        actual = set(draws[i]['numbers'])
        bets = gen_fn(history)
        hits = [len(set(b) & actual) for b in bets]
        all_bet_hits.append(hits)

    coverage_results = {}

    for k in subset_sizes:
        combos = list(combinations(range(n_bets), k))
        n_combos = len(combos)
        p_base = 1 - (1 - game['p_single']) ** k

        # For each combo, compute M3+ and M4+ over all periods
        combo_stats = []
        for combo in combos:
            m3 = sum(1 for hits in all_bet_hits if any(hits[j] >= 3 for j in combo))
            m4 = sum(1 for hits in all_bet_hits if any(hits[j] >= 4 for j in combo))
            rate_m3 = m3 / n_eval
            rate_m4 = m4 / n_eval
            edge_m3 = (rate_m3 - p_base) / p_base if p_base > 0 else 0

            combo_stats.append({
                'combo': combo,
                'combo_label': '+'.join(f'B{j+1}' for j in combo),
                'm3_count': m3,
                'm4_count': m4,
                'rate_m3': rate_m3,
                'rate_m4': rate_m4,
                'edge_m3_rel': edge_m3,
                'baseline': p_base,
            })

        # Best and worst combos
        best = max(combo_stats, key=lambda x: x['rate_m3'])
        worst = min(combo_stats, key=lambda x: x['rate_m3'])
        avg_m3 = np.mean([cs['rate_m3'] for cs in combo_stats])

        coverage_results[k] = {
            'n_combos': n_combos,
            'baseline': p_base,
            'all_combos': combo_stats,
            'best': best,
            'worst': worst,
            'avg_m3': avg_m3,
        }

        if verbose:
            print(f"\n  --- {k}注 (C({n_bets},{k})={n_combos} 組合, 基準={p_base:.2%}) ---")
            if n_combos <= 10:
                for cs in sorted(combo_stats, key=lambda x: -x['rate_m3']):
                    print(f"    {cs['combo_label']:<14} M3+={cs['rate_m3']:.2%} "
                          f"M4+={cs['rate_m4']:.2%} Edge={cs['edge_m3_rel']:+.2%}")
            else:
                print(f"    最佳: {best['combo_label']} M3+={best['rate_m3']:.2%} "
                      f"Edge={best['edge_m3_rel']:+.2%}")
                print(f"    最差: {worst['combo_label']} M3+={worst['rate_m3']:.2%} "
                      f"Edge={worst['edge_m3_rel']:+.2%}")
                print(f"    平均 M3+: {avg_m3:.2%}")

    return coverage_results


# ─────────────────────────────────────────────────────────
# 3. 獎金結構 ROI 分析
# ─────────────────────────────────────────────────────────
def roi_analysis(draws, game_key, eval_window=1500, verbose=True):
    """
    獎金結構 ROI 分析：計算不同注數組合的期望收益
    """
    game = GAMES[game_key]
    n_bets = game['n_bets']
    cost_per_bet = game['cost_per_bet']
    draws_per_year = game['draws_per_year']
    prize_table = game['prize_table']
    gen_fn = generate_biglotto_5bet if game_key == 'BIG_LOTTO' else generate_powerlotto_3bet

    start_idx = max(MIN_BUFFER, len(draws) - eval_window)
    n_eval = len(draws) - start_idx

    if verbose:
        print(f"\n{'='*60}")
        print(f"  3. ROI 分析: {game['name']} ({n_eval} 期)")
        print(f"{'='*60}")

    # Compute per-draw detailed prizes
    if n_bets == 5:
        subset_sizes = [1, 2, 3, 5]
    elif n_bets == 3:
        subset_sizes = [1, 2, 3]
    else:
        subset_sizes = list(range(1, n_bets + 1))

    # Pre-compute bets and detailed match info per draw
    draw_details = []
    for i in range(start_idx, len(draws)):
        history = draws[:i]
        actual = set(draws[i]['numbers'])
        special = draws[i].get('special', 0)
        bets = gen_fn(history)

        per_bet = []
        for b in bets:
            m = len(set(b) & actual)
            s = special in set(b)
            # Find best prize for this bet
            best_p = 0
            for (pm, ps), prize in prize_table.items():
                if m >= pm and (not ps or s):
                    if pm == m and ps == s:
                        best_p = max(best_p, prize)
                    elif pm == m and not ps:
                        best_p = max(best_p, prize)
            # More precise: check exact match
            prize_val = prize_table.get((m, s), 0)
            prize_no_s = prize_table.get((m, False), 0)
            best_p = max(prize_val, prize_no_s)
            per_bet.append({'hits': m, 'special': s, 'prize': best_p})
        draw_details.append(per_bet)

    roi_results = {}

    for k in subset_sizes:
        combos = list(combinations(range(n_bets), k))
        cost_per_draw = k * cost_per_bet
        annual_cost = cost_per_draw * draws_per_year

        combo_rois = []
        for combo in combos:
            total_prize = 0
            prize_counts = Counter()
            for dd in draw_details:
                best_prize_this = max(dd[j]['prize'] for j in combo)
                total_prize += best_prize_this
                if best_prize_this > 0:
                    prize_counts[best_prize_this] += 1

            total_cost = cost_per_draw * n_eval
            roi = (total_prize - total_cost) / total_cost if total_cost > 0 else 0
            avg_prize_per_draw = total_prize / n_eval
            label = '+'.join(f'B{j+1}' for j in combo)

            combo_rois.append({
                'combo_label': label,
                'total_prize': total_prize,
                'total_cost': total_cost,
                'roi': roi,
                'avg_prize_per_draw': avg_prize_per_draw,
                'cost_per_draw': cost_per_draw,
                'annual_cost': annual_cost,
                'prize_distribution': dict(prize_counts.most_common()),
            })

        best = max(combo_rois, key=lambda x: x['roi'])
        roi_results[k] = {
            'n_combos': len(combos),
            'cost_per_draw': cost_per_draw,
            'annual_cost': annual_cost,
            'all_combos': combo_rois,
            'best': best,
        }

        if verbose:
            print(f"\n  --- {k}注 (成本 {cost_per_draw} TWD/期, "
                  f"年成本 {annual_cost:,} TWD) ---")
            for cr in sorted(combo_rois, key=lambda x: -x['roi'])[:5]:
                print(f"    {cr['combo_label']:<14} "
                      f"總獎金={cr['total_prize']:>10,} TWD | "
                      f"ROI={cr['roi']:+.2%} | "
                      f"均獎/期={cr['avg_prize_per_draw']:.1f} TWD")

    return roi_results


# ─────────────────────────────────────────────────────────
# 4. Permutation Test (洗牌 M3+ 標籤)
# ─────────────────────────────────────────────────────────
def permutation_test(draws, game_key, n_perm=500, eval_window=1500, verbose=True):
    """
    Permutation Test: 洗牌開獎號碼順序，破壞時序結構。
    比較真實 M3+ 率 vs 洗牌後分布。
    """
    game = GAMES[game_key]
    n_bets = game['n_bets']
    p_baseline = 1 - (1 - game['p_single']) ** n_bets

    if verbose:
        print(f"\n{'='*60}")
        print(f"  4. Permutation Test: {game['name']} (n={n_perm})")
        print(f"{'='*60}")

    # Real walk-forward
    results = walk_forward(draws, game_key, eval_window)
    n = len(results)
    real_m3 = sum(1 for r in results if r['best_hit'] >= 3)
    real_rate = real_m3 / n
    real_edge = (real_rate - p_baseline) / p_baseline

    if verbose:
        print(f"  真實 M3+: {real_m3}/{n} = {real_rate:.2%}, Edge = {real_edge:+.2%}")
        print(f"  基準    : {p_baseline:.2%}")
        print(f"  洗牌 {n_perm} 次...")

    rng = np.random.RandomState(SEED)
    perm_edges = []
    t_start = time.time()

    # Efficient: shuffle draw numbers (not re-run strategy)
    # We shuffle the actual numbers for each draw, preserving strategy predictions
    start_idx = max(MIN_BUFFER, len(draws) - eval_window)
    gen_fn = generate_biglotto_5bet if game_key == 'BIG_LOTTO' else generate_powerlotto_3bet

    # Pre-compute strategy predictions (fixed)
    predictions = []
    for i in range(start_idx, len(draws)):
        history = draws[:i]
        bets = gen_fn(history)
        predictions.append(bets)

    # Real numbers
    real_numbers = [set(draws[i]['numbers']) for i in range(start_idx, len(draws))]
    all_number_sets = list(real_numbers)  # Will shuffle this

    for perm_i in range(n_perm):
        # Shuffle which draw's numbers appear at which position
        shuffled_indices = rng.permutation(len(all_number_sets))
        perm_m3 = 0
        for j, pred in enumerate(predictions):
            actual_shuffled = all_number_sets[shuffled_indices[j]]
            best = max(len(set(b) & actual_shuffled) for b in pred)
            if best >= 3:
                perm_m3 += 1
        perm_rate = perm_m3 / n
        perm_edge = (perm_rate - p_baseline) / p_baseline
        perm_edges.append(perm_edge)

        if verbose and (perm_i + 1) % 100 == 0:
            elapsed = time.time() - t_start
            print(f"    {perm_i+1}/{n_perm} ({elapsed:.1f}s)")

    perm_arr = np.array(perm_edges)
    p_perm = float(np.mean(perm_arr >= real_edge))
    perm_mean = float(perm_arr.mean())
    perm_std = float(perm_arr.std())
    perm_95 = float(np.percentile(perm_arr, 95))
    cohen_d = (real_edge - perm_mean) / (perm_std + 1e-12)

    if verbose:
        print(f"\n  真實 Edge    : {real_edge:+.4f}")
        print(f"  Perm 均值    : {perm_mean:+.4f} +/- {perm_std:.4f}")
        print(f"  Perm 95th %  : {perm_95:+.4f}")
        print(f"  p-value      : {p_perm:.4f}")
        print(f"  Cohen's d    : {cohen_d:.3f}")
        if p_perm < 0.05:
            print(f"  判定: SIGNAL DETECTED (p={p_perm:.4f} < 0.05)")
        else:
            print(f"  判定: NOT SIGNIFICANT (p={p_perm:.4f} >= 0.05)")

    return {
        'n': n,
        'real_rate': real_rate,
        'real_edge': real_edge,
        'perm_mean': perm_mean,
        'perm_std': perm_std,
        'perm_95': perm_95,
        'p_value': p_perm,
        'cohen_d': cohen_d,
        'signal_ratio': (real_edge - perm_mean) / (abs(real_edge) + 1e-12),
    }


# ─────────────────────────────────────────────────────────
# 5. 年度成本效益摘要
# ─────────────────────────────────────────────────────────
def cost_benefit_summary(stability, coverage, roi, game_key, verbose=True):
    """綜合成本效益摘要"""
    game = GAMES[game_key]
    draws_per_year = game['draws_per_year']
    n_bets = game['n_bets']

    if verbose:
        print(f"\n{'='*60}")
        print(f"  5. 年度成本效益摘要: {game['name']}")
        print(f"{'='*60}")

    for k in sorted(roi.keys()):
        r = roi[k]
        best = r['best']
        annual_cost = r['annual_cost']

        # Extrapolate annual prize from backtest
        # Use 1500p results = ~14.4 years for big lotto
        if 1500 in stability['windows']:
            n_eval = stability['windows'][1500]['n']
        else:
            n_eval = max(stability['windows'].keys())
            n_eval = stability['windows'][n_eval]['n']

        years_covered = n_eval / draws_per_year
        annual_prize = best['total_prize'] / years_covered if years_covered > 0 else 0
        annual_profit = annual_prize - annual_cost
        annual_roi = annual_profit / annual_cost if annual_cost > 0 else 0

        if verbose:
            print(f"\n  [{k}注] {best['combo_label']}")
            print(f"    年成本: {annual_cost:>10,} TWD ({k}注 x {game['cost_per_bet']} TWD x {draws_per_year}期)")
            print(f"    年預期獎金: {annual_prize:>10,.0f} TWD (基於 {n_eval}期推算)")
            print(f"    年預期損益: {annual_profit:>+10,.0f} TWD")
            print(f"    年 ROI: {annual_roi:+.2%}")
            if annual_profit < 0:
                print(f"    結論: 負期望值 (年虧損 {-annual_profit:,.0f} TWD)")
            else:
                print(f"    結論: 正期望值 (理論不應如此, 需警惕)")


# ─────────────────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='策略穩定性與覆蓋優化研究'
    )
    parser.add_argument('--lottery', default='BIG_LOTTO',
                        choices=['BIG_LOTTO', 'POWER_LOTTO'],
                        help='彩票種類 (default: BIG_LOTTO)')
    parser.add_argument('--n_perm', type=int, default=200,
                        help='Permutation 次數 (default: 200)')
    parser.add_argument('--no_perm', action='store_true',
                        help='跳過 Permutation Test')
    parser.add_argument('--output', default=None,
                        help='輸出 JSON 路徑')
    args = parser.parse_args()

    game = GAMES[args.lottery]
    sep = "=" * 60

    print(sep)
    print(f"  策略穩定性與覆蓋優化研究")
    print(f"  彩種: {game['name']} ({args.lottery})")
    print(f"  策略: {game['n_bets']}注已驗證策略")
    print(f"  Permutation: {args.n_perm} 次")
    print(sep)

    # Load data
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    if not os.path.exists(db_path):
        db_path = os.path.join(project_root, 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    draws = list(reversed(db.get_all_draws(lottery_type=args.lottery)))
    print(f"\n  資料: {len(draws)} 期")
    print(f"  最早: {draws[0].get('date','?')} | 最新: {draws[-1].get('date','?')}")

    t_start = time.time()

    # Step 1: Stability
    stab = stability_analysis(draws, args.lottery)

    # Step 2: Coverage Simulation
    cov = coverage_simulation(draws, args.lottery)

    # Step 3: ROI Analysis
    roi = roi_analysis(draws, args.lottery)

    # Step 4: Permutation Test
    perm = None
    if not args.no_perm:
        perm = permutation_test(draws, args.lottery, n_perm=args.n_perm)

    # Step 5: Cost-Benefit Summary
    cost_benefit_summary(stab, cov, roi, args.lottery)

    elapsed = time.time() - t_start

    # ─── 最終結論 ─────────────────────────────────────────
    print(f"\n{sep}")
    print(f"  最終結論")
    print(sep)

    # Stability verdict
    stab_pass = stab['pattern'] in ('STABLE_POSITIVE', 'ACCELERATING')
    print(f"  穩定性: {stab['pattern']} {'PASS' if stab_pass else 'WARN'}")

    # Bonferroni
    bonf = stab['bonferroni_passes']
    print(f"  Bonferroni 通過: {bonf if bonf else 'None'}")

    # Best coverage
    n_bets = game['n_bets']
    if n_bets in cov:
        best_m3 = cov[n_bets]['best']['rate_m3']
        baseline = cov[n_bets]['baseline']
        print(f"  最佳{n_bets}注 M3+: {best_m3:.2%} (基準 {baseline:.2%})")

    # Perm
    if perm:
        print(f"  Permutation: p={perm['p_value']:.4f}, Cohen's d={perm['cohen_d']:.2f}")
        sig = perm['p_value'] < 0.05
        print(f"  信號: {'DETECTED' if sig else 'NOT SIGNIFICANT'} "
              f"(信號佔比 {perm['signal_ratio']:.0%})")

    # ROI
    if n_bets in roi:
        best_roi = roi[n_bets]['best']
        print(f"  ROI ({n_bets}注): {best_roi['roi']:+.2%} "
              f"(獎金 {best_roi['total_prize']:,} / 成本 {best_roi['total_cost']:,})")

    print(f"\n  耗時: {elapsed:.1f}s")

    # Save JSON
    out_path = args.output or os.path.join(
        project_root,
        f'stability_coverage_{args.lottery}.json'
    )

    # Serialize (convert numpy/tuple keys)
    def serialize(obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, tuple):
            return list(obj)
        return str(obj)

    output = {
        'lottery': args.lottery,
        'stability': {
            'pattern': stab['pattern'],
            'bonferroni_passes': [int(w) for w in stab['bonferroni_passes']],
            'windows': {str(w): v for w, v in stab['windows'].items()},
        },
        'coverage': {
            str(k): {
                'n_combos': v['n_combos'],
                'baseline': v['baseline'],
                'best': {kk: vv for kk, vv in v['best'].items() if kk != 'combo'},
                'avg_m3': v['avg_m3'],
            } for k, v in cov.items()
        },
        'roi': {
            str(k): {
                'cost_per_draw': v['cost_per_draw'],
                'annual_cost': v['annual_cost'],
                'best_roi': v['best']['roi'],
                'best_label': v['best']['combo_label'],
                'best_avg_prize': v['best']['avg_prize_per_draw'],
            } for k, v in roi.items()
        },
        'permutation': perm,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=serialize)
    print(f"\n  結果已儲存: {out_path}")
    print(f"\n{sep}\n")


if __name__ == '__main__':
    main()
