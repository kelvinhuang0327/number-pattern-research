#!/usr/bin/env python3
"""
激進派策略 (Gap Strategy) 回測工具
目的：驗證「斷層策略」在歷史上的表現
測試邏輯：回測過去 300 期，針對每種 Gap 類型 (Gap 01-19, Gap 20-29 等) 進行即時判斷與模擬下注
"""
import sys
import os
import logging
from collections import Counter
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class RadicalBacktester:
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
        
    def backtest_gap_strategy(self, history, window=300):
        """
        回測：假設我們每一期都使用「斷層策略」，效果如何？
        或者，我們能檢測到「斷層前兆」嗎？(暫時先每一期都跑，看 ROI)
        
        策略 A: 針對每個 Gap Zone (如 Zone 1: 01-19) 建立一注
        如果該期真的發生 Gap，我們是否能中獎？
        """
        print(f"📊 開始回測激進策略 (Gap Strategy) - 近 {window} 期")
        print("-" * 60)
        
        test_data = history[:window] if window < len(history) else history
        # Reverse to simulate chronological order: Old -> New
        # history usually New -> Old
        chronological_data = list(reversed(test_data))
        
        wins = {
            'Gap_01-19': {'hits': [], 'match_3_plus': 0, 'actual_gaps': 0},
            'Gap_20-29': {'hits': [], 'match_3_plus': 0, 'actual_gaps': 0},
            'Gap_30-39': {'hits': [], 'match_3_plus': 0, 'actual_gaps': 0},
        }
        
        for i, target_draw in enumerate(chronological_data):
            if i < 50: continue # Need initial history
            
            # Context history
            current_history = list(reversed(chronological_data[:i])) # New -> Old
            
            # Actual result
            actual_nums = set(target_draw['numbers'])
            
            # Check Actual Gaps
            has_gap_1 = not any(1 <= n <= 19 for n in actual_nums)
            has_gap_2 = not any(20 <= n <= 29 for n in actual_nums)
            has_gap_3 = not any(30 <= n <= 39 for n in actual_nums)
            
            if has_gap_1: wins['Gap_01-19']['actual_gaps'] += 1
            if has_gap_2: wins['Gap_20-29']['actual_gaps'] += 1
            if has_gap_3: wins['Gap_30-39']['actual_gaps'] += 1
            
            # Predict & Evaluate
            # 1. Predict Gap 01-19
            # (Simplified prediction logic directly here to save time/imports)
            pred_1 = self._predict_gap(current_history, range(1, 20))
            hit_1 = len(set(pred_1) & actual_nums)
            wins['Gap_01-19']['hits'].append(hit_1)
            if hit_1 >= 3: wins['Gap_01-19']['match_3_plus'] += 1
            
            # 2. Predict Gap 20-29
            pred_2 = self._predict_gap(current_history, range(20, 30))
            hit_2 = len(set(pred_2) & actual_nums)
            wins['Gap_20-29']['hits'].append(hit_2)
            if hit_2 >= 3: wins['Gap_20-29']['match_3_plus'] += 1

        print("\n📈 回測結果摘要:")
        total_draws = len(wins['Gap_01-19']['hits'])
        
        for name, data in wins.items():
            if name == 'Gap_30-39': continue # Skip for brevity
            
            matches = data['match_3_plus']
            gaps = data['actual_gaps']
            avg_hit = np.mean(data['hits'])
            
            print(f"🔹 {name}:")
            print(f"   實際發生斷層次數: {gaps} / {total_draws} ({gaps/total_draws*100:.1f}%)")
            print(f"   策略 Match-3+ 次數: {matches} ({matches/total_draws*100:.1f}%)")
            print(f"   平均命中: {avg_hit:.2f}")
            
            # 如果我們只在「真的發生斷層」的時候才算命中率？
            # 當然現實中我們不知道何時發生，但這可以評估「如果你猜對了斷層，選號準不準」
            
    def _predict_gap(self, history, exclude_range):
        """Simplified Gap Prediction Logic"""
        rules = {'pickCount': 6, 'minNumber': 1, 'maxNumber': 49}
        candidates = Counter()
        
        # 1. Deviation
        try:
            res_dev = self.engine.deviation_predict(history, rules)
            for i, n in enumerate(res_dev['numbers']):
                if n not in exclude_range:
                    candidates[n] += (20 - i) * 1.5
        except: pass
                    
        # 2. Markov
        try:
            res_markov = self.engine.markov_predict(history, rules)
            for i, n in enumerate(res_markov['numbers']):
                if n not in exclude_range:
                    candidates[n] += (20 - i) * 1.2
        except: pass

        # 3. Frequency (Fixed)
        try:
            res_freq = self.engine.frequency_predict(history, rules)
            for i, n in enumerate(res_freq['numbers']):
                if n not in exclude_range:
                    candidates[n] += (20 - i) * 1.0
        except: pass
        
        # Select Top 6
        top = [n for n, s in candidates.most_common(12)]
        return sorted(top[:6]) # Simple Top 6 based on "Gap" constraints

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    
    backtester = RadicalBacktester()
    backtester.backtest_gap_strategy(history, window=300)

if __name__ == '__main__':
    main()
