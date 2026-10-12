#!/usr/bin/env python3
"""
對比測試：智能5注 vs. 隨機5注
"""
import sys
import os
import random

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from lottery_api.database import DatabaseManager

def generate_random_5_bets(lottery_type='BIG_LOTTO'):
    """產生隨機5注"""
    bets = []
    for _ in range(5):
        numbers = sorted(random.sample(range(1, 50), 6))
        bets.append(numbers)
    return bets

def backtest_random_5bets(year=2025):
    """回測隨機5注策略"""
    db = DatabaseManager()
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = list(reversed(all_draws))  # 時間順序
    
    test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
    
    total = len(test_draws)
    wins = 0
    
    print(f"\n🎲 隨機5注回測 (年份: {year}, 共 {total} 期)")
    
    for draw in test_draws:
        actual = set(draw['numbers'])
        
        # 每期隨機生成5注
        random_bets = generate_random_5_bets()
        
        # 檢查是否有任一注中獎
        draw_win = False
        for bet in random_bets:
            match = len(set(bet) & actual)
            if match >= 3:
                draw_win = True
                break
        
        if draw_win:
            wins += 1
    
    win_rate = wins / total if total > 0 else 0
    
    print(f"\n結果:")
    print(f"  總期數: {total}")
    print(f"  中獎期數: {wins}")
    print(f"  勝率: {win_rate*100:.2f}%")
    
    return win_rate

if __name__ == '__main__':
    # 運行10次取平均（因為是隨機的）
    rates = []
    for i in range(10):
        print(f"\n--- 第 {i+1} 次隨機測試 ---")
        rate = backtest_random_5bets(2025)
        rates.append(rate)
    
    avg_rate = sum(rates) / len(rates)
    
    print("\n" + "="*60)
    print(f"📊 隨機5注平均勝率 (10次測試): {avg_rate*100:.2f}%")
    print(f"📊 我們的智能5注勝率:          10.17%")
    print(f"📊 差距:                        {(0.1017 - avg_rate)*100:+.2f}%")
    print("="*60)
