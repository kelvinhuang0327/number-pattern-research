#!/usr/bin/env python3
"""
大樂透 Sum Regime Detector — 回測驗證
======================================
033期教訓: 連續7期 sum > mu 後暴跌至 -1.72σ，系統未偵測

Hypothesis:
  當近N期 sum 連續偏高/偏低，下期更可能出現反方向回歸。
  利用此信號調整候選號碼池的 zone 權重。

方案:
  1. 偵測連續 sum 偏高/偏低 (threshold = consecutive >= 5)
  2. HIGH_REGIME → 將候選池偏向低號 (1-25)
  3. LOW_REGIME → 將候選池偏向高號 (25-49)
  4. 嵌入現有 Triple Strike 和正交5注流程

驗證: 1500期三窗口 + permutation test
"""
import os
import sys
import json
import sqlite3
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'tools'))

from predict_biglotto_triple_strike import (
    fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet, generate_triple_strike,
    _sum_target, _SUM_WIN, MAX_NUM
)

DB_PATH = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')


# ========== Sum Regime Detector ==========

def detect_sum_regime(history, lookback=10, threshold=5):
    """
    偵測 sum 連續偏高/偏低的 regime。

    Args:
        history: 歷史開奬數據 (list of dicts)
        lookback: 查看最近幾期 (default: 10)
        threshold: 連續幾期才觸發 (default: 5)

    Returns:
        (regime, consecutive_count, direction_strength)
        regime: 'HIGH_REGIME' | 'LOW_REGIME' | 'NEUTRAL'
        consecutive_count: 連續偏離期數
        direction_strength: 平均偏離的 z-score
    """
    if len(history) < 50:
        return 'NEUTRAL', 0, 0.0

    h300 = history[-300:] if len(history) >= 300 else history
    sums = [sum(d['numbers']) for d in h300]
    mu, sg = np.mean(sums), np.std(sums)

    if sg < 1e-6:
        return 'NEUTRAL', 0, 0.0

    recent = history[-lookback:] if len(history) >= lookback else history
    recent_sums = [sum(d['numbers']) for d in recent]

    # Count consecutive above-mean from most recent
    consec_above = 0
    z_sum_above = 0.0
    for s in reversed(recent_sums):
        if s > mu:
            consec_above += 1
            z_sum_above += (s - mu) / sg
        else:
            break

    # Count consecutive below-mean from most recent
    consec_below = 0
    z_sum_below = 0.0
    for s in reversed(recent_sums):
        if s < mu:
            consec_below += 1
            z_sum_below += (mu - s) / sg
        else:
            break

    if consec_above >= threshold:
        avg_z = z_sum_above / consec_above
        return 'HIGH_REGIME', consec_above, avg_z
    elif consec_below >= threshold:
        avg_z = z_sum_below / consec_below
        return 'LOW_REGIME', consec_below, avg_z

    return 'NEUTRAL', 0, 0.0


def apply_regime_weight(scores_dict, regime, strength=0.3):
    """
    根據 regime 調整號碼分數。

    HIGH_REGIME → boost 低號(1-25), penalize 高號(26-49)
    LOW_REGIME  → boost 高號(26-49), penalize 低號(1-25)

    Args:
        scores_dict: {number: score} 字典
        regime: 'HIGH_REGIME' | 'LOW_REGIME' | 'NEUTRAL'
        strength: 調整強度 (0.0~1.0)

    Returns:
        adjusted {number: score} dict
    """
    if regime == 'NEUTRAL':
        return scores_dict

    adjusted = {}
    mid = 25  # 分界線
    for n, score in scores_dict.items():
        if regime == 'HIGH_REGIME':
            # 偏向低號
            if n <= mid:
                adjusted[n] = score * (1.0 + strength)
            else:
                adjusted[n] = score * (1.0 - strength)
        elif regime == 'LOW_REGIME':
            # 偏向高號
            if n > mid:
                adjusted[n] = score * (1.0 + strength)
            else:
                adjusted[n] = score * (1.0 - strength)
    return adjusted


# ========== Regime-Enhanced Fourier ==========

def fourier_regime_bet(history, window=500, regime='NEUTRAL', regime_strength=0.3):
    """Fourier Rhythm + Regime 調整"""
    from scipy.fft import fft, fftfreq

    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h_slice):
            if n in d['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            scores[n] = 0.0
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
        else:
            scores[n] = 0.0

    # Apply regime adjustment
    if regime != 'NEUTRAL':
        scores = apply_regime_weight(scores, regime, regime_strength)

    sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return sorted(sorted_nums[:6])


# ========== Regime-Enhanced Cold Bet ==========

def cold_regime_bet(history, window=100, exclude=None, pool_size=12, regime='NEUTRAL'):
    """Cold Numbers + Regime-Adjusted Sum Target"""
    exclude = exclude or set()
    recent = history[-window:]
    freq = Counter(n for d in recent for n in d['numbers'])

    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))

    # Regime-based pool adjustment: if HIGH_REGIME, prefer cold nums from low zone
    if regime == 'HIGH_REGIME':
        cold_low = [n for n in sorted_cold if n <= 25][:pool_size]
        cold_high = [n for n in sorted_cold if n > 25][:pool_size // 2]
        pool = (cold_low + cold_high)[:pool_size]
    elif regime == 'LOW_REGIME':
        cold_high = [n for n in sorted_cold if n > 25][:pool_size]
        cold_low = [n for n in sorted_cold if n <= 25][:pool_size // 2]
        pool = (cold_high + cold_low)[:pool_size]
    else:
        pool = sorted_cold[:pool_size]

    # Sum target (use existing logic but regime can shift it)
    h300 = history[-300:] if len(history) >= 300 else history
    sums = [sum(d['numbers']) for d in h300]
    mu, sg = np.mean(sums), np.std(sums)

    if regime == 'HIGH_REGIME':
        # LOW sum target (below mean)
        tlo, thi = mu - 1.5 * sg, mu - 0.3 * sg
    elif regime == 'LOW_REGIME':
        # HIGH sum target (above mean)
        tlo, thi = mu + 0.3 * sg, mu + 1.5 * sg
    else:
        tlo, thi = _sum_target(history)

    tmid = (tlo + thi) / 2.0

    best, best_dist, best_in = None, float('inf'), False
    for combo in combinations(pool, 6):
        s = sum(combo)
        in_range = (tlo <= s <= thi)
        dist = abs(s - tmid)
        if in_range and (not best_in or dist < best_dist):
            best, best_dist, best_in = combo, dist, True
        elif not in_range and not best_in and dist < best_dist:
            best, best_dist = combo, dist

    return sorted(best) if best else sorted(pool[:6])


# ========== Strategy Variants ==========

def ts3_regime_3bet(history):
    """Triple Strike v2 + Sum Regime (3注)"""
    regime, consec, strength = detect_sum_regime(history)

    if regime == 'NEUTRAL':
        # No regime signal → use original TS3
        return generate_triple_strike(history)

    # Regime active: adjust bet1 (Fourier) and bet2 (Cold)
    bet1 = fourier_regime_bet(history, window=500, regime=regime, regime_strength=0.3)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    return [bet1, bet2, bet3]


def ts3_regime_aggressive_3bet(history):
    """Triple Strike + Aggressive Regime (strength=0.5)"""
    regime, consec, strength = detect_sum_regime(history)

    if regime == 'NEUTRAL':
        return generate_triple_strike(history)

    bet1 = fourier_regime_bet(history, window=500, regime=regime, regime_strength=0.5)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    return [bet1, bet2, bet3]


def ts3_regime_fourier_only_3bet(history):
    """Only adjust Fourier bet by regime, keep Cold/Tail as-is"""
    regime, consec, strength = detect_sum_regime(history)

    if regime == 'NEUTRAL':
        return generate_triple_strike(history)

    bet1 = fourier_regime_bet(history, window=500, regime=regime, regime_strength=0.3)
    used = set(bet1)
    # Cold and Tail use original logic (no regime)
    bet2 = cold_numbers_bet(history, window=100, exclude=used)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    return [bet1, bet2, bet3]


def ts3_regime_threshold3_3bet(history):
    """Lower threshold: trigger at 3 consecutive (instead of 5)"""
    regime, consec, strength = detect_sum_regime(history, threshold=3)

    if regime == 'NEUTRAL':
        return generate_triple_strike(history)

    bet1 = fourier_regime_bet(history, window=500, regime=regime, regime_strength=0.3)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    return [bet1, bet2, bet3]


def ts3_regime_threshold7_3bet(history):
    """Higher threshold: trigger at 7 consecutive"""
    regime, consec, strength = detect_sum_regime(history, threshold=7)

    if regime == 'NEUTRAL':
        return generate_triple_strike(history)

    bet1 = fourier_regime_bet(history, window=500, regime=regime, regime_strength=0.3)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    return [bet1, bet2, bet3]


# ========== 2-Bet Variants ==========

def regime_fourier_cold_2bet(history):
    """2注: Regime-Fourier + Regime-Cold"""
    regime, _, _ = detect_sum_regime(history)
    bet1 = fourier_regime_bet(history, window=500, regime=regime, regime_strength=0.3)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    return [bet1, bet2]


# ========== Backtest Engine ==========

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'BIG_LOTTO'
        ORDER BY date ASC, draw ASC
    """)
    rows = c.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums[:6])})
    return draws


def backtest_strategy(draws, strategy_func, n_bets, test_periods, label=""):
    """Standard rolling backtest"""
    m3_hits = 0
    total = 0

    for i in range(test_periods):
        target_idx = len(draws) - test_periods + i
        if target_idx < 100:  # need at least 100 draws for training
            continue

        target = draws[target_idx]
        hist = draws[:target_idx]
        actual = set(target['numbers'][:6])

        try:
            bets = strategy_func(hist)
            assert len(bets) == n_bets, f"Expected {n_bets} bets, got {len(bets)}"

            hit = any(len(set(bet) & actual) >= 3 for bet in bets)
            if hit:
                m3_hits += 1
            total += 1
        except Exception as e:
            total += 1  # count as miss
            continue

    if total == 0:
        return {'m3_hits': 0, 'total': 0, 'rate': 0, 'edge': 0}

    rate = m3_hits / total * 100
    # Baseline for n_bets
    p1 = 1.86 / 100  # M3+ single bet probability for 49-choose-6
    baseline = (1 - (1 - p1) ** n_bets) * 100
    edge = rate - baseline

    return {
        'm3_hits': m3_hits, 'total': total,
        'rate': rate, 'baseline': baseline, 'edge': edge,
        'label': label
    }


def z_score(m3_hits, total, baseline_rate):
    p0 = baseline_rate / 100
    p_hat = m3_hits / total
    se = np.sqrt(p0 * (1 - p0) / total)
    if se == 0:
        return 0.0
    return (p_hat - p0) / se


def permutation_test(draws, strategy_func, n_bets, test_periods, n_perms=1000):
    """Permutation test: shuffle actual numbers and compare Edge"""
    import random
    # Actual edge
    real = backtest_strategy(draws, strategy_func, n_bets, test_periods, "real")
    real_edge = real['edge']

    # Generate permutation edges
    perm_edges = []
    rng = random.Random(42)

    for p in range(n_perms):
        shuffled_draws = []
        all_nums_pool = list(range(1, MAX_NUM + 1))
        for d in draws:
            shuffled_nums = sorted(rng.sample(all_nums_pool, 6))
            shuffled_draws.append({
                'draw': d['draw'], 'date': d['date'],
                'numbers': shuffled_nums
            })

        perm_result = backtest_strategy(shuffled_draws, strategy_func, n_bets, test_periods, f"perm_{p}")
        perm_edges.append(perm_result['edge'])

    # p-value: fraction of permutations with edge >= real edge
    p_value = sum(1 for pe in perm_edges if pe >= real_edge) / n_perms

    return {
        'real_edge': real_edge,
        'perm_mean': np.mean(perm_edges),
        'perm_std': np.std(perm_edges),
        'p_value': p_value,
        'n_perms': n_perms
    }


# ========== Main ==========

def main():
    draws = load_draws()
    print(f"Loaded {len(draws)} BIG_LOTTO draws")
    print(f"Last draw: {draws[-1]['draw']} ({draws[-1]['date']})")

    # === Regime distribution analysis ===
    print("\n" + "=" * 70)
    print("  Sum Regime Distribution (last 1500 draws)")
    print("=" * 70)

    regime_counts = Counter()
    for i in range(1500):
        idx = len(draws) - 1500 + i
        if idx < 100:
            continue
        hist = draws[:idx]
        regime, consec, strength = detect_sum_regime(hist)
        regime_counts[regime] += 1

    for r, cnt in regime_counts.most_common():
        pct = cnt / sum(regime_counts.values()) * 100
        print(f"  {r}: {cnt} ({pct:.1f}%)")

    # === Three-window validation for all variants ===
    strategies = [
        ("TS3 baseline (no regime)", generate_triple_strike, 3),
        ("TS3 + Regime (s=0.3, th=5)", ts3_regime_3bet, 3),
        ("TS3 + Regime Aggressive (s=0.5)", ts3_regime_aggressive_3bet, 3),
        ("TS3 + Regime Fourier-only", ts3_regime_fourier_only_3bet, 3),
        ("TS3 + Regime (th=3)", ts3_regime_threshold3_3bet, 3),
        ("TS3 + Regime (th=7)", ts3_regime_threshold7_3bet, 3),
        ("2bet Regime Fourier+Cold", regime_fourier_cold_2bet, 2),
    ]

    print("\n" + "=" * 70)
    print("  Three-Window Validation (150 / 500 / 1500)")
    print("=" * 70)

    results_all = {}
    for name, func, n_bets in strategies:
        print(f"\n--- {name} ({n_bets}-bet) ---")
        results = {}
        for periods in [150, 500, 1500]:
            r = backtest_strategy(draws, func, n_bets, periods, name)
            z = z_score(r['m3_hits'], r['total'], r['baseline'])
            results[periods] = r
            print(f"  {periods:5d}p: M3+={r['m3_hits']:3d}/{r['total']:4d} "
                  f"({r['rate']:.2f}%) Edge={r['edge']:+.2f}% z={z:.2f}")

        # Classify pattern
        edges = [results[p]['edge'] for p in [150, 500, 1500]]
        if all(e > 0 for e in edges):
            pattern = "STABLE"
        elif edges[2] < 0:
            pattern = "SHORT_MOMENTUM" if any(e > 0 for e in edges[:2]) else "INEFFECTIVE"
        elif edges[0] < 0 and edges[2] > 0:
            pattern = "LATE_BLOOMER"
        else:
            pattern = "MIXED"
        print(f"  Pattern: {pattern}")
        results_all[name] = {'results': results, 'pattern': pattern, 'edges': edges}

    # === Best candidate permutation test ===
    print("\n" + "=" * 70)
    print("  Permutation Test (best candidate)")
    print("=" * 70)

    # Find best STABLE strategy
    best_name = None
    best_1500_edge = -999
    for name, info in results_all.items():
        if info['pattern'] == 'STABLE' and info['edges'][2] > best_1500_edge:
            best_name = name
            best_1500_edge = info['edges'][2]

    if best_name is None:
        # Fallback to best 1500p edge
        for name, info in results_all.items():
            if info['edges'][2] > best_1500_edge:
                best_name = name
                best_1500_edge = info['edges'][2]

    if best_name:
        _, func, n_bets = next(s for s in strategies if s[0] == best_name)
        print(f"\n  Testing: {best_name} (1500p Edge: {best_1500_edge:+.2f}%)")
        perm = permutation_test(draws, func, n_bets, 1500, n_perms=200)
        print(f"  Real Edge:     {perm['real_edge']:+.2f}%")
        print(f"  Perm Mean:     {perm['perm_mean']:+.2f}% +/- {perm['perm_std']:.2f}%")
        print(f"  p-value:       {perm['p_value']:.4f}")
        print(f"  Significant:   {'YES (p<0.05)' if perm['p_value'] < 0.05 else 'NO'}")

        # Also test TS3 baseline for comparison
        print(f"\n  Testing: TS3 baseline (reference)")
        perm_base = permutation_test(draws, generate_triple_strike, 3, 1500, n_perms=200)
        print(f"  Real Edge:     {perm_base['real_edge']:+.2f}%")
        print(f"  Perm Mean:     {perm_base['perm_mean']:+.2f}% +/- {perm_base['perm_std']:.2f}%")
        print(f"  p-value:       {perm_base['p_value']:.4f}")

    # === Summary ===
    print("\n" + "=" * 70)
    print("  Summary")
    print("=" * 70)
    print(f"\n{'Strategy':<40} {'150p':>7} {'500p':>7} {'1500p':>7} {'Pattern':<15}")
    print("-" * 76)
    for name, info in results_all.items():
        e150, e500, e1500 = info['edges']
        print(f"  {name:<38} {e150:+.2f}% {e500:+.2f}% {e1500:+.2f}% {info['pattern']:<15}")


if __name__ == '__main__':
    main()
