#!/usr/bin/env python3
"""
Alpha 20 + Kill Consecutive Strategy Backtest
目標：驗證「殺連莊號」策略是否能提升勝率
"""
import sys
import os
import io
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class Alpha20KillConsecutiveBacktester:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()
        
    def get_data(self):
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))

    def _get_consecutive_nums(self, history):
        """取得連莊號碼 (連續 2 期都出現的號碼)"""
        if len(history) < 2:
            return set()
        last = set(history[-1]['numbers'])
        prev = set(history[-2]['numbers'])
        return last & prev

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
        
        print(f"🚀 Alpha 20 + Kill Consecutive 回測 (年份: {year})")
        print("策略: 殺連莊號 (連2期出現的號碼，下一期排除)")
        print("-" * 80)

        start_idx = all_draws.index(test_draws[0])
        total_rounds = 0
        wins = 0
        swaps = 0
        hits_distribution = Counter()
        
        for i, target_draw in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            # 1. Get Consecutive Numbers to Kill
            consecutive_nums = self._get_consecutive_nums(history)
            
            # 2. Bet 1: Frequency-50 with Consecutive Filter
            history_50 = history[-50:]
            all_nums_50 = [n for d in history_50 for n in d['numbers']]
            freq_50 = Counter(all_nums_50).most_common()
            
            bet1 = []
            for num, count in freq_50:
                if num in consecutive_nums:
                    swaps += 1
                    continue  # Skip consecutive numbers
                bet1.append(num)
                if len(bet1) == 6:
                    break
            bet1 = sorted(bet1)
            
            # 3. Bet 2: Zone Balance 500 with Consecutive Filter
            try:
                res = self.engine.zone_balance_predict(history[-500:], self.rules)
                raw_bet2 = res['numbers']
                bet2 = [n for n in raw_bet2 if n not in consecutive_nums]
                
                # If we filtered something out, fill from extra candidates
                if len(bet2) < 6:
                    # Get more candidates from frequency
                    extras = [n for n, c in freq_50 if n not in bet2 and n not in consecutive_nums]
                    bet2.extend(extras[:(6-len(bet2))])
                    swaps += (6 - len([n for n in raw_bet2 if n not in consecutive_nums]))
                
                bet2 = sorted(bet2[:6])
            except:
                bet2 = sorted(bet1)  # Fallback
            
            # 4. Check Result
            actual = target_draw['numbers']
            special = target_draw['special']
            
            m1, s1 = self._calculate_matches(bet1, actual, special)
            m2, s2 = self._calculate_matches(bet2, actual, special)
            
            if self._is_win(m1, s1) or self._is_win(m2, s2):
                wins += 1
                
            best_match = max(m1, m2)
            hits_distribution[best_match] += 1
            total_rounds += 1

        win_rate = wins / total_rounds * 100
        print(f"回測結束: 共 {total_rounds} 期")
        print(f"觸發替換次數: {swaps}")
        print(f"中獎期數: {wins}")
        print(f"總勝率 (Win Rate): {win_rate:.2f}%")
        print("-" * 40)
        print("命中分佈 (最佳注):")
        for m in sorted(hits_distribution.keys(), reverse=True):
            print(f"Match {m}: {hits_distribution[m]} 次 ({hits_distribution[m]/total_rounds*100:.1f}%)")
        print("-" * 80)
        
        return win_rate

def main():
    backtester = Alpha20KillConsecutiveBacktester()
    backtester.run(2025)

if __name__ == '__main__':
    main()
