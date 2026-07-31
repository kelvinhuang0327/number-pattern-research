#!/usr/bin/env python3
"""
Orthogonal Diversification Strategy for 2-3 Bet Optimization
=============================================================

Key insight from benchmarks: all methods underperform random.
This suggests the DIVERSIFICATION of bets matters more than prediction.

Strategy: Generate bets that are maximally orthogonal (non-overlapping).
This maximizes the coverage of the number space.
"""

import os
import sys
import json
import sqlite3
import random
import numpy as np
from typing import List, Dict, Set, Tuple
from itertools import combinations
from collections import Counter
from scipy.stats import binomtest
import logging

random.seed(42)
np.random.seed(42)

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
    cursor.execute("""
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
# ORTHOGONAL BET STRATEGIES
# =============================================================================

def strategy_full_random_orthogonal(max_num: int, num_bets: int) -> List[List[int]]:
    """
    Generate fully random orthogonal bets.
    Each bet shares minimal overlap with others.
    """
    bets = []
    used = set()
    
    for _ in range(num_bets):
        available = [n for n in range(1, max_num + 1) if n not in used]
        if len(available) >= 6:
            bet = sorted(random.sample(available, 6))
        else:
            # Not enough unused, pick some overlap
            bet = sorted(random.sample(range(1, max_num + 1), 6))
        bets.append(bet)
        used.update(bet)
    
    return bets

def strategy_zone_split(max_num: int, num_bets: int) -> List[List[int]]:
    """
    Split number space into zones, each bet covers different zones.
    """
    zone_size = max_num // num_bets
    bets = []
    
    for i in range(num_bets):
        start = i * zone_size + 1
        end = min((i + 1) * zone_size, max_num)
        if i == num_bets - 1:
            end = max_num
        zone = list(range(start, end + 1))
        
        if len(zone) >= 6:
            bet = sorted(random.sample(zone, 6))
        else:
            # Extend from neighbors
            extended = list(range(max(1, start - 3), min(max_num + 1, end + 4)))
            bet = sorted(random.sample(extended, 6))
        bets.append(bet)
    
    return bets

def strategy_hot_cold_split(history: List[Dict], max_num: int, num_bets: int) -> List[List[int]]:
    """
    Bet 1: Hot numbers only
    Bet 2: Cold numbers only
    Bet 3: Mixed
    """
    recent = history[:50]
    counter = Counter()
    for d in recent:
        counter.update(d['numbers'])
    
    all_nums = list(range(1, max_num + 1))
    sorted_by_freq = sorted(all_nums, key=lambda x: counter.get(x, 0), reverse=True)
    
    bets = []
    
    if num_bets >= 1:
        # Bet 1: Top hot
        bets.append(sorted(sorted_by_freq[:6]))
    
    if num_bets >= 2:
        # Bet 2: Coldest
        bets.append(sorted(sorted_by_freq[-6:]))
    
    if num_bets >= 3:
        # Bet 3: Middle tier
        mid_start = len(sorted_by_freq) // 3
        bets.append(sorted(sorted_by_freq[mid_start:mid_start+6]))
    
    return bets

def strategy_odd_even_split(max_num: int, num_bets: int) -> List[List[int]]:
    """
    Bet 1: All odd
    Bet 2: All even
    Bet 3: Mixed 3+3
    """
    odds = [n for n in range(1, max_num + 1) if n % 2 == 1]
    evens = [n for n in range(1, max_num + 1) if n % 2 == 0]
    
    bets = []
    
    if num_bets >= 1:
        bets.append(sorted(random.sample(odds, min(6, len(odds)))))
    
    if num_bets >= 2:
        bets.append(sorted(random.sample(evens, min(6, len(evens)))))
    
    if num_bets >= 3:
        # 3 odd + 3 even
        bet3 = random.sample(odds, 3) + random.sample(evens, 3)
        bets.append(sorted(bet3))
    
    return bets

def strategy_consecutive_spread(max_num: int, num_bets: int) -> List[List[int]]:
    """
    Each bet picks consecutive-friendly patterns in different ranges.
    """
    bets = []
    step = max_num // num_bets
    
    for i in range(num_bets):
        base = i * step + 1
        # Pick 2 consecutive pairs + 2 randoms
        consec1 = [base, base + 1]
        consec2 = [base + step//2, base + step//2 + 1]
        remaining = [n for n in range(base, min(base + step, max_num + 1)) 
                    if n not in consec1 + consec2]
        
        if len(remaining) >= 2:
            extras = random.sample(remaining, 2)
        else:
            extras = random.sample([n for n in range(1, max_num + 1) 
                                   if n not in consec1 + consec2], 2)
        
        bet = sorted(set(consec1 + consec2 + extras))[:6]
        bets.append(bet)
    
    return bets

def strategy_prime_composite(max_num: int, num_bets: int) -> List[List[int]]:
    """
    Bet 1: Prime numbers
    Bet 2: Composite numbers
    """
    def is_prime(n):
        if n < 2: return False
        for i in range(2, int(n**0.5) + 1):
            if n % i == 0: return False
        return True
    
    primes = [n for n in range(1, max_num + 1) if is_prime(n)]
    composites = [n for n in range(1, max_num + 1) if not is_prime(n) and n > 1]
    
    bets = []
    
    if num_bets >= 1 and len(primes) >= 6:
        bets.append(sorted(random.sample(primes, 6)))
    elif num_bets >= 1:
        bets.append(sorted(random.sample(range(1, max_num + 1), 6)))
    
    if num_bets >= 2 and len(composites) >= 6:
        bets.append(sorted(random.sample(composites, 6)))
    elif num_bets >= 2:
        bets.append(sorted(random.sample(range(1, max_num + 1), 6)))
    
    if num_bets >= 3:
        # Mixed
        bet3 = random.sample(primes[:10], 3) + random.sample(composites[:10], 3)
        bets.append(sorted(bet3))
    
    return bets

def strategy_fibonacci_geometric(max_num: int, num_bets: int) -> List[List[int]]:
    """
    Use Fibonacci-like patterns for spacing.
    """
    fib_ratios = [1, 2, 3, 5, 8, 13, 21]
    
    bets = []
    for b in range(num_bets):
        base = 1 + b * 3
        bet = []
        for r in fib_ratios[:6]:
            num = base + r
            if num <= max_num and num not in bet:
                bet.append(num)
        
        while len(bet) < 6:
            rand = random.randint(1, max_num)
            if rand not in bet:
                bet.append(rand)
        
        bets.append(sorted(bet[:6]))
    
    return bets

# =============================================================================
# BENCHMARK
# =============================================================================

def run_orthogonal_benchmark(lottery_type: str, num_bets: int, periods: int = 500):
    """Run orthogonal strategies benchmark."""
    
    print(f"\n{'='*70}")
    print(f"🔀 ORTHOGONAL STRATEGIES: {lottery_type} | {num_bets}-bet | {periods}P")
    print('='*70)
    
    all_history = load_history(lottery_type, periods + 500)
    max_num = 38 if lottery_type == 'POWER_LOTTO' else 49
    
    baseline_1bet = 0.0387 if lottery_type == 'POWER_LOTTO' else 0.0186
    baseline_nbet = 1 - (1 - baseline_1bet) ** num_bets
    
    strategies = {
        'Random Orthogonal': lambda h: strategy_full_random_orthogonal(max_num, num_bets),
        'Zone Split': lambda h: strategy_zone_split(max_num, num_bets),
        'Hot/Cold Split': lambda h: strategy_hot_cold_split(h, max_num, num_bets),
        'Odd/Even Split': lambda h: strategy_odd_even_split(max_num, num_bets),
        'Consecutive Spread': lambda h: strategy_consecutive_spread(max_num, num_bets),
        'Prime/Composite': lambda h: strategy_prime_composite(max_num, num_bets),
        'Fibonacci Pattern': lambda h: strategy_fibonacci_geometric(max_num, num_bets),
    }
    
    results = {}
    
    for name, strategy in strategies.items():
        hits = 0
        total_coverage = 0
        
        for i in range(periods):
            context = all_history[i+1:]
            target = set(all_history[i]['numbers'])
            
            try:
                bets = strategy(context)
            except:
                bets = [sorted(random.sample(range(1, max_num + 1), 6)) for _ in range(num_bets)]
            
            # Coverage calculation
            all_nums_in_bets = set()
            for bet in bets:
                all_nums_in_bets.update(bet)
            coverage = len(all_nums_in_bets) / max_num
            total_coverage += coverage
            
            is_win = any(len(set(bet) & target) >= 3 for bet in bets)
            if is_win:
                hits += 1
        
        rate = hits / periods
        edge = (rate - baseline_nbet) * 100
        avg_coverage = total_coverage / periods
        results[name] = {
            'hits': hits,
            'rate': rate,
            'edge': edge,
            'coverage': avg_coverage
        }
    
    # Random baseline
    random_hits = 0
    for i in range(periods):
        target = set(all_history[i]['numbers'])
        bets = [sorted(random.sample(range(1, max_num + 1), 6)) for _ in range(num_bets)]
        if any(len(set(bet) & target) >= 3 for bet in bets):
            random_hits += 1
    
    results['Pure Random'] = {
        'hits': random_hits,
        'rate': random_hits / periods,
        'edge': (random_hits / periods - baseline_nbet) * 100,
        'coverage': (6 * num_bets) / max_num  # Approximate
    }
    
    print(f"\n{'Strategy':<22} {'Hits':<7} {'Rate':<9} {'Edge':<9} {'Coverage'}")
    print('-'*60)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1]['rate'], reverse=True)
    for name, data in sorted_results:
        print(f"{name:<22} {data['hits']:<7} {data['rate']*100:>5.2f}%    {data['edge']:>+5.2f}%    {data['coverage']*100:>5.1f}%")
    
    print(f"\nBaseline ({num_bets}-bet): {baseline_nbet*100:.2f}%")
    
    return results

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    for ltype in ['POWER_LOTTO', 'BIG_LOTTO']:
        for nbets in [2, 3]:
            run_orthogonal_benchmark(ltype, nbets, 500)
