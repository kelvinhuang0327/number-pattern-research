#!/usr/bin/env python3
"""
Smart-2Bet (Orthogonal System) 回測驗證腳本
目標：驗證雙注組合 (Trend-Master + Gap-Hunter) 在 2025 年的表現
驗證標準：
1. Zero Leakage (嚴格滾動回測)
2. Match-3+ 勝率 > 8.0%
3. 雙注正交性 (Overlap 分析)
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

def backtest_smart_2bet(year=2025):
    print("=" * 70)
    print(f"🚀 Smart-2Bet (Orthogonal) 回測驗證 - {year}")
    print("=" * 70)

    # 1. 準備數據
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: x['date']) # 確保時間順序
    rules = get_lottery_rules('BIG_LOTTO')
    
    # 篩選測試年份
    test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
    if not test_draws:
        print(f"❌ 找不到 {year} 年的數據")
        return

    print(f"📊 測試期數: {len(test_draws)} 期")
    print(f"🔬 驗證模式: Strict Rolling Backtest (Zero Leakage)")
    print("-" * 70)

    optimizer = Orthogonal2BetOptimizer()
    
    total = 0
    wins = 0
    total_matches = 0
    hits_breakdown = {3: 0, 4: 0, 5: 0, 6: 0}
    strategy_wins = {'Trend-Master': 0, 'Gap-Hunter': 0}
    
    print(f"{'Draw':<10} {'Date':<12} {'Result':<10} {'Matches':<20} {'Strategy'}")
    print("-" * 70)

    for target_draw in test_draws:
        # 準備歷史數據 (只能看該期之前的數據)
        target_idx = all_draws.index(target_draw)
        history = all_draws[:target_idx]
        
        # 進行預測
        try:
            prediction = optimizer.predict(history, rules)
            bets = prediction['bets']
            elite_pool = prediction['elite_pool']
            elite_pool_size = len(elite_pool)
            
            # 檢查中獎
            actual = set(target_draw['numbers'])
            draw_win = False
            best_match = 0
            
            win_details = []
            
            # 檢查 Pool 覆蓋
            pool_hits = len(set(elite_pool) & actual)
            
            for bet in bets:
                pred_nums = set(bet['numbers'])
                match = len(pred_nums & actual)
                best_match = max(best_match, match)
                
                if match >= 3:
                    draw_win = True
                    hits_breakdown[match] += 1
                    strat_name = bet['strategy'].split(' ')[0]
                    strategy_wins[strat_name] += 1
                    win_details.append(f"{strat_name}({match})")
            
            total += 1
            if draw_win:
                wins += 1
                print(f"{target_draw['draw']:<10} {target_draw['date']:<12} {'✅ WIN':<10} {', '.join(win_details):<20} PoolMatch:{pool_hits}/{elite_pool_size}")
            # else:
            #     print(f"{target_draw['draw']:<10} {target_draw['date']:<12} {'❌ LOSS':<10} {'':<20} PoolMatch:{pool_hits}/{elite_pool_size}")
            
        except Exception as e:
            print(f"❌ Error in {target_draw['draw']}: {e}")
            continue

    # 統計結果
    win_rate = wins / total * 100
    
    print("=" * 70)
    print("📊 驗證結果總結")
    print("=" * 70)
    print(f"總期數:       {total}")
    print(f"中獎期數:     {wins}")
    print(f"組合勝率:     {win_rate:.2f}%")
    print("-" * 30)
    print("🏆 命中分佈:")
    print(f"  Match 3:    {hits_breakdown[3]}")
    print(f"  Match 4:    {hits_breakdown[4]}")
    print(f"  Match 5:    {hits_breakdown[5]}")
    print(f"  Match 6:    {hits_breakdown[6]}")
    print("-" * 30)
    print("⚔️ 策略貢獻:")
    print(f"  Trend-Master: {strategy_wins['Trend-Master']} 勝")
    print(f"  Gap-Hunter:   {strategy_wins['Gap-Hunter']} 勝")
    print("=" * 70)
    
    # 判定是否達標
    target_rate = 8.0
    if win_rate >= target_rate:
        print(f"✅ 成功達標! ({win_rate:.2f}% > {target_rate}%)")
    else:
        print(f"⚠️ 未達標 ({win_rate:.2f}% < {target_rate}%)")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2025, help='Backtest year')
    args = parser.parse_args()
    
    backtest_smart_2bet(args.year)
