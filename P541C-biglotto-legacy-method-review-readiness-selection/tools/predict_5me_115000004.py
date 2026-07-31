#!/usr/bin/env python3
"""
🎯 Big Lotto Draw 115000004 Prediction (5ME Strategy)
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.negative_selector import NegativeSelector

def predict_5ME():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()
    selector = NegativeSelector()
    
    print("=" * 60)
    print("🎯 大樂透 Draw 115000004 預測 (5ME 五機混和)")
    print("=" * 60)
    
    # 5-Method Ensemble: Stat, Dev, Mark, HotCold, Trend
    methods = ['statistical_predict', 'deviation_predict', 'markov_predict', 'hot_cold_mix_predict', 'trend_predict']
    method_names = ['統計綜合', '偏差分析', '馬可夫鏈', '冷熱混合', '趨勢分析']
    
    bets = []
    for i, m in enumerate(methods):
        try:
            res = getattr(engine, m)(all_draws, rules)
            nums = sorted(res['numbers'])
            bets.append(nums)
            print(f"\n注 {i+1} ({method_names[i]}): {nums}")
        except Exception as e:
            print(f"方法 {m} 失敗: {e}")
    
    # Show P1 Kill numbers for reference
    kill = selector.predict_kill_numbers(count=10, history=all_draws)
    print(f"\n⚠️ P1 殺號參考 (非強制): {sorted(kill)}")
    
    print("\n" + "=" * 60)
    print("📌 以上為 5ME 五注預測，祝您好運！")
    print("=" * 60)

if __name__ == '__main__':
    predict_5ME()
