#!/usr/bin/env python3
"""
大樂透三注智能組合預測器
策略：Deviation + Markov + Statistical 強制低重疊
"""
import sys
import os
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from tools.negative_selector import NegativeSelector

# 預測方法配置：(方法名, 函數名, 權重, 顯示名稱)
PREDICTION_METHODS = [
    ('deviation', 'deviation_predict', 2.0, '偏差分析'),
    ('markov', 'markov_predict', 1.5, '馬可夫鏈'),
    ('statistical', 'statistical_predict', 1.0, '統計綜合'),
]

# 三注切片配置：(起始, 結束)
BET_SLICES = [(0, 6), (4, 10), (8, 14)]


class BigLotto3BetOptimizer:
    """大樂透三注智能組合優化器"""

    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.engine = UnifiedPredictionEngine()
        self.selector = NegativeSelector(lottery_type)

    def _collect_candidates(self, history, lottery_rules):
        """收集並加權候選號碼"""
        candidates = Counter()
        print("🔍 收集候選號碼...")

        for _, func_name, weight, display_name in PREDICTION_METHODS:
            try:
                result = getattr(self.engine, func_name)(history, lottery_rules)
                for num in result['numbers']:
                    candidates[num] += weight
                print(f"  ✅ {display_name}: {result['numbers']}")
            except Exception as e:
                print(f"  ⚠️ {display_name}失敗: {e}")

        return candidates

    def _generate_bets(self, top_18):
        """根據切片配置生成三注"""
        return [sorted(top_18[start:end]) for start, end in BET_SLICES]

    def predict_3bets_diversified(self, history, lottery_rules, use_kill=True):
        """生成三注多樣化組合 (整合 P1 殺號)"""
        # Step 1: 執行 P1 動態殺號
        kill_nums = []
        if use_kill:
            kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
            if __name__ == '__main__':
                print(f"🔪 P1 負向排除: {kill_nums}")

        # Step 2: 收集候選號碼
        candidates = self._collect_candidates(history, lottery_rules)

        # Step 3: 應用殺號過濾 (P1 整合)
        if use_kill:
            for n in kill_nums:
                candidates[n] = -9999

        # Step 4: 選出 Top 18
        top_18 = [num for num, _ in candidates.most_common(18)]
        if __name__ == '__main__':
            print(f"\n📊 Top 18 候選號碼 (過濾後): {top_18}")

        # Step 3: 生成三注
        bets = self._generate_bets(top_18)
        covered = set().union(*bets)

        # 輸出結果
        print(f"\n🎯 三注組合生成:")
        for i, bet in enumerate(bets):
            overlap = len(set(bet) & set(bets[i - 1])) if i > 0 else 0
            suffix = f" (與注{i}重疊 {overlap} 個)" if i > 0 else ""
            print(f"  注{i + 1}: {bet}{suffix}")
        print(f"  總覆蓋: {len(covered)}/18 候選 ({len(covered) / 18 * 100:.1f}%)")

        return {
            'bets': [{'numbers': bet} for bet in bets],
            'candidates': top_18,
            'method': '3bet_diversified',
            'coverage': len(covered),
            'strategy': f'Top3方法+低重疊 (覆蓋{len(covered)}/18)'
        }

if __name__ == '__main__':
    from database import DatabaseManager
    from common import get_lottery_rules
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
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
