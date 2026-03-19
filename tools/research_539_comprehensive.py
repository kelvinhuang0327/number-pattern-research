#!/usr/bin/env python3
"""
=============================================================================
今彩539 Comprehensive Quantitative Research Engine
=============================================================================
Tests ALL known lottery prediction methodologies:
  Frequency, Gap, Hot/Cold, Markov, Fourier, Tail, Cluster, Regime,
  Entropy, Orthogonal, Monte Carlo, Bayesian, Covering Design,
  Adaptive Ensemble, Feature Interaction, Multiplicative, State-Space,
  Sum Constraint, AC Value, Pattern Match, Cycle Regression

Validation protocol:
  Walk-forward | Permutation test | Three-window stability | OOS

Output: Best 2-ticket & 3-ticket strategies with full statistical analysis
=============================================================================
"""

import sys
import os
import json
import random
import math
import time
import warnings
from collections import Counter, defaultdict
from itertools import combinations
from typing import List, Dict, Tuple, Optional, Callable
from datetime import datetime

import numpy as np
from scipy import stats as scipy_stats

warnings.filterwarnings('ignore')

# ─── Project Setup ───────────────────────────────────────────────
_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_base, '..', 'lottery_api'))
sys.path.insert(0, os.path.join(_base, '..'))
from database import DatabaseManager

# ─── Constants ───────────────────────────────────────────────────
MIN_NUM = 1
MAX_NUM = 39
PICK_COUNT = 5
TOTAL_NUMBERS = list(range(MIN_NUM, MAX_NUM + 1))

# Theoretical baselines (hypergeometric)
# P(match=k) = C(5,k)*C(34,5-k)/C(39,5)
from math import comb
C39_5 = comb(39, 5)  # 575757

def _p_match_exactly(k):
    return comb(5, k) * comb(34, 5 - k) / C39_5

P_MATCH = {k: _p_match_exactly(k) for k in range(6)}
P_GE2_SINGLE = sum(P_MATCH[k] for k in range(2, 6))   # ~0.1140
P_GE3_SINGLE = sum(P_MATCH[k] for k in range(3, 6))   # ~0.01004

BASELINES = {
    'ge2': {
        1: P_GE2_SINGLE,
        2: 1 - (1 - P_GE2_SINGLE) ** 2,
        3: 1 - (1 - P_GE2_SINGLE) ** 3,
    },
    'ge3': {
        1: P_GE3_SINGLE,
        2: 1 - (1 - P_GE3_SINGLE) ** 2,
        3: 1 - (1 - P_GE3_SINGLE) ** 3,
    },
}

print(f"[INFO] Theoretical Baselines:")
print(f"  match≥2: 1-bet={BASELINES['ge2'][1]*100:.2f}%  2-bet={BASELINES['ge2'][2]*100:.2f}%  3-bet={BASELINES['ge2'][3]*100:.2f}%")
print(f"  match≥3: 1-bet={BASELINES['ge3'][1]*100:.2f}%  2-bet={BASELINES['ge3'][2]*100:.2f}%  3-bet={BASELINES['ge3'][3]*100:.2f}%")


# ═══════════════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════════════
def load_data():
    db_path = os.path.join(_base, '..', 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    raw = db.get_all_draws('DAILY_539')
    draws = sorted(raw, key=lambda x: (x['date'], x['draw']))
    print(f"[DATA] Loaded {len(draws)} draws from {draws[0]['date']} to {draws[-1]['date']}")
    return draws


# ═══════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════
def get_numbers(draw):
    """Extract number list from a draw record."""
    nums = draw.get('numbers', [])
    if isinstance(nums, str):
        nums = json.loads(nums)
    return list(nums)

def numbers_from_history(hist, window=None):
    """Flatten last `window` draws into flat list."""
    if window:
        hist = hist[-window:]
    return [n for d in hist for n in get_numbers(d)]

def freq_counter(hist, window=None):
    return Counter(numbers_from_history(hist, window))

def weighted_sample(scores_dict, k=5, rng=None):
    """Weighted sampling without replacement from {number: score}."""
    if rng is None:
        rng = random
    items = [(n, max(s, 0.001)) for n, s in scores_dict.items()]
    selected = []
    for _ in range(k):
        if not items:
            break
        total = sum(s for _, s in items)
        r = rng.random() * total
        cum = 0
        for idx, (n, s) in enumerate(items):
            cum += s
            if cum >= r:
                selected.append(n)
                items.pop(idx)
                break
    return sorted(selected)

def top_k(scores_dict, k=5):
    """Top-k numbers by score."""
    return sorted(sorted(scores_dict, key=scores_dict.get, reverse=True)[:k])

def ensure_valid(nums):
    """Ensure 5 unique valid numbers."""
    nums = [n for n in nums if MIN_NUM <= n <= MAX_NUM]
    nums = list(dict.fromkeys(nums))  # unique preserving order
    while len(nums) < PICK_COUNT:
        n = random.randint(MIN_NUM, MAX_NUM)
        if n not in nums:
            nums.append(n)
    return sorted(nums[:PICK_COUNT])


# ═══════════════════════════════════════════════════════════════════
#  METHOD IMPLEMENTATIONS (18 categories)
# ═══════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────
# 1. FREQUENCY-BASED (Hot numbers)
# ──────────────────────────────────────────────────────────────
def method_frequency(hist, window=100):
    """Pick the most frequently appearing numbers in recent window."""
    fc = freq_counter(hist, window)
    return top_k(fc, PICK_COUNT)

def method_frequency_w50(hist):
    return method_frequency(hist, 50)

def method_frequency_w100(hist):
    return method_frequency(hist, 100)

def method_frequency_w200(hist):
    return method_frequency(hist, 200)


# ──────────────────────────────────────────────────────────────
# 2. GAP ANALYSIS (Overdue numbers)
# ──────────────────────────────────────────────────────────────
def method_gap(hist, window=200):
    """Numbers with largest gap since last appearance."""
    recent = hist[-window:] if window else hist
    last_seen = {}
    for i, d in enumerate(recent):
        for n in get_numbers(d):
            last_seen[n] = i
    total = len(recent)
    gaps = {}
    for n in TOTAL_NUMBERS:
        if n in last_seen:
            gaps[n] = total - last_seen[n]
        else:
            gaps[n] = total + 10  # never seen → very overdue
    return top_k(gaps, PICK_COUNT)


# ──────────────────────────────────────────────────────────────
# 3. HOT/COLD MIX
# ──────────────────────────────────────────────────────────────
def method_hot_cold(hist, hot_w=30, cold_w=200):
    """3 hot (recent 30) + 2 cold (absent longest in 200)."""
    hot_fc = freq_counter(hist, hot_w)
    hot_nums = sorted(hot_fc, key=hot_fc.get, reverse=True)

    last_seen = {}
    recent = hist[-cold_w:]
    for i, d in enumerate(recent):
        for n in get_numbers(d):
            last_seen[n] = i
    cold_gaps = {n: (len(recent) - last_seen.get(n, -cold_w)) for n in TOTAL_NUMBERS}
    cold_nums = sorted(cold_gaps, key=cold_gaps.get, reverse=True)

    picked = []
    for n in hot_nums:
        if len(picked) >= 3:
            break
        if n not in picked:
            picked.append(n)
    for n in cold_nums:
        if len(picked) >= 5:
            break
        if n not in picked:
            picked.append(n)
    return ensure_valid(picked)


# ──────────────────────────────────────────────────────────────
# 4. MARKOV TRANSITIONS
# ──────────────────────────────────────────────────────────────
def method_markov(hist, order=1, window=300):
    """First-order Markov: P(number | numbers in previous draw)."""
    recent = hist[-window:]
    transition = defaultdict(Counter)
    for i in range(1, len(recent)):
        prev_nums = get_numbers(recent[i - 1])
        curr_nums = get_numbers(recent[i])
        for pn in prev_nums:
            for cn in curr_nums:
                transition[pn][cn] += 1

    last_draw = get_numbers(recent[-1])
    scores = Counter()
    for pn in last_draw:
        for cn, count in transition[pn].items():
            scores[cn] += count
    return top_k(scores, PICK_COUNT) if scores else method_frequency(hist)


# ──────────────────────────────────────────────────────────────
# 5. FOURIER / SPECTRAL ANALYSIS
# ──────────────────────────────────────────────────────────────
def method_fourier(hist, window=500):
    """FFT on each number's appearance time series to detect periodicity."""
    recent = hist[-window:]
    scores = {}
    for n in TOTAL_NUMBERS:
        series = [1 if n in get_numbers(d) else 0 for d in recent]
        if sum(series) < 3:
            scores[n] = 0
            continue
        fft = np.fft.rfft(series)
        power = np.abs(fft) ** 2
        # Skip DC component (index 0)
        if len(power) > 1:
            dominant_freq_idx = np.argmax(power[1:]) + 1
            period = len(series) / dominant_freq_idx if dominant_freq_idx > 0 else len(series)
            # Phase: where in the cycle are we?
            phase = np.angle(fft[dominant_freq_idx])
            # How much power is concentrated in dominant frequency
            spectral_power = power[dominant_freq_idx] / (np.sum(power[1:]) + 1e-10)
            # Predict if number is "due" based on phase
            cycles_elapsed = len(series) / period
            phase_position = (cycles_elapsed * 2 * np.pi + phase) % (2 * np.pi)
            # Score higher when phase suggests next appearance
            due_score = np.cos(phase_position)  # peaks when "due"
            scores[n] = spectral_power * (1 + due_score) * power[dominant_freq_idx]
        else:
            scores[n] = 0
    return top_k(scores, PICK_COUNT)

def method_fourier_w300(hist):
    return method_fourier(hist, 300)

def method_fourier_w500(hist):
    return method_fourier(hist, 500)


# ──────────────────────────────────────────────────────────────
# 6. TAIL DISTRIBUTION (Last Digit)
# ──────────────────────────────────────────────────────────────
def method_tail(hist, window=100):
    """Select numbers ensuring diverse last digits, weighted by freq."""
    fc = freq_counter(hist, window)
    tail_groups = defaultdict(list)
    for n in TOTAL_NUMBERS:
        tail_groups[n % 10].append(n)

    # Sort tails by how common they are
    tail_freq = Counter()
    for n, c in fc.items():
        tail_freq[n % 10] += c

    picked = []
    used_tails = set()
    # First pass: one from each hot tail
    for tail in sorted(tail_freq, key=tail_freq.get, reverse=True):
        if len(picked) >= 5:
            break
        candidates = [(n, fc.get(n, 0)) for n in tail_groups[tail] if n not in picked]
        if candidates:
            best = max(candidates, key=lambda x: x[1])
            picked.append(best[0])
            used_tails.add(tail)

    # Fill remaining
    while len(picked) < 5:
        remaining = [(n, fc.get(n, 0)) for n in TOTAL_NUMBERS if n not in picked]
        if remaining:
            best = max(remaining, key=lambda x: x[1])
            picked.append(best[0])
        else:
            break
    return ensure_valid(picked)


# ──────────────────────────────────────────────────────────────
# 7. CLUSTER / ZONE BALANCE
# ──────────────────────────────────────────────────────────────
def method_zone_balance(hist, window=200):
    """Pick numbers matching most common zone distribution pattern."""
    recent = hist[-window:]
    fc = freq_counter(hist, window)

    def zone(n):
        if n <= 13: return 0
        if n <= 26: return 1
        return 2

    # Find most common zone pattern
    patterns = Counter()
    for d in recent:
        nums = get_numbers(d)
        z = tuple(sorted(Counter(zone(n) for n in nums).values(), reverse=True))
        # More specific: count per zone
        zc = [0, 0, 0]
        for n in nums:
            zc[zone(n)] += 1
        patterns[tuple(zc)] += 1

    top_pattern = patterns.most_common(1)[0][0]

    # Pick best numbers matching this zone pattern
    zones = [[], [], []]
    for n in TOTAL_NUMBERS:
        zones[zone(n)].append(n)

    picked = []
    for z_idx, count in enumerate(top_pattern):
        zone_nums = sorted(zones[z_idx], key=lambda n: fc.get(n, 0), reverse=True)
        picked.extend(zone_nums[:count])

    return ensure_valid(picked)


# ──────────────────────────────────────────────────────────────
# 8. REGIME SWITCHING (Gap-based regime detection)
# ──────────────────────────────────────────────────────────────
def method_regime(hist, window=300):
    """Detect hot/cold regimes for each number and predict transitions."""
    recent = hist[-window:]
    scores = {}

    for n in TOTAL_NUMBERS:
        appearances = [i for i, d in enumerate(recent) if n in get_numbers(d)]
        if len(appearances) < 3:
            scores[n] = 0
            continue

        gaps = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
        avg_gap = np.mean(gaps)
        current_gap = len(recent) - appearances[-1] if appearances else window

        # Regime: short gaps = hot, long gaps = cold
        recent_gaps = gaps[-3:] if len(gaps) >= 3 else gaps
        recent_avg = np.mean(recent_gaps)

        # Transition probability: if in cold regime (large gaps), expect return to hot
        if recent_avg > avg_gap * 1.3:  # cold regime
            scores[n] = current_gap / avg_gap  # higher = more overdue
        elif recent_avg < avg_gap * 0.7:  # hot regime
            scores[n] = 0.5 + (1 - current_gap / avg_gap) * 0.5
        else:  # neutral
            scores[n] = abs(current_gap / avg_gap - 1)

    return top_k(scores, PICK_COUNT)


# ──────────────────────────────────────────────────────────────
# 9. ENTROPY RANKING
# ──────────────────────────────────────────────────────────────
def method_entropy(hist, window=200):
    """Numbers whose appearance pattern has lowest entropy (most predictable)."""
    recent = hist[-window:]
    scores = {}

    for n in TOTAL_NUMBERS:
        series = [1 if n in get_numbers(d) else 0 for d in recent]
        if sum(series) == 0 or sum(series) == len(series):
            scores[n] = 0
            continue

        # Split into chunks of 10 and measure consistency
        chunk_size = 10
        chunks = [series[i:i+chunk_size] for i in range(0, len(series), chunk_size)]
        chunk_rates = [sum(c) / len(c) for c in chunks if len(c) == chunk_size]

        if len(chunk_rates) < 2:
            scores[n] = 0
            continue

        # Lower entropy in chunk rates = more predictable
        p = sum(series) / len(series)
        # Shannon entropy of presence
        if 0 < p < 1:
            h = -p * np.log2(p) - (1-p) * np.log2(1-p)
        else:
            h = 0

        # Variance of chunk rates: lower = more stable
        var = np.var(chunk_rates)
        stability = 1 / (1 + var * 100)

        # Score: predictable + frequent → good pick
        scores[n] = stability * p * 10

    return top_k(scores, PICK_COUNT)


# ──────────────────────────────────────────────────────────────
# 10. ORTHOGONAL FREQUENCY
# ──────────────────────────────────────────────────────────────
def method_orthogonal(hist, window=150):
    """Select numbers that are frequency-orthogonal: diverse in appearance timing."""
    recent = hist[-window:]
    # Build appearance vectors
    vectors = {}
    for n in TOTAL_NUMBERS:
        vectors[n] = np.array([1.0 if n in get_numbers(d) else 0.0 for d in recent])

    fc = freq_counter(hist, window)
    # Start with highest freq number
    if not fc:
        return method_frequency(hist)

    candidates = sorted(fc, key=fc.get, reverse=True)[:15]  # top 15 pool
    selected = [candidates[0]]

    while len(selected) < PICK_COUNT and candidates:
        best_n = None
        best_score = -1
        for n in candidates:
            if n in selected:
                continue
            # Compute max correlation with already selected
            max_corr = 0
            for s in selected:
                corr = np.corrcoef(vectors[n], vectors[s])[0, 1]
                if np.isnan(corr):
                    corr = 0
                max_corr = max(max_corr, abs(corr))
            # Want LOW correlation (orthogonal) + HIGH frequency
            score = fc.get(n, 0) * (1 - max_corr)
            if score > best_score:
                best_score = score
                best_n = n
        if best_n:
            selected.append(best_n)
            candidates.remove(best_n)
        else:
            break

    return ensure_valid(selected)


# ──────────────────────────────────────────────────────────────
# 11. RANDOM BASELINE (Permutation)
# ──────────────────────────────────────────────────────────────
def method_random(hist):
    """Pure random selection — the baseline to beat."""
    return sorted(random.sample(TOTAL_NUMBERS, PICK_COUNT))


# ──────────────────────────────────────────────────────────────
# 12. MONTE CARLO COVERAGE SIMULATION
# ──────────────────────────────────────────────────────────────
def method_monte_carlo(hist, window=300, trials=300):
    """Monte Carlo: simulate many combos, keep one with best coverage score."""
    fc = freq_counter(hist, window)
    recent = hist[-window:]

    # Historical sum stats
    sums = [sum(get_numbers(d)) for d in recent]
    mean_sum = np.mean(sums)
    std_sum = np.std(sums)

    # Historical odd count stats
    odds = [sum(1 for n in get_numbers(d) if n % 2 == 1) for d in recent]
    common_odd = Counter(odds).most_common(3)
    valid_odds = set(c[0] for c in common_odd)

    best_combo = None
    best_score = -1

    for _ in range(trials):
        # Weighted random sampling
        combo = weighted_sample(fc, PICK_COUNT)
        if len(combo) < PICK_COUNT:
            continue

        s = sum(combo)
        odd_count = sum(1 for n in combo if n % 2 == 1)

        score = 0
        # Sum in range
        if mean_sum - std_sum <= s <= mean_sum + std_sum:
            score += 5
        elif mean_sum - 2*std_sum <= s <= mean_sum + 2*std_sum:
            score += 2

        # Odd/even
        if odd_count in valid_odds:
            score += 3

        # Zone coverage
        zones = set()
        for n in combo:
            if n <= 13: zones.add(0)
            elif n <= 26: zones.add(1)
            else: zones.add(2)
        score += len(zones)

        # Tail diversity
        tails = set(n % 10 for n in combo)
        score += len(tails) * 0.5

        # Freq heat
        score += sum(fc.get(n, 0) for n in combo) / 50

        if score > best_score:
            best_score = score
            best_combo = combo

    return ensure_valid(best_combo) if best_combo else method_frequency(hist)


# ──────────────────────────────────────────────────────────────
# 13. BAYESIAN POSTERIOR PROBABILITY
# ──────────────────────────────────────────────────────────────
def method_bayesian(hist, window=200):
    """Bayesian update: prior = uniform, likelihood = recent freq, posterior = updated."""
    recent = hist[-window:]
    # Prior: uniform 1/39
    prior = {n: 1/39 for n in TOTAL_NUMBERS}

    # Likelihood: frequency-based
    fc = freq_counter(hist, window)
    total_appearances = sum(fc.values())
    if total_appearances == 0:
        return method_frequency(hist)

    likelihood = {}
    for n in TOTAL_NUMBERS:
        likelihood[n] = (fc.get(n, 0) + 1) / (total_appearances + 39)  # Laplace smoothing

    # Posterior ∝ prior × likelihood
    posterior = {n: prior[n] * likelihood[n] for n in TOTAL_NUMBERS}
    total_posterior = sum(posterior.values())
    posterior = {n: p / total_posterior for n, p in posterior.items()}

    # Additional decay factor: recency
    decay_scores = {}
    for n in TOTAL_NUMBERS:
        last_idx = None
        for i in range(len(recent) - 1, -1, -1):
            if n in get_numbers(recent[i]):
                last_idx = i
                break
        if last_idx is not None:
            recency = (last_idx + 1) / len(recent)
            decay_scores[n] = posterior[n] * (0.5 + 0.5 * recency)
        else:
            decay_scores[n] = posterior[n] * 0.3

    return top_k(decay_scores, PICK_COUNT)


# ──────────────────────────────────────────────────────────────
# 14. COMBINATORIAL COVERING DESIGN
# ──────────────────────────────────────────────────────────────
def method_covering(hist, window=100):
    """Use covering design principles: maximize 2-element coverage of likely pairs."""
    fc = freq_counter(hist, window)
    recent = hist[-window:]

    # Pair frequency
    pair_freq = Counter()
    for d in recent:
        nums = get_numbers(d)
        for pair in combinations(sorted(nums), 2):
            pair_freq[pair] += 1

    # Greedy: pick numbers that cover the most frequent pairs
    pool = sorted(fc, key=fc.get, reverse=True)[:20]
    selected = []

    for _ in range(PICK_COUNT):
        best_n = None
        best_coverage = -1
        for n in pool:
            if n in selected:
                continue
            # Count pair coverage if we add n
            coverage = 0
            for s in selected:
                pair = tuple(sorted([n, s]))
                coverage += pair_freq.get(pair, 0)
            # Plus individual frequency
            coverage += fc.get(n, 0) * 0.5
            if coverage > best_coverage:
                best_coverage = coverage
                best_n = n
        if best_n:
            selected.append(best_n)
        else:
            # Fill with top freq not selected
            for n in pool:
                if n not in selected:
                    selected.append(n)
                    break

    return ensure_valid(selected)


# ──────────────────────────────────────────────────────────────
# 15. ADAPTIVE WEIGHTED ENSEMBLE
# ──────────────────────────────────────────────────────────────
def method_adaptive_ensemble(hist, lookback=15):
    """Run multiple base methods, weight by recent performance, vote."""
    base_methods = {
        'freq': method_frequency_w100,
        'gap': method_gap,
        'bayesian': method_bayesian,
        'fourier': method_fourier_w300,
        'covering': method_covering,
    }

    # Evaluate each method on last `lookback` draws
    method_scores = Counter()
    for i in range(min(lookback, len(hist) - 50)):
        idx = len(hist) - lookback + i
        if idx < 50:
            continue
        target = get_numbers(hist[idx])
        sub_hist = hist[:idx]
        for name, func in base_methods.items():
            try:
                pred = func(sub_hist)
                matches = len(set(pred) & set(target))
                method_scores[name] += matches
            except:
                pass

    # Normalize to weights
    total = sum(method_scores.values()) + 1e-10
    weights = {name: max(0.1, method_scores[name] / total) for name in base_methods}

    # Weighted vote
    votes = Counter()
    for name, func in base_methods.items():
        try:
            pred = func(hist)
            for n in pred:
                votes[n] += weights[name]
        except:
            pass

    return top_k(votes, PICK_COUNT) if votes else method_frequency(hist)


# ──────────────────────────────────────────────────────────────
# 16. FEATURE INTERACTIONS (Pair Frequency)
# ──────────────────────────────────────────────────────────────
def method_pair_interaction(hist, window=200):
    """Find hot pairs and build bet around them."""
    recent = hist[-window:]
    pair_freq = Counter()
    for d in recent:
        nums = sorted(get_numbers(d))
        for pair in combinations(nums, 2):
            pair_freq[pair] += 1

    # Find hottest pair
    if not pair_freq:
        return method_frequency(hist)

    top_pair = pair_freq.most_common(1)[0][0]
    picked = list(top_pair)

    # Fill remaining with numbers that pair well with selected
    fc = freq_counter(hist, window)
    while len(picked) < PICK_COUNT:
        best_n = None
        best_score = -1
        for n in TOTAL_NUMBERS:
            if n in picked:
                continue
            score = fc.get(n, 0)
            for p in picked:
                pair = tuple(sorted([n, p]))
                score += pair_freq.get(pair, 0) * 2
            if score > best_score:
                best_score = score
                best_n = n
        if best_n:
            picked.append(best_n)
        else:
            break

    return ensure_valid(picked)


# ──────────────────────────────────────────────────────────────
# 17. MULTIPLICATIVE SIGNALS
# ──────────────────────────────────────────────────────────────
def method_multiplicative(hist, window=200):
    """Multiply independent signal scores (freq × recency × gap_due × zone_fit)."""
    recent = hist[-window:]
    fc = freq_counter(hist, window)

    # Signal 1: Frequency (normalized)
    max_freq = max(fc.values()) if fc else 1
    freq_signal = {n: (fc.get(n, 0) + 1) / (max_freq + 1) for n in TOTAL_NUMBERS}

    # Signal 2: Recency
    recency_signal = {}
    for n in TOTAL_NUMBERS:
        last_idx = None
        for i in range(len(recent) - 1, -1, -1):
            if n in get_numbers(recent[i]):
                last_idx = i
                break
        if last_idx is not None:
            recency_signal[n] = (last_idx + 1) / len(recent)
        else:
            recency_signal[n] = 0.1

    # Signal 3: Gap due ratio
    gap_signal = {}
    for n in TOTAL_NUMBERS:
        appearances = [i for i, d in enumerate(recent) if n in get_numbers(d)]
        if len(appearances) >= 2:
            gaps = [appearances[j+1] - appearances[j] for j in range(len(appearances)-1)]
            avg_gap = np.mean(gaps)
            current_gap = len(recent) - appearances[-1]
            ratio = current_gap / avg_gap if avg_gap > 0 else 1
            # Sweet spot: ratio around 1.0-1.5
            gap_signal[n] = max(0, 1 - abs(ratio - 1.2) / 2)
        else:
            gap_signal[n] = 0.3

    # Multiplicative combination
    scores = {}
    for n in TOTAL_NUMBERS:
        scores[n] = freq_signal[n] * recency_signal[n] * gap_signal[n]

    return top_k(scores, PICK_COUNT)


# ──────────────────────────────────────────────────────────────
# 18. STATE-SPACE MODEL (Kalman-like)
# ──────────────────────────────────────────────────────────────
def method_state_space(hist, window=300):
    """Simple Kalman-like filter: track smoothed appearance rate per number."""
    recent = hist[-window:]
    scores = {}

    for n in TOTAL_NUMBERS:
        series = [1.0 if n in get_numbers(d) else 0.0 for d in recent]
        if sum(series) < 2:
            scores[n] = 0
            continue

        # Kalman-like smoothing
        state = series[0]
        process_noise = 0.01
        measurement_noise = 0.5
        estimate_error = 1.0

        for obs in series[1:]:
            # Predict
            predict_error = estimate_error + process_noise
            # Update
            kalman_gain = predict_error / (predict_error + measurement_noise)
            state = state + kalman_gain * (obs - state)
            estimate_error = (1 - kalman_gain) * predict_error

        # State = smoothed probability of appearing
        # Higher state = more likely to appear
        # Also factor in trend (last 30 vs last 100)
        recent_rate = sum(series[-30:]) / 30
        older_rate = sum(series[-100:-30]) / 70 if len(series) > 100 else sum(series) / len(series)
        trend = recent_rate - older_rate

        scores[n] = state * (1 + trend * 2)

    return top_k(scores, PICK_COUNT)


# ──────────────────────────────────────────────────────────────
# ADDITIONAL METHODS FROM EXISTING CODEBASE
# ──────────────────────────────────────────────────────────────

def method_sum_constraint(hist, window=300, trials=500):
    """Pick combo whose sum falls in historical μ±σ range, freq-weighted."""
    recent = hist[-window:]
    fc = freq_counter(hist, min(window, 100))
    sums = [sum(get_numbers(d)) for d in recent]
    mean_s, std_s = np.mean(sums), np.std(sums)
    lo, hi = mean_s - std_s, mean_s + std_s

    best_combo = None
    best_score = -1
    for _ in range(trials):
        combo = weighted_sample(fc, PICK_COUNT)
        if len(combo) < PICK_COUNT:
            continue
        s = sum(combo)
        score = sum(fc.get(n, 0) for n in combo)
        if lo <= s <= hi:
            score += 50
        elif lo - std_s <= s <= hi + std_s:
            score += 10
        if score > best_score:
            best_score = score
            best_combo = combo

    return ensure_valid(best_combo) if best_combo else method_frequency(hist)


def method_ac_value(hist, window=200, trials=1500):
    """AC-value optimized: select combos with historically common AC values."""
    recent = hist[-window:]

    # Compute historical AC values
    ac_hist = []
    for d in recent:
        nums = sorted(get_numbers(d))
        diffs = set()
        for a, b in combinations(nums, 2):
            diffs.add(b - a)
        ac_hist.append(len(diffs))

    common_ac = Counter(ac_hist).most_common(5)
    valid_ac = set(c[0] for c in common_ac)
    median_ac = np.median(ac_hist)

    fc = freq_counter(hist, min(window, 100))
    best_combo = None
    best_score = -1

    for _ in range(trials):
        combo = weighted_sample(fc, PICK_COUNT)
        if len(combo) < PICK_COUNT:
            continue

        diffs = set()
        for a, b in combinations(sorted(combo), 2):
            diffs.add(b - a)
        ac = len(diffs)

        score = sum(fc.get(n, 0) for n in combo) / 10
        if ac in valid_ac:
            score += 5
        if abs(ac - median_ac) <= 1:
            score += 3

        # Zone coverage bonus
        zones = set()
        for n in combo:
            if n <= 13: zones.add(0)
            elif n <= 26: zones.add(1)
            else: zones.add(2)
        if len(zones) >= 3:
            score += 2

        if score > best_score:
            best_score = score
            best_combo = combo

    return ensure_valid(best_combo) if best_combo else method_frequency(hist)


def method_pattern_match(hist, window=200, pattern_len=5):
    """Match recent pattern (last 5 draws signature) against history; vote from similar next draws."""
    recent = hist[-window:]
    if len(recent) < pattern_len + 1:
        return method_frequency(hist)

    def signature(draws_slice):
        """Feature signature: sum, odd_count, zone_dist tuple."""
        features = []
        for d in draws_slice:
            nums = get_numbers(d)
            features.append((
                sum(nums),
                sum(1 for n in nums if n % 2 == 1),
                sum(1 for n in nums if n <= 13),
                sum(1 for n in nums if 14 <= n <= 26),
                sum(1 for n in nums if n >= 27),
            ))
        return features

    current_sig = signature(recent[-pattern_len:])

    # Compare against all windows in history
    votes = Counter()
    for i in range(pattern_len, len(recent) - 1):
        window_sig = signature(recent[i - pattern_len:i])
        # Similarity: sum of feature matches
        sim = 0
        for cs, ws in zip(current_sig, window_sig):
            for cf, wf in zip(cs, ws):
                if abs(cf - wf) <= 2:
                    sim += 1
        if sim >= len(current_sig) * 3:  # threshold
            next_nums = get_numbers(recent[i])
            for n in next_nums:
                votes[n] += sim

    if votes:
        fc = freq_counter(hist, window)
        final_scores = {n: votes.get(n, 0) * 2 + fc.get(n, 0) for n in TOTAL_NUMBERS}
        return top_k(final_scores, PICK_COUNT)
    return method_frequency(hist)


def method_cycle_regression(hist, window=200):
    """Overdue ratio sweet spot: 1.0-2.5× avg gap = due for appearance."""
    recent = hist[-window:]
    scores = {}

    for n in TOTAL_NUMBERS:
        appearances = [i for i, d in enumerate(recent) if n in get_numbers(d)]
        if len(appearances) < 3:
            scores[n] = 0
            continue

        gaps = [appearances[j+1] - appearances[j] for j in range(len(appearances)-1)]
        avg_gap = np.mean(gaps)
        current_gap = len(recent) - appearances[-1]
        ratio = current_gap / avg_gap if avg_gap > 0 else 0

        if 1.0 <= ratio <= 2.5:
            scores[n] = ratio
        elif 0.7 <= ratio < 1.0:
            scores[n] = ratio * 0.5
        else:
            scores[n] = max(0, 0.2 - abs(ratio - 1.5) * 0.1)

    return top_k(scores, PICK_COUNT) if any(v > 0 for v in scores.values()) else method_frequency(hist)


def method_cold_rebound(hist, window=200):
    """Pure cold numbers: those absent longest, betting on regression to mean."""
    recent = hist[-window:]
    last_seen = {}
    for i, d in enumerate(recent):
        for n in get_numbers(d):
            last_seen[n] = i

    cold_scores = {}
    for n in TOTAL_NUMBERS:
        if n not in last_seen:
            cold_scores[n] = window + 50
        else:
            cold_scores[n] = len(recent) - last_seen[n]

    return top_k(cold_scores, PICK_COUNT)


def method_consecutive_inject(hist, window=100):
    """Inject a hot consecutive pair into freq-based selection."""
    recent = hist[-window:]
    fc = freq_counter(hist, window)

    # Find consecutive pairs in history
    consec_freq = Counter()
    for d in recent:
        nums = sorted(get_numbers(d))
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                consec_freq[(nums[i], nums[i+1])] += 1

    base = top_k(fc, 7)  # get top 7

    if consec_freq:
        hot_pair = consec_freq.most_common(1)[0][0]
        # Check if pair already partially in base
        result = list(base[:3])
        for n in hot_pair:
            if n not in result:
                result.append(n)
        # Fill to 5
        for n in base:
            if n not in result and len(result) < 5:
                result.append(n)
        return ensure_valid(result)

    return ensure_valid(base[:5])


# ──────────────────────────────────────────────────────────────
# ADVANCED: Weighted position model (digit position analysis)
# ──────────────────────────────────────────────────────────────
def method_position_bias(hist, window=200):
    """Analyze which numbers appear at which sorted position (1st smallest, 2nd, etc.)."""
    recent = hist[-window:]
    position_freq = [Counter() for _ in range(PICK_COUNT)]

    for d in recent:
        nums = sorted(get_numbers(d))
        for pos, n in enumerate(nums):
            position_freq[pos][n] += 1

    # Pick best number for each position
    picked = []
    used = set()
    for pos in range(PICK_COUNT):
        for n, _ in position_freq[pos].most_common():
            if n not in used:
                picked.append(n)
                used.add(n)
                break

    return ensure_valid(picked)


def method_lag_echo(hist, lag=2):
    """Echo: numbers from N-lag draws get boosted."""
    if len(hist) < lag + 1:
        return method_frequency(hist)

    fc = freq_counter(hist, 100)
    echo_nums = get_numbers(hist[-lag])
    echo_boost = {n: fc.get(n, 0) + 5 for n in echo_nums}

    scores = {n: fc.get(n, 0) for n in TOTAL_NUMBERS}
    for n in echo_nums:
        scores[n] = echo_boost[n]

    return top_k(scores, PICK_COUNT)


# ═══════════════════════════════════════════════════════════════════
#  METHOD REGISTRY
# ═══════════════════════════════════════════════════════════════════
ALL_METHODS = {
    # Category: Frequency-based
    'freq_w50':         method_frequency_w50,
    'freq_w100':        method_frequency_w100,
    'freq_w200':        method_frequency_w200,
    # Category: Gap analysis
    'gap':              method_gap,
    'cold_rebound':     method_cold_rebound,
    # Category: Hot/Cold
    'hot_cold':         method_hot_cold,
    # Category: Markov transitions
    'markov':           method_markov,
    # Category: Fourier/spectral
    'fourier_w300':     method_fourier_w300,
    'fourier_w500':     method_fourier_w500,
    # Category: Tail distribution
    'tail':             method_tail,
    # Category: Cluster/Zone
    'zone_balance':     method_zone_balance,
    # Category: Regime switching
    'regime':           method_regime,
    # Category: Entropy ranking
    'entropy':          method_entropy,
    # Category: Orthogonal frequency
    'orthogonal':       method_orthogonal,
    # Category: Monte Carlo
    'monte_carlo':      method_monte_carlo,
    # Category: Bayesian posterior
    'bayesian':         method_bayesian,
    # Category: Combinatorial covering
    'covering':         method_covering,
    # Category: Adaptive ensemble
    'adaptive_ensemble': method_adaptive_ensemble,
    # Category: Feature interactions
    'pair_interaction': method_pair_interaction,
    # Category: Multiplicative
    'multiplicative':   method_multiplicative,
    # Category: State-space
    'state_space':      method_state_space,
    # Category: Sum constraint
    'sum_constraint':   method_sum_constraint,
    # Category: AC value
    'ac_value':         method_ac_value,
    # Category: Pattern matching
    'pattern_match':    method_pattern_match,
    # Category: Cycle regression
    'cycle_regression': method_cycle_regression,
    # Category: Consecutive
    'consecutive':      method_consecutive_inject,
    # Category: Position
    'position_bias':    method_position_bias,
    # Category: Lag echo
    'lag_echo':         method_lag_echo,
    # Baseline: Random
    'random':           method_random,
}

METHOD_CATEGORIES = {
    'freq_w50': 'Frequency', 'freq_w100': 'Frequency', 'freq_w200': 'Frequency',
    'gap': 'Gap Analysis', 'cold_rebound': 'Gap Analysis',
    'hot_cold': 'Hot/Cold',
    'markov': 'Markov Transition',
    'fourier_w300': 'Fourier/Spectral', 'fourier_w500': 'Fourier/Spectral',
    'tail': 'Tail Distribution',
    'zone_balance': 'Cluster/Zone',
    'regime': 'Regime Switching',
    'entropy': 'Entropy Ranking',
    'orthogonal': 'Orthogonal Frequency',
    'monte_carlo': 'Monte Carlo',
    'bayesian': 'Bayesian Posterior',
    'covering': 'Covering Design',
    'adaptive_ensemble': 'Adaptive Ensemble',
    'pair_interaction': 'Feature Interaction',
    'multiplicative': 'Multiplicative Signal',
    'state_space': 'State-Space Model',
    'sum_constraint': 'Sum Constraint',
    'ac_value': 'AC Value',
    'pattern_match': 'Pattern Match',
    'cycle_regression': 'Cycle Regression',
    'consecutive': 'Consecutive Inject',
    'position_bias': 'Position Bias',
    'lag_echo': 'Lag Echo',
    'random': 'Random Baseline',
}


# ═══════════════════════════════════════════════════════════════════
#  BACKTEST ENGINE (Leakage-Free Walk-Forward)
# ═══════════════════════════════════════════════════════════════════
def backtest_single(predict_func, all_draws, test_periods=1500, seed=42, verbose=False):
    """
    Walk-forward backtest for a single-bet method.
    Returns detailed per-draw results.
    """
    random.seed(seed)
    np.random.seed(seed)

    results = []
    min_train = 100  # minimum training periods

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < min_train:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(get_numbers(target))

        try:
            pred = predict_func(hist)
            pred_set = set(pred)
            matches = len(pred_set & actual)
            results.append({
                'idx': target_idx,
                'draw': target.get('draw', ''),
                'matches': matches,
                'ge2': matches >= 2,
                'ge3': matches >= 3,
            })
        except Exception as e:
            if verbose:
                print(f"  [WARN] idx={target_idx}: {e}")
            continue

    total = len(results)
    if total == 0:
        return {'total': 0, 'ge2_hits': 0, 'ge3_hits': 0, 'ge2_rate': 0, 'ge3_rate': 0,
                'ge2_edge': 0, 'ge3_edge': 0, 'results': []}

    ge2_hits = sum(1 for r in results if r['ge2'])
    ge3_hits = sum(1 for r in results if r['ge3'])
    ge2_rate = ge2_hits / total
    ge3_rate = ge3_hits / total

    return {
        'total': total,
        'ge2_hits': ge2_hits,
        'ge3_hits': ge3_hits,
        'ge2_rate': ge2_rate,
        'ge3_rate': ge3_rate,
        'ge2_edge': ge2_rate - BASELINES['ge2'][1],
        'ge3_edge': ge3_rate - BASELINES['ge3'][1],
        'avg_matches': np.mean([r['matches'] for r in results]),
        'max_matches': max(r['matches'] for r in results),
        'results': results,
    }


def backtest_multi(predict_funcs, all_draws, test_periods=1500, seed=42):
    """
    Walk-forward backtest for multi-bet (N tickets).
    predict_funcs: list of functions, each returns 5 numbers.
    """
    random.seed(seed)
    np.random.seed(seed)

    n_bets = len(predict_funcs)
    results = []
    min_train = 100

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < min_train:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(get_numbers(target))

        any_ge2 = False
        any_ge3 = False
        bet_matches = []

        for func in predict_funcs:
            try:
                pred = func(hist)
                matches = len(set(pred) & actual)
                bet_matches.append(matches)
                if matches >= 2:
                    any_ge2 = True
                if matches >= 3:
                    any_ge3 = True
            except:
                bet_matches.append(0)

        results.append({
            'idx': target_idx,
            'ge2': any_ge2,
            'ge3': any_ge3,
            'bet_matches': bet_matches,
        })

    total = len(results)
    if total == 0:
        return {'total': 0, 'ge2_rate': 0, 'ge3_rate': 0, 'ge2_edge': 0, 'ge3_edge': 0}

    ge2_hits = sum(1 for r in results if r['ge2'])
    ge3_hits = sum(1 for r in results if r['ge3'])

    return {
        'total': total,
        'n_bets': n_bets,
        'ge2_hits': ge2_hits,
        'ge3_hits': ge3_hits,
        'ge2_rate': ge2_hits / total,
        'ge3_rate': ge3_hits / total,
        'ge2_edge': ge2_hits / total - BASELINES['ge2'][n_bets],
        'ge3_edge': ge3_hits / total - BASELINES['ge3'][n_bets],
        'results': results,
    }


# ═══════════════════════════════════════════════════════════════════
#  VALIDATION FRAMEWORK
# ═══════════════════════════════════════════════════════════════════
def three_window_test(predict_func, all_draws, seed=42):
    """Three-window stability: 150 / 500 / 1500 draws."""
    results = {}
    for period in [150, 500, 1500]:
        if len(all_draws) < period + 100:
            continue
        r = backtest_single(predict_func, all_draws, period, seed)
        results[period] = r

    edges = {p: r['ge2_edge'] for p, r in results.items()}

    # Classify stability
    if all(e > 0 for e in edges.values()):
        stability = 'STABLE'
    elif edges.get(1500, 0) > 0 and edges.get(150, 0) <= 0:
        stability = 'LATE_BLOOMER'
    elif edges.get(1500, 0) <= 0 and edges.get(150, 0) > 0:
        stability = 'SHORT_MOMENTUM'
    elif all(e <= 0 for e in edges.values()):
        stability = 'INEFFECTIVE'
    else:
        stability = 'MIXED'

    return {
        'windows': results,
        'edges': edges,
        'stability': stability,
    }


def permutation_test(predict_func, all_draws, test_periods=500, n_perms=50, seed=42):
    """
    Permutation test: compare strategy's hit rate against shuffled baselines.
    Returns p-value.
    """
    # Actual performance
    actual_result = backtest_single(predict_func, all_draws, test_periods, seed)
    actual_ge2 = actual_result['ge2_rate']

    # Permuted baselines
    perm_rates = []
    for perm_seed in range(n_perms):
        rng = random.Random(perm_seed + 10000)
        np_rng = np.random.RandomState(perm_seed + 10000)

        def random_predict(hist):
            return sorted(rng.sample(TOTAL_NUMBERS, PICK_COUNT))

        r = backtest_single(random_predict, all_draws, test_periods, perm_seed + 10000)
        perm_rates.append(r['ge2_rate'])

    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates) if np.std(perm_rates) > 0 else 1e-10
    z_score = (actual_ge2 - perm_mean) / perm_std
    # One-sided p-value
    p_value = 1 - scipy_stats.norm.cdf(z_score)

    return {
        'actual_rate': actual_ge2,
        'perm_mean': perm_mean,
        'perm_std': perm_std,
        'z_score': z_score,
        'p_value': p_value,
        'significant': p_value < 0.05,
    }


def z_test_vs_baseline(hits, total, baseline_rate):
    """Z-test: method vs theoretical baseline."""
    p_hat = hits / total
    p0 = baseline_rate
    se = math.sqrt(p0 * (1 - p0) / total)
    z = (p_hat - p0) / se if se > 0 else 0
    p_value = 1 - scipy_stats.norm.cdf(z)
    return {'z': z, 'p_value': p_value, 'significant': p_value < 0.05}


def compute_full_metrics(name, method_func, all_draws, seed=42):
    """Compute all scoring metrics for a method."""
    print(f"  Testing: {name}...", end='', flush=True)
    t0 = time.time()

    # Three-window test
    tw = three_window_test(method_func, all_draws, seed)

    # Primary result (1500 periods)
    primary = tw['windows'].get(1500, tw['windows'].get(500, tw['windows'].get(150, {})))
    if not primary or primary['total'] == 0:
        print(f" SKIP (no data)")
        return None

    # Z-test
    zt_ge2 = z_test_vs_baseline(primary['ge2_hits'], primary['total'], BASELINES['ge2'][1])
    zt_ge3 = z_test_vs_baseline(primary['ge3_hits'], primary['total'], BASELINES['ge3'][1])

    # Consistency: coefficient of variation across windows
    edges = list(tw['edges'].values())
    if len(edges) >= 2 and np.mean(edges) != 0:
        consistency = 1 - min(1, np.std(edges) / (abs(np.mean(edges)) + 1e-10))
    else:
        consistency = 0

    # Stability score: 1 if all windows positive, 0 otherwise + consistency
    n_positive = sum(1 for e in edges if e > 0)
    stability_score = n_positive / len(edges) if edges else 0

    # Coverage efficiency: unique numbers covered per draw (for multi-bet eval)
    # For single bet: 5 numbers cover 5/39 = 12.8% of pool
    coverage_eff = PICK_COUNT / MAX_NUM

    # Complexity (1 for all single-method, varies for ensembles)
    complexity = 1.0
    if 'ensemble' in name or 'adaptive' in name:
        complexity = 3.0
    elif 'monte_carlo' in name or 'ac_value' in name:
        complexity = 2.0

    # Edge
    edge = primary['ge2_edge']
    significance = -math.log10(max(zt_ge2['p_value'], 1e-20))

    # Final rank score
    rank_score = (edge * stability_score * significance) / complexity if edge > 0 else edge

    elapsed = time.time() - t0
    print(f" done ({elapsed:.1f}s) | ge2={primary['ge2_rate']*100:.2f}% edge={edge*100:+.2f}%")

    return {
        'name': name,
        'category': METHOD_CATEGORIES.get(name, 'Other'),
        'ge2_rate': primary['ge2_rate'],
        'ge3_rate': primary['ge3_rate'],
        'ge2_edge': primary['ge2_edge'],
        'ge3_edge': primary['ge3_edge'],
        'ge2_edge_pct': primary['ge2_edge'] * 100,
        'ge3_edge_pct': primary['ge3_edge'] * 100,
        'avg_matches': primary.get('avg_matches', 0),
        'max_matches': primary.get('max_matches', 0),
        'total': primary['total'],
        'z_score_ge2': zt_ge2['z'],
        'p_value_ge2': zt_ge2['p_value'],
        'significant_ge2': zt_ge2['significant'],
        'z_score_ge3': zt_ge3['z'],
        'p_value_ge3': zt_ge3['p_value'],
        'three_window': tw,
        'stability': tw['stability'],
        'stability_score': stability_score,
        'consistency': consistency,
        'coverage_efficiency': coverage_eff,
        'complexity': complexity,
        'rank_score': rank_score,
        'elapsed': elapsed,
    }


# ═══════════════════════════════════════════════════════════════════
#  MULTI-TICKET COMBINATION SEARCH
# ═══════════════════════════════════════════════════════════════════
def find_best_multi_ticket(method_results, all_draws, n_tickets=2, top_n=10, test_periods=500, seed=42):
    """
    Find optimal N-ticket combination from top single methods.
    Evaluates diversity + coverage.
    """
    # Sort by ge2_edge
    ranked = sorted(
        [r for r in method_results if r is not None and r['ge2_edge'] > 0],
        key=lambda x: x['rank_score'],
        reverse=True
    )[:top_n]

    if len(ranked) < n_tickets:
        ranked = sorted(
            [r for r in method_results if r is not None],
            key=lambda x: x['ge2_edge'],
            reverse=True
        )[:top_n]

    print(f"\n[MULTI-TICKET] Searching best {n_tickets}-ticket combo from top {len(ranked)} methods...")
    method_names = [r['name'] for r in ranked]

    best_combo = None
    best_edge = -999
    combo_results = []

    for combo in combinations(method_names, n_tickets):
        funcs = [ALL_METHODS[name] for name in combo]
        r = backtest_multi(funcs, all_draws, test_periods, seed)

        combo_results.append({
            'methods': combo,
            'ge2_rate': r['ge2_rate'],
            'ge3_rate': r['ge3_rate'],
            'ge2_edge': r['ge2_edge'],
            'ge3_edge': r['ge3_edge'],
            'total': r['total'],
        })

        if r['ge2_edge'] > best_edge:
            best_edge = r['ge2_edge']
            best_combo = combo

        print(f"  {'+'.join(combo)}: ge2={r['ge2_rate']*100:.2f}% edge={r['ge2_edge']*100:+.2f}%")

    # Sort combos
    combo_results.sort(key=lambda x: x['ge2_edge'], reverse=True)

    return {
        'best_combo': best_combo,
        'best_edge': best_edge,
        'all_combos': combo_results,
    }


def validate_multi_ticket(combo_names, all_draws, n_tickets, seed=42):
    """Full validation of a multi-ticket strategy."""
    funcs = [ALL_METHODS[name] for name in combo_names]

    # Three-window
    tw_results = {}
    for period in [150, 500, 1500]:
        if len(all_draws) < period + 100:
            continue
        r = backtest_multi(funcs, all_draws, period, seed)
        tw_results[period] = r

    # Permutation test for multi-ticket
    actual = backtest_multi(funcs, all_draws, 500, seed)
    perm_rates = []
    for ps in range(50):
        def _make_rand_func(seed_val):
            def rand_pred(hist):
                rng = random.Random(seed_val)
                return sorted(rng.sample(TOTAL_NUMBERS, PICK_COUNT))
            return rand_pred
        rand_funcs = [_make_rand_func(ps * 100 + j + 20000) for j in range(n_tickets)]
        r = backtest_multi(rand_funcs, all_draws, 500, ps + 20000)
        perm_rates.append(r['ge2_rate'])

    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates) if np.std(perm_rates) > 0 else 1e-10
    z = (actual['ge2_rate'] - perm_mean) / perm_std
    p = 1 - scipy_stats.norm.cdf(z)

    # Z-test vs theoretical
    zt = z_test_vs_baseline(actual['ge2_hits'], actual['total'], BASELINES['ge2'][n_tickets])

    edges = {p_key: r['ge2_edge'] for p_key, r in tw_results.items()}
    if all(e > 0 for e in edges.values()):
        stability = 'STABLE'
    elif edges.get(1500, 0) <= 0:
        stability = 'SHORT_MOMENTUM' if any(e > 0 for e in edges.values()) else 'INEFFECTIVE'
    else:
        stability = 'MIXED'

    return {
        'methods': combo_names,
        'n_tickets': n_tickets,
        'three_window': tw_results,
        'edges': edges,
        'stability': stability,
        'permutation': {
            'actual_rate': actual['ge2_rate'],
            'perm_mean': perm_mean,
            'perm_std': perm_std,
            'z_score': z,
            'p_value': p,
            'significant': p < 0.05,
        },
        'z_test': zt,
    }


# ═══════════════════════════════════════════════════════════════════
#  RANDOMNESS TEST
# ═══════════════════════════════════════════════════════════════════
def test_randomness(all_draws, window=1000):
    """Test whether 539 draws exhibit detectable non-randomness."""
    recent = all_draws[-window:]
    print(f"\n{'='*60}")
    print(f"  RANDOMNESS ANALYSIS ({window} draws)")
    print(f"{'='*60}")

    # 1. Chi-squared test for uniform frequency
    fc = Counter()
    for d in recent:
        for n in get_numbers(d):
            fc[n] += 1
    expected = len(recent) * PICK_COUNT / MAX_NUM
    chi2 = sum((fc.get(n, 0) - expected) ** 2 / expected for n in TOTAL_NUMBERS)
    chi2_p = 1 - scipy_stats.chi2.cdf(chi2, MAX_NUM - 1)
    print(f"\n1. Chi-squared (uniform freq): χ²={chi2:.2f}, p={chi2_p:.4f} {'*SIGNAL*' if chi2_p < 0.05 else '(random)'}")

    # 2. Serial correlation test (autocorrelation of number appearances)
    serial_results = {}
    significant_serial = 0
    for n in TOTAL_NUMBERS:
        series = [1 if n in get_numbers(d) else 0 for d in recent]
        if sum(series) < 5:
            continue
        mean_s = np.mean(series)
        centered = np.array(series) - mean_s
        var = np.var(series)
        if var == 0:
            continue
        autocorr_1 = np.correlate(centered[:-1], centered[1:])[0] / (var * (len(series) - 1))
        # Approximate z-test for autocorrelation
        se = 1 / math.sqrt(len(series))
        z = autocorr_1 / se
        if abs(z) > 1.96:
            significant_serial += 1
        serial_results[n] = {'autocorr': autocorr_1, 'z': z}

    expected_significant = MAX_NUM * 0.05  # false positive rate
    print(f"2. Serial correlation: {significant_serial}/{MAX_NUM} numbers significant (expected {expected_significant:.1f} by chance)")

    # 3. Runs test (too many/few streaks)
    runs_significant = 0
    for n in TOTAL_NUMBERS:
        series = [1 if n in get_numbers(d) else 0 for d in recent]
        n1 = sum(series)
        n0 = len(series) - n1
        if n1 < 5 or n0 < 5:
            continue
        # Count runs
        runs = 1
        for i in range(1, len(series)):
            if series[i] != series[i-1]:
                runs += 1
        expected_runs = 1 + 2 * n0 * n1 / (n0 + n1)
        var_runs = 2 * n0 * n1 * (2 * n0 * n1 - n0 - n1) / ((n0 + n1) ** 2 * (n0 + n1 - 1))
        if var_runs > 0:
            z_runs = (runs - expected_runs) / math.sqrt(var_runs)
            if abs(z_runs) > 1.96:
                runs_significant += 1

    print(f"3. Runs test: {runs_significant}/{MAX_NUM} numbers significant (expected {expected_significant:.1f} by chance)")

    # 4. Pair co-occurrence vs independent
    pair_fc = Counter()
    pair_total = 0
    for d in recent:
        nums = sorted(get_numbers(d))
        for pair in combinations(nums, 2):
            pair_fc[pair] += 1
        pair_total += 1

    # Expected pair frequency under independence
    marginals = {n: fc.get(n, 0) / (len(recent) * PICK_COUNT) for n in TOTAL_NUMBERS}
    chi2_pair = 0
    n_pairs = 0
    sig_pairs = 0
    for (a, b), obs in pair_fc.items():
        exp = marginals[a] * marginals[b] * pair_total * PICK_COUNT * (PICK_COUNT - 1)
        if exp > 0:
            chi2_pair += (obs - exp) ** 2 / exp
            n_pairs += 1
            # Individual test
            z_pair = (obs - exp) / math.sqrt(exp) if exp > 0 else 0
            if abs(z_pair) > 3.0:  # Bonferroni-approximate
                sig_pairs += 1

    print(f"4. Pair co-occurrence: {sig_pairs} significant pairs out of {n_pairs} tested")

    # Summary
    signals = []
    if chi2_p < 0.05:
        signals.append('frequency_bias')
    if significant_serial > expected_significant * 2:
        signals.append('serial_correlation')
    if runs_significant > expected_significant * 2:
        signals.append('runs_pattern')
    if sig_pairs > n_pairs * 0.01:
        signals.append('pair_dependence')

    verdict = 'NON-RANDOM (signals detected)' if signals else 'CONSISTENT WITH RANDOM'
    print(f"\n  VERDICT: {verdict}")
    if signals:
        print(f"  Signals: {', '.join(signals)}")

    return {
        'chi2': chi2, 'chi2_p': chi2_p,
        'serial_significant': significant_serial,
        'runs_significant': runs_significant,
        'pair_significant': sig_pairs,
        'signals': signals,
        'verdict': verdict,
    }


# ═══════════════════════════════════════════════════════════════════
#  REPORT GENERATION
# ═══════════════════════════════════════════════════════════════════
def generate_report(all_results, best_2ticket, best_3ticket, randomness, best_2_validation, best_3_validation, elapsed_total):
    """Generate comprehensive research report."""

    # Sort by rank_score
    ranked = sorted(
        [r for r in all_results if r is not None],
        key=lambda x: x['rank_score'],
        reverse=True
    )

    report = []
    report.append("=" * 80)
    report.append("  今彩539 COMPREHENSIVE QUANTITATIVE RESEARCH REPORT")
    report.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"  Total computation time: {elapsed_total:.0f} seconds")
    report.append("=" * 80)

    # ── Section 1: Strategy Ranking Table ──
    report.append("\n" + "=" * 80)
    report.append("  SECTION 1: STRATEGY RANKING TABLE")
    report.append("=" * 80)
    report.append(f"\n{'Rank':<5} {'Method':<25} {'Category':<22} {'ge2%':>7} {'Edge%':>8} {'ge3%':>7} {'z':>6} {'p':>8} {'Stab':>12} {'Score':>8}")
    report.append("-" * 115)

    for i, r in enumerate(ranked):
        sig_marker = '*' if r.get('significant_ge2') else ' '
        report.append(
            f"{i+1:<5} {r['name']:<25} {r['category']:<22} "
            f"{r['ge2_rate']*100:>6.2f}% {r['ge2_edge_pct']:>+7.2f}% "
            f"{r['ge3_rate']*100:>6.2f}% {r['z_score_ge2']:>5.2f} {r['p_value_ge2']:>8.4f}{sig_marker} "
            f"{r['stability']:>12} {r['rank_score']:>8.4f}"
        )

    # Baselines
    report.append(f"\n  Theoretical Baselines (1 bet):")
    report.append(f"    match≥2: {BASELINES['ge2'][1]*100:.2f}%")
    report.append(f"    match≥3: {BASELINES['ge3'][1]*100:.2f}%")

    # ── Section 2: Best 2-Ticket Strategy ──
    report.append("\n" + "=" * 80)
    report.append("  SECTION 2: BEST 2-TICKET STRATEGY")
    report.append("=" * 80)

    if best_2ticket and best_2ticket.get('all_combos'):
        top5 = best_2ticket['all_combos'][:5]
        report.append(f"\n  Top 5 two-ticket combinations:")
        report.append(f"  {'Rank':<5} {'Methods':<55} {'ge2%':>7} {'Edge%':>8} {'ge3%':>7}")
        report.append("  " + "-" * 90)
        for i, c in enumerate(top5):
            report.append(
                f"  {i+1:<5} {'+'.join(c['methods']):<55} "
                f"{c['ge2_rate']*100:>6.2f}% {c['ge2_edge']*100:>+7.2f}% "
                f"{c['ge3_rate']*100:>6.2f}%"
            )

        # Best combo details
        best = top5[0]
        report.append(f"\n  ★ BEST 2-TICKET: {' + '.join(best['methods'])}")
        report.append(f"    Hit rate (match≥2): {best['ge2_rate']*100:.2f}%")
        report.append(f"    Edge vs random:     {best['ge2_edge']*100:+.2f}%")
        report.append(f"    Hit rate (match≥3): {best['ge3_rate']*100:.2f}%")
        report.append(f"    Baseline (2 bets):  {BASELINES['ge2'][2]*100:.2f}%")

        if best_2_validation:
            v = best_2_validation
            report.append(f"\n  Validation:")
            report.append(f"    Stability: {v['stability']}")
            for p, r_val in v.get('three_window', {}).items():
                report.append(f"    {p}-draw: ge2={r_val['ge2_rate']*100:.2f}% edge={r_val['ge2_edge']*100:+.2f}%")
            perm = v.get('permutation', {})
            report.append(f"    Permutation test: z={perm.get('z_score', 0):.2f}, p={perm.get('p_value', 1):.4f} {'✓ SIGNIFICANT' if perm.get('significant') else '✗ NOT SIGNIFICANT'}")

    # ── Section 3: Best 3-Ticket Strategy ──
    report.append("\n" + "=" * 80)
    report.append("  SECTION 3: BEST 3-TICKET STRATEGY")
    report.append("=" * 80)

    if best_3ticket and best_3ticket.get('all_combos'):
        top5 = best_3ticket['all_combos'][:5]
        report.append(f"\n  Top 5 three-ticket combinations:")
        report.append(f"  {'Rank':<5} {'Methods':<70} {'ge2%':>7} {'Edge%':>8}")
        report.append("  " + "-" * 95)
        for i, c in enumerate(top5):
            report.append(
                f"  {i+1:<5} {'+'.join(c['methods']):<70} "
                f"{c['ge2_rate']*100:>6.2f}% {c['ge2_edge']*100:>+7.2f}%"
            )

        best = top5[0]
        report.append(f"\n  ★ BEST 3-TICKET: {' + '.join(best['methods'])}")
        report.append(f"    Hit rate (match≥2): {best['ge2_rate']*100:.2f}%")
        report.append(f"    Edge vs random:     {best['ge2_edge']*100:+.2f}%")
        report.append(f"    Baseline (3 bets):  {BASELINES['ge2'][3]*100:.2f}%")

        if best_3_validation:
            v = best_3_validation
            report.append(f"\n  Validation:")
            report.append(f"    Stability: {v['stability']}")
            for p, r_val in v.get('three_window', {}).items():
                report.append(f"    {p}-draw: ge2={r_val['ge2_rate']*100:.2f}% edge={r_val['ge2_edge']*100:+.2f}%")
            perm = v.get('permutation', {})
            report.append(f"    Permutation test: z={perm.get('z_score', 0):.2f}, p={perm.get('p_value', 1):.4f} {'✓ SIGNIFICANT' if perm.get('significant') else '✗ NOT SIGNIFICANT'}")

    # ── Section 4: Statistical Validity ──
    report.append("\n" + "=" * 80)
    report.append("  SECTION 4: STATISTICAL VALIDITY")
    report.append("=" * 80)

    sig_methods = [r for r in ranked if r.get('significant_ge2') and r['ge2_edge'] > 0]
    report.append(f"\n  Methods with statistically significant positive Edge (p<0.05):")
    if sig_methods:
        for r in sig_methods:
            report.append(f"    {r['name']}: edge={r['ge2_edge_pct']:+.2f}%, z={r['z_score_ge2']:.2f}, p={r['p_value_ge2']:.4f}")
    else:
        report.append(f"    None achieved p<0.05 significance individually.")
        report.append(f"    Note: with ~1500 trials, detecting ~1% edge requires z>1.96")
        report.append(f"    Minimum detectable edge: ~{1.96 * math.sqrt(BASELINES['ge2'][1] * (1-BASELINES['ge2'][1]) / 1500) * 100:.2f}%")

    # Bonferroni correction
    n_tests = len(ranked)
    bonferroni_threshold = 0.05 / n_tests
    bonf_sig = [r for r in ranked if r['p_value_ge2'] < bonferroni_threshold and r['ge2_edge'] > 0]
    report.append(f"\n  After Bonferroni correction (p<{bonferroni_threshold:.4f}, {n_tests} tests):")
    if bonf_sig:
        for r in bonf_sig:
            report.append(f"    {r['name']}: p={r['p_value_ge2']:.6f}")
    else:
        report.append(f"    None survive Bonferroni correction.")

    # ── Section 5: Stability Analysis ──
    report.append("\n" + "=" * 80)
    report.append("  SECTION 5: STABILITY ANALYSIS")
    report.append("=" * 80)

    stability_groups = defaultdict(list)
    for r in ranked:
        stability_groups[r['stability']].append(r['name'])

    for stab, methods in stability_groups.items():
        report.append(f"\n  {stab}: {len(methods)} methods")
        for m in methods:
            r = next(x for x in ranked if x['name'] == m)
            edges = r['three_window']['edges']
            e_str = ', '.join(f"{p}p={e*100:+.2f}%" for p, e in edges.items())
            report.append(f"    {m}: {e_str}")

    # ── Section 6: Edge Source Explanation ──
    report.append("\n" + "=" * 80)
    report.append("  SECTION 6: EDGE SOURCE EXPLANATION")
    report.append("=" * 80)

    report.append("""
  Edge Analysis:
  
  The edge (if any) in lottery prediction comes from exploiting:
  
  1. FREQUENCY BIAS: If the draw mechanism produces slightly non-uniform 
     frequencies (e.g., ball weight, machine mechanics), frequency-based
     methods capture this signal.
  
  2. TEMPORAL PATTERNS: Serial correlation, regime switching, and cycle-based
     methods exploit temporal dependencies in the draw sequence.
  
  3. STRUCTURAL CONSTRAINTS: Real draws tend to have specific sum ranges,
     odd/even balances, and zone distributions. Constrained methods filter
     for likely structural patterns.
  
  4. COVERAGE OPTIMIZATION: Multi-ticket strategies that maximize diversity
     (minimal overlap) between tickets achieve better coverage of the 
     probability space per dollar spent.
  
  Important: Even with detected edges, the house advantage in 539 remains
  significant. The expected return per NT$50 bet is far below NT$50 regardless
  of strategy. Edge analysis measures RELATIVE improvement vs random play,
  not absolute profitability.
""")

    # ── Section 7: Failure Modes ──
    report.append("=" * 80)
    report.append("  SECTION 7: FAILURE MODES")
    report.append("=" * 80)

    report.append("""
  Known failure modes:
  
  1. SHORT_MOMENTUM: Methods that appear to work in 150-500 draws but 
     fail at 1500 draws. Likely overfitting to recent regime.
  
  2. LOOK-AHEAD BIAS: If any method uses future data (we guard against
     this with strict walk-forward but it must be verified).
  
  3. MULTIPLE TESTING: With 28 methods tested, ~1.4 will show p<0.05
     by chance alone. Bonferroni correction addresses this.
  
  4. REGIME CHANGE: Lottery machines are periodically replaced/maintained.
     Patterns from old regimes may not transfer.
  
  5. SAMPLE SIZE: Even 5792 draws may be insufficient for detecting
     very small but real edges (e.g., 0.5% improvement requires ~10000
     draws for significance at p<0.05).
""")

    # ── Section 8: Scientific Verdict ──
    report.append("=" * 80)
    report.append("  SECTION 8: FINAL SCIENTIFIC VERDICT")
    report.append("=" * 80)

    # Randomness verdict
    report.append(f"\n  Randomness Test: {randomness['verdict']}")
    if randomness['signals']:
        report.append(f"  Detected signals: {', '.join(randomness['signals'])}")

    # Best strategies existence
    positive_edge = [r for r in ranked if r['ge2_edge'] > 0]
    stable_positive = [r for r in ranked if r['stability'] == 'STABLE' and r['ge2_edge'] > 0]

    report.append(f"\n  Summary Statistics:")
    report.append(f"    Total methods tested: {len(ranked)}")
    report.append(f"    Methods with positive edge: {len(positive_edge)}")
    report.append(f"    STABLE methods with positive edge: {len(stable_positive)}")
    report.append(f"    Significant at p<0.05: {len(sig_methods)}")
    report.append(f"    Survive Bonferroni: {len(bonf_sig)}")

    if stable_positive:
        best_single = max(stable_positive, key=lambda x: x['ge2_edge'])
        report.append(f"\n  Best single-ticket method: {best_single['name']}")
        report.append(f"    Edge: {best_single['ge2_edge_pct']:+.2f}%")
        report.append(f"    Stability: {best_single['stability']}")

    report.append(f"\n  Conclusion:")
    if len(bonf_sig) > 0:
        report.append(f"    STATISTICALLY SIGNIFICANT EDGE DETECTED")
        report.append(f"    {len(bonf_sig)} method(s) survive multiple-testing correction.")
        report.append(f"    This suggests genuine non-randomness in the draw process.")
    elif len(sig_methods) > 0:
        report.append(f"    MARGINAL EVIDENCE OF EDGE")
        report.append(f"    {len(sig_methods)} method(s) significant at p<0.05 but none survive Bonferroni.")
        report.append(f"    Could be genuine small edge or multiple-testing artifact.")
    elif len(positive_edge) > len(ranked) * 0.5:
        report.append(f"    WEAK EVIDENCE OF EDGE")
        report.append(f"    Majority of methods show positive edge, suggesting possible signal.")
        report.append(f"    However, individual edges are not statistically significant.")
    else:
        report.append(f"    NO RELIABLE EDGE DETECTED")
        report.append(f"    The lottery appears consistent with random draws.")
        report.append(f"    No strategy reliably outperforms random selection.")

    report.append(f"\n  IMPORTANT: This analysis is for research purposes only.")
    report.append(f"  Playing the lottery has negative expected value regardless of strategy.")
    report.append("\n" + "=" * 80)

    return '\n'.join(report)


# ═══════════════════════════════════════════════════════════════════
#  MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════
def main():
    total_start = time.time()
    print("=" * 80)
    print("  今彩539 COMPREHENSIVE QUANTITATIVE RESEARCH")
    print(f"  {len(ALL_METHODS)} methods × 3 windows × validation")
    print("=" * 80)

    # Load data
    all_draws = load_data()

    # ── Phase 0: Randomness Test ──
    randomness = test_randomness(all_draws, 2000)

    # ── Phase 1: Test all single methods ──
    print(f"\n{'='*60}")
    print(f"  PHASE 1: SINGLE-METHOD EVALUATION ({len(ALL_METHODS)} methods)")
    print(f"{'='*60}")

    all_results = []
    for name, func in ALL_METHODS.items():
        r = compute_full_metrics(name, func, all_draws, seed=42)
        all_results.append(r)

    # ── Phase 2: Permutation tests for top methods ──
    print(f"\n{'='*60}")
    print(f"  PHASE 2: PERMUTATION TESTS (top methods)")
    print(f"{'='*60}")

    valid_results = [r for r in all_results if r is not None]
    top_methods = sorted(valid_results, key=lambda x: x['ge2_edge'], reverse=True)[:8]

    for r in top_methods:
        if r['name'] == 'random':
            continue
        print(f"  Permutation test: {r['name']}...", end='', flush=True)
        perm = permutation_test(ALL_METHODS[r['name']], all_draws, 500, 100, 42)
        r['permutation'] = perm
        print(f" z={perm['z_score']:.2f}, p={perm['p_value']:.4f} {'✓' if perm['significant'] else '✗'}")

    # ── Phase 3: Multi-ticket search ──
    print(f"\n{'='*60}")
    print(f"  PHASE 3: MULTI-TICKET COMBINATION SEARCH")
    print(f"{'='*60}")

    # Find best 2-ticket combo (top 10 single methods)
    best_2ticket = find_best_multi_ticket(valid_results, all_draws, n_tickets=2, top_n=10)

    # Find best 3-ticket combo (top 8 to limit C(8,3)=56 combos)
    best_3ticket = find_best_multi_ticket(valid_results, all_draws, n_tickets=3, top_n=8)

    # ── Phase 4: Full validation of best combos ──
    print(f"\n{'='*60}")
    print(f"  PHASE 4: FULL VALIDATION OF BEST COMBOS")
    print(f"{'='*60}")

    best_2_validation = None
    best_3_validation = None

    if best_2ticket and best_2ticket['best_combo']:
        print(f"\n  Validating 2-ticket: {best_2ticket['best_combo']}")
        best_2_validation = validate_multi_ticket(
            best_2ticket['best_combo'], all_draws, 2, seed=42
        )
        print(f"    Stability: {best_2_validation['stability']}")
        print(f"    Permutation: z={best_2_validation['permutation']['z_score']:.2f}, p={best_2_validation['permutation']['p_value']:.4f}")

    if best_3ticket and best_3ticket['best_combo']:
        print(f"\n  Validating 3-ticket: {best_3ticket['best_combo']}")
        best_3_validation = validate_multi_ticket(
            best_3ticket['best_combo'], all_draws, 3, seed=42
        )
        print(f"    Stability: {best_3_validation['stability']}")
        print(f"    Permutation: z={best_3_validation['permutation']['z_score']:.2f}, p={best_3_validation['permutation']['p_value']:.4f}")

    # ── Phase 5: Generate report ──
    total_elapsed = time.time() - total_start
    report = generate_report(
        all_results, best_2ticket, best_3ticket,
        randomness, best_2_validation, best_3_validation,
        total_elapsed
    )

    # Print report
    print("\n\n")
    print(report)

    # Save report
    report_path = os.path.join(os.path.dirname(__file__), '..', 'RESEARCH_539_REPORT.md')
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"\n[SAVED] Report saved to {report_path}")

    # Save raw results JSON
    json_path = os.path.join(os.path.dirname(__file__), '..', 'research_539_results.json')
    json_data = {
        'generated': datetime.now().isoformat(),
        'total_draws': len(all_draws),
        'baselines': {k: {str(kk): vv for kk, vv in v.items()} for k, v in BASELINES.items()},
        'randomness': {k: v for k, v in randomness.items() if k != 'signals' or True},
        'single_methods': [
            {k: v for k, v in r.items() if k != 'three_window'}
            for r in (all_results if all(r is not None for r in all_results) else [r for r in all_results if r])
        ],
        'best_2ticket': {
            'methods': best_2ticket['best_combo'] if best_2ticket else None,
            'top_combos': best_2ticket['all_combos'][:10] if best_2ticket else [],
        },
        'best_3ticket': {
            'methods': best_3ticket['best_combo'] if best_3ticket else None,
            'top_combos': best_3ticket['all_combos'][:10] if best_3ticket else [],
        },
    }

    def make_serializable(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [make_serializable(i) for i in obj]
        return obj

    with open(json_path, 'w') as f:
        json.dump(make_serializable(json_data), f, indent=2, ensure_ascii=False)
    print(f"[SAVED] Results saved to {json_path}")


if __name__ == '__main__':
    main()
