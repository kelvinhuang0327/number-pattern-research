#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import numpy as np
from collections import Counter
from itertools import combinations
import random

# Setup paths
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)

from lottery_api.models.individual_rhythm_predictor import IndividualRhythmPredictor

DB_PATH = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
POOL = 39
PICK = 5
BASELINE_GE2 = 0.113973

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'DAILY_539'
        ORDER BY date ASC, draw ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums)})
    return draws

def generate_wheel_k5(pool, guarantee_t=2, condition_m=2):
    """
    Greedy wheel generator for k=5 (Daily 539)
    v = len(pool)
    t = guarantee_t
    m = condition_m
    k = 5
    """
    v = len(pool)
    target_combos = list(combinations(range(v), condition_m))
    remaining = set(range(len(target_combos)))
    tickets = []
    
    while remaining:
        best_ticket = None
        max_covered = -1
        
        # Candidate sampling (greedy with some random trials)
        for _ in range(200):
            cand = tuple(sorted(random.sample(range(v), 5)))
            cand_set = set(cand)
            covered = 0
            for idx in remaining:
                if len(cand_set & set(target_combos[idx])) >= guarantee_t:
                    covered += 1
            if covered > max_covered:
                max_covered = covered
                best_ticket = cand
        
        if not best_ticket or max_covered == 0:
            break
            
        tickets.append(sorted([pool[i] for i in best_ticket]))
        
        # Update remaining
        new_remaining = set()
        cand_set = set(best_ticket)
        for idx in remaining:
            if len(cand_set & set(target_combos[idx])) < guarantee_t:
                new_remaining.add(idx)
        remaining = new_remaining
        
    return tickets

def run_wheel_backtest(draws, test_periods, pool_size=8):
    train_data = draws[:-test_periods]
    test_data = draws[-test_periods:]
    
    predictor = IndividualRhythmPredictor(pool=POOL, pick=PICK)
    predictor.train(train_data, decay_factor=0.995)
    
    total_bets = 0
    total_wins_ge2 = 0
    periods_with_win = 0
    
    print(f"Backtesting IRAP-Wheel (Pool={pool_size}, k=5) on {test_periods} draws...")
    
    for i in range(len(test_data)):
        # 1. Get pool of high confidence numbers
        res = predictor.predict(draws[:len(train_data)+i], n_to_pick=pool_size)
        pool = res['numbers']
        
        # 2. Generate Wheel (Guarantee 2 if 2)
        tickets = generate_wheel_k5(pool, guarantee_t=2, condition_m=2)
        
        # 3. Check hits
        actual = set(test_data[i]['numbers'])
        win_this_period = False
        
        for ticket in tickets:
            total_bets += 1
            if len(set(ticket) & actual) >= 2:
                total_wins_ge2 += 1
                win_this_period = True
        
        if win_this_period:
            periods_with_win += 1
            
    avg_tickets = total_bets / test_periods
    period_win_rate = periods_with_win / test_periods
    
    # Expected random period win rate for N tickets
    # P(win in N tickets) = 1 - (1 - P_ge2)^N
    random_period_win_rate = 1 - (1 - BASELINE_GE2)**avg_tickets
    
    return {
        'total_bets': total_bets,
        'avg_tickets': avg_tickets,
        'period_win_rate': period_win_rate,
        'expected_rand_rate': random_period_win_rate,
        'edge': period_win_rate - random_period_win_rate,
        'test_count': test_periods
    }

def main():
    draws = load_draws()
    
    print("=" * 80)
    print("IRAP-Wheel (Daily 539) 強化回測審計")
    print("策略：利用 IRAP 選出 8 個高信心號碼，並使用正交矩陣 (Wheel) 生成投注")
    print("=" * 80)
    
    # Test on different windows
    for w in [150, 500]:
        res = run_wheel_backtest(draws, w, pool_size=8)
        print(f"\n窗口 {w} 期結果:")
        print(f"  平均每期注數: {res['avg_tickets']:.2f}")
        print(f"  實際週期勝率: {res['period_win_rate']*100:.2f}%")
        print(f"  隨機週期勝率: {res['expected_rand_rate']*100:.2f}%")
        print(f"  超額贏率 (Edge): {res['edge']*100:+.2f}%")
        
    print("\n" + "=" * 80)
    print("結論：IRAP-Wheel 是否能透過『多注覆蓋』轉化個體節律優勢？")
    print("=" * 80)

if __name__ == "__main__":
    main()
