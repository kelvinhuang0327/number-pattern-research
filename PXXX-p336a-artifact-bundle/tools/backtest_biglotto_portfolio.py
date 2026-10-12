#!/usr/bin/env python3
"""
Backtest: Big Lotto Optimized Portfolio (4 Bets)
組合策略：
1. 主力 (Bets 1-3): Standard Cluster Pivot (3 Bets) -> 抓長期結構
2. 輔助 (Bet 4): Hybrid Strategy (Top 1 Bet) -> 抓近期/長期混合趨勢
目標: 驗證 "3+1" 用法是否比 "4注 Cluster Pivot" 或 "3+Random" 更優。
"""

import sys
import os
import json
import random
import numpy as np
from collections import Counter
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

# Import existing logic
from tools.backtest_cluster_pivot_biglotto import (
    get_all_draws, 
    cluster_pivot_3bet, 
    cluster_pivot_hybrid,
    cluster_pivot_windowed
)

# SEED for reproducibility
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

def run_portfolio_backtest():
    print("=" * 80)
    print("🔬 Big Lotto Portfolio Backtest (3+1 Strategy)")
    print("=" * 80)
    
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws(db_path, lottery_type='BIG_LOTTO')
    
    test_periods = 150
    start_idx = len(all_draws) - test_periods
    
    print(f"Testing Range: {all_draws[start_idx]['draw_number']} ~ {all_draws[-1]['draw_number']}")
    
    # Trackers
    results_portfolio = {'m3': 0, 'm4': 0, 'total_draws': 0, 'total_bets': 0, 'score': 0, 'cost': 0}
    results_baseline = {'m3': 0, 'm4': 0, 'total_draws': 0, 'total_bets': 0, 'score': 0, 'cost': 0}
    
    for i in range(start_idx, len(all_draws)):
        target = all_draws[i]
        history = all_draws[:i]
        actual = set(target['numbers'])
        
        if len(history) < 100: continue
        
        # --- Strategy A: Portfolio (3 Cluster + 1 Hybrid) ---
        bets_portfolio = []
        
        # 1. Core: 3 Bets from Cluster Pivot
        core_bets = cluster_pivot_3bet(history, max_num=49)
        if core_bets:
            bets_portfolio.extend(core_bets[:3])
            
        # 2. Aux: 1 Bet from Hybrid (The best one)
        # Note: Hybrid returns multiple bets. We take the first one (usually strongest).
        # We must ensure it's not a duplicate of core bets.
        aux_bets = cluster_pivot_hybrid(history, max_num=49, num_bets=1) # Get top hybrid bet
        if aux_bets:
            aux_bet = aux_bets[0]
            if aux_bet not in bets_portfolio:
                bets_portfolio.append(aux_bet)
                
        # Fill if missing (rare)
        while len(bets_portfolio) < 4:
            # Fallback to simple windowed 50
            w50 = cluster_pivot_windowed(history, window=50, num_bets=1)
            if w50 and w50[0] not in bets_portfolio:
                bets_portfolio.append(w50[0])
            else:
                break # Should not happen often
                
        # Normalize to 4 bets max
        bets_portfolio = bets_portfolio[:4]
        
        # --- Strategy B: Baseline (4 Random Bets) ---
        bets_baseline = []
        for _ in range(4):
            bets_baseline.append(sorted(random.sample(range(1, 50), 6)))
            
        # --- Evaluate Portfolio ---
        max_m_port = 0
        for bet in bets_portfolio:
            m = len(set(bet) & actual)
            max_m_port = max(max_m_port, m)
            
        results_portfolio['total_draws'] += 1
        if max_m_port >= 3: results_portfolio['m3'] += 1
        if max_m_port >= 4: results_portfolio['m4'] += 1
        
        prize_port = (100000000 if max_m_port==6 else 20000 if max_m_port==5 else 2000 if max_m_port==4 else 400 if max_m_port==3 else 0)
        results_portfolio['score'] += prize_port
        results_portfolio['cost'] += len(bets_portfolio) * 50 # 50 NTD per bet
        results_portfolio['total_bets'] += len(bets_portfolio)
        
        
        # --- Evaluate Baseline ---
        results_baseline['total_draws'] += 1  # Update baseline count
        max_m_base = 0
        for bet in bets_baseline:
            m = len(set(bet) & actual)
            max_m_base = max(max_m_base, m)
            
        if max_m_base >= 3: results_baseline['m3'] += 1
        if max_m_base >= 4: results_baseline['m4'] += 1
        
        prize_base = (100000000 if max_m_base==6 else 20000 if max_m_base==5 else 2000 if max_m_base==4 else 400 if max_m_base==3 else 0)
        results_baseline['score'] += prize_base
        results_baseline['cost'] += 200 # 4 bets * 50

    # Output
    print("\n" + "="*80)
    print("📊 Portfolio Results (3 Cluster + 1 Hybrid)")
    print("="*80)
    
    # Portfolio Stats
    p_win_rate = results_portfolio['m3'] / results_portfolio['total_draws'] * 100
    p_roi = (results_portfolio['score'] - results_portfolio['cost']) / results_portfolio['cost'] * 100
    
    # Baseline Stats
    b_win_rate = results_baseline['m3'] / results_baseline['total_draws'] * 100
    b_roi = (results_baseline['score'] - results_baseline['cost']) / results_baseline['cost'] * 100
    
    print(f"Portfolio Win Rate: {p_win_rate:.2f}%")
    print(f"Portfolio ROI     : {p_roi:.1f}%")
    print(f"Match 4+: {results_portfolio['m4']}")
    print("-" * 40)
    print(f"Random Baseline Win Rate: {b_win_rate:.2f}%")
    print(f"Random Baseline ROI     : {b_roi:.1f}%")
    print("-" * 40)
    print(f"Edge (Win Rate): {p_win_rate - b_win_rate:+.2f}%")
    print(f"Edge (ROI)     : {p_roi - b_roi:+.1f}%")

if __name__ == '__main__':
    run_portfolio_backtest()
