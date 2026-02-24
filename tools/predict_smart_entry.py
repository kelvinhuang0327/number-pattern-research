#!/usr/bin/env python3
"""
Power & Big Lotto Smart Entry (統一智慧預測入口)
==============================================
1. 自動導航：根據彩種與注數，調用 Leaderboard 找出最近回測表現最佳的 (策略, 窗口)。
2. 智慧預測：執行最佳策略並生成最終號碼。
3. 專家整合：結合 Zone 2 (威力彩) 或 Cluster (大樂透)。
"""
import os
import sys
import argparse
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard
from lottery_api.models.special_predictor import PowerLottoSpecialPredictor
from lottery_api.common import get_lottery_rules

def main():
    parser = argparse.ArgumentParser(description='智慧預測入口')
    parser.add_argument('--lottery', default='POWER_LOTTO', choices=['POWER_LOTTO', 'BIG_LOTTO'], help='彩種')
    parser.add_argument('--num', type=int, default=2, help='注數')
    args = parser.parse_args()
    
    lottery = args.lottery
    num_bets = args.num
    
    print("\n" + "╔" + "═"*68 + "╗")
    print("║" + " "*18 + f"🚀  SMART ENTRY: {lottery:<11}  🚀" + " "*18 + "║")
    print("╚" + "═"*68 + "╝")
    
    lb = StrategyLeaderboard(lottery_type=lottery)
    history = lb.draws
    rules = get_lottery_rules(lottery)
    
    # 1. 自動尋找最佳參數 (Auto-Tuning)
    print(f"\n🔍 Phase 1: Auto-Scanning Best Strategy for {lottery} ({num_bets} Bets)...")
    
    best_strategy_name = ""
    best_func = None
    best_window = 100
    max_rate = 0
    
    # Define search space
    windows = [20, 50, 100, 150, 200]
    
    if lottery == 'BIG_LOTTO':
        search_strategies = [
            ("ROI Optimized Ensemble", lb.strat_optimized_ensemble),
            ("GUM Consensus", lb.strat_gum),
            ("Cluster Pivot", lb.strat_cluster_pivot),
            ("Cold Complement", lb.strat_twin_strike),
            ("Frequency (Hot)", lb.strat_frequency_hot)
        ]
    else:
        search_strategies = [
            ("GUM Consensus", lb.strat_gum),
            ("Cold Complement", lb.strat_twin_strike),
            ("Frequency (Hot)", lb.strat_frequency_hot),
            ("Markov Transition", lb.strat_markov)
        ]
        
    for name, func in search_strategies:
        for w in windows:
            # Quick backtest on recent 100 draws
            rate = lb.run_backtest(func, periods=100, n_bets=num_bets, window=w)
            if rate > max_rate:
                max_rate = rate
                best_strategy_name = name
                best_func = func
                best_window = w
                
    print(f"👉 Optimal Config Identified:")
    print(f"   - Strategy: {best_strategy_name}")
    print(f"   - Window  : {best_window} periods")
    print(f"   - Recent Success: {max_rate*100:.2f}% (M3+)")
    
    # 2. 生成最終推薦
    print(f"\n🔍 Phase 2: Generating Final Recommendation...")
    
    bets_ready = best_func(history, n_bets=num_bets, window=best_window)
    
    # Special Number Handling (Zone 2)
    special_nums = []
    if lottery == 'POWER_LOTTO':
        sp_predictor = PowerLottoSpecialPredictor(rules)
        special_nums = sp_predictor.predict_top_n(history, n=num_bets)
    else:
        # Big Lotto Special (Bonus) usually focus on main 6
        # Fill with random or secondary signals if needed
        special_nums = [None] * num_bets
        
    print("\n" + "="*70)
    print(f"🎯 SMART RECOMMENDATION (Lottery: {lottery} | Draw: {int(history[-1]['draw'])+1})")
    print("-" * 70)
    
    for i, b in enumerate(bets_ready):
        num_str = ", ".join(f"{n:02d}" for n in b)
        spec = f" | 特別號: {special_nums[i]:02d}" if special_nums[i] else ""
        print(f"注 {i+1}: [{num_str}]{spec}")
        
    print("=" * 70)
    print(f"💡 Logic: Used {best_strategy_name} with {best_window}-period window.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
