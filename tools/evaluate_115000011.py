#!/usr/bin/env python3
"""
Comprehensive Evaluation of All Power Lotto Prediction Methods
Against Actual Draw 115000011: [7, 22, 28, 34, 36, 37], Special: 7

Uses ONLY data up to draw 115000010 (no data leakage).
"""

import sqlite3
import json
import numpy as np
import random
from collections import Counter, defaultdict
from pathlib import Path

# ====== CONFIGURATION ======
DB_PATH = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db")
ACTUAL_NUMBERS = {7, 22, 28, 34, 36, 37}
ACTUAL_SPECIAL = 7
ACTUAL_DRAW = '115000011'
CUTOFF_DRAW = '115000010'
MAX_NUM = 38       # Power Lotto main numbers: 1-38
SPECIAL_MAX = 8    # Power Lotto special: 1-8
SEED = 42

np.random.seed(SEED)
random.seed(SEED)

# ====== DATA LOADING ======
def load_history_up_to(cutoff_draw):
    """Load all Power Lotto draws up to (and including) cutoff_draw."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
        SELECT draw, date, numbers, special
        FROM draws
        WHERE lottery_type='POWER_LOTTO' AND draw <= ?
        ORDER BY draw ASC
    ''', (cutoff_draw,))
    
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for draw, date, numbers_json, special in rows:
        nums = json.loads(numbers_json) if isinstance(numbers_json, str) else numbers_json
        history.append({
            'draw': draw,
            'date': date,
            'numbers': nums,
            'special': special
        })
    
    return history

# ====== SCORING FUNCTIONS ======
def score_prediction(predicted_numbers, predicted_special=None):
    """Score a single prediction against actual draw."""
    pred_set = set(predicted_numbers[:6])
    matches = pred_set & ACTUAL_NUMBERS
    match_count = len(matches)
    special_hit = (predicted_special == ACTUAL_SPECIAL) if predicted_special else False
    
    # Closeness score: match_count * 10 + (5 if special_hit) + proximity bonus
    proximity_bonus = 0
    for p in pred_set:
        for a in ACTUAL_NUMBERS:
            if abs(p - a) == 1:
                proximity_bonus += 0.5
            elif abs(p - a) == 2:
                proximity_bonus += 0.2
    
    closeness = match_count * 10 + (5 if special_hit else 0) + proximity_bonus
    
    return {
        'match_count': match_count,
        'matched_numbers': sorted(matches),
        'special_hit': special_hit,
        'closeness': closeness,
        'predicted': sorted(pred_set),
        'predicted_special': predicted_special
    }

def score_multi_bet(bets, specials=None):
    """Score multiple bets, return best result."""
    best = None
    all_results = []
    for i, bet in enumerate(bets):
        sp = specials[i] if specials and i < len(specials) else None
        result = score_prediction(bet, sp)
        result['bet_index'] = i + 1
        all_results.append(result)
        if best is None or result['closeness'] > best['closeness']:
            best = result
    
    # Overall coverage
    all_predicted = set()
    for b in bets:
        all_predicted.update(b[:6])
    coverage_matches = all_predicted & ACTUAL_NUMBERS
    
    return {
        'best': best,
        'all_results': all_results,
        'total_coverage': len(all_predicted),
        'coverage_matches': len(coverage_matches),
        'coverage_matched_nums': sorted(coverage_matches),
        'num_bets': len(bets)
    }

# ====== PREDICTION METHODS ======

def method_frequency_w30(history):
    """Frequency-based: Top 6 by frequency in last 30 draws."""
    recent = history[-30:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    top6 = sorted([n for n, _ in freq.most_common(6)])
    return [top6], None, "Top 6 most frequent in last 30 draws"

def method_frequency_w50(history):
    """Frequency-based: Top 6 by frequency in last 50 draws."""
    recent = history[-50:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    top6 = sorted([n for n, _ in freq.most_common(6)])
    return [top6], None, "Top 6 most frequent in last 50 draws"

def method_frequency_w100(history):
    """Frequency-based: Top 6 by frequency in last 100 draws."""
    recent = history[-100:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    top6 = sorted([n for n, _ in freq.most_common(6)])
    return [top6], None, "Top 6 most frequent in last 100 draws"

def method_deviation(history):
    """Deviation-based: Numbers most overdue based on expected frequency."""
    recent = history[-100:]
    n_draws = len(recent)
    expected_freq = n_draws * 6 / MAX_NUM  # Each number expected ~15.8 times in 100 draws
    
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    
    # Deviation = expected - actual (positive = overdue)
    deviations = {}
    for n in range(1, MAX_NUM + 1):
        deviations[n] = expected_freq - freq.get(n, 0)
    
    # Top 6 most overdue
    sorted_nums = sorted(deviations.items(), key=lambda x: x[1], reverse=True)
    top6 = sorted([n for n, _ in sorted_nums[:6]])
    return [top6], None, "Top 6 most overdue (deviation from expected frequency)"

def method_cold_numbers_w100(history):
    """Cold numbers: 6 least frequent in last 100 draws."""
    recent = history[-100:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    
    sorted_nums = sorted(range(1, MAX_NUM + 1), key=lambda x: freq.get(x, 0))
    top6 = sorted(sorted_nums[:6])
    return [top6], None, "6 coldest numbers in last 100 draws"

def method_markov_w30(history):
    """Markov chain: Numbers most likely to follow previous draw's numbers."""
    recent = history[-30:]
    
    # Build transition matrix
    transitions = Counter()
    for i in range(len(recent) - 1):
        prev = set(recent[i]['numbers'])
        curr = recent[i + 1]['numbers']
        for p in prev:
            for c in curr:
                transitions[(p, c)] += 1
    
    # Score based on last draw
    last = recent[-1]['numbers']
    scores = Counter()
    for num in last:
        for (p, c), count in transitions.items():
            if p == num:
                scores[c] += count
    
    result = [n for n, _ in scores.most_common(6)]
    
    # Fill if < 6
    if len(result) < 6:
        freq = Counter()
        for d in recent:
            freq.update(d['numbers'])
        for n, _ in freq.most_common():
            if n not in result and len(result) < 6:
                result.append(n)
    
    return [sorted(result[:6])], None, "Markov transition probabilities from last draw (W30)"

def method_fourier_rhythm(history, window=500):
    """Fourier Rhythm: FFT period detection + phase alignment."""
    from scipy.fft import fft, fftfreq
    
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    
    # Create bitstreams
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            bitstreams[n][idx] = 1
    
    # Detect periods and score
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bs = bitstreams[n]
        if sum(bs) < 2:
            continue
        
        yf = fft(bs - np.mean(bs))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        
        if len(pos_yf) == 0:
            continue
        
        peak_idx = np.argmax(pos_yf)
        freq = pos_xf[peak_idx]
        
        if freq == 0:
            continue
        period = 1 / freq
        
        if 2 < period < w / 2:
            last_hit = np.where(bs == 1)[0][-1]
            gap = (w - 1) - last_hit
            dist_to_peak = abs(gap - period)
            scores[n] = 1.0 / (dist_to_peak + 1.0)
    
    all_indices = np.arange(1, MAX_NUM + 1)
    sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
    
    bets = []
    for i in range(2):  # 2 bets
        start = i * 6
        end = (i + 1) * 6
        bets.append(sorted(sorted_indices[start:end].tolist()))
    
    return bets, None, "FFT period detection + phase alignment (W500, 2 bets)"

def method_fourier30_markov30_hedging(history):
    """
    Fourier30+Markov30 hedging (our validated 2-bet method).
    Bet1: Weighted frequency (recent emphasis)
    Bet2: Markov transition
    With diversification.
    """
    # Bet 1: Fourier30 (weighted frequency)
    recent = history[-30:] if len(history) >= 30 else history
    weighted_freq = Counter()
    n = len(recent)
    for i, h in enumerate(recent):
        weight = 1 + 2 * (i / n)
        for num in h['numbers']:
            weighted_freq[num] += weight
    bet1 = sorted([n for n, _ in weighted_freq.most_common(6)])
    
    # Bet 2: Markov30
    transitions = Counter()
    for i in range(len(recent) - 1):
        prev = set(recent[i]['numbers'])
        curr = recent[i + 1]['numbers']
        for p in prev:
            for c in curr:
                transitions[(p, c)] += 1
    
    last = recent[-1]['numbers']
    scores = Counter()
    for num in last:
        for (p, c), count in transitions.items():
            if p == num:
                scores[c] += count
    
    result = [n for n, _ in scores.most_common(6)]
    if len(result) < 6:
        all_nums = []
        for h in recent:
            all_nums.extend(h['numbers'])
        freq = Counter(all_nums)
        for n, _ in freq.most_common():
            if n not in result and len(result) < 6:
                result.append(n)
    bet2 = sorted(result[:6])
    
    # Diversification: max 3 overlap
    overlap = set(bet1) & set(bet2)
    if len(overlap) > 3:
        # Replace some in bet2 with cold numbers
        recent50 = history[-50:] if len(history) >= 50 else history
        last_seen = {i: len(recent50) for i in range(1, MAX_NUM + 1)}
        for idx, h in enumerate(recent50):
            for num in h['numbers']:
                gap = len(recent50) - 1 - idx
                if gap < last_seen[num]:
                    last_seen[num] = gap
        
        new_bet2 = [n for n in bet2 if n not in overlap][:3]
        cold = sorted(last_seen.items(), key=lambda x: -x[1])
        
        def get_zone(num):
            if 1 <= num <= 10: return 1
            elif 11 <= num <= 20: return 2
            elif 21 <= num <= 30: return 3
            else: return 4
        
        zones_used = Counter(get_zone(n) for n in new_bet2)
        for n, gap in cold:
            if n not in bet1 and n not in new_bet2 and len(new_bet2) < 6:
                z = get_zone(n)
                if zones_used[z] < 2:
                    new_bet2.append(n)
                    zones_used[z] += 1
        for n, gap in cold:
            if n not in bet1 and n not in new_bet2 and len(new_bet2) < 6:
                new_bet2.append(n)
        bet2 = sorted(new_bet2[:6])
    
    return [bet1, bet2], None, "Fourier30 (weighted freq) + Markov30 hedging (2 bets)"

def method_cold_complement_2bet(history):
    """Cold Number Complement: 2 bets from coldest 12 numbers."""
    recent = history[-100:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    
    sorted_nums = sorted(range(1, MAX_NUM + 1), key=lambda x: freq.get(x, 0))
    bet1 = sorted(sorted_nums[:6])
    bet2 = sorted(sorted_nums[6:12])
    
    return [bet1, bet2], None, "Coldest 12 numbers split into 2 non-overlapping bets (W100)"

def method_cluster_pivot(history, n_bets=2):
    """Cluster Pivot: K-means clustering on recent number patterns."""
    from sklearn.cluster import KMeans
    
    recent = history[-100:]
    
    # Create feature vectors: each draw is a 38-dim binary vector
    vectors = []
    for d in recent:
        v = np.zeros(MAX_NUM)
        for n in d['numbers']:
            v[n - 1] = 1
        vectors.append(v)
    
    X = np.array(vectors)
    
    # K-means clustering
    n_clusters = max(3, n_bets + 1)
    kmeans = KMeans(n_clusters=n_clusters, random_state=SEED, n_init=10)
    kmeans.fit(X)
    
    # Get cluster centers and pick top numbers from each
    bets = []
    for i in range(n_bets):
        center = kmeans.cluster_centers_[i]
        top_indices = np.argsort(center)[-6:]
        bet = sorted([idx + 1 for idx in top_indices])
        bets.append(bet)
    
    return bets, None, f"K-means clustering on recent 100 draws ({n_bets} bets)"

def method_echo_aware(history):
    """Echo-aware: Combine echo patterns (2-5 draws ago) with frequency."""
    recent = history[-50:]
    
    # Echo scores: numbers from 2-5 draws ago get higher echo weight
    echo_scores = Counter()
    for offset in range(2, 6):  # 2, 3, 4, 5 draws ago
        if offset <= len(recent):
            d = recent[-offset]
            weight = 1.0 / offset  # Closer = higher weight
            for n in d['numbers']:
                echo_scores[n] += weight
    
    # Frequency scores
    freq_scores = Counter()
    for d in recent:
        for n in d['numbers']:
            freq_scores[n] += 1
    
    # Combine: 60% echo + 40% frequency (normalized)
    max_echo = max(echo_scores.values()) if echo_scores else 1
    max_freq = max(freq_scores.values()) if freq_scores else 1
    
    combined = {}
    for n in range(1, MAX_NUM + 1):
        e = echo_scores.get(n, 0) / max_echo
        f = freq_scores.get(n, 0) / max_freq
        combined[n] = 0.6 * e + 0.4 * f
    
    sorted_nums = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    bet1 = sorted([n for n, _ in sorted_nums[:6]])
    bet2 = sorted([n for n, _ in sorted_nums[6:12]])
    
    return [bet1, bet2], None, "Echo patterns (2-5 draws ago) + frequency (2 bets)"

def method_zone_balance(history):
    """Zone balance: Ensure representation from all 4 zones (1-10, 11-20, 21-30, 31-38)."""
    recent = history[-50:]
    
    zones = {1: [], 2: [], 3: [], 4: []}
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    
    for n in range(1, MAX_NUM + 1):
        if 1 <= n <= 10: zones[1].append((n, freq.get(n, 0)))
        elif 11 <= n <= 20: zones[2].append((n, freq.get(n, 0)))
        elif 21 <= n <= 30: zones[3].append((n, freq.get(n, 0)))
        else: zones[4].append((n, freq.get(n, 0)))
    
    # Pick top from each zone: 2-1-2-1 or 1-2-1-2 distribution
    bet = []
    distributions = [(2, 1, 2, 1), (1, 2, 1, 2), (2, 2, 1, 1), (1, 1, 2, 2)]
    
    # Use the distribution that best matches recent draws
    recent_dist = Counter()
    for d in recent[-10:]:
        for n in d['numbers']:
            if 1 <= n <= 10: recent_dist[1] += 1
            elif 11 <= n <= 20: recent_dist[2] += 1
            elif 21 <= n <= 30: recent_dist[3] += 1
            else: recent_dist[4] += 1
    
    # Normalize
    total = sum(recent_dist.values()) or 1
    zone_ratios = {z: recent_dist.get(z, 0) / total for z in range(1, 5)}
    
    # Pick proportionally
    for z in range(1, 5):
        zone_sorted = sorted(zones[z], key=lambda x: x[1], reverse=True)
        count = max(1, round(zone_ratios[z] * 6))
        for n, _ in zone_sorted[:count]:
            if len(bet) < 6:
                bet.append(n)
    
    # Fill to 6
    all_sorted = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    for n, _ in all_sorted:
        if n not in bet and len(bet) < 6:
            bet.append(n)
    
    return [sorted(bet[:6])], None, "Zone-balanced selection (proportional to recent zone distribution)"

def method_hot_cold_mix(history):
    """Hot-Cold Mix: 3 hot + 3 cold numbers."""
    recent = history[-50:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    
    sorted_by_freq = sorted(range(1, MAX_NUM + 1), key=lambda x: freq.get(x, 0), reverse=True)
    hot3 = sorted_by_freq[:3]  # 3 hottest
    cold3 = sorted_by_freq[-3:]  # 3 coldest
    
    return [sorted(hot3 + cold3)], None, "3 hottest + 3 coldest numbers (W50)"

def method_gap_analysis(history):
    """Gap analysis: Numbers with gaps closest to their average gap."""
    recent = history[-200:]
    
    # Calculate gap for each number
    last_seen = {}
    gaps_history = defaultdict(list)
    
    for idx, d in enumerate(recent):
        for n in d['numbers']:
            if n in last_seen:
                gap = idx - last_seen[n]
                gaps_history[n].append(gap)
            last_seen[n] = idx
    
    # Current gap (since last appearance)
    current_gap = {}
    for n in range(1, MAX_NUM + 1):
        if n in last_seen:
            current_gap[n] = len(recent) - 1 - last_seen[n]
        else:
            current_gap[n] = len(recent)
    
    # Score: How close is current gap to average gap?
    scores = {}
    for n in range(1, MAX_NUM + 1):
        if n in gaps_history and len(gaps_history[n]) >= 2:
            avg_gap = np.mean(gaps_history[n])
            # Score is higher when gap approaches average (due for return)
            if current_gap[n] >= avg_gap * 0.8:
                scores[n] = 1.0 / (abs(current_gap[n] - avg_gap) + 1)
            else:
                scores[n] = 0.1
        else:
            scores[n] = 0.5
    
    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top6 = sorted([n for n, _ in sorted_nums[:6]])
    return [top6], None, "Gap analysis: numbers due for return (gap near average)"

def method_triple_strike(history):
    """
    Triple Strike: 3 complementary bets.
    Bet 1: Fourier Rhythm
    Bet 2: Cold numbers (exclude bet1)
    Bet 3: Tail balance (exclude bet1+2)
    """
    from scipy.fft import fft, fftfreq
    
    # Bet 1: Fourier Rhythm (simplified)
    w = min(500, len(history))
    h_slice = history[-w:]
    
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            bitstreams[n][idx] = 1
    
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bs = bitstreams[n]
        if sum(bs) < 2: continue
        yf = fft(bs - np.mean(bs))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        if len(pos_yf) == 0: continue
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0: continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bs == 1)[0][-1]
            gap = (w - 1) - last_hit
            dist_to_peak = abs(gap - period)
            scores[n] = 1.0 / (dist_to_peak + 1.0)
    
    all_indices = np.arange(1, MAX_NUM + 1)
    sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
    bet1 = sorted(sorted_indices[:6].tolist())
    exclude1 = set(bet1)
    
    # Bet 2: Cold numbers (exclude bet1)
    recent100 = history[-100:]
    freq_cold = Counter()
    for d in recent100:
        for n in d['numbers']:
            freq_cold[n] += 1
    
    cold_sorted = sorted(range(1, MAX_NUM + 1), key=lambda x: freq_cold.get(x, 0))
    bet2 = sorted([n for n in cold_sorted if n not in exclude1][:6])
    exclude2 = exclude1 | set(bet2)
    
    # Bet 3: Tail balance (exclude bet1+2)
    # Try to cover different tail digits (0-9)
    tail_groups = defaultdict(list)
    for n in range(1, MAX_NUM + 1):
        if n not in exclude2:
            tail = n % 10
            tail_groups[tail].append(n)
    
    bet3 = []
    used_tails = set()
    # Pick one from each tail group, prioritized by frequency
    for tail in range(10):
        if tail in tail_groups and tail not in used_tails and len(bet3) < 6:
            candidates = tail_groups[tail]
            best = max(candidates, key=lambda x: freq_cold.get(x, 0))
            bet3.append(best)
            used_tails.add(tail)
    
    # Fill remaining
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in exclude2 and n not in bet3]
    random.shuffle(remaining)
    while len(bet3) < 6 and remaining:
        bet3.append(remaining.pop())
    
    bet3 = sorted(bet3[:6])
    
    return [bet1, bet2, bet3], None, "Triple Strike: Fourier + Cold + Tail Balance (3 bets)"

def method_special_predictor(history):
    """Special number prediction using V3 multi-strategy ensemble."""
    # Simplified V3-like special predictor
    specials = [d['special'] for d in history if d.get('special')]
    
    scores = {n: 0.0 for n in range(1, SPECIAL_MAX + 1)}
    
    # 1. Long-term bias
    counts = Counter(specials)
    total = len(specials)
    for n in range(1, 9):
        scores[n] += counts.get(n, 0) / max(1, total) * 3.0
    
    # 2. Markov (from last special)
    if len(specials) >= 2:
        transitions = defaultdict(Counter)
        for i in range(len(specials) - 1):
            transitions[specials[i]][specials[i + 1]] += 1
        
        last_special = specials[0] if specials else 2  # history is ascending, [0] is oldest
        # Actually in our data, history is sorted ascending, so last is history[-1]
        last_special = history[-1].get('special', 2)
        if last_special in transitions:
            t_counts = transitions[last_special]
            t_total = sum(t_counts.values())
            for n, c in t_counts.items():
                if 1 <= n <= 8:
                    scores[n] += (c / t_total) * 2.0
    
    # 3. Gap pressure
    last_seen_sp = {n: 999 for n in range(1, 9)}
    for i, d in enumerate(reversed(history)):
        s = d.get('special')
        if s and 1 <= s <= 8 and last_seen_sp[s] == 999:
            last_seen_sp[s] = i
    
    avg_gap = sum(last_seen_sp[n] for n in range(1, 9) if last_seen_sp[n] < 999) / 8
    for n in range(1, 9):
        gap = last_seen_sp[n]
        if gap > avg_gap:
            scores[n] += (gap - avg_gap) / max(1, avg_gap) * 1.5
    
    # 4. Oscillation/Repeat
    recent_specials = [d['special'] for d in history[-5:] if d.get('special')]
    if recent_specials:
        scores[recent_specials[-1]] += 0.5  # Repeat boost
        if len(recent_specials) >= 3 and recent_specials[-1] != recent_specials[-2] and recent_specials[-1] == recent_specials[-3]:
            scores[recent_specials[-1]] += 0.3  # Oscillation
    
    # Sort and return top 3
    sorted_specials = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [n for n, _ in sorted_specials[:3]]

def method_random_baseline(history):
    """Random baseline: Random selection."""
    nums = random.sample(range(1, MAX_NUM + 1), 6)
    special = random.randint(1, SPECIAL_MAX)
    return [sorted(nums)], [special], "Random selection (seed=42)"

def method_random_baseline_2bet(history):
    """Random baseline: 2 random bets."""
    all_nums = list(range(1, MAX_NUM + 1))
    random.shuffle(all_nums)
    bet1 = sorted(all_nums[:6])
    bet2 = sorted(all_nums[6:12])
    sp1 = random.randint(1, SPECIAL_MAX)
    sp2 = random.randint(1, SPECIAL_MAX)
    return [bet1, bet2], [sp1, sp2], "2 random bets (seed=42)"

def method_sum_range(history):
    """Sum range: Pick numbers whose sum falls in the most common range."""
    recent = history[-100:]
    
    # Calculate sum range distribution
    sums = [sum(d['numbers']) for d in recent]
    avg_sum = np.mean(sums)
    
    # Generate candidates near average sum
    best_bet = None
    best_diff = float('inf')
    
    for _ in range(10000):
        candidate = sorted(random.sample(range(1, MAX_NUM + 1), 6))
        s = sum(candidate)
        diff = abs(s - avg_sum)
        if diff < best_diff:
            best_diff = diff
            best_bet = candidate
    
    return [best_bet], None, f"Sum-range optimized (target sum ~{avg_sum:.0f})"

def method_odd_even_balance(history):
    """Odd-Even balance: Match recent odd/even distribution."""
    recent = history[-30:]
    
    # Calculate average odd count
    odd_counts = []
    for d in recent:
        odd = sum(1 for n in d['numbers'] if n % 2 == 1)
        odd_counts.append(odd)
    avg_odd = round(np.mean(odd_counts))
    target_even = 6 - avg_odd
    
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    
    odds = sorted([(n, freq.get(n, 0)) for n in range(1, MAX_NUM + 1) if n % 2 == 1], key=lambda x: x[1], reverse=True)
    evens = sorted([(n, freq.get(n, 0)) for n in range(1, MAX_NUM + 1) if n % 2 == 0], key=lambda x: x[1], reverse=True)
    
    bet = [n for n, _ in odds[:avg_odd]] + [n for n, _ in evens[:target_even]]
    return [sorted(bet[:6])], None, f"Odd/Even balanced ({avg_odd}:{target_even})"

def method_consecutive_pattern(history):
    """Look for consecutive number patterns in recent draws."""
    recent = history[-30:]
    
    # Count consecutive pair occurrences
    consec_freq = Counter()
    for d in recent:
        nums = sorted(d['numbers'])
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] == 1:
                consec_freq[(nums[i], nums[i + 1])] += 1
    
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    
    # Start with most common consecutive pair
    bet = []
    if consec_freq:
        top_pair = consec_freq.most_common(1)[0][0]
        bet.extend(top_pair)
    
    # Fill with most frequent non-consecutive
    for n, _ in freq.most_common():
        if n not in bet and len(bet) < 6:
            bet.append(n)
    
    return [sorted(bet[:6])], None, "Consecutive pattern + high frequency fill"

def method_weighted_recency(history):
    """Exponentially weighted recency: More weight to recent draws."""
    recent = history[-50:]
    n = len(recent)
    
    scores = Counter()
    for i, d in enumerate(recent):
        weight = np.exp(0.05 * i)  # Exponential growth towards recent
        for num in d['numbers']:
            scores[num] += weight
    
    top6 = sorted([n for n, _ in scores.most_common(6)])
    return [top6], None, "Exponentially weighted recency (W50)"

def method_anti_hot(history):
    """Anti-hot: Bet on numbers NOT in the hottest group (contrarian)."""
    recent = history[-30:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    
    # Remove top 12 hottest, pick from remaining by moderate frequency
    sorted_nums = sorted(range(1, MAX_NUM + 1), key=lambda x: freq.get(x, 0), reverse=True)
    anti_hot = sorted_nums[12:]  # Skip top 12
    
    # From anti-hot, pick those with moderate frequency (not completely cold)
    moderate = sorted(anti_hot, key=lambda x: freq.get(x, 0), reverse=True)
    return [sorted(moderate[:6])], None, "Anti-hot contrarian (avoid top 12, pick moderate)"

def method_tail_digit_coverage(history):
    """Tail digit coverage: Ensure diverse tail digits (0-9)."""
    recent = history[-50:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    
    tail_groups = defaultdict(list)
    for n in range(1, MAX_NUM + 1):
        tail = n % 10
        tail_groups[tail].append((n, freq.get(n, 0)))
    
    bet = []
    used_tails = set()
    for tail in sorted(tail_groups.keys()):
        if len(bet) < 6:
            candidates = sorted(tail_groups[tail], key=lambda x: x[1], reverse=True)
            if candidates and tail not in used_tails:
                bet.append(candidates[0][0])
                used_tails.add(tail)
    
    # Fill remaining
    all_sorted = sorted(range(1, MAX_NUM + 1), key=lambda x: freq.get(x, 0), reverse=True)
    for n in all_sorted:
        if n not in bet and len(bet) < 6:
            bet.append(n)
    
    return [sorted(bet[:6])], None, "Tail digit coverage (diverse last digits)"


# ====== MAIN EVALUATION ======
def main():
    print("=" * 80)
    print("  COMPREHENSIVE EVALUATION: Power Lotto Draw 115000011")
    print(f"  Actual Numbers: {sorted(ACTUAL_NUMBERS)}  Special: {ACTUAL_SPECIAL}")
    print(f"  Previous Draw (115000010): [1, 12, 14, 15, 27, 29]  Special: 5")
    print(f"  Data Cutoff: {CUTOFF_DRAW} (strict no-leakage)")
    print("=" * 80)
    
    # Load data
    history = load_history_up_to(CUTOFF_DRAW)
    print(f"\nLoaded {len(history)} draws up to {CUTOFF_DRAW}")
    print(f"Last draw in data: {history[-1]['draw']} ({history[-1]['date']})")
    print(f"  Numbers: {history[-1]['numbers']}  Special: {history[-1]['special']}")
    
    # Verify no leakage
    for d in history:
        if d['draw'] == ACTUAL_DRAW:
            print("ERROR: Data leakage detected! Aborting.")
            return
    print("No data leakage confirmed.\n")
    
    # Get special predictions
    special_preds = method_special_predictor(history)
    print(f"Special Number V3 Predictions: Top-3 = {special_preds}")
    print(f"  Actual Special: {ACTUAL_SPECIAL}")
    print(f"  Special Hit (Top-1): {'YES' if special_preds[0] == ACTUAL_SPECIAL else 'NO'}")
    print(f"  Special Hit (Top-3): {'YES' if ACTUAL_SPECIAL in special_preds else 'NO'}")
    print()
    
    # Define all methods to test
    methods = [
        ("1. Frequency W30 (1-bet)", method_frequency_w30, 1),
        ("2. Frequency W50 (1-bet)", method_frequency_w50, 1),
        ("3. Frequency W100 (1-bet)", method_frequency_w100, 1),
        ("4. Deviation/Overdue (1-bet)", method_deviation, 1),
        ("5. Cold Numbers W100 (1-bet)", method_cold_numbers_w100, 1),
        ("6. Markov W30 (1-bet)", method_markov_w30, 1),
        ("7. Fourier Rhythm (2-bet)", method_fourier_rhythm, 2),
        ("8. Fourier30+Markov30 Hedging (2-bet)", method_fourier30_markov30_hedging, 2),
        ("9. Cold Complement (2-bet)", method_cold_complement_2bet, 2),
        ("10. Cluster Pivot (2-bet)", method_cluster_pivot, 2),
        ("11. Echo-Aware (2-bet)", method_echo_aware, 2),
        ("12. Triple Strike (3-bet)", method_triple_strike, 3),
        ("13. Zone Balance (1-bet)", method_zone_balance, 1),
        ("14. Hot-Cold Mix (1-bet)", method_hot_cold_mix, 1),
        ("15. Gap Analysis (1-bet)", method_gap_analysis, 1),
        ("16. Sum Range (1-bet)", method_sum_range, 1),
        ("17. Odd-Even Balance (1-bet)", method_odd_even_balance, 1),
        ("18. Consecutive Pattern (1-bet)", method_consecutive_pattern, 1),
        ("19. Weighted Recency (1-bet)", method_weighted_recency, 1),
        ("20. Anti-Hot Contrarian (1-bet)", method_anti_hot, 1),
        ("21. Tail Digit Coverage (1-bet)", method_tail_digit_coverage, 1),
        ("22. Random Baseline (1-bet)", method_random_baseline, 1),
        ("23. Random Baseline (2-bet)", method_random_baseline_2bet, 2),
    ]
    
    results = []
    
    print("-" * 80)
    print(f"{'Method':<45} {'Bets':>4} {'BestM':>5} {'CovM':>4} {'CovN':>4} {'Sp':>3} {'Score':>6}")
    print("-" * 80)
    
    for name, method_func, expected_bets in methods:
        try:
            bets, specials_from_method, description = method_func(history)
            
            # Use special predictor for methods that don't provide their own
            if specials_from_method is None:
                specials_used = special_preds[:len(bets)]
            else:
                specials_used = specials_from_method
            
            multi_result = score_multi_bet(bets, specials_used)
            
            best = multi_result['best']
            results.append({
                'name': name,
                'description': description,
                'bets': bets,
                'specials': specials_used,
                'best_match': best['match_count'],
                'best_matched_nums': best['matched_numbers'],
                'best_special_hit': best['special_hit'],
                'coverage_matches': multi_result['coverage_matches'],
                'coverage_matched_nums': multi_result['coverage_matched_nums'],
                'total_coverage': multi_result['total_coverage'],
                'num_bets': multi_result['num_bets'],
                'closeness': best['closeness'],
                'all_results': multi_result['all_results']
            })
            
            sp_str = "Y" if best['special_hit'] else "N"
            print(f"{name:<45} {multi_result['num_bets']:>4} {best['match_count']:>5} "
                  f"{multi_result['coverage_matches']:>4} {multi_result['total_coverage']:>4} "
                  f"{sp_str:>3} {best['closeness']:>6.1f}")
            
        except Exception as e:
            print(f"{name:<45} ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print("-" * 80)
    print("\nLegend: BestM=Best single-bet matches, CovM=Coverage matches (all bets combined),")
    print("        CovN=Total unique numbers covered, Sp=Special hit, Score=Closeness score")
    
    # Sort by coverage matches (most important) then by best match
    results.sort(key=lambda x: (x['coverage_matches'], x['best_match'], x['closeness']), reverse=True)
    
    # ====== DETAILED RESULTS ======
    print("\n" + "=" * 80)
    print("  DETAILED RESULTS (sorted by coverage matches)")
    print("=" * 80)
    
    for rank, r in enumerate(results, 1):
        cm = r['coverage_matches']
        bm = r['best_match']
        sp = "Special HIT!" if r['best_special_hit'] else ""
        
        print(f"\n{'='*70}")
        print(f"  #{rank}: {r['name']}")
        print(f"  {r['description']}")
        print(f"  Coverage Matches: {cm}/6 {r['coverage_matched_nums']}")
        print(f"  Best Single Bet: M{bm} {r['best_matched_nums']} {sp}")
        print(f"  Total Unique Numbers: {r['total_coverage']}")
        print(f"  Closeness Score: {r['closeness']:.1f}")
        
        for i, bet_result in enumerate(r['all_results']):
            sp_info = ""
            if r['specials'] and i < len(r['specials']):
                sp_val = r['specials'][i]
                sp_hit = "HIT" if sp_val == ACTUAL_SPECIAL else "miss"
                sp_info = f" | Sp: {sp_val} ({sp_hit})"
            
            bet_nums = bet_result['predicted']
            matched = bet_result['matched_numbers']
            mc = bet_result['match_count']
            
            # Highlight matched numbers
            display = []
            for n in bet_nums:
                if n in ACTUAL_NUMBERS:
                    display.append(f"*{n:02d}*")
                else:
                    display.append(f" {n:02d} ")
            
            print(f"    Bet {i+1}: [{', '.join(display)}] -> M{mc} {matched}{sp_info}")
    
    # ====== SUMMARY TABLE ======
    print("\n" + "=" * 80)
    print("  FINAL RANKING - ALL METHODS vs DRAW 115000011")
    print(f"  Actual: {sorted(ACTUAL_NUMBERS)} | Special: {ACTUAL_SPECIAL}")
    print("=" * 80)
    
    print(f"\n{'Rank':<5} {'Method':<42} {'Bets':>4} {'CovM':>5} {'BestM':>6} {'Sp':>4} {'Score':>7}")
    print("-" * 73)
    
    for rank, r in enumerate(results, 1):
        sp_str = "Y" if r['best_special_hit'] else "N"
        marker = ""
        if rank == 1:
            marker = " <-- BEST"
        elif r['coverage_matches'] == results[0]['coverage_matches']:
            marker = " <-- TIE"
        
        print(f"{rank:<5} {r['name']:<42} {r['num_bets']:>4} "
              f"{r['coverage_matches']:>5} {r['best_match']:>6} "
              f"{sp_str:>4} {r['closeness']:>7.1f}{marker}")
    
    # ====== ANALYSIS ======
    print("\n" + "=" * 80)
    print("  ANALYSIS")
    print("=" * 80)
    
    # Best method
    best = results[0]
    print(f"\n  WINNER: {best['name']}")
    print(f"  Coverage Matches: {best['coverage_matches']}/6 -> {best['coverage_matched_nums']}")
    print(f"  Best Single Bet: M{best['best_match']}")
    
    # Actual draw characteristics
    print(f"\n  DRAW 115000011 CHARACTERISTICS:")
    actual_list = sorted(ACTUAL_NUMBERS)
    print(f"    Numbers: {actual_list}")
    print(f"    Sum: {sum(actual_list)}")
    print(f"    Odd/Even: {sum(1 for n in actual_list if n % 2 == 1)}/{sum(1 for n in actual_list if n % 2 == 0)}")
    
    zones = Counter()
    for n in actual_list:
        if 1 <= n <= 10: zones['Z1(1-10)'] += 1
        elif 11 <= n <= 20: zones['Z2(11-20)'] += 1
        elif 21 <= n <= 30: zones['Z3(21-30)'] += 1
        else: zones['Z4(31-38)'] += 1
    print(f"    Zone Distribution: {dict(zones)}")
    
    # Consecutive check
    consec = []
    for i in range(len(actual_list) - 1):
        if actual_list[i + 1] - actual_list[i] == 1:
            consec.append((actual_list[i], actual_list[i + 1]))
    print(f"    Consecutive Pairs: {consec if consec else 'None'}")
    
    tail_digits = [n % 10 for n in actual_list]
    print(f"    Tail Digits: {tail_digits}")
    
    # Special number analysis
    print(f"\n  SPECIAL NUMBER ANALYSIS:")
    print(f"    Actual: {ACTUAL_SPECIAL}")
    print(f"    V3 Top-3: {special_preds}")
    if ACTUAL_SPECIAL in special_preds:
        print(f"    V3 ranked it #{special_preds.index(ACTUAL_SPECIAL) + 1}")
    else:
        print(f"    V3 did NOT include {ACTUAL_SPECIAL} in top-3")
    
    # How many methods got M3+
    m3_plus = [r for r in results if r['coverage_matches'] >= 3]
    print(f"\n  Methods achieving M3+ (coverage): {len(m3_plus)}/{len(results)}")
    for r in m3_plus:
        print(f"    - {r['name']}: M{r['coverage_matches']}")
    
    # Most predicted numbers (across all methods)
    all_predicted_nums = Counter()
    for r in results:
        for bet in r['bets']:
            for n in bet:
                all_predicted_nums[n] += 1
    
    print(f"\n  MOST PREDICTED NUMBERS (across all methods):")
    for n, count in all_predicted_nums.most_common(10):
        hit = "*" if n in ACTUAL_NUMBERS else " "
        print(f"    {hit} {n:2d}: predicted by {count}/{len(results)} methods")
    
    print(f"\n  ACTUAL NUMBERS PREDICTION FREQUENCY:")
    for n in sorted(ACTUAL_NUMBERS):
        count = all_predicted_nums.get(n, 0)
        print(f"    {n:2d}: predicted by {count}/{len(results)} methods ({count/len(results)*100:.0f}%)")

if __name__ == "__main__":
    main()
