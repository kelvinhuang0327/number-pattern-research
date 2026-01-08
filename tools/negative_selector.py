#!/usr/bin/env python3
"""
Negative Selector (Kill Model) - Optimized (Smart 10)
"""
import sys
import os
import io
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class NegativeSelector:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db_path = os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db')
        self.db = DatabaseManager(db_path=self.db_path)
        self.rules = get_lottery_rules(lottery_type)
        
    def get_data(self):
        # Get data ASC (Oldest -> Newest)
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))

    def predict_kill_numbers(self, count=5, history=None):
        """預測殺號 (排除號碼) - Optimized for 2025"""
        draws = history if history is not None else self.get_data()
        if not draws:
            return []
            
        # Strategy: Smart Cold (Avoid Gap Extremes)
        # Using 10 kills as per backtest optimization
        
        # 1. 計算頻率 (近100期)
        freq = Counter([n for d in draws[-100:] for n in d['numbers']])
        
        # 2. 計算遺漏值
        gaps = {}
        min_num = self.rules['minNumber']
        max_num = self.rules['maxNumber']
        for n in range(min_num, max_num + 1):
            gaps[n] = len(draws)
            for i, draw in enumerate(reversed(draws)):
                if n in draw['numbers']:
                    gaps[n] = i
                    break
                    
        scores = []
        for n in range(min_num, max_num + 1):
            f = freq.get(n, 0)
            g = gaps[n]
            
            # Risk Control: Do not kill if gap > 20 (Mean Reversion Risk)
            if g > 20: 
                scores.append((n, 9999))
            else:
                scores.append((n, f))
                
        # Sort by frequency ASC (lowest freq first), but high gaps pushed to end
        scores.sort(key=lambda x: x[1])
        
        # Select bottom 'count' candidates
        kill_candidates = [n for n, s in scores[:count]]
        
        return sorted(kill_candidates)

def main():
    selector = NegativeSelector()
    kill_nums = selector.predict_kill_numbers(count=10)
    
    print("================================================================================")
    print("負向排除模型 (Smart-10 Optimized)")
    print("================================================================================")
    print(f"殺號清單: {kill_nums}")
    print("================================================================================")

if __name__ == '__main__':
    main()
