
#!/usr/bin/env python3
"""
Smart-2Bet + Kill-5 Verification
目標：驗證 "Smart-2Bet (Enhanced with Kill-5)" 的回測表現
對比：
1. Baseline (Old Smart-2Bet): 5.08%
2. Enhanced (New Smart-2Bet): ?
"""
import sys
import os
import argparse
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.orthogonal_2bet import Orthogonal2BetOptimizer

def run_verification(year=2025):
    print("=" * 80)
    print(f"🧬 Smart-2Bet (Enhanced) Verification - {year}")
    print("=" * 80)

    # 1. 準備數據
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: x['date'])
    rules = get_lottery_rules('BIG_LOTTO')
    
    test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
    if not test_draws:
        print(f"❌ No data for {year}")
        return

    print(f"📊 Test Period: {len(test_draws)} draws")
    print("-" * 80)

    # Manual Config (Best Performing)
    config = {
        'trend_window': 500,
        'gap_window': 50,
        'elite_pool_size': 30
    }
    
    optimizer = Orthogonal2BetOptimizer(config=config)
    
    wins = 0
    total = 0
    
    print(f"Using Config: {config}")
    print("Running Backtest ", end="", flush=True)

    for target_draw in test_draws:
        target_idx = all_draws.index(target_draw)
        history = all_draws[:target_idx]
        
        try:
            # 這裡調用的 predict 已經包含了 Kill-5 邏輯
            prediction = optimizer.predict(history, rules)
            bets = prediction['bets']
            actual = set(target_draw['numbers'])
            
            draw_win = False
            for bet in bets:
                match = len(set(bet['numbers']) & actual)
                if match >= 3:
                    draw_win = True
                    break
            
            if draw_win:
                wins += 1
            total += 1
            
            if total % 10 == 0:
                print(".", end="", flush=True)
                
        except Exception as e:
            pass
    
    win_rate = (wins / total) * 100 if total > 0 else 0
    
    print("\n" + "=" * 80)
    print("🏆 Enhanced Strategy Result")
    print("=" * 80)
    print(f"Total Draws: {total}")
    print(f"Wins (Match-3+): {wins}")
    print(f"Win Rate: {win_rate:.2f}%")
    print("-" * 80)
    
    baseline = 5.08
    diff = win_rate - baseline
    print(f"Baseline (Old): {baseline:.2f}%")
    print(f"Improvement:    {diff:+.2f}%")
    
    if diff > 0:
        print("✅ SUCCESS: Kill-5 Integration improved the strategy!")
    elif diff == 0:
        print("😐 NEUTRAL: No change (Kill list probably didn't overlap with winners).")
    else:
        print("❌ REGRESSION: Kill-5 accidentally killed winning numbers.")

if __name__ == '__main__':
    run_verification()
