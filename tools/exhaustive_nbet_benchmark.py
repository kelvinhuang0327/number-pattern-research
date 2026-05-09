#!/usr/bin/env python3
"""
Unified 2-Bet and 3-Bet SBP Benchmark Framework
================================================

Exhaustively tests all prediction methods for 2-bet and 3-bet strategies
using the Standardized Backtest Protocol (SBP).

Goal: Find methods that can achieve break-even for 2-3 bet strategies.
"""

import os
import sys
import json
import sqlite3
import random
import numpy as np
from typing import List, Dict, Callable, Tuple
from itertools import combinations
from collections import Counter
from scipy.stats import binomtest
import logging

# Standardized Seed
random.seed(42)
np.random.seed(42)

logging.basicConfig(level=logging.WARNING)

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

# =============================================================================
# DATA LOADING
# =============================================================================

def load_history(lottery_type: str, max_records: int = 2000) -> List[Dict]:
    db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT draw, numbers, special, date FROM draws 
        WHERE lottery_type = ? 
        ORDER BY draw DESC LIMIT ?
    """, (lottery_type, max_records))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        nums = json.loads(r[1]) if isinstance(r[1], str) else []
        special = r[2]
        if len(nums) == 6:
            history.append({
                'draw': r[0], 
                'numbers': nums, 
                'special': int(special) if special else None, 
                'date': r[3]
            })
    return history

# =============================================================================
# BASELINE CALCULATIONS
# =============================================================================

def get_baselines(lottery_type: str, num_bets: int) -> Dict:
    """Calculate theoretical baselines for given lottery and bet count."""
    if lottery_type == 'POWER_LOTTO':
        max_num = 38
        baseline_1bet = 0.0387  # M3+ for 6/38
    else:  # BIG_LOTTO
        max_num = 49
        baseline_1bet = 0.0186  # M3+ for 6/49
    
    # n-bet baseline: 1 - (1 - p)^n
    baseline_nbet = 1 - (1 - baseline_1bet) ** num_bets
    
    # Break-even calculation (assuming 400 TWD prize, 100 TWD per bet for Power, 50 for Big)
    cost_per_bet = 100 if lottery_type == 'POWER_LOTTO' else 50
    prize = 400
    break_even = (cost_per_bet * num_bets) / prize
    
    return {
        'baseline_1bet': baseline_1bet,
        'baseline_nbet': baseline_nbet,
        'break_even': break_even,
        'max_num': max_num
    }

# =============================================================================
# PREDICTION METHODS
# =============================================================================

def method_frequency_hot(history: List[Dict], max_num: int) -> List[int]:
    """Hot numbers from recent 50 draws."""
    recent = history[:50]
    counter = Counter()
    for d in recent:
        counter.update(d['numbers'])
    return [n for n, _ in counter.most_common(6)]

def method_frequency_cold(history: List[Dict], max_num: int) -> List[int]:
    """Cold numbers - least frequent in recent 100 draws."""
    recent = history[:100]
    counter = Counter()
    for d in recent:
        counter.update(d['numbers'])
    all_nums = set(range(1, max_num + 1))
    for n in all_nums:
        if n not in counter:
            counter[n] = 0
    return [n for n, _ in counter.most_common()[-6:]]

def method_gap_pressure(history: List[Dict], max_num: int) -> List[int]:
    """Numbers with highest gap pressure (overdue)."""
    gaps = {n: 0 for n in range(1, max_num + 1)}
    for n in gaps:
        for i, d in enumerate(history):
            if n in d['numbers']:
                gaps[n] = i
                break
        else:
            gaps[n] = len(history)
    sorted_gaps = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
    return [n for n, _ in sorted_gaps[:6]]

def method_markov_transition(history: List[Dict], max_num: int) -> List[int]:
    """Markov chain: predict based on last draw transitions."""
    if len(history) < 2:
        return list(range(1, 7))
    
    last_draw = set(history[0]['numbers'])
    transitions = Counter()
    
    for i in range(1, len(history) - 1):
        prev = set(history[i+1]['numbers'])
        curr = set(history[i]['numbers'])
        for p in prev:
            for c in curr:
                transitions[(p, c)] += 1
    
    scores = Counter()
    for n in last_draw:
        for target in range(1, max_num + 1):
            scores[target] += transitions.get((n, target), 0)
    
    return [n for n, _ in scores.most_common(6)]

def method_zone_balance(history: List[Dict], max_num: int) -> List[int]:
    """Balanced zone selection: 2 numbers from each zone."""
    zone_size = max_num // 3
    zones = [
        list(range(1, zone_size + 1)),
        list(range(zone_size + 1, 2 * zone_size + 1)),
        list(range(2 * zone_size + 1, max_num + 1))
    ]
    
    # Get hot numbers per zone
    recent = history[:50]
    counter = Counter()
    for d in recent:
        counter.update(d['numbers'])
    
    result = []
    for zone in zones:
        zone_scores = [(n, counter.get(n, 0)) for n in zone]
        zone_scores.sort(key=lambda x: x[1], reverse=True)
        result.extend([n for n, _ in zone_scores[:2]])
    
    return sorted(result[:6])

def method_odd_even_balance(history: List[Dict], max_num: int) -> List[int]:
    """3 odd + 3 even, prioritized by frequency."""
    recent = history[:50]
    counter = Counter()
    for d in recent:
        counter.update(d['numbers'])
    
    odds = [(n, counter.get(n, 0)) for n in range(1, max_num + 1) if n % 2 == 1]
    evens = [(n, counter.get(n, 0)) for n in range(1, max_num + 1) if n % 2 == 0]
    
    odds.sort(key=lambda x: x[1], reverse=True)
    evens.sort(key=lambda x: x[1], reverse=True)
    
    return sorted([odds[i][0] for i in range(3)] + [evens[i][0] for i in range(3)])

def method_sum_optimal(history: List[Dict], max_num: int) -> List[int]:
    """Target optimal sum range based on historical distribution."""
    recent = history[:200]
    sums = [sum(d['numbers']) for d in recent]
    avg_sum = sum(sums) / len(sums)
    
    # Generate candidates and pick closest to avg_sum
    from itertools import combinations as combs
    all_nums = list(range(1, max_num + 1))
    
    # Sample for efficiency
    random.seed(42)
    candidates = [random.sample(all_nums, 6) for _ in range(1000)]
    
    best = None
    best_diff = float('inf')
    for c in candidates:
        s = sum(c)
        diff = abs(s - avg_sum)
        if diff < best_diff:
            best_diff = diff
            best = c
    
    return sorted(best)

def method_clustering_centroid(history: List[Dict], max_num: int) -> List[int]:
    """K-Means inspired: find cluster centroids."""
    recent = history[:100]
    vectors = []
    for d in recent:
        vec = [1 if i in d['numbers'] else 0 for i in range(1, max_num + 1)]
        vectors.append(vec)
    
    avg_vec = np.mean(vectors, axis=0)
    indexed = [(i+1, avg_vec[i]) for i in range(len(avg_vec))]
    indexed.sort(key=lambda x: x[1], reverse=True)
    
    return [n for n, _ in indexed[:6]]

def method_entropy_max(history: List[Dict], max_num: int) -> List[int]:
    """Maximize entropy: pick numbers that diversify coverage."""
    recent = history[:100]
    cooccur = Counter()
    for d in recent:
        for pair in combinations(sorted(d['numbers']), 2):
            cooccur[pair] += 1
    
    # Pick numbers that minimize co-occurrence
    scores = {n: 0 for n in range(1, max_num + 1)}
    for (a, b), count in cooccur.items():
        scores[a] += count
        scores[b] += count
    
    sorted_scores = sorted(scores.items(), key=lambda x: x[1])
    return [n for n, _ in sorted_scores[:6]]

def method_anti_repeat(history: List[Dict], max_num: int) -> List[int]:
    """Avoid all numbers from last draw."""
    if not history:
        return list(range(1, 7))
    
    last = set(history[0]['numbers'])
    candidates = [n for n in range(1, max_num + 1) if n not in last]
    
    # From candidates, pick by frequency
    recent = history[:50]
    counter = Counter()
    for d in recent:
        counter.update(d['numbers'])
    
    cand_scores = [(n, counter.get(n, 0)) for n in candidates]
    cand_scores.sort(key=lambda x: x[1], reverse=True)
    
    return [n for n, _ in cand_scores[:6]]

def method_tail_pattern(history: List[Dict], max_num: int) -> List[int]:
    """Select based on last digit patterns."""
    recent = history[:50]
    tail_counter = Counter()
    for d in recent:
        for n in d['numbers']:
            tail_counter[n % 10] += 1
    
    # Best tails
    best_tails = [t for t, _ in tail_counter.most_common(6)]
    
    # Pick one number per tail
    result = []
    for tail in best_tails:
        for n in range(tail if tail > 0 else 10, max_num + 1, 10):
            if n <= max_num and n not in result:
                result.append(n)
                break
        if len(result) >= 6:
            break
    
    # Fill if needed
    while len(result) < 6:
        for n in range(1, max_num + 1):
            if n not in result:
                result.append(n)
                break
    
    return sorted(result[:6])

def method_hybrid_hot_cold(history: List[Dict], max_num: int) -> List[int]:
    """3 hot + 3 cold numbers."""
    hot = method_frequency_hot(history, max_num)[:3]
    cold = method_frequency_cold(history, max_num)[:3]
    return sorted(list(set(hot + cold))[:6])

def method_random_baseline(history: List[Dict], max_num: int) -> List[int]:
    """Random baseline for comparison."""
    return sorted(random.sample(range(1, max_num + 1), 6))

# =============================================================================
# DIVERSIFIED N-BET GENERATION
# =============================================================================

def generate_diverse_nbets(history: List[Dict], max_num: int, num_bets: int, 
                           methods: List[Callable]) -> List[List[int]]:
    """Generate n diverse bets using different methods."""
    bets = []
    used_methods = []
    
    for i in range(num_bets):
        method = methods[i % len(methods)]
        bet = method(history, max_num)
        bets.append(bet)
        used_methods.append(method.__name__)
    
    return bets

# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def run_benchmark(lottery_type: str, num_bets: int, periods: int = 500) -> Dict:
    """Run SBP benchmark for given lottery and bet count."""
    
    print(f"\n{'='*70}")
    print(f"📊 SBP BENCHMARK: {lottery_type} | {num_bets}-bet | {periods} periods")
    print('='*70)
    
    all_history = load_history(lottery_type, periods + 500)
    baselines = get_baselines(lottery_type, num_bets)
    
    # All methods to test
    all_methods = [
        method_frequency_hot,
        method_frequency_cold,
        method_gap_pressure,
        method_markov_transition,
        method_zone_balance,
        method_odd_even_balance,
        method_sum_optimal,
        method_clustering_centroid,
        method_entropy_max,
        method_anti_repeat,
        method_tail_pattern,
        method_hybrid_hot_cold,
    ]
    
    results = {}
    
    # Single method benchmark (each method used for all bets)
    for method in all_methods:
        hits = 0
        for i in range(periods):
            context = all_history[i+1:]
            target = set(all_history[i]['numbers'])
            
            bets = [method(context, baselines['max_num']) for _ in range(num_bets)]
            
            is_win = any(len(set(bet) & target) >= 3 for bet in bets)
            if is_win:
                hits += 1
        
        rate = hits / periods
        edge = (rate - baselines['baseline_nbet']) * 100
        results[method.__name__] = {
            'hits': hits,
            'rate': rate,
            'edge': edge
        }
    
    # Diverse method combinations
    diverse_hits = 0
    for i in range(periods):
        context = all_history[i+1:]
        target = set(all_history[i]['numbers'])
        
        bets = generate_diverse_nbets(context, baselines['max_num'], num_bets, all_methods)
        
        is_win = any(len(set(bet) & target) >= 3 for bet in bets)
        if is_win:
            diverse_hits += 1
    
    diverse_rate = diverse_hits / periods
    diverse_edge = (diverse_rate - baselines['baseline_nbet']) * 100
    results['DIVERSE_ENSEMBLE'] = {
        'hits': diverse_hits,
        'rate': diverse_rate,
        'edge': diverse_edge
    }
    
    # Random baseline
    random_hits = 0
    for i in range(periods):
        target = set(all_history[i]['numbers'])
        bets = [method_random_baseline([], baselines['max_num']) for _ in range(num_bets)]
        is_win = any(len(set(bet) & target) >= 3 for bet in bets)
        if is_win:
            random_hits += 1
    
    results['RANDOM_BASELINE'] = {
        'hits': random_hits,
        'rate': random_hits / periods,
        'edge': (random_hits / periods - baselines['baseline_nbet']) * 100
    }
    
    # Print results
    print(f"\n{'Method':<25} {'Hits':<8} {'Rate':<10} {'Edge':<10} {'Break-Even'}")
    print('-'*70)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1]['rate'], reverse=True)
    for name, data in sorted_results:
        be_status = "✅" if data['rate'] >= baselines['break_even'] else "❌"
        print(f"{name:<25} {data['hits']:<8} {data['rate']*100:>6.2f}%    {data['edge']:>+6.2f}%    {be_status}")
    
    print(f"\nBaseline ({num_bets}-bet): {baselines['baseline_nbet']*100:.2f}%")
    print(f"Break-Even Threshold: {baselines['break_even']*100:.2f}%")
    
    return {
        'lottery_type': lottery_type,
        'num_bets': num_bets,
        'periods': periods,
        'baselines': baselines,
        'results': results
    }

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Power Lotto benchmarks
    run_benchmark('POWER_LOTTO', 2, 500)
    run_benchmark('POWER_LOTTO', 3, 500)
    
    # Big Lotto benchmarks
    run_benchmark('BIG_LOTTO', 2, 500)
    run_benchmark('BIG_LOTTO', 3, 500)
