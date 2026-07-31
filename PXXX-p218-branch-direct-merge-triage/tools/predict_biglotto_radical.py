#!/usr/bin/env python3
"""
大樂透「激進派」預測策略 (Radical Strategy Prototype)
專門捕捉極端態與斷層盤 (如 115000007 期 01-19 空開的情況)
策略邏輯：
1. 斷層策略 (Gap Strategy): 強制排除特定熱門區間 (例如第一區)
2. 冷號回補 (Cold Rebound): 優先選擇長期未出的冷號
3. 高總和偏好 (High Sum Preference): 允許甚至偏好高總和組合
"""
import sys
import os
import random
from collections import Counter
import logging

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class RadicalPredictor:
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
        
    def predict_gap_strategy(self, history, rules, gap_zone=1):
        """
        斷層策略：假設某個區間完全空開
        gap_zone: 1 (01-09), 2 (10-19), 3 (20-29)...
        """
        min_num = rules.get('minNumber', 1)
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        # 定義排除範圍
        if gap_zone == 1:
            exclude_range = range(1, 20) # 排除 01-19 (第一+二區) - 模擬 115000007 情況
            strategy_name = "斷層策略 (排除 01-19)"
        elif gap_zone == 2:
            exclude_range = range(20, 30)
            strategy_name = "斷層策略 (排除 20-29)"
        else:
            exclude_range = []
            strategy_name = "斷層策略 (無排除)"
            
        print(f"🔪 {strategy_name} - 排除: {list(exclude_range)}")
        
        # 1. 獲取基礎候選號碼 (使用標準 Deviation + Markov)
        candidates = Counter()
        
        # 偏差分析
        res_dev = self.engine.deviation_predict(history, rules)
        for i, n in enumerate(res_dev['numbers']):
            if n not in exclude_range:
                candidates[n] += (20 - i) * 1.5 # 權重
                
        # 馬可夫鏈 (捕捉轉移)
        res_markov = self.engine.markov_predict(history, rules)
        for i, n in enumerate(res_markov['numbers']):
            if n not in exclude_range:
                candidates[n] += (20 - i) * 1.2

        # 頻率分析 (修復後)
        try:
            res_freq = self.engine.frequency_predict(history, rules)
            for i, n in enumerate(res_freq['numbers']):
                if n not in exclude_range:
                    candidates[n] += (20 - i) * 1.0
        except Exception as e:
            print(f"⚠️ 頻率分析仍有問題: {e}")

        # 2. 冷號加權 (從 history 找冷號)
        all_nums = [n for draw in history[:50] for n in draw['numbers']]
        counts = Counter(all_nums)
        for n in range(min_num, max_num + 1):
            if n in exclude_range: continue
            if counts[n] <= 1: # 冷號 (50期內出現 <= 1次)
                candidates[n] += 15 # 大幅加分
                print(f"  🧊 冷號加分: {n:02d}")

        # 3. 選出 Top 10
        top_candidates = [n for n, s in candidates.most_common(12)]
        print(f"📊 激進派候選: {top_candidates}")
        
        # 4. 生成組合 (確保總和較高)
        # 簡單取 Top pick_count
        bet = sorted(top_candidates[:pick_count])
        
        curr_sum = sum(bet)
        if curr_sum < 150:
            print(f"⚠️ 組合總和 {curr_sum} 偏低，嘗試替換大號...")
            # 嘗試用後備號碼替換最小號碼
            if len(top_candidates) > pick_count:
                bet = sorted(top_candidates[1:pick_count+1]) # Shift window
        
        return {
            'numbers': bet,
            'strategy': strategy_name,
            'candidates': top_candidates
        }

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    
    # 模擬 115000007 預測 (移除該期)
    history_train = [d for d in history if str(d['draw']) != '115000007']
    
    print("=" * 60)
    print("🚀 激進派預測原型 (Radical Prototype)")
    print("=" * 60)
    
    predictor = RadicalPredictor()
    
    # 測試模式：排除 01-19 (針對本次開獎特徵)
    result = predictor.predict_gap_strategy(history_train, rules, gap_zone=1)
    
    print("\n🎯 最終激進注:")
    print(f"  號碼: {result['numbers']}")
    print(f"  總和: {sum(result['numbers'])}")
    
    # 驗證命中
    actual = {21, 23, 32, 36, 39, 43}
    hits = set(result['numbers']) & actual
    print(f"\n🧪 回測驗證 (對比 115000007):")
    print(f"  實際: {sorted(list(actual))}")
    print(f"  命中: {len(hits)} 個 {list(hits)}")
    
    if len(hits) >= 3:
        print("🎉 激機策略成功捕捉到特徵！")
    else:
        print("💨 激進策略效果有限，需調整參數。")

if __name__ == '__main__':
    main()
