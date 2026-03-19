#!/usr/bin/env python3
"""
Optimization: Big Lotto Cluster Pivot (Enhanced)
目標: 優化已驗證有效的 Cluster Pivot 策略，嘗試提升 Win Rate 和 ROI。
優化方向:
1. Dynamic Expansion: 引入隨機性擴展 (不再總是選 Top-K 共現)，增加覆蓋率。
2. Negative Filtering: 整合 NegativeSelector 排除廢號。
"""

import sys
import os
import json
import random
import numpy as np
from collections import Counter
from typing import List, Dict, Set

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from tools.backtest_cluster_pivot_biglotto import get_all_draws, build_cooccurrence_matrix, find_cluster_centers

# SEED for reproducibility
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

def expand_from_anchor_dynamic(anchor: int, cooccur: Dict, max_num: int = 49,
                               pick_count: int = 6, exclude: Set[int] = None,
                               temperature: float = 1.0) -> List[int]:
    """
    動態擴展選號 (Weighted Random Walk)
    temperature: 控制隨機性 (0.0 = Greedy Top-K, 1.0 = Weighted Prob)
    """
    if exclude is None:
        exclude = set()

    # 找出與錨點共現的號碼及其權重
    candidates = {}
    for (a, b), count in cooccur.items():
        curr = None
        if a == anchor and b not in exclude: curr = b
        elif b == anchor and a not in exclude: curr = a
        
        if curr:
            candidates[curr] = count

    # 確保錨點在內
    selected = [anchor]
    
    # 剩餘名額
    needed = pick_count - 1
    if needed <= 0: return [anchor]
    
    # 準備權重池
    search_space = []
    weights = []
    
    for num in range(1, max_num + 1):
        if num == anchor or num in exclude: continue
        search_space.append(num)
        w = candidates.get(num, 0.1) # base weight for non-cooccurring
        weights.append(w)
        
    if not search_space:
        return selected # Should not happen

    # Normalize weights
    weights = np.array(weights)
    weights = weights / weights.sum()
    
    # Weighted Sample
    # If temperature is low, sharpen the distribution (closer to greedy)
    if temperature < 1.0:
        weights = weights ** (1/temperature)
        weights = weights / weights.sum()
        
    chosen = np.random.choice(search_space, size=min(len(search_space), needed), replace=False, p=weights)
    selected.extend(chosen)
    
    return sorted(selected)

def cluster_pivot_optimized(history: List[Dict], max_num: int = 49,
                            pick_count: int = 6, num_bets: int = 4,
                            negative_pool: Set[int] = None) -> List[List[int]]:
    
    if len(history) < 50: return []
    
    cooccur = build_cooccurrence_matrix(history, max_num)
    centers = find_cluster_centers(cooccur, max_num, top_k=num_bets + 5) # Get more candidates
    
    if len(centers) < num_bets: return []
    
    # Filter centers if they are in negative pool? 
    # Maybe bad idea to exclude Pivot itself, but exclude expansion targets.
    if negative_pool is None: negative_pool = set()
    
    bets = []
    used_anchors = set()
    
    # Strategy: 
    # Bet 1: Greedy (Top Pivot, Top Co-occur) - Stability
    # Bet 2-4: Dynamic (Top Pivot, Weighted Co-occur) - Exploration
    
    # Bet 1: Greedy
    if centers[0] not in negative_pool:
        bet1 = expand_from_anchor_dynamic(centers[0], cooccur, max_num, pick_count, 
                                          exclude=negative_pool, temperature=0.1) # Low temp ~ Greedy
        bets.append(bet1)
        used_anchors.add(centers[0])
    
    # Bets 2+: Dynamic
    curr_center_idx = 1
    while len(bets) < num_bets and curr_center_idx < len(centers):
        anchor = centers[curr_center_idx]
        if anchor in used_anchors or anchor in negative_pool:
            curr_center_idx += 1
            continue
            
        # exclude used numbers from previous bets to ensure diversity? 
        # Or just exclude anchors? Let's exclude numbers from Bet 1 to force orthogonality
        exclude_set = negative_pool.copy()
        if len(bets) > 0:
            exclude_set.update(bets[0]) 
            
        bet = expand_from_anchor_dynamic(anchor, cooccur, max_num, pick_count,
                                         exclude=exclude_set, temperature=0.8) # High temp
        bets.append(bet)
        used_anchors.add(anchor)
        curr_center_idx += 1
        
    return bets

def run_optimization_backtest():
    print("=" * 80)
    print("🚀 Optimization: Big Lotto Cluster Pivot (Dynamic + Negative Filter)")
    print("=" * 80)
    
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws(db_path, lottery_type='BIG_LOTTO')
    
    test_periods = 150
    start_idx = len(all_draws) - test_periods
    
    # Baseline: Original 4-bet Cluster Pivot
    # (We can use import logic or re-impl. For strict comparison, let's assume baseline ~7% win rate)
    
    # Simulated Negative Pool (Since we don't have the full NegativeSelector loaded here easily)
    # We will simulate a "Perfect" negative selector that knows 5 correct negative numbers
    # To see theoretical upper bound if Negative Selector works.
    # OR better: use a simple frequency-based negative selector (e.g., coldest 5 numbers)
    
    results = {'total': 0, 'm3': 0, 'm4': 0, 'score': 0}
    
    print(f"Testing Range: {all_draws[start_idx]['draw_number']} ~ {all_draws[-1]['draw_number']}")
    
    random_score_acc = 0
    total_cost = 0
    
    for i in range(start_idx, len(all_draws)):
        target = all_draws[i]
        history = all_draws[:i]
        actual = set(target['numbers'])
        
        # Simple Negative Selector: Last 10 draws, pick 5 random numbers that didn't appear? 
        # No, let's use "Coldest 5 in last 50 draws" as negative pool
        recent_nums = [n for d in history[-50:] for n in d['numbers']]
        freq = Counter(recent_nums)
        # 1-49
        all_n = list(range(1, 50))
        sorted_cold = sorted(all_n, key=lambda n: freq.get(n, 0))
        negative_pool = set(sorted_cold[:5]) # Bottom 5 cold numbers
        
        # Checking if negative pool was actually negative (Safe to remove?)
        # If actual winning number is in negative_pool, we accidentally killed a winner.
        # This is part of the test.
        
        bets = cluster_pivot_optimized(history, max_num=49, num_bets=4, negative_pool=negative_pool)
        
        max_match = 0
        for bet in bets:
            m = len(set(bet) & actual)
            max_match = max(max_match, m)
            
        results['total'] += 1
        if max_match >= 3: results['m3'] += 1
        if max_match >= 4: results['m4'] += 1
        
        prize = (100000000 if max_match==6 else 20000 if max_match==5 else 2000 if max_match==4 else 400 if max_match==3 else 0)
        results['score'] += prize
        total_cost += 400 # 4 bets * 100
        
        # Random Baseline Update
        # 4 random bets
        r_max = 0
        for _ in range(4):
            rb = set(random.sample(range(1, 50), 6))
            r_max = max(r_max, len(rb & actual))
        r_prize = (100000000 if r_max==6 else 20000 if r_max==5 else 2000 if r_max==4 else 400 if r_max==3 else 0)
        random_score_acc += r_prize
        
        if (i - start_idx) % 50 == 0:
            print(f"Progress: {i}/{len(all_draws)}")
            
    # Stats
    win_rate = results['m3'] / results['total'] * 100
    roi = (results['score'] - total_cost) / total_cost * 100
    random_roi = (random_score_acc - total_cost) / total_cost * 100
    
    print("\n" + "="*80)
    print("📊 Big Lotto Optimization Results")
    print("="*80)
    print(f"Strategy: Cluster Pivot (Dynamic + Cold Filter)")
    print(f"Win Rate: {win_rate:.2f}% ({results['m3']}/{results['total']})")
    print(f"Match 4+: {results['m4']}")
    print(f"Total Score: {results['score']}")
    print(f"ROI: {roi:+.1f}%")
    print(f"Random Baseline ROI: {random_roi:+.1f}%")
    print(f"Edge: {roi - random_roi:+.1f}%")

if __name__ == '__main__':
    run_optimization_backtest()
