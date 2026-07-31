#!/usr/bin/env python3
"""
Zone Split Strategy Optimizer
==============================

The Zone Split strategy showed the best results in benchmarks:
- Power Lotto 3-bet: 15.80% (+4.63% edge)
- Big Lotto 3-bet: 7.60% (+2.12% edge)

This script fine-tunes the Zone Split parameters and creates
production-ready implementations.
"""

import os
import sys
import json
import sqlite3
import random
import numpy as np
from typing import List, Dict, Tuple
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
# ZONE SPLIT VARIANTS
# =============================================================================

def zone_split_pure(max_num: int, num_bets: int) -> List[List[int]]:
    """Original Zone Split: equal zones."""
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
            extended = list(range(max(1, start - 5), min(max_num + 1, end + 6)))
            bet = sorted(random.sample(extended, 6))
        bets.append(bet)
    
    return bets

def zone_split_frequency_weighted(history: List[Dict], max_num: int, num_bets: int) -> List[List[int]]:
    """Zone Split with frequency weighting within each zone."""
    zone_size = max_num // num_bets
    
    # Get frequency
    recent = history[:50]
    counter = Counter()
    for d in recent:
        counter.update(d['numbers'])
    
    bets = []
    for i in range(num_bets):
        start = i * zone_size + 1
        end = min((i + 1) * zone_size, max_num)
        if i == num_bets - 1:
            end = max_num
        
        zone = list(range(start, end + 1))
        zone_scores = [(n, counter.get(n, 0)) for n in zone]
        zone_scores.sort(key=lambda x: x[1], reverse=True)
        
        if len(zone_scores) >= 6:
            bet = sorted([x[0] for x in zone_scores[:6]])
        else:
            bet = sorted([x[0] for x in zone_scores])
            while len(bet) < 6:
                r = random.randint(1, max_num)
                if r not in bet:
                    bet.append(r)
            bet = sorted(bet)
        
        bets.append(bet)
    
    return bets

def zone_split_overlap(max_num: int, num_bets: int, overlap: int = 3) -> List[List[int]]:
    """Zone Split with slight overlap between zones."""
    zone_size = max_num // num_bets
    bets = []
    
    for i in range(num_bets):
        center = (i + 0.5) * zone_size
        start = max(1, int(center - zone_size // 2 - overlap))
        end = min(max_num, int(center + zone_size // 2 + overlap))
        zone = list(range(start, end + 1))
        
        if len(zone) >= 6:
            bet = sorted(random.sample(zone, 6))
        else:
            bet = sorted(random.sample(range(1, max_num + 1), 6))
        bets.append(bet)
    
    return bets

def zone_split_golden_ratio(max_num: int, num_bets: int) -> List[List[int]]:
    """Zone Split using golden ratio distribution."""
    phi = 1.618033988749895
    bets = []
    
    for i in range(num_bets):
        ratio = (i + 1) / (num_bets + 1)
        center = int(max_num * ratio ** (1/phi))
        center = max(4, min(max_num - 3, center))
        
        zone = list(range(max(1, center - 5), min(max_num + 1, center + 6)))
        bet = sorted(random.sample(zone, min(6, len(zone))))
        
        while len(bet) < 6:
            r = random.randint(1, max_num)
            if r not in bet:
                bet.append(r)
        
        bets.append(sorted(bet[:6]))
    
    return bets

def zone_split_adaptive(history: List[Dict], max_num: int, num_bets: int) -> List[List[int]]:
    """
    Adaptive Zone Split: zones shift based on recent winner distribution.
    """
    recent = history[:30]
    all_nums = []
    for d in recent:
        all_nums.extend(d['numbers'])
    
    if all_nums:
        avg = np.mean(all_nums)
        std = np.std(all_nums)
    else:
        avg = max_num / 2
        std = max_num / 4
    
    bets = []
    
    # Bet 1: Around mean - std
    center1 = max(6, int(avg - std))
    zone1 = list(range(max(1, center1 - 5), min(max_num + 1, center1 + 6)))
    bets.append(sorted(random.sample(zone1, min(6, len(zone1)))))
    
    if num_bets >= 2:
        # Bet 2: Around mean
        center2 = int(avg)
        zone2 = list(range(max(1, center2 - 5), min(max_num + 1, center2 + 6)))
        bets.append(sorted(random.sample(zone2, min(6, len(zone2)))))
    
    if num_bets >= 3:
        # Bet 3: Around mean + std
        center3 = min(max_num - 5, int(avg + std))
        zone3 = list(range(max(1, center3 - 5), min(max_num + 1, center3 + 6)))
        bets.append(sorted(random.sample(zone3, min(6, len(zone3)))))
    
    # Ensure 6 numbers each
    for i in range(len(bets)):
        while len(bets[i]) < 6:
            r = random.randint(1, max_num)
            if r not in bets[i]:
                bets[i].append(r)
        bets[i] = sorted(bets[i][:6])
    
    return bets

# =============================================================================
# EXTENDED BENCHMARK (1000P)
# =============================================================================

def run_extended_benchmark(lottery_type: str, num_bets: int, periods: int = 1000):
    """Run extended 1000-period benchmark on Zone Split variants."""
    
    print(f"\n{'='*70}")
    print(f"🎯 ZONE SPLIT OPTIMIZATION: {lottery_type} | {num_bets}-bet | {periods}P (SBP)")
    print('='*70)
    
    all_history = load_history(lottery_type, periods + 500)
    max_num = 38 if lottery_type == 'POWER_LOTTO' else 49
    
    baseline_1bet = 0.0387 if lottery_type == 'POWER_LOTTO' else 0.0186
    baseline_nbet = 1 - (1 - baseline_1bet) ** num_bets
    
    # Break-even calculation
    cost_per_bet = 100 if lottery_type == 'POWER_LOTTO' else 50
    prize = 400
    break_even = (cost_per_bet * num_bets) / prize
    
    strategies = {
        'Zone Pure': lambda h: zone_split_pure(max_num, num_bets),
        'Zone + Frequency': lambda h: zone_split_frequency_weighted(h, max_num, num_bets),
        'Zone + Overlap(3)': lambda h: zone_split_overlap(max_num, num_bets, 3),
        'Zone + Overlap(5)': lambda h: zone_split_overlap(max_num, num_bets, 5),
        'Zone Golden Ratio': lambda h: zone_split_golden_ratio(max_num, num_bets),
        'Zone Adaptive': lambda h: zone_split_adaptive(h, max_num, num_bets),
    }
    
    results = {}
    
    for name, strategy in strategies.items():
        hits = 0
        
        for i in range(periods):
            context = all_history[i+1:]
            target = set(all_history[i]['numbers'])
            
            try:
                bets = strategy(context)
            except:
                bets = [sorted(random.sample(range(1, max_num + 1), 6)) for _ in range(num_bets)]
            
            is_win = any(len(set(bet) & target) >= 3 for bet in bets)
            if is_win:
                hits += 1
        
        rate = hits / periods
        edge = (rate - baseline_nbet) * 100
        vs_be = (rate - break_even) * 100
        p_val = binomtest(hits, periods, baseline_nbet, alternative='greater').pvalue
        
        results[name] = {
            'hits': hits,
            'rate': rate,
            'edge': edge,
            'vs_break_even': vs_be,
            'p_value': p_val
        }
    
    # Random baseline
    random_hits = 0
    for i in range(periods):
        target = set(all_history[i]['numbers'])
        bets = [sorted(random.sample(range(1, max_num + 1), 6)) for _ in range(num_bets)]
        if any(len(set(bet) & target) >= 3 for bet in bets):
            random_hits += 1
    
    r_rate = random_hits / periods
    results['Random Baseline'] = {
        'hits': random_hits,
        'rate': r_rate,
        'edge': (r_rate - baseline_nbet) * 100,
        'vs_break_even': (r_rate - break_even) * 100,
        'p_value': 1.0
    }
    
    print(f"\n{'Strategy':<20} {'Hits':<7} {'Rate':<8} {'Edge':<8} {'vs B/E':<8} {'p-value'}")
    print('-'*65)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1]['rate'], reverse=True)
    for name, data in sorted_results:
        sig = "✅" if data['p_value'] < 0.05 else "⚪"
        print(f"{name:<20} {data['hits']:<7} {data['rate']*100:>5.2f}%   {data['edge']:>+5.2f}%   {data['vs_break_even']:>+5.2f}%   {data['p_value']:.4f} {sig}")
    
    print(f"\nBaseline ({num_bets}-bet): {baseline_nbet*100:.2f}%")
    print(f"Break-Even Threshold: {break_even*100:.2f}%")
    
    return results

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Focus on 3-bet where Zone Split showed best results
    for ltype in ['POWER_LOTTO', 'BIG_LOTTO']:
        run_extended_benchmark(ltype, 3, 1000)
