#!/usr/bin/env python3
"""
Alpha 20 Strategy 1: Post-Selection Filtering (Backtest)
邏輯：先產生號碼，再針對「極度危險」的號碼進行單點替換
危險定義：連續出現 3 期以上的號碼 (大樂透極少連 4)
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

class PostSelectionBacktester:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()
        
    def get_data(self):
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))

    def _get_danger_numbers(self, history):
        """定義後置殺號規則：連續出現過 3 次的號碼，第 4 次出現機率極低"""
        if len(history) < 3: return set()
        last = set(history[-1]['numbers'])
        p1 = set(history[-2]['numbers'])
        p2 = set(history[-3]['numbers'])
        # 取交集：連三期的號碼
        triple_streak = last & p1 & p2
        return triple_streak

    def run(self, year=2025):
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        print(f"🚀 Strategy 1: 後置殺號 (Post-Selection) 回測 (年份: {year})")
        print("規則：若預測號碼中包含『連三期出現』之號碼，則改選該策略的下一個候選號")
        print("-" * 80)

        start_idx = all_draws.index(test_draws[0])
        total_rounds = 0
        wins = 0
        swaps_total = 0
        
        for i, target_draw in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            danger_nums = self._get_danger_numbers(history)
            
            # --- Bet 1: Frequency-50 With Post-Swap ---
            history_50 = history[-50:]
            all_nums_50 = [n for d in history_50 for n in d['numbers']]
            freq_50 = Counter(all_nums_50).most_common()
            
            bet1 = []
            candidates = [n for n, c in freq_50]
            ptr = 0
            while len(bet1) < 6 and ptr < len(candidates):
                num = candidates[ptr]
                if num in danger_nums:
                    swaps_total += 1
                    # Skip it and move to next candidate
                else:
                    bet1.append(num)
                ptr += 1
            bet1 = sorted(bet1)

            # --- Bet 2: Zone Balance 500 ---
            # NOTE: Zone Balance doesn't easily return 'next candidates'.
            # If it contains a danger_num, we'll try a slightly different window.
            try:
                res = self.engine.zone_balance_predict(history[-500:], self.rules)
                bet2 = res['numbers']
                if set(bet2) & danger_nums:
                    # Attempt a swap by changing window
                    swaps_total += 1
                    res = self.engine.zone_balance_predict(history[-510:], self.rules)
                    bet2 = res['numbers']
            except:
                bet2 = [1,2,3,4,5,6]
            bet2 = sorted(bet2)

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
        print(f"觸發替換次數: {swaps_total}")
        print(f"中獎期數: {wins}")
        print(f"總勝率 (Win Rate): {wins/total_rounds*100:.2f}%")
        print("-" * 40)

def main():
    backtester = PostSelectionBacktester()
    backtester.run(2025)

if __name__ == '__main__':
    main()

