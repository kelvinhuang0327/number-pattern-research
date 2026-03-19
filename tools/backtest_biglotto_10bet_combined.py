#!/usr/bin/env python3
"""
回測腳本：(大樂透頻率正交5注) + (P1+偏差互補+Sum均值)5注，總共10注
測試期數：1500期
"""

import sys
import os
import time
from collections import Counter

# 將專案根目錄和 lottery_api 加入路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import biglotto_5bet_orthogonal, biglotto_p1_deviation_5bet

def run_backtest(periods=1500):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db_manager = DatabaseManager(db_path)
    all_draws = sorted(db_manager.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    if len(all_draws) < periods + 500:
        print(f"數據不足！需要至少 {periods + 500} 期，目前只有 {len(all_draws)} 期")
        return

    print("=" * 60)
    print(f"🚀 開始回測 大樂透 10注組合策略")
    print(f"策略構成: 頻率正交5注 + (P1+偏差互補+Sum均值)5注")
    print(f"回測期數: {periods} 期")
    print("=" * 60)

    wins = 0  # M3+ 次數
    m4_plus = 0
    match_dist = Counter()
    
    start_time = time.time()
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        # 取得兩組 5注，加起來成為 10注
        bets_ortho = biglotto_5bet_orthogonal(history)
        bets_p1dev = biglotto_p1_deviation_5bet(history)
        
        bets = [bet['numbers'] for bet in bets_ortho] + [bet['numbers'] for bet in bets_p1dev]
        
        best_match = 0
        hit = False
        
        # 我們只關注是否這10注中有撞中的
        for bet in bets:
            m = len(set(bet) & actual)
            if m > best_match: 
                best_match = m
            if m >= 3: 
                hit = True
                
        if hit: 
            wins += 1
        if best_match >= 4: 
            m4_plus += 1
            
        match_dist[best_match] += 1
        
        if (i+1) % 50 == 0:
            elapsed = time.time() - start_time
            rate = wins / (i + 1) * 100
            print(f"  Progress: {i+1}/{periods}... Rate: {rate:.2f}% (Elapsed: {elapsed:.1f}s)")

    rate = wins / periods * 100
    
    # N注基準計算
    # 大樂透單注 M3+ 機率是 0.01863754
    p_single = 0.01863754
    baseline = (1 - (1 - p_single) ** 10) * 100
    edge = rate - baseline
    
    print("=" * 60)
    print(f"✅ 回測完成！ ({periods} 期)")
    print(f"策略: (頻率正交5注) + (P1+偏差互補+Sum均值)5注")
    print("-" * 60)
    print(f"📊 實測勝率 (M3+): {rate:.2f}%")
    print(f"📈 隨機基準 (10注): {baseline:.2f}%")
    
    edge_str = f"+{edge:.2f}%" if edge > 0 else f"{edge:.2f}%"
    print(f"⭐ 策略 Edge: {edge_str} {'✅' if edge > 0 else '❌'}")
    print("-" * 60)
    print(f"🎯 命中分佈: M3:{match_dist[3]}  M4:{match_dist[4]}  M5:{match_dist[5]}  M6:{match_dist[6]}")
    print(f"🏆 M4+ 總次數: {m4_plus}")
    print("=" * 60)

if __name__ == '__main__':
    run_backtest(1500)
