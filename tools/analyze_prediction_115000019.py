#!/usr/bin/env python3
"""
Draw 115000019 Prediction Analysis
====================================
Generate predictions that WOULD have been made BEFORE seeing draw 115000019,
using all verified strategies, then compare with actual result.

CRITICAL: No data leakage - only use draws BEFORE 115000019 (up to 115000018).

Actual Result: [16, 35, 36, 37, 39, 49]

Strategies tested:
  1. 2-bet P0 (Deviation + Echo) - Edge +1.21%
  2. 3-bet Triple Strike (Fourier + Cold + Tail) - Edge +0.98%
  3. 4-bet TS3+Markov(w=30) - Edge +1.23%
  4. 5-bet TS3+Markov+FreqOrtho - Edge +1.77% (BEST, P3 VERIFIED)
  5. 5-bet Orthogonal (from backtest_big_lotto_orthogonal_5bet.py)
"""
import os
import sys
import json
import sqlite3
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

# ============================================================
# Setup paths
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

# ============================================================
# Constants
# ============================================================
ACTUAL_DRAW = '115000019'
ACTUAL_NUMBERS = [16, 35, 36, 37, 39, 49]
ACTUAL_SET = set(ACTUAL_NUMBERS)
MAX_NUM = 49
PICK = 6
CUTOFF_DRAW = '115000018'  # Only use draws up to this

P_SINGLE = 0.0186  # Single-bet M3+ baseline for BIG_LOTTO (49 choose 6)
BASELINES = {n: (1 - (1 - P_SINGLE) ** n) * 100 for n in range(1, 8)}


# ============================================================
# Data Loading (NO DATA LEAKAGE)
# ============================================================
def load_history():
    """Load all BIG_LOTTO draws up to 115000018 from DB."""
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT draw, date, numbers, special
        FROM draws
        WHERE lottery_type = 'BIG_LOTTO'
        ORDER BY date ASC, draw ASC
    """)

    history = []
    for row in cursor.fetchall():
        draw_id = row['draw']
        # CRITICAL: Strict cutoff - only draws BEFORE 115000019
        if draw_id >= ACTUAL_DRAW:
            continue
        nums = json.loads(row['numbers'])
        history.append({
            'draw': draw_id,
            'date': row['date'],
            'numbers': nums,
            'special': row['special']
        })

    conn.close()

    # Also check lottery_history.json for any draws not in DB
    json_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_history.json')
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            dbt = data.get('data_by_type', {})
            bl_json = dbt.get('BIG_LOTTO', [])
            existing_draws = {d['draw'] for d in history}
            added = 0
            for item in bl_json:
                if item['draw'] not in existing_draws and item['draw'] < ACTUAL_DRAW:
                    history.append({
                        'draw': item['draw'],
                        'date': item['date'],
                        'numbers': item['numbers'],
                        'special': item.get('special', 0)
                    })
                    added += 1
            if added > 0:
                print(f"  Added {added} draws from lottery_history.json")
        except Exception as e:
            print(f"  Warning: Could not read lottery_history.json: {e}")

    # Sort by date and draw (oldest first)
    history.sort(key=lambda x: (x['date'], x['draw']))

    # DATA LEAKAGE CHECK
    for d in history:
        assert d['draw'] < ACTUAL_DRAW, f"DATA LEAKAGE! Draw {d['draw']} >= {ACTUAL_DRAW}"

    return history


# ============================================================
# Strategy 1: P0 2-bet (Deviation + Echo)
# ============================================================
def biglotto_p0_2bet(history, window=50, echo_boost=1.5):
    """2-bet P0: Hot+Echo + Cold (Edge +1.21%, deterministic)"""
    recent = history[-window:] if len(history) > window else history
    expected = len(recent) * PICK / MAX_NUM

    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1

    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = freq.get(n, 0) - expected

    # P0: Lag-2 echo boost
    if len(history) >= 3:
        for n in history[-2]['numbers']:
            if n <= MAX_NUM:
                scores[n] += echo_boost

    hot = sorted([(n, s) for n, s in scores.items() if s > 1],
                 key=lambda x: x[1], reverse=True)
    cold = sorted([(n, abs(s)) for n, s in scores.items() if s < -1],
                  key=lambda x: x[1], reverse=True)

    # Bet 1: Hot+Echo
    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)
    if len(bet1) < PICK:
        mid = sorted(range(1, MAX_NUM + 1), key=lambda n: abs(scores[n]))
        for n in mid:
            if n not in used and len(bet1) < PICK:
                bet1.append(n)
                used.add(n)

    # Bet 2: Cold
    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK:
            bet2.append(n)
            used.add(n)
    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK:
                bet2.append(n)
                used.add(n)

    return [sorted(bet1[:PICK]), sorted(bet2[:PICK])]


# ============================================================
# Strategy 2: Triple Strike 3-bet (Fourier + Cold + Tail)
# ============================================================
def fourier_rhythm_bet(history, window=500):
    """Fourier Rhythm - FFT period analysis"""
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
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    sorted_idx = np.argsort(scores[1:])[::-1] + 1
    return sorted(sorted_idx[:6].tolist())


def cold_numbers_bet(history, window=100, exclude=None):
    """Cold Numbers - least frequent in recent N draws"""
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))
    return sorted(sorted_cold[:6])


def tail_balance_bet(history, window=100, exclude=None):
    """Tail Balance - balanced digit coverage"""
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)

    tail_groups = {i: [] for i in range(10)}
    for n in range(1, MAX_NUM + 1):
        if n not in exclude:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for t in tail_groups:
        tail_groups[t].sort(key=lambda x: x[1], reverse=True)

    selected = []
    available_tails = sorted(
        [t for t in range(10) if tail_groups[t]],
        key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0,
        reverse=True
    )
    idx_in_group = {t: 0 for t in range(10)}

    while len(selected) < 6:
        added = False
        for tail in available_tails:
            if len(selected) >= 6:
                break
            if idx_in_group[tail] < len(tail_groups[tail]):
                num, _ = tail_groups[tail][idx_in_group[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                idx_in_group[tail] += 1
        if not added:
            break

    if len(selected) < 6:
        remaining = [n for n in range(1, MAX_NUM + 1) if n not in selected and n not in exclude]
        remaining.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(remaining[:6 - len(selected)])

    return sorted(selected[:6])


def generate_triple_strike(history):
    """Triple Strike 3-bet"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


# ============================================================
# Strategy 3: TS3+Markov 4-bet
# ============================================================
def markov_orthogonal_bet(history, exclude=None, markov_window=30):
    """Markov orthogonal bet - transition matrix conditional probability"""
    exclude = exclude or set()
    window = min(markov_window, len(history))
    recent = history[-window:]

    transitions = Counter()
    for i in range(len(recent) - 1):
        for p in recent[i]['numbers']:
            for n in recent[i + 1]['numbers']:
                transitions[(p, n)] += 1

    if len(history) < 2:
        candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
        return sorted(candidates[:6])

    scores = Counter()
    for prev_num in history[-1]['numbers']:
        for n in range(1, MAX_NUM + 1):
            scores[n] += transitions.get((prev_num, n), 0)

    candidates = [(n, scores[n]) for n in range(1, MAX_NUM + 1) if n not in exclude]
    candidates.sort(key=lambda x: -x[1])

    selected = [n for n, _ in candidates[:PICK]]
    if len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in selected]
        selected.extend(remaining[:PICK - len(selected)])

    return sorted(selected[:PICK])


def generate_ts3_markov4(history):
    """TS3 + Markov orthogonal 4-bet"""
    bets = generate_triple_strike(history)
    ts3_used = set()
    for b in bets:
        ts3_used.update(b)
    bet4 = markov_orthogonal_bet(history, exclude=ts3_used, markov_window=30)
    return bets + [bet4]


# ============================================================
# Strategy 4: TS3+Markov+FreqOrtho 5-bet (BEST, P3 VERIFIED)
# ============================================================
def freq_orthogonal_bet(history, window=200, exclude=None):
    """Frequency Orthogonal - highest frequency from remaining pool"""
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    candidates = [(n, freq.get(n, 0)) for n in range(1, MAX_NUM + 1) if n not in exclude]
    candidates.sort(key=lambda x: -x[1])
    return sorted([n for n, _ in candidates[:6]])


def generate_ts3_markov4_freqortho5(history):
    """5-bet PRODUCTION: TS3+Markov+FreqOrtho (Edge +1.77%, P3 VERIFIED)"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    ts3_used = set(bet1) | set(bet2) | set(bet3)
    bet4 = markov_orthogonal_bet(history, exclude=ts3_used, markov_window=30)
    used_4 = ts3_used | set(bet4)
    bet5 = freq_orthogonal_bet(history, window=200, exclude=used_4)
    return [bet1, bet2, bet3, bet4, bet5]


# ============================================================
# Analysis and Comparison
# ============================================================
def analyze_bet(bet_numbers, actual_set, label=""):
    """Analyze a single bet against actual result."""
    bet_set = set(bet_numbers)
    matched = sorted(bet_set & actual_set)
    missed = sorted(actual_set - bet_set)
    return {
        'label': label,
        'numbers': sorted(bet_numbers),
        'match_count': len(matched),
        'matched': matched,
        'missed': missed,
        'is_m3': len(matched) >= 3,
    }


def analyze_strategy(bets, actual_set, strategy_name, num_bets, edge_str):
    """Analyze a multi-bet strategy against actual result."""
    results = []
    best_match = 0
    best_idx = -1
    all_covered = set()

    bet_labels = {
        2: ['Hot+Echo', 'Cold'],
        3: ['Fourier Rhythm', 'Cold Numbers', 'Tail Balance'],
        4: ['Fourier Rhythm', 'Cold Numbers', 'Tail Balance', 'Markov(w=30)'],
        5: ['Fourier Rhythm', 'Cold Numbers', 'Tail Balance', 'Markov(w=30)', 'Freq Orthogonal'],
    }
    labels = bet_labels.get(num_bets, [f'Bet {i+1}' for i in range(num_bets)])

    for i, bet in enumerate(bets):
        label = labels[i] if i < len(labels) else f'Bet {i+1}'
        r = analyze_bet(bet, actual_set, label)
        results.append(r)
        all_covered.update(bet)
        if r['match_count'] > best_match:
            best_match = r['match_count']
            best_idx = i

    any_m3 = any(r['is_m3'] for r in results)
    total_unique_matched = sorted(all_covered & actual_set)
    baseline = BASELINES.get(num_bets, 0)

    return {
        'strategy': strategy_name,
        'num_bets': num_bets,
        'edge': edge_str,
        'baseline': baseline,
        'bets': results,
        'best_match': best_match,
        'best_bet_idx': best_idx,
        'any_m3': any_m3,
        'coverage': len(all_covered),
        'unique_matched': total_unique_matched,
        'unique_match_count': len(total_unique_matched),
    }


def print_strategy_result(result):
    """Print formatted strategy analysis result."""
    print()
    print(f"{'=' * 70}")
    m3_marker = " <<< M3+ HIT!" if result['any_m3'] else ""
    print(f"  Strategy: {result['strategy']} ({result['num_bets']}-bet){m3_marker}")
    print(f"  Verified Edge: {result['edge']} | Baseline: {result['baseline']:.2f}%")
    print(f"{'=' * 70}")

    for i, bet in enumerate(result['bets'], 1):
        nums_str = ', '.join(f'{n:02d}' for n in bet['numbers'])
        matched_str = ', '.join(f'{n:02d}' for n in bet['matched']) if bet['matched'] else 'none'
        m3_flag = " *** M3+!" if bet['is_m3'] else ""
        print(f"  Bet {i} ({bet['label']}): [{nums_str}]")
        print(f"    Match: {bet['match_count']}/6 -> [{matched_str}]{m3_flag}")

    print(f"  {'~' * 66}")
    print(f"  Coverage: {result['coverage']}/49 ({result['coverage']/49*100:.1f}%)")
    print(f"  Best single bet: Bet {result['best_bet_idx']+1} with {result['best_match']} matches")
    unique_str = ', '.join(f'{n:02d}' for n in result['unique_matched'])
    print(f"  Total unique hits: {result['unique_match_count']}/6 -> [{unique_str}]")
    missed_all = sorted(ACTUAL_SET - set().union(*[set(b['numbers']) for b in result['bets']]))
    if missed_all:
        missed_str = ', '.join(f'{n:02d}' for n in missed_all)
        print(f"  Numbers NOT covered by any bet: [{missed_str}]")
    print()


def print_number_analysis(history):
    """Analyze the actual winning numbers in context of recent history."""
    print(f"\n{'=' * 70}")
    print(f"  Number-by-Number Analysis for {ACTUAL_DRAW}")
    print(f"{'=' * 70}")
    print(f"  Actual Result: [{', '.join(f'{n:02d}' for n in ACTUAL_NUMBERS)}]")
    print()

    recent_50 = history[-50:]
    recent_100 = history[-100:]
    freq_50 = Counter(n for d in recent_50 for n in d['numbers'])
    freq_100 = Counter(n for d in recent_100 for n in d['numbers'])
    expected_50 = len(recent_50) * PICK / MAX_NUM
    expected_100 = len(recent_100) * PICK / MAX_NUM

    # Last draw info
    last_draw = history[-1]
    second_last = history[-2] if len(history) >= 2 else None

    print(f"  Last draw ({last_draw['draw']}): {last_draw['numbers']}")
    if second_last:
        print(f"  N-2 draw  ({second_last['draw']}): {second_last['numbers']}")
    print()

    # Check structural properties of actual result
    actual_sorted = sorted(ACTUAL_NUMBERS)
    odd_count = sum(1 for n in actual_sorted if n % 2 == 1)
    even_count = 6 - odd_count
    low = sum(1 for n in actual_sorted if n <= 16)
    mid = sum(1 for n in actual_sorted if 17 <= n <= 33)
    high = sum(1 for n in actual_sorted if n >= 34)
    total_sum = sum(actual_sorted)
    consecutive_pairs = sum(1 for i in range(len(actual_sorted)-1) if actual_sorted[i+1] - actual_sorted[i] == 1)
    tails = set(n % 10 for n in actual_sorted)

    print(f"  Structural Profile:")
    print(f"    Sum: {total_sum} (typical range: 100-200)")
    print(f"    Odd/Even: {odd_count}/{even_count}")
    print(f"    Zone (Low/Mid/High): {low}/{mid}/{high}")
    print(f"    Consecutive pairs: {consecutive_pairs}")
    print(f"    Tail digits: {sorted(tails)} ({len(tails)}/10)")
    print()

    print(f"  Per-Number Analysis:")
    print(f"  {'Number':>8} | {'Freq50':>6} | {'Dev50':>8} | {'Freq100':>7} | {'Gap':>4} | {'Echo?':>6} | {'Assessment':>20}")
    print(f"  {'-'*8}-+-{'-'*6}-+-{'-'*8}-+-{'-'*7}-+-{'-'*4}-+-{'-'*6}-+-{'-'*20}")

    for n in ACTUAL_NUMBERS:
        f50 = freq_50.get(n, 0)
        f100 = freq_100.get(n, 0)
        dev50 = f50 - expected_50

        # Calculate gap (how many draws since last appearance)
        gap = 0
        for d in reversed(history):
            if n in d['numbers']:
                break
            gap += 1

        # Check echo (was in N-2 draw)
        echo = "Yes" if second_last and n in second_last['numbers'] else "No"

        # Assessment
        if dev50 > 2:
            assessment = "HOT"
        elif dev50 > 0.5:
            assessment = "warm"
        elif dev50 < -2:
            assessment = "COLD"
        elif dev50 < -0.5:
            assessment = "cool"
        else:
            assessment = "gray zone"

        print(f"  {n:>8} | {f50:>6} | {dev50:>+8.2f} | {f100:>7} | {gap:>4} | {echo:>6} | {assessment:>20}")

    print()


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 70)
    print("  DRAW 115000019 PREDICTION ANALYSIS")
    print("  Actual Result: [16, 35, 36, 37, 39, 49]")
    print("=" * 70)

    # Load history
    print("\n[1] Loading historical data...")
    history = load_history()
    print(f"  Total draws loaded: {len(history)}")
    print(f"  Date range: {history[0]['date']} ({history[0]['draw']}) to {history[-1]['date']} ({history[-1]['draw']})")
    print(f"  Last draw before target: {history[-1]['draw']} -> {history[-1]['numbers']}")

    # Data leakage verification
    assert history[-1]['draw'] < ACTUAL_DRAW, "DATA LEAKAGE DETECTED!"
    print(f"  Data leakage check: PASSED (last draw {history[-1]['draw']} < {ACTUAL_DRAW})")

    # Number analysis
    print_number_analysis(history)

    # ================================================================
    # Generate predictions for all strategies
    # ================================================================
    print("\n[2] Generating predictions with verified strategies...\n")

    all_results = []

    # Strategy 1: P0 2-bet
    print("  Generating: P0 2-bet (Deviation + Echo)...")
    bets_2 = biglotto_p0_2bet(history)
    r1 = analyze_strategy(bets_2, ACTUAL_SET, "P0 Deviation+Echo", 2, "+1.21%")
    all_results.append(r1)

    # Strategy 2: Triple Strike 3-bet
    print("  Generating: Triple Strike 3-bet...")
    bets_3 = generate_triple_strike(history)
    r2 = analyze_strategy(bets_3, ACTUAL_SET, "Triple Strike", 3, "+0.98%")
    all_results.append(r2)

    # Strategy 3: TS3+Markov 4-bet
    print("  Generating: TS3+Markov 4-bet...")
    bets_4 = generate_ts3_markov4(history)
    r3 = analyze_strategy(bets_4, ACTUAL_SET, "TS3+Markov(w=30)", 4, "+1.23%")
    all_results.append(r3)

    # Strategy 4: TS3+Markov+FreqOrtho 5-bet (BEST)
    print("  Generating: TS3+Markov+FreqOrtho 5-bet (BEST STRATEGY)...")
    bets_5 = generate_ts3_markov4_freqortho5(history)
    r4 = analyze_strategy(bets_5, ACTUAL_SET, "TS3+Markov+FreqOrtho (BEST)", 5, "+1.77%")
    all_results.append(r4)

    # ================================================================
    # Print detailed results
    # ================================================================
    print("\n[3] Detailed Results per Strategy:")
    for result in all_results:
        print_strategy_result(result)

    # ================================================================
    # Summary comparison
    # ================================================================
    print("\n" + "=" * 70)
    print("  SUMMARY COMPARISON")
    print("=" * 70)
    print(f"  Actual Draw {ACTUAL_DRAW}: [{', '.join(f'{n:02d}' for n in ACTUAL_NUMBERS)}]")
    print()
    print(f"  {'Strategy':<35} | {'Bets':>4} | {'Best':>4} | {'M3+':>4} | {'Coverage':>8} | {'Unique Hits':>11}")
    print(f"  {'-'*35}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*8}-+-{'-'*11}")

    for r in all_results:
        m3_str = "YES" if r['any_m3'] else "no"
        cov_str = f"{r['coverage']}/49"
        uhits = f"{r['unique_match_count']}/6"
        print(f"  {r['strategy']:<35} | {r['num_bets']:>4} | {r['best_match']:>4} | {m3_str:>4} | {cov_str:>8} | {uhits:>11}")

    # Coverage analysis
    print()
    print(f"  {'~' * 66}")
    print(f"  Coverage Analysis:")

    # Numbers covered by ANY strategy
    all_numbers_predicted = set()
    for r in all_results:
        for bet in r['bets']:
            all_numbers_predicted.update(bet['numbers'])

    covered_actual = sorted(all_numbers_predicted & ACTUAL_SET)
    uncovered_actual = sorted(ACTUAL_SET - all_numbers_predicted)

    print(f"  Total unique numbers across all strategies: {len(all_numbers_predicted)}/49")
    print(f"  Actual numbers covered by at least one strategy: {len(covered_actual)}/6 -> [{', '.join(f'{n:02d}' for n in covered_actual)}]")
    if uncovered_actual:
        print(f"  Actual numbers NOT covered by ANY strategy: [{', '.join(f'{n:02d}' for n in uncovered_actual)}]")

    # Number frequency across predictions
    print()
    print(f"  Prediction Frequency for Actual Numbers:")
    for n in ACTUAL_NUMBERS:
        count = 0
        which_bets = []
        for r in all_results:
            for i, bet in enumerate(r['bets']):
                if n in bet['numbers']:
                    count += 1
                    which_bets.append(f"{r['strategy'][:15]} Bet{i+1}")
        status = f"Predicted {count}x" if count > 0 else "NEVER predicted"
        details = f" ({'; '.join(which_bets)})" if which_bets else ""
        print(f"    {n:02d}: {status}{details}")

    print()
    print("=" * 70)
    print("  END OF ANALYSIS")
    print("=" * 70)


if __name__ == '__main__':
    main()
