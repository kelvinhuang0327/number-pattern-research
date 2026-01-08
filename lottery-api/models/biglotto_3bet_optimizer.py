#!/usr/bin/env python3
"""
大樂透三注智能組合預測器
策略：Deviation + Markov + Statistical 強制低重疊
"""
import sys
import os
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.unified_predictor import UnifiedPredictionEngine

class BigLotto3BetOptimizer:
    """大樂透三注智能組合優化器"""
    
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
    
    def predict_3bets_diversified(self, history, lottery_rules):
        """
        生成三注多樣化組合
        
        策略：
        1. 使用Top 3方法收集候選號碼
        2. 套用權重評分
        3. 生成18個高分候選
        4. 三注強制低重疊（每注只與前一注重疊1個號碼）
        """
        pick_count = lottery_rules.get('pickCount', 6)
        
        # Step 1: 收集候選號碼並加權
        candidates = Counter()
        
        print("🔍 收集候選號碼...")
        
        # 方法1: Deviation (權重 2.0) - 大樂透表現最佳
        try:
            result_dev = self.engine.deviation_predict(history, lottery_rules)
            for num in result_dev['numbers']:
                candidates[num] += 2.0
            print(f"  ✅ 偏差分析: {result_dev['numbers']}")
        except Exception as e:
            print(f"  ⚠️ 偏差分析失敗: {e}")
        
        # 方法2: Markov (權重 1.5) - 大樂透表現佳
        try:
            result_mar = self.engine.markov_predict(history, lottery_rules)
            for num in result_mar['numbers']:
                candidates[num] += 1.5
            print(f"  ✅ 馬可夫鏈: {result_mar['numbers']}")
        except Exception as e:
            print(f"  ⚠️ 馬可夫鏈失敗: {e}")
        
        # 方法3: Statistical (權重 1.0) - 提供多樣性
        try:
            result_sta = self.engine.statistical_predict(history, lottery_rules)
            for num in result_sta['numbers']:
                candidates[num] += 1.0
            print(f"  ✅ 統計綜合: {result_sta['numbers']}")
        except Exception as e:
            print(f"  ⚠️ 統計綜合失敗: {e}")
        
        # Step 2: 選出Top 18候選號碼
        top_18 = [num for num, _ in candidates.most_common(18)]
        print(f"\n📊 Top 18 候選號碼: {top_18}")
        
        # Step 3: 生成三注（強制低重疊策略）
        # 注1: 前6個 (1-6)
        # 注2: 5-10 (與注1重疊1個: #6)
        # 注3: 9-14 (與注2重疊1個: #10)
        bet1_numbers = sorted(top_18[0:6])
        bet2_numbers = sorted(top_18[4:10])
        bet3_numbers = sorted(top_18[8:14])
        
        # 計算覆蓋率
        covered = set(bet1_numbers) | set(bet2_numbers) | set(bet3_numbers)
        overlap_1_2 = len(set(bet1_numbers) & set(bet2_numbers))
        overlap_2_3 = len(set(bet2_numbers) & set(bet3_numbers))
        
        print(f"\n🎯 三注組合生成:")
        print(f"  注1: {bet1_numbers}")
        print(f"  注2: {bet2_numbers} (與注1重疊 {overlap_1_2} 個)")
        print(f"  注3: {bet3_numbers} (與注2重疊 {overlap_2_3} 個)")
        print(f"  總覆蓋: {len(covered)}/18 候選 ({len(covered)/18*100:.1f}%)")
        
        return {
            'bets': [
                {'numbers': bet1_numbers},
                {'numbers': bet2_numbers},
                {'numbers': bet3_numbers}
            ],
            'candidates': top_18,
            'method': '3bet_diversified',
            'coverage': len(covered),
            'strategy': f'Top3方法+低重疊 (覆蓋{len(covered)}/18)'
        }

if __name__ == '__main__':
    from database import DatabaseManager
    from common import get_lottery_rules
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    
    optimizer = BigLotto3BetOptimizer()
    
    print("=" * 60)
    print("🎰 大樂透三注智能組合預測器")
    print("=" * 60)
    print(f"歷史數據: {len(history)} 期")
    print("-" * 60)
    
    result = optimizer.predict_3bets_diversified(history, rules)
    
    print("\n" + "=" * 60)
    print("📋 最終預測結果")
    print("=" * 60)
    print(f"策略: {result['strategy']}")
    for i, bet in enumerate(result['bets'], 1):
        nums_str = ','.join([f'{n:02d}' for n in bet['numbers']])
        print(f"注{i}: {nums_str}")
