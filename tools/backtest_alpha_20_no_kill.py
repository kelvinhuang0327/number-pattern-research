#!/usr/bin/env python3
"""
Alpha 20 Strategy Rolling Backtest - CONTROL GROUP (No Kill)
目標：驗證 Alpha 20 策略在「不殺號」情況下的表現，以對比殺號機制的影響
"""
import sys
import os
import io
import logging
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

class Alpha20BacktesterNoKill:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()
        
    def get_data(self):
        # Get data ASC
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))

    def _calculate_matches(self, prediction, actual_numbers, special_number):
        main_matches = len(set(prediction) & set(actual_numbers))
        special_match = special_number in prediction
        return main_matches, special_match

    def _is_win(self, main_matches, special_match):
        if main_matches >= 3: return True
        if main_matches == 2 and special_match: return True
        return False

    def run(self, year=2025):
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        if not test_draws:
            print(f"No data for {year}")
            return

        print(f"🚀 Alpha 20 對照組 (無殺號) 回測啟動 (年份: {year})")
        print("配置: 無殺號 | 第一注: Freq-50 | 第二注: Zone-500")
        print("-" * 80)

        start_idx = all_draws.index(test_draws[0])
        total_rounds = 0
        wins = 0
        hits_distribution = Counter()
        
        for i, target_draw in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            # NO KILL NUMBERS generated
            
            # 2. Bet 1: Frequency-50 (Pure)
            history_50 = history[-50:]
            all_nums_50 = [n for d in history_50 for n in d['numbers']]
            freq_50 = Counter(all_nums_50)
            candidates_1 = [n for n, c in freq_50.most_common()]
            bet1 = sorted(candidates_1[:6])
            
            # 3. Bet 2: Zone Balance 500 (Pure)
            try:
                res = self.engine.zone_balance_predict(history[-500:], self.rules)
                bet2 = sorted(res['numbers'])
            except:
                bet2 = [1,2,3,4,5,6]

            # 4. Check Result
            actual = target_draw['numbers']
            special = target_draw['special']
            
            m1, s1 = self._calculate_matches(bet1, actual, special)
            m2, s2 = self._calculate_matches(bet2, actual, special)
            
            win1 = self._is_win(m1, s1)
            win2 = self._is_win(m2, s2)
            
            if win1 or win2:
                wins += 1
                
            best_match = max(m1, m2)
            hits_distribution[best_match] += 1
            total_rounds += 1

        print(f"回測結束: 共 {total_rounds} 期")
        print(f"中獎期數: {wins}")
        print(f"總勝率 (Win Rate): {wins/total_rounds*100:.2f}%")
        print("-" * 40)
        print("命中分佈 (最佳注):")
        for m in sorted(hits_distribution.keys(), reverse=True):
            print(f"Match {m}: {hits_distribution[m]} 次")
        print("-" * 80)

def main():
    backtester = Alpha20BacktesterNoKill()
    backtester.run(2025)

if __name__ == '__main__':
    main()
