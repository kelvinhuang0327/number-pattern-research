#!/usr/bin/env python3
"""
大樂透 034期教訓: Fourier/Markov競爭 + Cold提權 + 奇偶約束
==========================================================
034期結果:
  - Fourier Top6: 0命中 (連續失效)
  - Cold+Sum: 2命中 (連續最佳)
  - #11: Fourier=47 vs Markov=3 (嚴重衝突)
  - 全奇數(6:0): 1.37% 極端事件

改進方案:
  1. Fourier confidence gating: Fourier信號弱時降級為Markov
  2. Cold提權: 2注以Cold為bet1
  3. 奇偶soft constraint: max_same_parity=5

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
    fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet,
    generate_triple_strike, _sum_target, _SUM_WIN, MAX_NUM
)
from predict_biglotto_regime import (
    detect_sum_regime, apply_regime_weight, fourier_regime_bet,
    cold_regime_bet
)

DB_PATH = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')


# ========== New: Fourier Confidence Score ==========

def fourier_confidence(history, window=500):
    """
    Calculate Fourier signal quality score.
    Returns (confidence, scores_dict) where confidence is the
    ratio of top-6 score sum to total, indicating signal concentration.
    
    High confidence = Fourier has clear periodic signals
    Low confidence = Fourier is guessing (flat scores)
    """
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

    sorted_scores = sorted(scores.values(), reverse=True)
    total = sum(sorted_scores) + 1e-10
    top6_sum = sum(sorted_scores[:6])
    confidence = top6_sum / total

    return confidence, scores


def markov_bet(history, window=30, exclude=None):
    """Markov transition bet: top-6 by transition probability"""
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history

    trans = Counter()
    for i in range(len(recent) - 1):
        curr = set(recent[i]['numbers'])
        nxt = set(recent[i + 1]['numbers'])
        for c in curr:
            for n in nxt:
                trans[(c, n)] += 1

    last_nums = set(history[-1]['numbers'])
    scores = {}
    for n in range(1, MAX_NUM + 1):
        if n in exclude:
            scores[n] = 0.0
            continue
        s = sum(trans.get((prev, n), 0) for prev in last_nums)
        scores[n] = s

    sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    result = [n for n in sorted_nums if n not in exclude][:6]
    return sorted(result)


# ========== New: Competitive Fourier/Markov Bet ==========

def competitive_bet1(history, window=500, confidence_threshold=0.25,
                     regime='NEUTRAL', regime_strength=0.3):
    """
    Fourier/Markov competitive selection for bet1.
    
    If Fourier confidence >= threshold: use Fourier
    If Fourier confidence < threshold: use Markov
    Both can be regime-adjusted.
    """
    conf, f_scores = fourier_confidence(history, window)

    if conf >= confidence_threshold:
        # Fourier has good signal
        if regime != 'NEUTRAL':
            f_scores = apply_regime_weight(f_scores, regime, regime_strength)
        sorted_nums = sorted(f_scores.keys(), key=lambda x: f_scores[x], reverse=True)
        return sorted(sorted_nums[:6]), 'fourier', conf
    else:
        # Markov takes over
        bet = markov_bet(history, window=30)
        return bet, 'markov', conf


# ========== New: Parity Soft Constraint ==========

def enforce_parity(bet, max_same=5, max_num=49):
    """
    If all 6 numbers have same parity, swap one to ensure max_same limit.
    Minimal intervention: only swap the weakest (last) number.
    """
    odd_count = sum(1 for n in bet if n % 2 == 1)
    even_count = 6 - odd_count

    if odd_count <= max_same and even_count <= max_same:
        return bet  # no intervention needed

    bet = list(bet)
    if odd_count > max_same:
        # Too many odd, swap last odd with nearest even
        odd_nums = [n for n in bet if n % 2 == 1]
        target = odd_nums[-1]  # swap the last odd
        # Find closest even not in bet
        candidates = [n for n in range(1, max_num + 1) if n % 2 == 0 and n not in bet]
        if candidates:
            replacement = min(candidates, key=lambda x: abs(x - target))
            bet[bet.index(target)] = replacement
    elif even_count > max_same:
        # Too many even, swap last even with nearest odd
        even_nums = [n for n in bet if n % 2 == 0]
        target = even_nums[-1]
        candidates = [n for n in range(1, max_num + 1) if n % 2 == 1 and n not in bet]
        if candidates:
            replacement = min(candidates, key=lambda x: abs(x - target))
            bet[bet.index(target)] = replacement

    return sorted(bet)


# ========== Strategy Variants ==========

# --- V1: Competitive bet1 (Fourier/Markov gating) + Cold + Tail ---
def ts3_competitive_3bet(history):
    """TS3 with Fourier/Markov competitive bet1"""
    regime, _, _ = detect_sum_regime(history)
    bet1, method, conf = competitive_bet1(history, confidence_threshold=0.25,
                                           regime=regime, regime_strength=0.3)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    return [bet1, bet2, bet3]


# --- V2: Like V1 but threshold=0.20 (more Fourier) ---
def ts3_competitive_t20_3bet(history):
    """Competitive with lower threshold (0.20) - prefers Fourier more"""
    regime, _, _ = detect_sum_regime(history)
    bet1, _, _ = competitive_bet1(history, confidence_threshold=0.20,
                                   regime=regime, regime_strength=0.3)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    return [bet1, bet2, bet3]


# --- V3: Like V1 but threshold=0.30 (more Markov) ---
def ts3_competitive_t30_3bet(history):
    """Competitive with higher threshold (0.30) - switches to Markov more"""
    regime, _, _ = detect_sum_regime(history)
    bet1, _, _ = competitive_bet1(history, confidence_threshold=0.30,
                                   regime=regime, regime_strength=0.3)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    return [bet1, bet2, bet3]


# --- V4: Cold-first 2bet (Cold + Fourier/Markov competitive) ---
def cold_first_2bet(history):
    """2bet: Cold as bet1 (promoted), competitive bet2"""
    regime, _, _ = detect_sum_regime(history)
    bet1 = cold_regime_bet(history, window=100, exclude=set(), regime=regime)
    used = set(bet1)
    bet2, _, _ = competitive_bet1(history, confidence_threshold=0.25,
                                   regime=regime, regime_strength=0.3)
    # Remove overlap with bet1
    bet2_clean = [n for n in range(1, MAX_NUM + 1) if n not in used]
    conf, f_scores = fourier_confidence(history)
    if conf >= 0.25:
        # Use Fourier scores for remaining
        remaining_scores = {n: f_scores.get(n, 0) for n in bet2_clean}
        if regime != 'NEUTRAL':
            remaining_scores = apply_regime_weight(remaining_scores, regime, 0.3)
        sorted_nums = sorted(remaining_scores.keys(), key=lambda x: remaining_scores[x], reverse=True)
        bet2 = sorted(sorted_nums[:6])
    else:
        bet2 = markov_bet(history, window=30, exclude=used)
    return [bet1, bet2]


# --- V5: Current regime 2bet (baseline for comparison) ---
def regime_2bet_baseline(history):
    """Current production 2bet (Fourier+Cold with regime)"""
    regime, _, _ = detect_sum_regime(history)
    bet1 = fourier_regime_bet(history, window=500, regime=regime, regime_strength=0.3)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    return [bet1, bet2]


# --- V6: TS3+Regime baseline (current production) ---
def ts3_regime_baseline(history):
    """Current production 3bet (TS3+Regime)"""
    regime, consec, strength = detect_sum_regime(history)
    if regime == 'NEUTRAL':
        return generate_triple_strike(history)
    bet1 = fourier_regime_bet(history, window=500, regime=regime, regime_strength=0.3)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    return [bet1, bet2, bet3]


# --- V7: V1 + parity constraint ---
def ts3_competitive_parity_3bet(history):
    """V1 + parity constraint on all bets"""
    regime, _, _ = detect_sum_regime(history)
    bet1, _, _ = competitive_bet1(history, confidence_threshold=0.25,
                                   regime=regime, regime_strength=0.3)
    bet1 = enforce_parity(bet1, max_same=5)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    bet2 = enforce_parity(bet2, max_same=5)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    bet3 = enforce_parity(bet3, max_same=5)
    return [bet1, bet2, bet3]


# --- V8: Cold-first 2bet + parity ---
def cold_first_parity_2bet(history):
    """Cold-first 2bet + parity constraint"""
    bets = cold_first_2bet(history)
    return [enforce_parity(b, max_same=5) for b in bets]


# --- V9: Pure Markov 3bet (extreme test) ---
def markov_3bet(history):
    """All 3 bets from Markov (control test)"""
    bet1 = markov_bet(history, window=30)
    used = set(bet1)
    bet2 = cold_numbers_bet(history, window=100, exclude=used)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    return [bet1, bet2, bet3]


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
        if target_idx < 100:
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
            total += 1
            continue

    if total == 0:
        return {'m3_hits': 0, 'total': 0, 'rate': 0, 'edge': 0}

    rate = m3_hits / total * 100
    p1 = 1.86 / 100
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


# ========== Main ==========

if __name__ == '__main__':
    print("Loading BIG_LOTTO draws...")
    draws = load_draws()
    print(f"Total draws: {len(draws)}")

    # Define strategies to test
    strategies_3bet = [
        ("TS3+Regime (baseline)", ts3_regime_baseline, 3),
        ("TS3+Competitive t=0.25", ts3_competitive_3bet, 3),
        ("TS3+Competitive t=0.20", ts3_competitive_t20_3bet, 3),
        ("TS3+Competitive t=0.30", ts3_competitive_t30_3bet, 3),
        ("TS3+Competitive+Parity", ts3_competitive_parity_3bet, 3),
        ("Markov+Cold+Tail (ctrl)", markov_3bet, 3),
    ]

    strategies_2bet = [
        ("Regime F+C (baseline)", regime_2bet_baseline, 2),
        ("Cold-first+Competitive", cold_first_2bet, 2),
        ("Cold-first+Parity", cold_first_parity_2bet, 2),
    ]

    windows = [150, 500, 1500]

    # --- 3-bet strategies ---
    print("\n" + "=" * 90)
    print("  3-BET STRATEGIES — 3-Window Validation")
    print("=" * 90)

    results_3bet = {}
    for name, func, n_bets in strategies_3bet:
        results_3bet[name] = {}
        print(f"\n  [{name}]")
        for w in windows:
            r = backtest_strategy(draws, func, n_bets, w, f"{name}_{w}")
            results_3bet[name][w] = r
            z = z_score(r['m3_hits'], r['total'], r['baseline'])
            stable = "STABLE" if r['edge'] > 0 else "NEGATIVE"
            print(f"    {w:4d}p: {r['m3_hits']:3d}/{r['total']:4d} = {r['rate']:.2f}% "
                  f"(base={r['baseline']:.2f}%) Edge={r['edge']:+.2f}% z={z:.2f} {stable}")

    # --- 2-bet strategies ---
    print("\n" + "=" * 90)
    print("  2-BET STRATEGIES — 3-Window Validation")
    print("=" * 90)

    results_2bet = {}
    for name, func, n_bets in strategies_2bet:
        results_2bet[name] = {}
        print(f"\n  [{name}]")
        for w in windows:
            r = backtest_strategy(draws, func, n_bets, w, f"{name}_{w}")
            results_2bet[name][w] = r
            z = z_score(r['m3_hits'], r['total'], r['baseline'])
            stable = "STABLE" if r['edge'] > 0 else "NEGATIVE"
            print(f"    {w:4d}p: {r['m3_hits']:3d}/{r['total']:4d} = {r['rate']:.2f}% "
                  f"(base={r['baseline']:.2f}%) Edge={r['edge']:+.2f}% z={z:.2f} {stable}")

    # --- Fourier confidence distribution analysis ---
    print("\n" + "=" * 90)
    print("  Fourier Confidence Distribution (last 1500 draws)")
    print("=" * 90)

    conf_values = []
    fourier_chosen = 0
    markov_chosen = 0
    for i in range(1500):
        target_idx = len(draws) - 1500 + i
        if target_idx < 100:
            continue
        hist = draws[:target_idx]
        conf, _ = fourier_confidence(hist)
        conf_values.append(conf)
        if conf >= 0.25:
            fourier_chosen += 1
        else:
            markov_chosen += 1

    conf_arr = np.array(conf_values)
    print(f"  Mean confidence: {np.mean(conf_arr):.4f}")
    print(f"  Std confidence:  {np.std(conf_arr):.4f}")
    print(f"  Min: {np.min(conf_arr):.4f}, Max: {np.max(conf_arr):.4f}")
    print(f"  Fourier chosen (>= 0.25): {fourier_chosen} ({fourier_chosen/len(conf_values)*100:.1f}%)")
    print(f"  Markov chosen  (< 0.25):  {markov_chosen} ({markov_chosen/len(conf_values)*100:.1f}%)")

    # Percentiles
    for pct in [10, 25, 50, 75, 90]:
        print(f"  P{pct}: {np.percentile(conf_arr, pct):.4f}")

    # --- Summary comparison ---
    print("\n" + "=" * 90)
    print("  SUMMARY — 1500-period Edge Comparison")
    print("=" * 90)
    print(f"  {'Strategy':<35s} {'Edge':>8s} {'Rate':>8s} {'Hits':>6s}")
    print("  " + "-" * 60)

    all_results = {}
    for name in results_3bet:
        r = results_3bet[name].get(1500, {})
        edge = r.get('edge', 0)
        rate = r.get('rate', 0)
        hits = r.get('m3_hits', 0)
        print(f"  {name:<35s} {edge:+7.2f}% {rate:7.2f}% {hits:5d}")
        all_results[name] = r

    for name in results_2bet:
        r = results_2bet[name].get(1500, {})
        edge = r.get('edge', 0)
        rate = r.get('rate', 0)
        hits = r.get('m3_hits', 0)
        print(f"  {name:<35s} {edge:+7.2f}% {rate:7.2f}% {hits:5d}")
        all_results[name] = r

    # Find best 3bet and 2bet
    best_3bet = max(results_3bet.items(), key=lambda x: x[1].get(1500, {}).get('edge', -999))
    best_2bet = max(results_2bet.items(), key=lambda x: x[1].get(1500, {}).get('edge', -999))

    print(f"\n  Best 3-bet: {best_3bet[0]} (Edge={best_3bet[1][1500]['edge']:+.2f}%)")
    print(f"  Best 2-bet: {best_2bet[0]} (Edge={best_2bet[1][1500]['edge']:+.2f}%)")

    # Check 3-window stability for best strategies
    for name, res in [(best_3bet[0], best_3bet[1]), (best_2bet[0], best_2bet[1])]:
        all_positive = all(res[w]['edge'] > 0 for w in windows)
        status = "ALL POSITIVE (STABLE)" if all_positive else "UNSTABLE"
        print(f"  {name}: {status}")

    print("\n  Done.")
