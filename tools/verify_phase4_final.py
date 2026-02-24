
#!/usr/bin/env python3
"""
Phase 4 Final Verification Script
目標：對比 "Smart-2Bet (Manual)" 與 "Smart-2Bet (Auto-Optimized)" 的回測表現
驗證 2025 全年數據，確認最佳參數是否真的有效。
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

# 定義策略配置
STRATEGIES = {
    'Manual (Baseline)': {
        'trend_window': 500,
        'gap_window': 50,
        'elite_pool_size': 30
    },
    'Genetic Optimized': {
        'trend_window': 200,   # Found by Genetic Algo
        'gap_window': 30,     # Found by Genetic Algo
        'elite_pool_size': 30
    }
}

def run_verification(year=2025):
    print("=" * 80)
    print(f"🧬 Phase 4 Final Verification - {year}")
    print("=" * 80)

    # 1. 準備數據
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: x['date'])
    rules = get_lottery_rules('BIG_LOTTO')
    
    test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
    if not test_draws:
        print(f"❌ No data for {year}")
        return

    print(f"📊 Test Period: {len(test_draws)} draws")
    print("-" * 80)

    results = {}

    for strat_name, config in STRATEGIES.items():
        print(f"\n🔄 Testing Strategy: {strat_name}")
        print(f"   Config: {config}")
        
        optimizer = Orthogonal2BetOptimizer(config=config)
        wins = 0
        total = 0
        
        for target_draw in test_draws:
            target_idx = all_draws.index(target_draw)
            history = all_draws[:target_idx]
            
            try:
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
                
                # Progress dot
                if total % 10 == 0:
                    print(".", end="", flush=True)
                    
            except Exception as e:
                pass
        
        win_rate = (wins / total) * 100 if total > 0 else 0
        results[strat_name] = win_rate
        print(f"\n   ✅ Result: {wins}/{total} ({win_rate:.2f}%)")

    print("\n" + "=" * 80)
    print("🏆 Final Comparison Report")
    print("=" * 80)
    print(f"{'Strategy':<25} {'Win Rate':<10} {'Improvement'}")
    print("-" * 60)
    
    baseline = results.get('Manual (Baseline)', 0)
    
    for name, rate in results.items():
        diff = rate - baseline
        print(f"{name:<25} {rate:.2f}%     {'+' if diff >=0 else ''}{diff:.2f}%")
        
    print("=" * 80)

if __name__ == '__main__':
    run_verification()
