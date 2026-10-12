
#!/usr/bin/env python3
"""
Banker + Kill-5 Strategy Analyzer
目標：驗證「必中一碼 (Banker)」與「殺5碼 (Kill-5)」結合的綜效。
假設：如果「殺號模型」認為某個號碼會死，而「膽碼模型」認為它會開，這就是「矛盾」。
驗證：
1. 當 Banker 出現在 Kill List 時，Banker 的勝率是否顯著降低？（如果是，則 Kill 有效）
2. 排除矛盾後的「淨化膽碼 (Clean Banker)」勝率是否提升？
"""
import sys
import os
import argparse
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

def analyze_combination(year=2025):
    print("=" * 100)
    print(f"⚔️ Banker vs Kill-5 Synergy Analysis - {year}")
    print("=" * 100)

    # 1. 準備數據
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: x['date'])
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()

    test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
    if not test_draws:
        print(f"❌ No data for {year}")
        return

    print(f"📊 Test Data: {len(test_draws)} draws")
    print("-" * 100)

    # 定義策略
    # Banker: Bayesian Top 1 (2025最強)
    # Kill Strategy: 使用 Trend 的最後 5 碼 (長期冷門)
    banker_method = 'bayesian_predict'
    kill_method = 'trend_predict' 
    
    total = 0
    raw_banker_wins = 0
    
    conflict_count = 0
    conflict_banker_wins = 0 # 矛盾但Banker贏了 (Kill失敗)
    
    clean_count = 0
    clean_banker_wins = 0   # 沒矛盾且Banker贏了
    
    kill_success_count = 0  # Kill-5 確實一個都沒開
    
    print(f"Banker Strategy: {banker_method} (Top 1)")
    print(f"Kill-5 Strategy: {kill_method} (Bottom 5)")
    print("-" * 100)
    
    for target_draw in test_draws:
        target_idx = all_draws.index(target_draw)
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            # 1. Get Banker
            b_func = getattr(engine, banker_method)
            b_res = b_func(history, rules)
            banker = b_res['numbers'][0]
            
            # 2. Get Kill List (Trend Bottom 5)
            # Trend returns ranked numbers, so we take the last 5
            k_func = getattr(engine, kill_method)
            k_res = k_func(history, rules)
            kill_list = set(k_res['numbers'][-5:])
            
            # 3. Analyze
            is_win = banker in actual
            is_conflict = banker in kill_list
            is_kill_success = len(kill_list & actual) == 0
            
            total += 1
            if is_win:
                raw_banker_wins += 1
                
            if is_kill_success:
                kill_success_count += 1
                
            if is_conflict:
                conflict_count += 1
                if is_win:
                    conflict_banker_wins += 1
            else:
                clean_count += 1
                if is_win:
                    clean_banker_wins += 1
                    
        except Exception as e:
            pass

    # 計算統計
    raw_win_rate = (raw_banker_wins / total * 100)
    
    conflict_win_rate = (conflict_banker_wins / conflict_count * 100) if conflict_count > 0 else 0
    clean_win_rate = (clean_banker_wins / clean_count * 100) if clean_count > 0 else 0
    
    real_kill_accuracy = (kill_success_count / total * 100)
    
    print(f"Total Draws: {total}")
    print(f"Conflict Occurred: {conflict_count} times ({conflict_count/total*100:.1f}%)")
    print(f"Kill-5 Accuracy (0 hits): {real_kill_accuracy:.2f}%")
    print("-" * 100)
    print(f"{'Scenario':<30} | {'Win Rate':<15} | {'Improvement'}")
    print("-" * 100)
    print(f"{'Raw Banker (不看 Kill)':<30} | {raw_win_rate:.2f}%          | Baseline")
    print(f"{'Conflict Banker (被 Kill 鎖定)':<30} | {conflict_win_rate:.2f}%          | {conflict_win_rate - raw_win_rate:+.2f}%")
    print(f"{'Clean Banker (Kill 同意)':<30} | {clean_win_rate:.2f}%          | {clean_win_rate - raw_win_rate:+.2f}%")
    print("-" * 100)
    
    if clean_win_rate > raw_win_rate:
        print("✅ 結論：有幫助！結合 Kill-5 能有效過濾掉部分錯誤的膽碼。")
    else:
        print("❌ 結論：幫助不大。Kill 策略與 Banker 策略相關性低，或 Kill 準度不足。")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2025)
    args = parser.parse_args()
    
    analyze_combination(args.year)
