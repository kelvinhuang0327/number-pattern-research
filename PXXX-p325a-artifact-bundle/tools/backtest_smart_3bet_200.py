#!/usr/bin/env python3
"""
🧪 3-bet Smart Combination Backtest (Latest 200 Periods)
Strategy: Deviation + Markov + Statistical (Weighted Top 18, Sliced)
Goal: Verify the 7.33% claim and compare with Integrated P0+P1.
"""
import sys
import os
import io
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def run_smart_3bet_backtest(test_periods=200):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    optimizer = BigLotto3BetOptimizer()
    
    print("=" * 80)
    print(f"🔬 Big Lotto 三注智能組合回測 (最近 {test_periods} 期)")
    print("-" * 80)
    print(f"策略: Deviation + Markov + Statistical (Top 18 Sliced)")
    print("=" * 80)

    wins = 0
    match_3_plus = 0
    match_dist = Counter()
    total = 0
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            # Silence internal prints
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_diversified(history, rules)
            
            bets = res['bets']
            best_match = 0
            for bet_data in bets:
                match_count = len(set(bet_data['numbers']) & actual)
                if match_count > best_match:
                    best_match = match_count
            
            match_dist[best_match] += 1
            if best_match >= 3:
                match_3_plus += 1
            
            total += 1
            
            if (i + 1) % 20 == 0:
                print(f"進度: {i+1}/{test_periods} | 當前 Match-3+: {match_3_plus/total*100:.2f}% | 最佳平均: {sum(m*c for m,c in match_dist.items())/total:.2f}")

        except Exception as e:
            continue

    print("\n" + "=" * 80)
    print("📊 最終統計結果 (Smart 3-Bet)")
    print("-" * 80)
    print(f"總測試期數: {total}")
    print(f"中獎期數 (Match 3+): {match_3_plus}")
    print(f"最終中獎率 (Match-3+ Rate): {match_3_plus/total*100:.2f}%")
    print("-" * 40)
    print("命中分佈:")
    for m in sorted(match_dist.keys(), reverse=True):
        count = match_dist[m]
        pct = count / total * 100
        print(f"  Match {m}: {count:3d} 次 ({pct:5.2f}%) " + "█" * int(pct/2))
    print("=" * 80)

if __name__ == '__main__':
    run_smart_3bet_backtest(200)
