#!/usr/bin/env python3
"""
威力彩高注數 (7-10注) Echo Boost 潛力分析
=======================================
探討多注數下，Echo 信號對成功率的推動效果。
"""
import os
import sys
import numpy as np
from collections import Counter
from tqdm import tqdm

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lottery_api.database import DatabaseManager
from tools.predict_power_quad_precision import get_fourier_rank

def generate_power_multi_echo(history, n_bets=10):
    # 1. Fourier Rank (基石)
    f_rank = get_fourier_rank(history)
    idx = 0
    while idx < len(f_rank) and f_rank[idx] == 0: idx += 1
    
    bets = []
    # 前 N-2 注取 Fourier
    for i in range(n_bets - 2):
        start = idx + (i * 6)
        bets.append(sorted(f_rank[start:start+6].tolist()))
    
    used = set([n for b in bets for n in b])
    
    # 第 N-1 注: Echo Boost (Lag-2)
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= 38 and n not in used]
    else:
        echo_nums = []
    
    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    rem = [n for n in range(1, 39) if n not in used and n not in echo_nums]
    rem.sort(key=lambda x: freq.get(x, 0)) # Cold
    bet_echo = sorted((echo_nums + rem)[:6])
    bets.append(bet_echo)
    used |= set(bet_echo)
    
    # 第 N 注: Gray Zone Gap
    recent_50 = history[-50:]
    freq_50 = Counter([n for d in recent_50 for n in d['numbers']])
    expected = (50 * 6) / 38
    gray = [n for n in range(1, 39) if n not in used]
    gray.sort(key=lambda x: abs(freq_50.get(x, 0) - expected))
    bet_gray = sorted(gray[:6])
    bets.append(bet_gray)
    
    return bets[:n_bets]

def run_multi_test(n_bets, periods=1384):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    # 精確計算 N 注隨機基準: 1 - (1 - 0.0387)^N
    p_single = 0.0387
    baseline = (1 - (1 - p_single)**n_bets) * 100
    
    hits = 0
    total = min(len(draws)-500, periods)
    
    for i in range(len(draws)-total, len(draws)):
        history = draws[:i]
        actual = set(draws[i]['numbers'])
        predicts = generate_power_multi_echo(history, n_bets)
        
        is_hit = False
        for bet in predicts:
            if len(set(bet) & actual) >= 3:
                is_hit = True
                break
        if is_hit: hits += 1
        
    rate = hits / total * 100
    return rate, baseline

if __name__ == "__main__":
    print(f"🔬 探討 Lag-2 Echo 在多注策略中的天花板 (N=1384)...")
    for n in [5, 7, 10]:
        rate, base = run_multi_test(n)
        print(f"  [{n:2d}注] 成功率: {rate:.2f}% | 隨機基準: {base:.2f}% | Edge: {rate-base:+.2f}%")
