#!/usr/bin/env python3
"""
🧪 Smart 3-bet + P1 Dynamic Kill (Latest 200 Periods)
Strategy: Weighted (Dev/Mark/Stat) + P1 Kill Filtering -> Top 18 Sliced
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
from tools.negative_selector import NegativeSelector

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def run_smart_p1_backtest(test_periods=200):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    optimizer = BigLotto3BetOptimizer()
    selector = NegativeSelector('BIG_LOTTO')
    
    print("=" * 80)
    print(f"🔬 Big Lotto 智能 3-bet + P1 殺號 整合回測 (最近 {test_periods} 期)")
    print("-" * 80)
    print(f"策略: (Dev*2 + Markov*1.5 + Stat*1) - P1 Kill -> Sliced Top 18")
    print("=" * 80)

    match_dist = Counter()
    total = 0
    match_3_plus = 0
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            # 1. 執行 P1 動態殺號
            kill_nums = selector.predict_kill_numbers(count=10, history=history)
            kill_set = set(kill_nums)

            # 2. 獲取原始權重分數 (借用 optimizer 的內部邏輯)
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                candidates = optimizer._collect_candidates(history, rules)
            
            # 3. 應用殺號過濾 (分數設為負大數)
            for n in kill_set:
                candidates[n] = -9999
                
            # 4. 選出過濾後的 Top 18
            top_18 = [num for num, _ in candidates.most_common(18)]
            
            # 5. 生成三注
            bets = optimizer._generate_bets(top_18)
            
            best_match = 0
            for bet in bets:
                m = len(set(bet) & actual)
                if m > best_match:
                    best_match = m
            
            match_dist[best_match] += 1
            if best_match >= 3:
                match_3_plus += 1
            
            total += 1
            
            if (i + 1) % 20 == 0:
                print(f"進度: {i+1}/{test_periods} | 當前 Match-3+: {match_3_plus/total*100:.2f}% | 最佳平均: {sum(m*c for m,c in match_dist.items())/total:.2f}")

        except Exception as e:
            continue

    print("\n" + "=" * 80)
    print("📊 最終統計結果 (Smart + P1 Integrated)")
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
    run_smart_p1_backtest(200)
