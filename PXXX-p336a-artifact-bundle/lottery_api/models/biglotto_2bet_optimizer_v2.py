#!/usr/bin/env python3
"""
大樂透雙注覆蓋優化預測器 V2（優化版）
改進：1. 擴大候選池 2. 減少重疊 3. 調整權重
"""
import sys
import os
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine

class BigLotto2BetOptimizerV2:
    """優化版雙注預測器"""
    
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
    
    def predict_2bets_optimized(self, history, lottery_rules):
        """
        V2 優化策略：
        1. 擴大候選池至 18 個
        2. 雙注重疊只保留 2 個（減少冗餘）
        3. 引入更多方法提升多樣性
        """
        candidates = Counter()
        
        print("🔍 V2 優化：收集候選號碼")
        
        # 使用更多方法，權重相等（避免過度依賴單一方法）
        methods = {
            'deviation': (self.engine.deviation_predict, 1.5),
            'markov': (self.engine.markov_predict, 1.5),
            'statistical': (self.engine.statistical_predict, 1.2),
            'bayesian': (self.engine.bayesian_predict, 1.0),
            'frequency': (self.engine.frequency_predict, 1.0),
        }
        
        for name, (func, weight) in methods.items():
            try:
                result = func(history, lottery_rules)
                for num in result['numbers']:
                    candidates[num] += weight
                print(f"  ✅ {name}: {result['numbers']}")
            except Exception as e:
                print(f"  ⚠️ {name} 失敗: {e}")
        
        # 擴大候選池至 18 個
        top_candidates = [n for n, _ in candidates.most_common(18)]
        print(f"\n📊 Top 18 候選號碼: {top_candidates}")
        
        # 策略改進：前 6 個 vs 第 5-10 個（只有 2 個重疊）
        bet1_numbers = sorted(top_candidates[:6])
        bet2_numbers = sorted(top_candidates[4:10])
        
        covered = set(bet1_numbers) | set(bet2_numbers)
        overlap = set(bet1_numbers) & set(bet2_numbers)
        
        print(f"\n🎯 V2 雙注組合")
        print(f"  注 1: {bet1_numbers}")
        print(f"  注 2: {bet2_numbers}")
        print(f"  重疊: {len(overlap)} 個 - {sorted(overlap)}")
        print(f"  覆蓋: {len(covered)}/18 ({len(covered)/18*100:.1f}%)")
        
        return {
            'bets': [
                {'numbers': bet1_numbers},
                {'numbers': bet2_numbers}
            ],
            'candidates': top_candidates,
            'method': '2bet_coverage_v2',
            'overlap': len(overlap),
            'coverage_rate': len(covered) / 18 * 100
        }

if __name__ == '__main__':
    from database import DatabaseManager
    from common import get_lottery_rules
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    
    optimizer = BigLotto2BetOptimizerV2()
    result = optimizer.predict_2bets_optimized(history, rules)
    
    print("\n" + "=" * 60)
    print("📋 V2 最終預測")
    print("=" * 60)
    print(f"注 1: {','.join([f'{n:02d}' for n in result['bets'][0]['numbers']])}")
    print(f"注 2: {','.join([f'{n:02d}' for n in result['bets'][1]['numbers']])}")
