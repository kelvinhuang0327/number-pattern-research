#!/usr/bin/env python3
"""
Dynamic Frequency Predictor
自動測試多個窗口大小，找出當下最佳的熱號窗口
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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class DynamicFrequencyPredictor:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        self.windows = [30, 50, 100, 200, 300]
        
    def get_data(self):
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))

    def _frequency_predict(self, history, window):
        """使用指定窗口的頻率預測"""
        recent = history[-window:] if len(history) > window else history
        all_nums = [n for d in recent for n in d['numbers']]
        freq = Counter(all_nums)
        return [n for n, c in freq.most_common(6)]

    def find_optimal_window(self, lookback=50):
        """用近 N 期表現找出最佳窗口"""
        draws = self.get_data()
        
        if len(draws) < 200:
            return 50  # 資料不足時用預設
        
        # 測試每個窗口在最近 lookback 期的表現
        window_scores = {}
        
        for window in self.windows:
            total_hits = 0
            for i in range(lookback):
                test_idx = len(draws) - lookback + i
                history = draws[:test_idx]
                actual = set(draws[test_idx]['numbers'])
                
                predicted = set(self._frequency_predict(history, window))
                hits = len(predicted & actual)
                total_hits += hits
            
            avg_hits = total_hits / lookback
            window_scores[window] = avg_hits
        
        # 找出平均命中最高的窗口
        best_window = max(window_scores, key=window_scores.get)
        return best_window, window_scores

    def predict(self, pick_count=6, consecutive_filter=None):
        """使用最佳窗口進行預測"""
        draws = self.get_data()
        best_window, scores = self.find_optimal_window()
        
        candidates = self._frequency_predict(draws, best_window)
        
        # 應用連莊過濾
        if consecutive_filter:
            candidates = [n for n in candidates if n not in consecutive_filter]
            # 補足
            if len(candidates) < pick_count:
                all_nums = [n for d in draws[-best_window:] for n in d['numbers']]
                freq = Counter(all_nums)
                extras = [n for n, c in freq.most_common() if n not in candidates and n not in (consecutive_filter or set())]
                candidates.extend(extras[:(pick_count - len(candidates))])
        
        return {
            'numbers': sorted(candidates[:pick_count]),
            'window': best_window,
            'window_scores': scores
        }

def backtest_dynamic_window(year=2025):
    """回測動態窗口策略"""
    predictor = DynamicFrequencyPredictor()
    draws = predictor.get_data()
    test_draws = [d for d in draws if d['date'].startswith(str(year))]
    
    print(f"🔄 動態窗口頻率策略回測 (年份: {year})")
    print("-" * 60)
    
    start_idx = draws.index(test_draws[0])
    wins = 0
    total = 0
    window_usage = Counter()
    
    for i, target in enumerate(test_draws):
        idx = start_idx + i
        history = draws[:idx]
        
        # 動態找最佳窗口
        result = predictor.predict(pick_count=6)
        predicted = set(result['numbers'])
        best_window = result['window']
        window_usage[best_window] += 1
        
        actual = set(target['numbers'])
        special = target['special']
        
        matches = len(predicted & actual)
        special_match = special in predicted
        
        if matches >= 3 or (matches == 2 and special_match):
            wins += 1
        total += 1
    
    print(f"中獎期數: {wins}/{total}")
    print(f"勝率: {wins/total*100:.2f}%")
    print(f"窗口使用分佈: {dict(window_usage)}")
    print("-" * 60)
    
    return wins / total

def main():
    # 1. 回測對比
    print("=" * 80)
    print("📊 動態窗口 vs 固定窗口 對比測試")
    print("=" * 80)
    
    # 動態窗口
    dynamic_rate = backtest_dynamic_window(2025)
    
    # 固定窗口 (50)
    print("\n📊 固定窗口 (50) 對照組")
    predictor = DynamicFrequencyPredictor()
    draws = predictor.get_data()
    test_draws = [d for d in draws if d['date'].startswith('2025')]
    start_idx = draws.index(test_draws[0])
    
    fixed_wins = 0
    for i, target in enumerate(test_draws):
        history = draws[:start_idx + i]
        predicted = set(predictor._frequency_predict(history, 50))
        actual = set(target['numbers'])
        special = target['special']
        matches = len(predicted & actual)
        if matches >= 3 or (matches == 2 and special in predicted):
            fixed_wins += 1
    
    fixed_rate = fixed_wins / len(test_draws)
    print(f"固定窗口(50) 勝率: {fixed_rate*100:.2f}%")
    
    print("\n🏆 結論:")
    if dynamic_rate > fixed_rate:
        print(f"動態窗口更優! (+{(dynamic_rate-fixed_rate)*100:.2f}%)")
    else:
        print(f"固定窗口更穩定 (差異: {(dynamic_rate-fixed_rate)*100:.2f}%)")

if __name__ == '__main__':
    main()
