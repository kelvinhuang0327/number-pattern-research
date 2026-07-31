[Error] Failed to load resource: the server responded with a status of 404 (Not Found) (local-backup, line 0)
[Log] [PhotoStorage] DB initialized successfully (photoStorage.ts, line 76)
[Error] Failed to load resource: the server responded with a status of 404 (Not Found) (local-backup, line 0)#!/usr/bin/env python3
"""
Alpha 20 Strategy 2: Conditional Constraints (Backtest)
邏輯：基於全局規則進行「修剪」
1. 尾數過濾：單一尾數不得超過 2 個號碼
2. 區域飽和：單一 10 號區間不得超過 3 個號碼
"""
import sys
import os
import io
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class ConditionalStrategyBacktester:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()
        
    def get_data(self):
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))

    def _apply_constraints(self, candidate_list, pick_count=6):
        """核心規則優化：尾數與區域分布"""
        final_nums = []
        tail_counts = Counter()
        zone_counts = Counter() # 1-10, 11-20, ...
        
        for num in candidate_list:
            tail = num % 10
            zone = (num - 1) // 10
            
            # 條件 1: 單一尾數上限 2
            # 條件 2: 單一區間上限 3
            if tail_counts[tail] < 2 and zone_counts[zone] < 3:
                final_nums.append(num)
                tail_counts[tail] += 1
                zone_counts[zone] += 1
            
            if len(final_nums) == pick_count:
                break
        
        # 如果規則太嚴格導致號碼不足，回補一些
        if len(final_nums) < pick_count:
            remaining = [n for n in candidate_list if n not in final_nums]
            final_nums.extend(remaining[:(pick_count - len(final_nums))])
            
        return sorted(final_nums)

    def run(self, year=2025):
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        print(f"🚀 Strategy 2: 全局條件約束 (Conditional Constraints) 回測 (年份: {year})")
        print("規則設定：尾數上限=2 (防止過度集中), 區間上限=3 (防止區域飽和)")
        print("-" * 80)

        start_idx = all_draws.index(test_draws[0])
        total_rounds = 0
        wins = 0
        
        for i, target_draw in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            # --- Bet 1: 頻率策略 + 條件過濾 ---
            history_50 = history[-50:]
            all_nums_50 = [n for d in history_50 for n in d['numbers']]
            candidate_list_1 = [n for n, c in Counter(all_nums_50).most_common()]
            bet1 = self._apply_constraints(candidate_list_1)

            # --- Bet 2: 平衡策略 (因 Zone Balance 本身就有區域邏輯，故測試其純淨版) ---
            try:
                res = self.engine.zone_balance_predict(history[-500:], self.rules)
                bet2 = sorted(res['numbers'])
            except:
                bet2 = [1,2,3,4,5,6]

            # --- Check Result ---
            actual = target_draw['numbers']
            special = target_draw['special']
            m1 = len(set(bet1) & set(actual))
            s1 = special in bet1
            m2 = len(set(bet2) & set(actual))
            s2 = special in bet2
            
            if (m1 >= 3 or (m1 == 2 and s1)) or (m2 >= 3 or (m2 == 2 and s2)):
                wins += 1
            total_rounds += 1

        print(f"回測結束: 共 {total_rounds} 期")
        print(f"中獎期數: {wins}")
        print(f"總勝率 (Win Rate): {wins/total_rounds*100:.2f}%")
        print("-" * 80)

def main():
    backtester = ConditionalStrategyBacktester()
    backtester.run(2025)

if __name__ == '__main__':
    main()
