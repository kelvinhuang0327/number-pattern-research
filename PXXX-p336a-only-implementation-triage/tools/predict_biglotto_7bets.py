#!/usr/bin/env python3
"""
大樂透七注智能組合預測器 - 第115000006期
策略：基於Top3方法 + 多樣化切片生成七注
"""
import sys
import os
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from tools.negative_selector import NegativeSelector

# 預測方法配置：(方法名, 函數名, 權重, 顯示名稱)
PREDICTION_METHODS = [
    ('deviation', 'deviation_predict', 2.5, '偏差分析'),
    ('markov', 'markov_predict', 2.0, '馬可夫鏈'),
    ('statistical', 'statistical_predict', 1.5, '統計綜合'),
    ('zone_balance', 'zone_balance_predict', 1.5, '區域平衡'),
    ('frequency', 'frequency_predict', 1.0, '頻率分析'),
]

# 七注切片配置：從Top 30中選取，確保多樣化
# 每注6個號碼，逐漸從高分號碼向下擴展
BET_SLICES_7 = [
    (0, 6),    # 注1: 最高分前6個
    (3, 9),    # 注2: 輕微重疊
    (6, 12),   # 注3: 中高分段
    (9, 15),   # 注4: 中分段
    (12, 18),  # 注5: 中低分段
    (15, 21),  # 注6: 低分段
    (20, 26),  # 注7: 擴展覆蓋
]


class BigLotto7BetOptimizer:
    """大樂透七注智能組合優化器"""

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

    def _generate_7bets(self, top_30):
        """根據切片配置生成七注"""
        bets = []
        for start, end in BET_SLICES_7:
            if end <= len(top_30):
                bet = sorted(top_30[start:end])
                bets.append(bet)
            else:
                # 如果不夠30個，從剩餘中選取
                remaining = len(top_30) - start
                if remaining >= 6:
                    bet = sorted(top_30[start:start+6])
                    bets.append(bet)
        return bets

    def predict_7bets_diversified(self, history, lottery_rules, use_kill=True):
        """生成七注多樣化組合 (整合殺號)"""
        # Step 1: 執行動態殺號
        kill_nums = []
        if use_kill:
            kill_nums = self.selector.predict_kill_numbers(count=10, history=history)
            print(f"🔪 負向排除: {kill_nums}")

        # Step 2: 收集候選號碼
        candidates = self._collect_candidates(history, lottery_rules)

        # Step 3: 應用殺號過濾
        if use_kill:
            for n in kill_nums:
                candidates[n] = -9999

        # Step 4: 選出 Top 30
        top_30 = [num for num, _ in candidates.most_common(30)]
        print(f"\n📊 Top 30 候選號碼 (過濾後): {top_30}")

        # Step 5: 生成七注
        bets = self._generate_7bets(top_30)
        covered = set().union(*bets)

        # 計算重疊度
        print(f"\n🎯 七注組合生成:")
        for i, bet in enumerate(bets):
            overlap = len(set(bet) & set(bets[i - 1])) if i > 0 else 0
            suffix = f" (與注{i}重疊 {overlap} 個)" if i > 0 else ""
            print(f"  注{i + 1}: {bet}{suffix}")
        print(f"  總覆蓋: {len(covered)}/{len(top_30)} 候選 ({len(covered) / len(top_30) * 100:.1f}%)")

        return {
            'bets': [{'numbers': bet} for bet in bets],
            'candidates': top_30,
            'method': '7bet_diversified',
            'coverage': len(covered),
            'strategy': f'Top5方法+多樣化切片 (覆蓋{len(covered)}/{len(top_30)})',
            'kill_numbers': kill_nums
        }


def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    
    if not history:
        print("❌ 無法載入歷史數據")
        return
    
    # 獲取下期期號
    last_draw = history[0]['draw']
    next_draw = int(str(last_draw)[-3:]) + 1
    next_draw_id = f"{str(last_draw)[:-3]}{next_draw:03d}"
    
    optimizer = BigLotto7BetOptimizer()
    
    print("=" * 70)
    print(f"🎰 大樂透七注智能組合預測器 - 第{next_draw_id}期")
    print("=" * 70)
    print(f"歷史數據: {len(history)} 期")
    print(f"最新期數: {last_draw}")
    print(f"預測期數: {next_draw_id}")
    print("-" * 70)
    
    result = optimizer.predict_7bets_diversified(history, rules)
    
    print("\n" + "=" * 70)
    print("📋 最終預測結果")
    print("=" * 70)
    print(f"策略: {result['strategy']}")
    print(f"期號: {next_draw_id}")
    print("\n預測號碼:")
    for i, bet in enumerate(result['bets'], 1):
        nums_str = ', '.join([f'{n:02d}' for n in bet['numbers']])
        print(f"  注{i}: {nums_str}")
    
    print("\n" + "=" * 70)
    print("📊 預期表現")
    print("=" * 70)
    print(f"  Match-3+ 機率: ~15-20% (七注組合)")
    print(f"  成本: NT$350 (7注 × 50元)")
    print(f"  覆蓋範圍: {result['coverage']} 個號碼")
    print(f"  方法組合: 5種預測方法加權投票")
    print("=" * 70)
    
    # 保存結果
    import json
    output = {
        'draw': next_draw_id,
        'lottery_type': 'BIG_LOTTO',
        'method': result['method'],
        'strategy': result['strategy'],
        'bets': result['bets'],
        'candidates': result['candidates'],
        'kill_numbers': result['kill_numbers'],
        'coverage': result['coverage'],
        'generated_at': '2026-01-19'
    }
    
    output_file = os.path.join(project_root, 'tools', f'prediction_biglotto_{next_draw_id}_7bets.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 預測已保存: {output_file}")


if __name__ == '__main__':
    main()
