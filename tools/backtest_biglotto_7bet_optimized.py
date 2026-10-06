#!/usr/bin/env python3
"""
大樂透 7注優化最終回測 (Optimized 7-Bet Portfolio)
組合策略：多變體集成 (Multi-Variant Ensemble)
目標：Match-3+ 率 > 15%
"""
import sys
import os
import io
import random
from collections import Counter
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def backtest_optimized_7bet():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()
    
    test_periods = 150
    print(f"🚀 大樂透 7注優化策略最終驗證 (最近 {test_periods} 期)")
    print("=" * 80)
    
    wins = 0
    match3 = 0
    match4 = 0
    total = 0
    
    method_stats = Counter()
    
    portfolio_config = [
        ('1. Markov (W50)', 'markov_predict', 50),
        ('2. Markov (W100)', 'markov_predict', 100),
        ('3. Deviation (W100)', 'deviation_predict', 100),
        ('4. Deviation (W200)', 'deviation_predict', 200),
        ('5. Statistical (W100)', 'statistical_predict', 100),
        ('6. Statistical (W110)', 'statistical_predict', 110),
    ]
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        actual = set(target_draw['numbers'])
        
        # 1. Generate 6 Base Bets
        bets = []
        all_predicted_numbers = []
        
        for name, method_name, windowit in portfolio_config:
            start_hist = max(0, target_idx - windowit)
            hist = all_draws[start_hist:target_idx]
            try:
                res = getattr(engine, method_name)(hist, rules)
                nums = res['numbers'][:6]
                bets.append((name, set(nums)))
                all_predicted_numbers.extend(nums)
            except:
                pass
                
        # 2. Generate 7th Bet: Consensus (Unweighted - Proven to be better)
        if all_predicted_numbers:
            common = Counter(all_predicted_numbers).most_common(6)
            consensus_nums = [n for n, _ in common]
            bets.append(('7. Consensus', set(consensus_nums)))
        else:
            bets.append(('7. Consensus', set(random.sample(range(1, 50), 6))))

            
        # 3. Check Wins
        period_win = False
        period_match3 = False
        
        best_match = 0
        
        for name, nums in bets:
            match_count = len(nums & actual)
            best_match = max(best_match, match_count)
            
            if match_count >= 3:
                period_match3 = True
                period_win = True
                method_stats[name] += 1
            elif match_count >= 1:
                period_win = True
        
        if period_match3:
            match3 += 1
        if best_match >= 4:
            match4 += 1
        if period_win:
            wins += 1
            
        total += 1
        
        if (i+1) % 50 == 0:
            print(f"進度 {i+1}/{test_periods}: Match-3+ 率 = {match3/(i+1)*100:.2f}%")

    # Final Report
    print("\n" + "=" * 80)
    print("📊 最終回測結果")
    print("=" * 80)
    print(f"測試期數: {total}")
    print(f"策略注數: 7 注")
    print(f"🎯 Match-3+ 率: {match3/total*100:.2f}%  (目標 > 15%)")
    print(f"   Match-4+ 率: {match4/total*100:.2f}%")
    print("-" * 80)
    
    if match3/total*100 > 15.0:
        print("✅ 成功達成目標！策略有效。")
    else:
        print("⚠️ 未達目標，需進一步調整。")
        
    print("\n🏆 方法貢獻榜:")
    for m, c in method_stats.most_common():
        print(f"  {m}: {c} 次")
        
    print(f"\n💡 與隨機對比:")
    print(f"  隨機 7 注期望值: ~12.3%")
    print(f"  策略提升幅度: +{(match3/total*100 - 12.3):.2f}%")

if __name__ == '__main__':
    backtest_optimized_7bet()
