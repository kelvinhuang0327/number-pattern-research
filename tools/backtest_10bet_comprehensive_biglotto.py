#!/usr/bin/env python3
"""
回測腳本：大樂透 10注各種組合策略比較
涵蓋：
A. (頻率正交5注) + (P1+偏差互補+Sum均值)5注 [現有最佳]
B. (頻率正交5注) + (Triple Strike 3注) + (P1+偏差互補+Sum均值)前2注
C. (P1+偏差互補+Sum均值)5注 + (Triple Strike 3注) + (頻率正交5注)前2注
"""

import sys
import os
import time
from collections import Counter
import itertools

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import (
    biglotto_5bet_orthogonal, biglotto_p1_deviation_5bet,
    biglotto_triple_strike
)

def run_backtest(periods=1500):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db_manager = DatabaseManager(db_path)
    all_draws = sorted(db_manager.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    if len(all_draws) < periods + 500:
        print(f"數據不足！")
        return

    print("=" * 60)
    print(f"🚀 開始回測 大樂透 10注組合策略對決")
    print(f"回測期數: {periods} 期")
    print("=" * 60)

    strategies = {
        'A': {'name': 'FreqOrtho(5) + P1Dev(5)', 'wins': 0, 'm4': 0},
        'B': {'name': 'FreqOrtho(5) + TS3(3) + P1Dev(2)', 'wins': 0, 'm4': 0},
        'C': {'name': 'P1Dev(5) + TS3(3) + FreqOrtho(2)', 'wins': 0, 'm4': 0}
    }
    
    start_time = time.time()
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        # 取得各組注碼
        b_ortho = [b['numbers'] for b in biglotto_5bet_orthogonal(history)]
        b_p1dev = [b['numbers'] for b in biglotto_p1_deviation_5bet(history)]
        b_ts3 = [b['numbers'] for b in biglotto_triple_strike(history)]
        
        # 組合成 10注
        bets_A = b_ortho[:5] + b_p1dev[:5]
        bets_B = b_ortho[:5] + b_ts3[:3] + b_p1dev[:2]
        bets_C = b_p1dev[:5] + b_ts3[:3] + b_ortho[:2]
        
        combos = {
            'A': bets_A,
            'B': bets_B,
            'C': bets_C
        }
        
        for key, bets in combos.items():
            best_m = max([len(set(b) & actual) for b in bets])
            if best_m >= 3: strategies[key]['wins'] += 1
            if best_m >= 4: strategies[key]['m4'] += 1
                
        if (i+1) % 100 == 0:
            rate_A = strategies['A']['wins'] / (i + 1) * 100
            print(f"  Progress: {i+1}/{periods}... A:{rate_A:.2f}%")

    # 大樂透單注 M3+ 機率 = 0.01863754
    p_single = 0.01863754
    baseline = (1 - (1 - p_single) ** 10) * 100
    
    print("\n=" * 60)
    print(f"✅ 10注組合對決結果！ ({periods} 期)")
    print(f"📈 隨機基準 (10注): {baseline:.2f}%")
    print("-" * 60)
    
    # Sort by wins
    sorted_strats = sorted(strategies.items(), key=lambda x: x[1]['wins'], reverse=True)
    
    for key, data in sorted_strats:
        rate = data['wins'] / periods * 100
        edge = rate - baseline
        print(f"[{key}] {data['name']:<35} | Edge: +{edge:.2f}% (勝率: {rate:.2f}%, M4+: {data['m4']})")
        
    print("=" * 60)

if __name__ == '__main__':
    run_backtest(1500)
