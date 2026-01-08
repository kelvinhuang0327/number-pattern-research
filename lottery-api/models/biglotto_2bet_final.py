#!/usr/bin/env python3
"""
大樂透雙注優化 V3 - 最終版
基於回測數據的最優策略
"""
import sys
import os
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.unified_predictor import UnifiedPredictionEngine

class BigLotto2BetOptimizerV3:
    """
    V3 最終優化策略：
    1. 候選池 15 個 (介於 V1 的 12 和 V2 的 18 之間)
    2. 重疊 3 個 (介於 V1 的 4-5 和 V2 的 2 之間)
    3. 只用 Top 3 方法，但權重重新平衡
    4. 特殊策略：第二注強制包含「反向號碼」(大號段)
    """
    
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
    
    def predict_2bets_final(self, history, lottery_rules):
        """最終優化預測"""
        candidates = Counter()
        
        print("🔍 V3 最終優化：智能候選收集")
        
        # 只用最強的 3 個方法，權重相等
        methods = [
            ('deviation', self.engine.deviation_predict, 2.0),
            ('markov', self.engine.markov_predict, 2.0),
            ('statistical', self.engine.statistical_predict, 2.0),
        ]
        
        for name, func, weight in methods:
            try:
                result = func(history, lottery_rules)
                for num in result['numbers']:
                    candidates[num] += weight
                print(f"  ✅ {name}: {result['numbers']}")
            except Exception as e:
                print(f"  ⚠️ {name} 失敗")
        
        # 候選池 15 個
        top_candidates = [n for n, _ in candidates.most_common(15)]
        print(f"\n📊 Top 15 候選: {top_candidates}")
        
        # 分析候選號碼的分佈
        small_nums = [n for n in top_candidates if n <= 24]  # 小號段
        large_nums = [n for n in top_candidates if n > 24]   # 大號段
        
        print(f"  小號段 (1-24): {small_nums}")
        print(f"  大號段 (25-49): {large_nums}")
        
        # 策略：注1 取前6，注2 取第4-9但強制包含大號
        bet1_numbers = sorted(top_candidates[:6])
        
        # 注2：從第4開始，但優先選大號
        bet2_candidates = top_candidates[3:12]
        bet2_numbers = []
        
        # 先加入大號（最多3個）
        for num in bet2_candidates:
            if num > 24 and len([n for n in bet2_numbers if n > 24]) < 3:
                bet2_numbers.append(num)
        
        # 再補充其他候選
        for num in bet2_candidates:
            if num not in bet2_numbers and len(bet2_numbers) < 6:
                bet2_numbers.append(num)
        
        bet2_numbers = sorted(bet2_numbers)
        
        overlap = set(bet1_numbers) & set(bet2_numbers)
        covered = set(bet1_numbers) | set(bet2_numbers)
        
        print(f"\n🎯 V3 最終組合")
        print(f"  注 1: {bet1_numbers} (均衡型)")
        print(f"  注 2: {bet2_numbers} (大號加強型)")
        print(f"  重疊: {len(overlap)} 個 - {sorted(overlap)}")
        print(f"  覆蓋: {len(covered)}/15 ({len(covered)/15*100:.1f}%)")
        
        return {
            'bets': [
                {'numbers': bet1_numbers},
                {'numbers': bet2_numbers}
            ],
            'candidates': top_candidates,
            'method': '2bet_coverage_v3_final',
            'strategy': f'Top3平衡+大號增強 (覆蓋{len(covered)}/15)'
        }

if __name__ == '_main__':
    from database import DatabaseManager
    from common import get_lottery_rules
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    
    optimizer = BigLotto2BetOptimizerV3()
    result = optimizer.predict_2bets_final(history, rules)
    
    print("\n" + "=" * 60)
    print("📋 V3 最終預測")
    print("=" * 60)
    print(f"注 1: {','.join([f'{n:02d}' for n in result['bets'][0]['numbers']])}")
    print(f"注 2: {','.join([f'{n:02d}' for n in result['bets'][1]['numbers']])}")
