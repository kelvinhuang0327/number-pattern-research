#!/usr/bin/env python3
"""
Alpha 20 Strategy Rolling Backtest (2025)
目標：驗證 Alpha 20 策略 (Smart-10 殺號 + 雙注) 在 2025 年的實際勝率
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
from tools.negative_selector import NegativeSelector

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class Alpha20Backtester:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()
        self.selector = NegativeSelector(lottery_type)
        
    def get_data(self):
        # Get data ASC (Oldest -> Newest)
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))

    def _calculate_matches(self, prediction, actual_numbers, special_number):
        main_matches = len(set(prediction) & set(actual_numbers))
        special_match = special_number in prediction
        return main_matches, special_match

    def _is_win(self, main_matches, special_match):
        # Big Lotto Win Conditions (Simplified)
        # 3 main -> Prize 8 (JP$ 400)
        # 2 main + special -> Prize 7 (JP$ 400) - Actually Prize 7 is 2+S or 3+0?
        # Let's use strict match >= 3 OR (match >= 2 and special)
        if main_matches >= 3:
            return True
        if main_matches == 2 and special_match:
            return True
        return False

    def run(self, year=2025):
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        if not test_draws:
            print(f"No data for {year}")
            return

        print(f"🚀 Alpha 20 策略回測啟動 (年份: {year})")
        print("配置: Smart-10 殺號 | 第一注: Freq-50 | 第二注: Zone-500")
        print("-" * 80)

        start_idx = all_draws.index(test_draws[0])
        total_rounds = 0
        wins = 0
        total_cost = 0
        total_prize = 0 # Simplified estimate
        
        # Stats
        hits_distribution = Counter()
        
        for i, target_draw in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            # 1. Negative Selection (Kill 10)
            kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
            kill_set = set(kill_nums)
            
            # 2. Bet 1: Frequency-50 + Filter
            history_50 = history[-50:]
            
            # Custom Freq Logic to ensure filter
            all_nums_50 = [n for d in history_50 for n in d['numbers']]
            freq_50 = Counter(all_nums_50)
            candidates_1 = [n for n, c in freq_50.most_common() if n not in kill_set]
            # Need 6 numbers, if not enough (unlikely), take from kill set
            if len(candidates_1) < 6:
                candidates_1.extend([n for n in kill_nums if n not in candidates_1])
            bet1 = sorted(candidates_1[:6])
            
            # 3. Bet 2: Zone Balance 500 + Filter
            # Retry logic implemented inline
            bet2 = []
            max_attempts = 20
            window = 500
            
            for attempt in range(max_attempts):
                # Slide window back slightly
                sub_hist = history[-(window + attempt):]
                if attempt > 0: sub_hist = sub_hist[:-attempt] # Actually slice end
                
                try:
                    res = self.engine.zone_balance_predict(sub_hist, self.rules)
                    raw_nums = res['numbers']
                    if not (set(raw_nums) & kill_set):
                        bet2 = sorted(raw_nums)
                        break
                except: pass
            
            if not bet2:
                # Fallback
                try:
                    res = self.engine.zone_balance_predict(history[-500:], self.rules)
                    bet2 = sorted(res['numbers'])
                except:
                    bet2 = [1,2,3,4,5,6] # Should not happen

            # 4. Check Result
            actual = target_draw['numbers']
            special = target_draw['special']
            
            m1, s1 = self._calculate_matches(bet1, actual, special)
            m2, s2 = self._calculate_matches(bet2, actual, special)
            
            win1 = self._is_win(m1, s1)
            win2 = self._is_win(m2, s2)
            
            # Update Stats
            if win1 or win2:
                wins += 1
                
            # Track best match for reporting
            best_match = max(m1, m2)
            hits_distribution[best_match] += 1
            
            total_rounds += 1
            total_cost += 100 # 2 bets * 50
            
            # Verbose log for wins
            if win1 or win2:
                # print(f"期數 {target_draw['draw']} ({target_draw['date']}) | 中獎! (B1:{m1}+{int(s1)}, B2:{m2}+{int(s2)})")
                pass

        print(f"回測結束: 共 {total_rounds} 期")
        print(f"中獎期數: {wins}")
        print(f"總勝率 (Win Rate): {wins/total_rounds*100:.2f}%")
        print("-" * 40)
        print("命中分佈 (最佳注):")
        for m in sorted(hits_distribution.keys(), reverse=True):
            print(f"Match {m}: {hits_distribution[m]} 次")
        print("-" * 80)
        
        return wins/total_rounds

def main():
    backtester = Alpha20Backtester()
    backtester.run(2025)

if __name__ == '__main__':
    main()
