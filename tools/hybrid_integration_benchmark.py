#!/usr/bin/env python3
"""
Hybrid Integration: Zone Split + Production Predictors
=======================================================

Combine the Zone Split orthogonalization with existing production
prediction methods to see if synergy exists.

Key hypothesis: Zone Split provides diversification, while prediction
methods select within zones. This could combine benefits.
"""

import os
import sys
import json
import sqlite3
import random
import numpy as np
from typing import List, Dict
from collections import Counter
from scipy.stats import binomtest

random.seed(42)
np.random.seed(42)

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.multi_bet_optimizer import MultiBetOptimizer

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
# HYBRID STRATEGIES
# =============================================================================

def hybrid_zone_frequency(history: List[Dict], max_num: int, num_bets: int) -> List[List[int]]:
    """
    Zone Split with frequency-weighted selection within each zone.
    """
    zone_size = max_num // num_bets
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
        
        # Take top 6 by frequency within zone
        bet = sorted([x[0] for x in zone_scores[:6]])
        
        if len(bet) < 6:
            remaining = [n for n in zone if n not in bet]
            bet.extend(remaining[:6 - len(bet)])
        
        bets.append(sorted(bet[:6]))
    
    return bets

def hybrid_zone_gap(history: List[Dict], max_num: int, num_bets: int) -> List[List[int]]:
    """
    Zone Split with gap-pressure selection within each zone.
    """
    zone_size = max_num // num_bets
    
    # Calculate gaps
    gaps = {n: 0 for n in range(1, max_num + 1)}
    for n in gaps:
        for i, d in enumerate(history):
            if n in d['numbers']:
                gaps[n] = i
                break
        else:
            gaps[n] = len(history)
    
    bets = []
    for i in range(num_bets):
        start = i * zone_size + 1
        end = min((i + 1) * zone_size, max_num)
        if i == num_bets - 1:
            end = max_num
        
        zone = list(range(start, end + 1))
        zone_scores = [(n, gaps.get(n, 0)) for n in zone]
        zone_scores.sort(key=lambda x: x[1], reverse=True)  # Highest gap first
        
        bet = sorted([x[0] for x in zone_scores[:6]])
        
        if len(bet) < 6:
            remaining = [n for n in zone if n not in bet]
            bet.extend(remaining[:6 - len(bet)])
        
        bets.append(sorted(bet[:6]))
    
    return bets

def hybrid_zone_entropy(history: List[Dict], max_num: int, num_bets: int) -> List[List[int]]:
    """
    Zone Split with entropy-maximizing selection (low co-occurrence).
    """
    zone_size = max_num // num_bets
    
    # Build co-occurrence matrix
    cooccur = Counter()
    for d in history[:100]:
        nums = d['numbers']
        for i, a in enumerate(nums):
            for b in nums[i+1:]:
                cooccur[(min(a,b), max(a,b))] += 1
    
    # Score each number by total co-occurrence (lower = more entropy)
    scores = {n: 0 for n in range(1, max_num + 1)}
    for (a, b), count in cooccur.items():
        scores[a] += count
        scores[b] += count
    
    bets = []
    for i in range(num_bets):
        start = i * zone_size + 1
        end = min((i + 1) * zone_size, max_num)
        if i == num_bets - 1:
            end = max_num
        
        zone = list(range(start, end + 1))
        zone_scores = [(n, scores.get(n, 0)) for n in zone]
        zone_scores.sort(key=lambda x: x[1])  # Lowest co-occurrence first
        
        bet = sorted([x[0] for x in zone_scores[:6]])
        
        if len(bet) < 6:
            remaining = [n for n in zone if n not in bet]
            bet.extend(remaining[:6 - len(bet)])
        
        bets.append(sorted(bet[:6]))
    
    return bets

def hybrid_production_optimizer(history: List[Dict], lottery_type: str, num_bets: int) -> List[List[int]]:
    """
    Use the production MultiBetOptimizer.
    """
    optimizer = MultiBetOptimizer()
    rules = {
        'minNumber': 1,
        'maxNumber': 38 if lottery_type == 'POWER_LOTTO' else 49,
        'pickCount': 6,
        'lotteryType': lottery_type
    }
    
    try:
        result = optimizer.generate_optimized_bets(history, rules, num_bets)
        bets = [b['numbers'] for b in result['bets'][:num_bets]]
        return bets
    except Exception as e:
        print(f"Optimizer error: {e}")
        return [sorted(random.sample(range(1, rules['maxNumber'] + 1), 6)) for _ in range(num_bets)]

def hybrid_mixed_strategy(history: List[Dict], max_num: int, num_bets: int) -> List[List[int]]:
    """
    Bet 1: Zone 1 + Frequency
    Bet 2: Zone 2 + Gap Pressure
    Bet 3: Zone 3 + Entropy
    """
    zone_size = max_num // 3
    
    # Frequency for Bet 1
    recent = history[:50]
    counter = Counter()
    for d in recent:
        counter.update(d['numbers'])
    
    zone1 = list(range(1, zone_size + 1))
    zone1_scores = [(n, counter.get(n, 0)) for n in zone1]
    zone1_scores.sort(key=lambda x: x[1], reverse=True)
    bet1 = sorted([x[0] for x in zone1_scores[:6]])
    
    # Gap for Bet 2
    gaps = {n: 0 for n in range(1, max_num + 1)}
    for n in gaps:
        for i, d in enumerate(history):
            if n in d['numbers']:
                gaps[n] = i
                break
        else:
            gaps[n] = len(history)
    
    zone2 = list(range(zone_size + 1, 2 * zone_size + 1))
    zone2_scores = [(n, gaps.get(n, 0)) for n in zone2]
    zone2_scores.sort(key=lambda x: x[1], reverse=True)
    bet2 = sorted([x[0] for x in zone2_scores[:6]])
    
    # Entropy for Bet 3
    cooccur = Counter()
    for d in history[:100]:
        nums = d['numbers']
        for i, a in enumerate(nums):
            for b in nums[i+1:]:
                cooccur[(min(a,b), max(a,b))] += 1
    
    scores = {n: 0 for n in range(1, max_num + 1)}
    for (a, b), count in cooccur.items():
        scores[a] += count
        scores[b] += count
    
    zone3 = list(range(2 * zone_size + 1, max_num + 1))
    zone3_scores = [(n, scores.get(n, 0)) for n in zone3]
    zone3_scores.sort(key=lambda x: x[1])
    bet3 = sorted([x[0] for x in zone3_scores[:6]])
    
    bets = [bet1, bet2, bet3][:num_bets]
    
    # Ensure 6 numbers each
    for i in range(len(bets)):
        while len(bets[i]) < 6:
            r = random.randint(1, max_num)
            if r not in bets[i]:
                bets[i].append(r)
        bets[i] = sorted(bets[i][:6])
    
    return bets

# =============================================================================
# BENCHMARK
# =============================================================================

def run_hybrid_benchmark(lottery_type: str, num_bets: int, periods: int = 1000):
    """Extended hybrid benchmark."""
    
    print(f"\n{'='*70}")
    print(f"🔧 HYBRID STRATEGIES: {lottery_type} | {num_bets}-bet | {periods}P")
    print('='*70)
    
    all_history = load_history(lottery_type, periods + 500)
    max_num = 38 if lottery_type == 'POWER_LOTTO' else 49
    
    baseline_1bet = 0.0387 if lottery_type == 'POWER_LOTTO' else 0.0186
    baseline_nbet = 1 - (1 - baseline_1bet) ** num_bets
    
    strategies = {
        'Zone + Frequency': lambda h: hybrid_zone_frequency(h, max_num, num_bets),
        'Zone + Gap Press': lambda h: hybrid_zone_gap(h, max_num, num_bets),
        'Zone + Entropy': lambda h: hybrid_zone_entropy(h, max_num, num_bets),
        'Mixed Strategy': lambda h: hybrid_mixed_strategy(h, max_num, num_bets),
        'Prod Optimizer': lambda h: hybrid_production_optimizer(h, lottery_type, num_bets),
    }
    
    results = {}
    
    for name, strategy in strategies.items():
        hits = 0
        
        for i in range(periods):
            context = all_history[i+1:]
            target = set(all_history[i]['numbers'])
            
            try:
                bets = strategy(context)
            except Exception as e:
                bets = [sorted(random.sample(range(1, max_num + 1), 6)) for _ in range(num_bets)]
            
            is_win = any(len(set(bet) & target) >= 3 for bet in bets)
            if is_win:
                hits += 1
        
        rate = hits / periods
        edge = (rate - baseline_nbet) * 100
        p_val = binomtest(hits, periods, baseline_nbet, alternative='greater').pvalue
        
        results[name] = {'hits': hits, 'rate': rate, 'edge': edge, 'p_value': p_val}
    
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
        'p_value': 1.0
    }
    
    print(f"\n{'Strategy':<18} {'Hits':<7} {'Rate':<8} {'Edge':<8} {'p-value'}")
    print('-'*50)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1]['rate'], reverse=True)
    for name, data in sorted_results:
        sig = "✅" if data['p_value'] < 0.05 else "⚪"
        print(f"{name:<18} {data['hits']:<7} {data['rate']*100:>5.2f}%   {data['edge']:>+5.2f}%   {data['p_value']:.4f} {sig}")
    
    print(f"\nBaseline ({num_bets}-bet): {baseline_nbet*100:.2f}%")
    
    return results

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    for ltype in ['POWER_LOTTO', 'BIG_LOTTO']:
        run_hybrid_benchmark(ltype, 3, 1000)
