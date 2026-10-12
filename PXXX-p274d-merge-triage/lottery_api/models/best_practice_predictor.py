#!/usr/bin/env python3
"""
最佳實戰預測器 (Best Practice Predictor)
基於 2025 回測結果，使用馬可夫鏈作為核心
"""
import sys
import os
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules

class BestPracticePredictor:
    """
    最佳實戰預測器
    根據 2025 回測結果優化
    """
    
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
    
    def predict_single_bet(self, history, lottery_rules):
        """
        單注預測（使用馬可夫鏈）
        
        Returns:
            {
                'numbers': [1, 5, 12, ...],
                'special': 3,
                'confidence': 0.65,
                'method': 'markov_best_practice'
            }
        """
        # 直接使用表現最佳的馬可夫鏈
        result = self.engine.markov_predict(history, lottery_rules)
        result['method'] = 'markov_best_practice'
        return result
    
    def predict_4_bets(self, history, lottery_rules):
        """
        4 注預測（馬可夫鏈 + 輕量級多樣化）
        
        Returns:
            {
                'bets': [
                    {'numbers': [...], 'special': 1},
                    ...
                ],
                'method': 'markov_4bet_diversified',
                'anchors': [...]
            }
        """
        # 1. 馬可夫鏈作為主預測
        markov_result = self.engine.markov_predict(history, lottery_rules)
        main_numbers = markov_result['numbers']
        main_special = markov_result.get('special', 1)
        
        # 2. 貝葉斯和趨勢作為輔助
        bayesian_result = self.engine.bayesian_predict(history, lottery_rules)
        trend_result = self.engine.trend_predict(history, lottery_rules)
        
        # 3. 識別核心錨點（馬可夫鏈前 2 名）
        anchors = main_numbers[:2]
        
        # 4. 收集候選號碼
        all_candidates = set(main_numbers) | set(bayesian_result['numbers']) | set(trend_result['numbers'])
        
        # 5. 號碼評分（馬可夫鏈優先）
        number_scores = Counter()
        for num in main_numbers:
            number_scores[num] += 3.0  # 馬可夫鏈權重最高
        for num in bayesian_result['numbers']:
            number_scores[num] += 1.5
        for num in trend_result['numbers']:
            number_scores[num] += 1.0
        
        # 6. 生成 4 注
        bets = []
        pick_count = lottery_rules.get('pickCount', 6)
        
        # 注 1: 馬可夫鏈核心
        bets.append({
            'numbers': main_numbers,
            'special': main_special
        })
        
        # 注 2-4: 基於評分的變化組合
        top_candidates = [n for n, _ in number_scores.most_common(12)]
        
        for i in range(1, 4):
            # 保留錨點，變化其他號碼
            bet_numbers = list(anchors)
            
            # 從候選中選擇
            offset = i * 2
            for candidate in top_candidates[offset:]:
                if candidate not in bet_numbers and len(bet_numbers) < pick_count:
                    bet_numbers.append(candidate)
            
            # 如果不足，從全部候選補充
            if len(bet_numbers) < pick_count:
                for candidate in all_candidates:
                    if candidate not in bet_numbers:
                        bet_numbers.append(candidate)
                        if len(bet_numbers) >= pick_count:
                            break
            
            # 特別號輪詢
            special_candidates = [main_special, bayesian_result.get('special', 1), trend_result.get('special', 1)]
            special = special_candidates[i % len(special_candidates)]
            
            bets.append({
                'numbers': sorted(bet_numbers[:pick_count]),
                'special': special
            })
        
        return {
            'bets': bets,
            'method': 'markov_4bet_diversified',
            'anchors': anchors,
            'summary': f"核心方法: 馬可夫鏈 (16.10% 勝率)"
        }

if __name__ == '__main__':
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    predictor = BestPracticePredictor()
    
    print("=" * 60)
    print("🎯 最佳實戰預測器 (基於 2025 回測優化)")
    print("=" * 60)
    
    # 單注預測
    print("\n📍 單注預測 (馬可夫鏈):")
    single = predictor.predict_single_bet(history, rules)
    print(f"號碼: {single['numbers']}")
    print(f"特別號: {single['special']}")
    print(f"方法: {single['method']}")
    
    # 4 注預測
    print("\n📍 4 注預測 (馬可夫鏈 + 輕量級多樣化):")
    multi = predictor.predict_4_bets(history, rules)
    print(f"核心錨點: {multi['anchors']}")
    print(f"{multi['summary']}")
    print("-" * 60)
    
    for i, bet in enumerate(multi['bets'], 1):
        nums = ",".join([f"{n:02d}" for n in bet['numbers']])
        print(f"注 {i}: {nums} | 特別號: {bet['special']:02d}")
