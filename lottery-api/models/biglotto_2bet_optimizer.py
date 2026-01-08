#!/usr/bin/env python3
"""
大樂透雙注覆蓋優化預測器
基於評審團短期方案：結合 Top 3 方法 + 覆蓋優化
目標：Match-3+ 率從 3.39% 提升至 6-8%
"""
import sys
import os
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules

class BigLotto2BetOptimizer:
    """
    大樂透雙注覆蓋優化器
    
    策略：
    1. 結合 Top 3 方法（偏差分析、馬可夫鏈、統計綜合）
    2. 生成 12 個高分候選號碼
    3. 雙注最大化覆蓋這 12 個候選
    """
    
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
    
    def predict_2bets(self, history, lottery_rules):
        """
        生成 2 注優化組合
        
        Returns:
            {
                'bets': [
                    {'numbers': [...]},
                    {'numbers': [...]}
                ],
                'candidates': [...],  # 12 個候選號碼
                'method': '2bet_coverage_optimization',
                'strategy': '...'
            }
        """
        pick_count = lottery_rules.get('pickCount', 6)
        
        # Step 1: 收集候選號碼（使用 Top 3 方法）
        candidates = Counter()
        
        print("🔍 Step 1: 收集候選號碼")
        
        # 偏差分析 (權重 2.0) - 大樂透最佳方法
        try:
            dev_result = self.engine.deviation_predict(history, lottery_rules)
            for num in dev_result['numbers']:
                candidates[num] += 2.0
            print(f"  ✅ 偏差分析: {dev_result['numbers']}")
        except Exception as e:
            print(f"  ⚠️ 偏差分析失敗: {e}")
        
        # 馬可夫鏈 (權重 1.5) - 威力彩最佳，大樂透次佳
        try:
            markov_result = self.engine.markov_predict(history, lottery_rules)
            for num in markov_result['numbers']:
                candidates[num] += 1.5
            print(f"  ✅ 馬可夫鏈: {markov_result['numbers']}")
        except Exception as e:
            print(f"  ⚠️ 馬可夫鏈失敗: {e}")
        
        # 統計綜合 (權重 1.0) - 大樂透並列第二
        try:
            stat_result = self.engine.statistical_predict(history, lottery_rules)
            for num in stat_result['numbers']:
                candidates[num] += 1.0
            print(f"  ✅ 統計綜合: {stat_result['numbers']}")
        except Exception as e:
            print(f"  ⚠️ 統計綜合失敗: {e}")
        
        # Step 2: 選出 Top 12 候選號碼
        top_candidates = [n for n, _ in candidates.most_common(12)]
        print(f"\n📊 Step 2: Top 12 候選號碼")
        print(f"  {top_candidates}")
        
        # Step 3: 生成 2 注（最大化覆蓋）
        print(f"\n🎯 Step 3: 生成雙注組合")
        
        # 策略：第一注取前 6 個，第二注取 4-9 位（有 2 個重疊）
        # 這樣可以覆蓋 Top 9 個候選號碼
        bet1_numbers = sorted(top_candidates[:6])
        bet2_numbers = sorted(top_candidates[3:9])
        
        # 計算覆蓋率
        covered_numbers = set(bet1_numbers) | set(bet2_numbers)
        coverage_rate = len(covered_numbers) / 12 * 100
        
        print(f"  注 1: {bet1_numbers}")
        print(f"  注 2: {bet2_numbers}")
        print(f"  覆蓋候選數: {len(covered_numbers)}/12 ({coverage_rate:.1f}%)")
        
        return {
            'bets': [
                {'numbers': bet1_numbers},
                {'numbers': bet2_numbers}
            ],
            'candidates': top_candidates,
            'method': '2bet_coverage_optimization',
            'strategy': f'Top3組合+覆蓋優化 (覆蓋率 {coverage_rate:.1f}%)',
            'coverage': {
                'covered': list(covered_numbers),
                'coverage_rate': coverage_rate
            }
        }

def test_predictor():
    """測試預測器"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    
    optimizer = BigLotto2BetOptimizer()
    
    print("=" * 60)
    print("🎰 大樂透雙注覆蓋優化預測器")
    print("=" * 60)
    print(f"歷史數據: {len(history)} 期")
    print("-" * 60)
    
    result = optimizer.predict_2bets(history, rules)
    
    print("\n" + "=" * 60)
    print("📋 最終預測結果")
    print("=" * 60)
    print(f"策略: {result['strategy']}")
    print(f"\n注 1: {','.join([f'{n:02d}' for n in result['bets'][0]['numbers']])}")
    print(f"注 2: {','.join([f'{n:02d}' for n in result['bets'][1]['numbers']])}")
    print(f"\nTop 12 候選: {result['candidates']}")
    print(f"覆蓋率: {result['coverage']['coverage_rate']:.1f}%")

if __name__ == '__main__':
    test_predictor()
