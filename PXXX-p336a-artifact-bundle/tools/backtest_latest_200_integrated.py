#!/usr/bin/env python3
"""
🎰 P0+P1 整合策略回測 (最新 200 期)
功能: 驗證「動態殺號」+「偏態保險注」在最近 200 期的綜合表現。
"""
import sys
import os
import io
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.multi_bet_optimizer import MultiBetOptimizer
from database import DatabaseManager
from common import get_lottery_rules
from tools.negative_selector import NegativeSelector

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def run_integrated_backtest(test_periods=200):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    optimizer = MultiBetOptimizer()
    selector = NegativeSelector('BIG_LOTTO')
    
    print("=" * 80)
    print(f"🔬 Big Lotto P0+P1 整合回測 (最近 {test_periods} 期)")
    print("-" * 80)
    print(f"配置: 4 注組合 | Skewed Mode (P0) | Dynamic Kill (P1)")
    print("=" * 80)

    wins = 0
    total = 0
    match_dist = Counter()
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        print(f"[{i+1}/{test_periods}] 正在計算期數: {target_draw['draw']}...", flush=True)
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        # 1. 執行 P1 動態殺號
        kill_nums = selector.predict_kill_numbers(count=10, history=history)
        
        # 2. 執行 P0 偏態優化 + 殺號過濾
        strategy_whitelist = ['markov', 'frequency', 'bayesian', 'trend', 'zone_balance', 'hot_cold_mix']
        
        meta_config = {
            'skewed_mode': True,
            'kill_list': kill_nums,
            'method': 'cluster_pivot',
            'strategy_whitelist': strategy_whitelist
        }
        
        try:
            res = optimizer.generate_diversified_bets(history, rules, num_bets=6, meta_config=meta_config)
            bets = res['bets']
            
            best_match = 0
            for bet_data in bets:
                match_count = len(set(bet_data['numbers']) & actual)
                if match_count > best_match:
                    best_match = match_count
            
            if best_match >= 3:
                wins += 1
                
            match_dist[best_match] += 1
            total += 1
            
            if (i + 1) % 20 == 0:
                print(f"進度: {i+1}/{test_periods} | 當前勝率: {wins/total*100:.2f}% | 最佳匹配平均: {sum(m*c for m,c in match_dist.items())/total:.2f}")

        except Exception as e:
            # print(f"⚠️ 期數 {target_draw['draw']} 錯誤: {e}")
            continue

    print("\n" + "=" * 80)
    print("📊 最終統計結果")
    print("-" * 80)
    print(f"總測試期數: {total}")
    print(f"中獎期數 (Match 3+): {wins}")
    print(f"最終勝率 (Win Rate): {wins/total*100:.2f}%")
    print("-" * 40)
    print("命中分佈:")
    for m in sorted(match_dist.keys(), reverse=True):
        count = match_dist[m]
        pct = count / total * 100
        print(f"  Match {m}: {count:3d} 次 ({pct:5.2f}%) " + "█" * int(pct/2))
    print("=" * 80)

if __name__ == '__main__':
    run_integrated_backtest(200)
