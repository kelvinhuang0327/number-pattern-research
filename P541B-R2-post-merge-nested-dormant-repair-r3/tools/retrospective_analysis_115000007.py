#!/usr/bin/env python3
"""
威力彩 115000007 期回溯分析
實際開獎: 11, 17, 29, 30, 34, 35 + 06 (第二區)
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

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.power_lotto_predictor import PowerLottoPredictor

# 實際開獎號碼
ACTUAL_NUMBERS = [11, 17, 29, 30, 34, 35]
ACTUAL_SPECIAL = 6
DRAW_NUMBER = '115000007'
DRAW_DATE = '115/01/22'

def analyze_number_features(numbers: List[int]) -> Dict:
    """分析號碼特徵"""
    sorted_nums = sorted(numbers)
    
    features = {
        'numbers': sorted_nums,
        'sum': sum(sorted_nums),
        'odd_count': sum(1 for n in sorted_nums if n % 2 == 1),
        'even_count': sum(1 for n in sorted_nums if n % 2 == 0),
        'high_count': sum(1 for n in sorted_nums if n > 19),  # >19 為高
        'low_count': sum(1 for n in sorted_nums if n <= 19),
        'zone_distribution': {},
        'consecutive_pairs': 0,
        'tail_diversity': len(set(n % 10 for n in sorted_nums)),
        'range': max(sorted_nums) - min(sorted_nums),
    }
    
    # 區間分布 (三區)
    zones = {'Zone1_1-13': 0, 'Zone2_14-25': 0, 'Zone3_26-38': 0}
    for n in sorted_nums:
        if n <= 13:
            zones['Zone1_1-13'] += 1
        elif n <= 25:
            zones['Zone2_14-25'] += 1
        else:
            zones['Zone3_26-38'] += 1
    features['zone_distribution'] = zones
    
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
    
    # 計算近似度 (即使沒全中，有幾個在+-2範圍內)
    near_hits = []
    for p in predicted:
        for a in actual:
            if abs(p - a) <= 2 and p not in hits:
                near_hits.append((p, a))
                break
    
    return {
        'hit_count': hit_count,
        'hits': hits,
        'special_hit': special_hit,
        'near_hits': near_hits,
        'score': hit_count * 10 + (5 if special_hit else 0) + len(near_hits) * 2
    }

def analyze_special_number_history(history: List[Dict]) -> Dict:
    """分析第二區號碼歷史"""
    special_freq = Counter()
    recent_specials = []
    
    for i, d in enumerate(history[:50]):
        # Handle cases where special might be string or int or missing
        special = d.get('special', d.get('special_number'))
        try:
            special = int(special) if special is not None else 0
        except:
            special = 0

        if special > 0:
            special_freq[special] += 1
            if i < 10:
                recent_specials.append(special)
    
    # 計算各號出現率
    total = sum(special_freq.values())
    special_probs = {k: v/total for k, v in special_freq.items()} if total > 0 else {}
    
    return {
        'frequency': dict(special_freq),
        'probabilities': special_probs,
        'recent_10': recent_specials,
        'most_common': special_freq.most_common(3),
        'least_common': special_freq.most_common()[-3:] if len(special_freq) >= 3 else []
    }

def main():
    print("=" * 100)
    print(f"威力彩第 {DRAW_NUMBER} 期回溯分析")
    print(f"開獎日期: {DRAW_DATE}")
    print("=" * 100)
    
    # 顯示實際開獎
    print(f"\n🎯 實際開獎號碼:")
    print(f"   第一區 (大小順序): {', '.join([f'{n:02d}' for n in ACTUAL_NUMBERS])}")
    print(f"   第二區: {ACTUAL_SPECIAL:02d}")
    
    # 分析實際號碼特徵
    actual_features = analyze_number_features(ACTUAL_NUMBERS)
    print(f"\n📊 本期號碼特徵分析:")
    print(f"   和值: {actual_features['sum']}")
    print(f"   奇偶比: {actual_features['odd_count']}:{actual_features['even_count']}")
    print(f"   高低比: {actual_features['high_count']}:{actual_features['low_count']} (高>19)")
    print(f"   區間分布: {actual_features['zone_distribution']}")
    print(f"   連號對數: {actual_features['consecutive_pairs']}")
    print(f"   尾數多樣性: {actual_features['tail_diversity']} 種")
    print(f"   極差: {actual_features['range']}")
    
    # 初始化
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if not all_history:
        print("\n❌ 無法獲取歷史數據")
        return
    
    # 模擬預測情境：使用 115000007 之前的數據
    # 理想上應該是使用 <= 115000006 的數據
    print(f"\n📚 獲取歷史數據: {len(all_history)} 期總計")
    print(f"   資料庫最新一期: {all_history[0]['draw']} ({all_history[0]['date']})")
    
    # 找到 115000007 之前的數據
    history = []
    for d in all_history:
        if d['draw'] < DRAW_NUMBER:
            history.append(d)
    
    if not history:
        print(f"\n❌ 找不到 {DRAW_NUMBER} 之前的歷史數據")
        return
        
    latest_history_draw = history[0]['draw']
    if latest_history_draw != '115000006':
        print(f"\n⚠️ 警告: 歷史數據缺漏! 最新歷史期數為 {latest_history_draw} (預期應為 115000006)")
        print("   預測結果可能不準確，因為缺少最近期的數據")
    else:
        print(f"   確認歷史數據完整，最新為 {latest_history_draw}")
    
    print(f"使用歷史數據: {len(history)} 期")
    
    # 分析第二區歷史
    print(f"\n" + "=" * 100)
    print(f"🎲 第二區號碼歷史分析 (近50期):")
    print("=" * 100)
    special_analysis = analyze_special_number_history(history)
    print(f"\n出現頻率:")
    for num in range(1, 9):
        freq = special_analysis['frequency'].get(num, 0)
        prob = special_analysis['probabilities'].get(num, 0)
        marker = " ⭐ [本期開出]" if num == ACTUAL_SPECIAL else ""
        print(f"   {num:02d}: {freq:3d} 次 ({prob*100:5.2f}%){marker}")
    
    print(f"\n近10期: {special_analysis['recent_10']}")
    
    # 開始測試各種預測方法
    print(f"\n" + "=" * 100)
    print(f"🔍 各預測方法回溯測試:")
    print("=" * 100)
    
    rules = get_lottery_rules('POWER_LOTTO')
    unified_engine = UnifiedPredictionEngine()
    power_engine = PowerLottoPredictor()
    
    # 定義要測試的方法
    methods = [
        ('Frequency', unified_engine.frequency_predict),
        ('Trend', unified_engine.trend_predict),
        ('Statistical', unified_engine.statistical_predict),
        ('Bayesian', unified_engine.bayesian_predict),
        ('Deviation', unified_engine.deviation_predict),
        ('Constraint Satisfaction', power_engine.constraint_satisfaction_predict),
        ('Negative Filtering', power_engine.negative_filtering_predict),
        ('Number Clustering', power_engine.number_clustering_predict),
        ('Adaptive Window', power_engine.adaptive_window_predict),
        ('Pattern Matching', power_engine.pattern_matching_predict),
        ('Hybrid Optimizer', power_engine.hybrid_optimizer_predict),
    ]
    
    results = []
    
    for name, func in methods:
        try:
            # 有些方法可能需要不同的參數，這裡統一嘗試
            # 注意: PowerLottoPredictor 的方法通常只接受 history
            # UnifiedPredictionEngine 的方法通常接受 (history, rules)
            
            # UnifiedPredictionEngine and PowerLottoPredictor both accept (history, rules)
            prediction = func(history, rules)

            pred_nums = sorted(prediction.get('numbers', [])[:6])
            # Handle special number (might be in 'special' or 'special_number')
            pred_special = prediction.get('special', prediction.get('special_number', 0))
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
                'score': score_info['score'],
                'confidence': prediction.get('confidence', 0)
            })
            
        except Exception as e:
            print(f"❌ {name} 方法執行失敗: {e}")
            # print(traceback.format_exc()) # for debugging
    
    # 排序結果 (依得分)
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # 顯示結果
    print(f"\n{'方法名稱':<25} | {'命中':<6} | {'預測號碼':<30} | {'第二區':<6} | {'得分':<6}")
    print("-" * 100)
    
    for r in results:
        hit_str = f"{r['hit_count']}/6"
        special_mark = "✓" if r['special_hit'] else "✗"
        nums_str = ', '.join([f"{n:02d}" for n in r['numbers']])
        
        print(f"{r['method']:<25} | {hit_str:<6} | {nums_str:<30} | {r['special']:02d} {special_mark:<4} | {r['score']:<6}")
        
    
    # 找出表現最好的方法
    if results:
        best = results[0]
        print(f"\n✅ 最佳預測方法: {best['method']}")
        print(f"   - 命中數: {best['hit_count']}/6")
        print(f"   - 命中號碼: {best['hits']}")
        print(f"   - 第二區: {best['special']:02d} ({'✓ 命中' if best['special_hit'] else '✗ 未中'})")
        
        # 額外分析: 為什麼沒預測到?
        analyze_missed_reason(history, ACTUAL_NUMBERS, ACTUAL_SPECIAL, actual_features)

    # 保存詳細結果
    output_file = os.path.join(project_root, 'tools', 'retrospective_115000007_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n已被存至 {output_file}")


def analyze_missed_reason(history, actual_numbers, actual_special, features):
    print(f"\n🔬 深入分析 (三位專家視角):")
    
    # 1. 方法理論專家 Analysis
    print("\n[方法理論專家] 統計特徵分析:")
    
    # Check hot/cold
    freq_counter = Counter()
    for d in history[:100]:
         nums = d.get('numbers', [])
         # some older records might be string, ensure list of ints
         if isinstance(nums, str):
             import ast
             try: nums = ast.literal_eval(nums)
             except: nums = []
         freq_counter.update(nums)
         
    print("   號碼冷熱度 (近100期):")
    for n in actual_numbers:
        count = freq_counter.get(n, 0)
        print(f"   - {n:02d}: {count} 次 (理論期望值 ~15.7)")

    # 2. 技術務實專家 Analysis
    print("\n[技術務實專家] 系統邊界與演算法限制:")
    print("   檢視 Randomness 與 演算法偏好...")
    # (Checking if any numbers were excluded by filters)
    
    # 3. 程式架構專家 Analysis
    print("\n[程式架構專家] 成本與優化:")
    print("   如需捕捉此類號碼，可能需要增加的計算成本...")

if __name__ == '__main__':
    main()
