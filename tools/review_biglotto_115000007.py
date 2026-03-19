#!/usr/bin/env python3
"""
大樂透 115000007 期 開獎檢討與深度分析工具
實際號碼: 21, 23, 32, 36, 39, 43 + 12
目的:
1. 評估各預測方法對本期號碼的命中率與排名
2. 分析本期號碼的統計特徵 (冷熱、區域、遺漏)
3. 找出為何沒預測到的原因
"""
import sys
import os
from collections import Counter
import json
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

# 本期實際開獎號碼
ACTUAL_DRAWS = {
    'numbers': [21, 23, 32, 36, 39, 43],
    'special': 12
}
ACTUAL_SET = set(ACTUAL_DRAWS['numbers'])

def analyze_number_properties(numbers, history):
    """分析號碼的統計屬性"""
    
    # 計算常見統計值
    s = sum(numbers)
    ac = 0 # 需要實現 AC 值計算邏輯 (暫略)
    odd_even = [n % 2 for n in numbers]
    odd_count = sum(odd_even)
    even_count = 6 - odd_count
    
    print(f"🔹 基礎特徵:")
    print(f"   總和: {s} (平均約 150)")
    print(f"   奇偶比: {odd_count}:{even_count}")
    
    # 區間分析
    zones = [0]*5
    for n in numbers:
        zones[(n-1)//10] += 1
    print(f"   區間分佈: {zones} (0-9, 10-19, 20-29, 30-39, 40-49)")
    
    # 冷熱分析 (短期 10 期)
    recent_10 = history[:10]
    freq = Counter()
    for draw in recent_10:
        for n in draw['numbers']:
            freq[n] += 1
            
    cold_nums = []
    hot_nums = []
    for n in numbers:
        count = freq[n]
        status = "一般"
        if count >= 3:
            status = "🔥 熱號"
            hot_nums.append(n)
        elif count == 0:
            status = "🧊 冷號"
            cold_nums.append(n)
        print(f"   號碼 {n:02d}: 近10期出現 {count} 次 - {status}")

    return {
        'hot': hot_nums,
        'cold': cold_nums
    }

def rank_actuals_in_prediction(method_name, predicted_numbers, actual_set):
    """查看實際號碼在預測列表中的排名"""
    ranks = {}
    hits = 0
    # predicted_numbers 應該是一個有序列表
    
    for act in actual_set:
        if act in predicted_numbers:
            rank = predicted_numbers.index(act) + 1
            ranks[act] = rank
            hits += 1
        else:
            ranks[act] = -1 # Not found
            
    print(f"🔸 方法 [{method_name}]")
    print(f"   總推薦數: {len(predicted_numbers)}")
    print(f"   命中數: {hits}")
    
    sorted_ranks = sorted([(k, v) for k, v in ranks.items()], key=lambda x: x[0])
    rank_str = []
    for num, rank in sorted_ranks:
        r_str = str(rank) if rank != -1 else "未入選"
        rank_str.append(f"{num:02d}(#{r_str})")
    print(f"   排名詳情: {', '.join(rank_str)}")
    
    # 計算 Top 10/12/20 命中率
    hits_top12 = sum(1 for _, r in ranks.items() if r != -1 and r <= 12)
    hits_top20 = sum(1 for _, r in ranks.items() if r != -1 and r <= 20)
    print(f"   Top12 命中: {hits_top12}, Top20 命中: {hits_top20}")

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    # 確保不包含 115000007 (如果已經導入的話)
    all_history = db.get_all_draws(lottery_type='BIG_LOTTO')
    history = [d for d in all_history if str(d['draw']) != '115000007']
    
    print(f"📊 使用歷史數據: {len(history)} 期 (最新: {history[0]['draw']})")
    print(f"🎯 目標 115000007 期號碼: {ACTUAL_DRAWS['numbers']} 特別號: {ACTUAL_DRAWS['special']}")
    print("=" * 60)
    
    # 1. 分析號碼特徵
    print("\n🧐 1. 開獎號碼特徵分析")
    props = analyze_number_properties(ACTUAL_DRAWS['numbers'], history)
    
    # 2. 回測各預測方法
    print("\n🧪 2. 預測模型回測")
    engine = UnifiedPredictionEngine()
    rules = get_lottery_rules('BIG_LOTTO')
    
    methods = [
        ('deviation_predict', '偏差分析'),
        ('markov_predict', '馬可夫鏈'),
        ('statistical_predict', '統計綜合'),
        ('zone_balance_predict', '區域平衡'),
        ('frequency_predict', '頻率分析')
    ]
    
    # 用於存儲每個號碼在各方法中的加權得分 (模擬 Ensemble)
    ensemble_scores = Counter()
    
    for func_name, display_name in methods:
        try:
            res = getattr(engine, func_name)(history, rules)
            pred_nums = res['numbers']
            rank_actuals_in_prediction(display_name, pred_nums, ACTUAL_SET)
            
            # 簡單加權模擬: Top 10 = 3分, Top 20 = 1分
            for i, n in enumerate(pred_nums):
                if i < 10:
                    ensemble_scores[n] += 3
                elif i < 20:
                    ensemble_scores[n] += 1
        except Exception as e:
            print(f"⚠️ {display_name} 執行失敗: {e}")

    # 3. 綜合評分排名
    print("\n🗳️ 3. 綜合 Ensemble 分析")
    sorted_ensemble = [n for n, s in ensemble_scores.most_common()]
    rank_actuals_in_prediction("Ensemble (綜合加權)", sorted_ensemble, ACTUAL_SET)

    # 4. 特別號分析
    print("\n🌟 4. 特別號 (12) 分析")
    # 這裡可以加入特別號的簡單檢查 (例如看它在不在最近的熱門列表)
    # 簡單檢查頻率
    specials = [d['special'] for d in history[:50]]
    if 12 in specials[:5]:
        print("   特別號 12 近期(5期內)曾出現")
    else:
        print("   特別號 12 近期未出現")
    
if __name__ == '__main__':
    main()
