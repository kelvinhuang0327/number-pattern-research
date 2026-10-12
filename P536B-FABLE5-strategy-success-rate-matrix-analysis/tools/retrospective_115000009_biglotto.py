#!/usr/bin/env python3
"""
大樂透 115000009 期回溯分析
實際開獎: 09, 13, 27, 31, 32, 39 + 19 (特別號)
分析目標:
1. 哪個預測方法最接近
2. 為什麼沒預測到
3. 是否有特別跡象或特徵
"""
import sys
import os
import json
from collections import Counter
from typing import List, Dict

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

# 實際開獎號碼
ACTUAL_NUMBERS = [9, 13, 27, 31, 32, 39]
ACTUAL_SPECIAL = 19
DRAW_NUMBER = '115000009'
DRAW_DATE = '115/01/30'

def analyze_number_features(numbers: List[int]) -> Dict:
    """分析號碼特徵"""
    sorted_nums = sorted(numbers)
    
    features = {
        'numbers': sorted_nums,
        'sum': sum(sorted_nums),
        'odd_count': sum(1 for n in sorted_nums if n % 2 == 1),
        'even_count': sum(1 for n in sorted_nums if n % 2 == 0),
        'high_count': sum(1 for n in sorted_nums if n > 25),  # Big Lotto split at 25
        'low_count': sum(1 for n in sorted_nums if n <= 25),
        'consecutive_pairs': 0,
        'tail_diversity': len(set(n % 10 for n in sorted_nums)),
        'range': max(sorted_nums) - min(sorted_nums),
    }
    
    # 連號對
    for i in range(len(sorted_nums) - 1):
        if sorted_nums[i+1] - sorted_nums[i] == 1:
            features['consecutive_pairs'] += 1
    
    return features

def calculate_hit_score(predicted: List[int], actual: List[int], pred_special: int, actual_special: int) -> Dict:
    """計算命中分數"""
    hits = sorted(list(set(predicted) & set(actual)))
    hit_count = len(hits)
    special_hit = (pred_special == actual_special)
    
    # 計算近似度 (+-1 範圍內)
    near_hits = []
    for p in predicted:
        for a in actual:
            if abs(p - a) <= 1 and p not in hits:
                near_hits.append((p, a))
                break
    
    return {
        'hit_count': hit_count,
        'hits': hits,
        'special_hit': special_hit,
        'near_hits': near_hits,
        'score': hit_count * 10 + (10 if special_hit else 0) + len(near_hits) * 2
    }

def main():
    print("=" * 100)
    print(f"大樂透第 {DRAW_NUMBER} 期回溯分析")
    print(f"開獎日期: {DRAW_DATE}")
    print("=" * 100)
    
    # 顯示實際開獎
    print(f"\n🎯 實際開獎號碼:")
    print(f"   主區 (大小順序): {', '.join([f'{n:02d}' for n in ACTUAL_NUMBERS])}")
    print(f"   特別號: {ACTUAL_SPECIAL:02d}")
    
    # 分析實際號碼特徵
    actual_features = analyze_number_features(ACTUAL_NUMBERS)
    print(f"\n📊 本期號碼特徵分析:")
    print(f"   和值: {actual_features['sum']} (均值 {actual_features['sum']/6:.1f})")
    print(f"   奇偶比: {actual_features['odd_count']}:{actual_features['even_count']}")
    print(f"   高低比: {actual_features['high_count']}:{actual_features['low_count']} (高>25)")
    print(f"   連號對數: {actual_features['consecutive_pairs']} (31, 32)")
    print(f"   尾數多樣性: {actual_features['tail_diversity']} 種 (9, 3, 7, 1, 2, 9 -> 9, 3, 7, 1, 2)")
    print(f"   極差: {actual_features['range']}")
    
    # 初始化
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='BIG_LOTTO')
    
    if not all_history:
        print("\n❌ 無法獲取歷史數據")
        return
    
    # 找到 115000009 之前的數據
    history = []
    for d in all_history:
        if d['draw'] < DRAW_NUMBER:
            history.append(d)
    
    print(f"\n📚 獲取歷史數據: {len(history)} 期 (排除目標期)")
    latest_history_draw = history[0]['draw']
    print(f"   最新歷史期數: {latest_history_draw}")
    
    # 開始測試各種預測方法
    print(f"\n" + "=" * 100)
    print(f"🔍 各預測方法回溯測試 (Top-1 Bet Only):")
    print("=" * 100)
    
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()
    
    # 定義要測試的方法
    methods = [
        ('Frequency', engine.frequency_predict),
        ('Trend', engine.trend_predict),
        ('Statistical', engine.statistical_predict),
        ('Bayesian', engine.bayesian_predict),
        ('Deviation', engine.deviation_predict),
        ('Markov', engine.markov_predict),
        ('Clustering', engine.clustering_predict),
        ('Entropy', engine.entropy_predict),
    ]
    
    results = []
    
    for name, func in methods:
        try:
            # Run prediction
            prediction = func(history, rules)
            
            # Predict can return a single bet or multiple bets
            # Some returns {'numbers': [...], 'special': ...}
            # Some returns list of such dicts
            
            if isinstance(prediction, list):
                top_pred = prediction[0]
            else:
                top_pred = prediction

            pred_nums = sorted(top_pred.get('numbers', [])[:6])
            pred_special = top_pred.get('special', top_pred.get('special_number', 0))
            if isinstance(pred_special, list) and len(pred_special) > 0:
                pred_special = pred_special[0]
            
            score_info = calculate_hit_score(pred_nums, ACTUAL_NUMBERS, int(pred_special), ACTUAL_SPECIAL)
            
            results.append({
                'method': name,
                'numbers': pred_nums,
                'special': int(pred_special),
                'hit_count': score_info['hit_count'],
                'hits': score_info['hits'],
                'special_hit': score_info['special_hit'],
                'near_hits': score_info['near_hits'],
                'score': score_info['score']
            })
            
        except Exception as e:
            print(f"❌ {name} 方法執行失敗: {e}")
    
    # 排序結果 (依得分)
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # 顯示結果
    print(f"\n{'方法名稱':<25} | {'命中':<6} | {'預測號碼':<30} | {'特別號':<6} | {'得分':<6}")
    print("-" * 100)
    
    for r in results:
        hit_str = f"{r['hit_count']}/6"
        special_mark = "✓" if r['special_hit'] else "✗"
        nums_str = ', '.join([f"{n:02d}" for n in r['numbers']])
        
        print(f"{r['method']:<25} | {hit_str:<6} | {nums_str:<30} | {r['special']:02d} {special_mark:<4} | {r['score']:<6}")
    
    # 深入分析缺失原因
    analyze_missed_reason(history, ACTUAL_NUMBERS, ACTUAL_SPECIAL, actual_features)

def analyze_missed_reason(history, actual_numbers, actual_special, features):
    print(f"\n" + "=" * 100)
    print(f"🔬 深入分析 (產品設計評審團):")
    print("=" * 100)
    
    # 1. 歷史頻率分析
    freq_counter = Counter()
    for d in history[:100]:
         nums = d.get('numbers', [])
         if isinstance(nums, str):
             try: nums = json.loads(nums)
             except: nums = []
         freq_counter.update(nums)
    
    print("\n[方法理論專家] 統計特徵分析:")
    print("   1. 號碼冷熱度評估 (近100期):")
    for n in actual_numbers:
        count = freq_counter.get(n, 0)
        status = "🔥 熱" if count > 15 else "❄️ 冷" if count < 8 else "😐 中"
        print(f"      - {n:02d}: {count} 次 ({status})")
    
    print("\n   2. 組合特徵:")
    print(f"      - 奇偶比 {features['odd_count']}:{features['even_count']} 為極端分佈 (預期 3:3)")
    print(f"      - 連號 (31, 32) 出現，通常在統計模型中權重較低")
    print(f"      - 尾數 9 出現兩次 (09, 39)，屬於尾數回補現象")

    print("\n[技術務實專家] 系統邊界與演算法限制:")
    print("   1. 偏差(Deviation)偵測失效: 本期號碼並非處於標準差極端，但分佈偏向奇數，模型若過於依賴平衡奇偶則會失效。")
    print("   2. 搜索窄域: 目前 2-bet 搜索空間僅限於 Top-N 高機率組合，未能覆蓋冷熱交替的黑天鵝事件。")

    print("\n[程式架構專家] 實作成本與優先級:")
    print("   1. 特徵工程瓶頸: 目前特徵維度不足以捕捉「尾數相關性」與「跨期節奏」。")
    print("   2. AIFeasibility: 建議導入 GNN (圖神經網路) 來分析號碼間的聯結強度，而非單純頻率。")

if __name__ == '__main__':
    main()
