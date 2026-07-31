#!/usr/bin/env python3
"""
大樂透兩注精選預測器 - 第115000007期
策略：基於綜合權重Top 12生成兩注互補型組合 (Top 6 + Next 6)
"""
import sys
import os
from collections import Counter
import json

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

# 兩注精選切片
BET_SLICES_2 = [
    (0, 6),    # 注1: 王者榮耀 (最高分前6個)
    (6, 12),   # 注2: 潛力新星 (第7-12名)
]

class BigLotto2BetOptimizer:
    """大樂透兩注精選優化器"""

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

    def _generate_2bets(self, top_list):
        """根據切片配置生成兩注"""
        bets = []
        for start, end in BET_SLICES_2:
            if len(top_list) >= end:
                bet = sorted(top_list[start:end])
                bets.append(bet)
            else:
                # 備用邏輯
                bet = sorted(top_list[:6]) # 如果不足就重複第一注
                bets.append(bet)
        return bets

    def predict_2bets(self, history, lottery_rules, use_kill=True):
        """生成兩注精選組合"""
        # Step 1: 執行動態殺號
        kill_nums = []
        if use_kill:
            try:
                kill_nums = self.selector.predict_kill_numbers(count=8, history=history)
                print(f"🔪 負向排除: {kill_nums}")
            except Exception as e:
                print(f"⚠️ 殺號失敗: {e}")

        # Step 2: 收集候選號碼
        candidates = self._collect_candidates(history, lottery_rules)

        # Step 3: 應用殺號過濾
        if use_kill:
            for n in kill_nums:
                candidates[n] = -9999

        # Step 4: 選出 Top 20
        top_20 = [num for num, _ in candidates.most_common(20)]
        print(f"\n📊 Top 20 候選號碼 (過濾後): {top_20}")

        # Step 5: 生成兩注
        bets = self._generate_2bets(top_20)
        
        # 顯示結果
        print(f"\n🎯 兩注精選生成:")
        labels = ["王者榮耀 (Top 6)", "潛力新星 (No.7-12)"]
        for i, bet in enumerate(bets):
            print(f"  注{i + 1} [{labels[i]}]: {bet}")

        return {
            'bets': [{'numbers': bet} for bet in bets],
            'candidates': top_20,
            'method': '2bet_elite',
            'strategy': 'Top12 分組覆蓋',
            'kill_numbers': kill_nums
        }


def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    
    if not history:
        print("❌ 無法載入歷史數據")
        return
    
    # 驗證最新期數
    last_draw = history[0]
    print(f"📅 資料庫最新期數: {last_draw['draw']} (日期: {last_draw['date']})")
    
    if str(last_draw['draw']) != '115000006':
        print("⚠️  警告: 資料庫最新期數不是 115000006！請確認是否已更新。")
        # 繼續執行，但也許應該停止？
        # proceed anyway
    
    next_draw_id = "115000007"
    
    optimizer = BigLotto2BetOptimizer()
    
    print("=" * 70)
    print(f"🎰 大樂透兩注精選預測器 - 第{next_draw_id}期")
    print("=" * 70)
    
    result = optimizer.predict_2bets(history, rules)
    
    print("\n" + "=" * 70)
    print("📋 最終預測結果")
    print("=" * 70)
    print(f"期號: {next_draw_id}")
    print("\n精選號碼:")
    for i, bet in enumerate(result['bets'], 1):
        nums_str = ', '.join([f'{n:02d}' for n in bet['numbers']])
        print(f"  第 {i} 注: {nums_str}")
    
    print("\n" + "=" * 70)
    
    # 保存結果
    output = {
        'draw': next_draw_id,
        'lottery_type': 'BIG_LOTTO',
        'method': result['method'],
        'strategy': result['strategy'],
        'bets': result['bets'],
        'generated_at': '2026-01-23'
    }
    
    output_file = os.path.join(project_root, 'tools', f'prediction_biglotto_{next_draw_id}_2bets.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"💾 預測已保存: {output_file}")


if __name__ == '__main__':
    main()
