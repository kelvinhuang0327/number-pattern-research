#!/usr/bin/env python3
"""
威力彩 115000005 期回溯分析
實際開獎: 08, 10, 16, 26, 31, 38 + 05 (第二區)
分析目標:
1. 哪個預測方法最接近
2. 為什麼沒預測到
3. 是否有特別跡象或特徵
4. 為什麼第二區 05 沒預測到，都預測01?  
"""
import sys
import os
import json
from collections import Counter
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.power_lotto_predictor import PowerLottoPredictor

# 實際開獎號碼
ACTUAL_NUMBERS = [8, 10, 16, 26, 31, 38]
ACTUAL_SPECIAL = 5
DRAW_NUMBER = '115000005'
DRAW_DATE = '115/01/15'

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
        special = d.get('special', d.get('special_number'))
        if special:
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
    
    # 模擬預測情境：使用 115000004 及之前的數據來進行預測
    # （假設我們在 115000005 開獎前進行預測）
    print(f"\n📚 獲取歷史數據: {len(all_history)} 期總計")
    
    # 找到 115000004，使用其及之前的所有數據作為歷史
    history = []
    for d in all_history:
        if d['draw'] <= '115000004':
            history.append(d)
    
    if not history:
        print(f"\n❌ 找不到 115000004 或更早的歷史數據")
        return
    
    print(f"使用歷史數據: {len(history)} 期 (最新: {history[0]['draw']} {history[0]['date']}, 最早: {history[-1]['draw']})")
    print(f"準備預測: 第 {DRAW_NUMBER} 期")
    
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
    print(f"最常見: {special_analysis['most_common'][:3]}")
    
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
            prediction = func(history, rules)
            pred_nums = sorted(prediction.get('numbers', [])[:6])
            pred_special = prediction.get('special', prediction.get('special_number', 0))
            
            score_info = calculate_hit_score(pred_nums, ACTUAL_NUMBERS, pred_special, ACTUAL_SPECIAL)
            
            results.append({
                'method': name,
                'numbers': pred_nums,
                'special': pred_special,
                'hit_count': score_info['hit_count'],
                'hits': score_info['hits'],
                'special_hit': score_info['special_hit'],
                'near_hits': score_info['near_hits'],
                'score': score_info['score'],
                'confidence': prediction.get('confidence', 0)
            })
            
        except Exception as e:
            print(f"❌ {name} 方法執行失敗: {e}")
    
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
        
        if r['hits']:
            print(f"{'':25}   └─ 命中: {r['hits']}")
        if r['near_hits']:
            near_str = ', '.join([f"{p}≈{a}" for p, a in r['near_hits']])
            print(f"{'':25}   └─ 接近: {near_str}")
    
    # 找出表現最好的方法
    print(f"\n" + "=" * 100)
    print(f"🏆 分析結論:")
    print("=" * 100)
    
    if results:
        best = results[0]
        print(f"\n✅ 最佳預測方法: {best['method']}")
        print(f"   - 命中數: {best['hit_count']}/6")
        print(f"   - 命中號碼: {best['hits']}")
        print(f"   - 第二區: {best['special']:02d} ({'✓ 命中' if best['special_hit'] else '✗ 未中'})")
        print(f"   - 綜合得分: {best['score']}")
        
        if best['near_hits']:
            print(f"   - 接近號碼: {best['near_hits']}")
    
    # 第二區分析
    print(f"\n📌 第二區號碼分析:")
    special_predictions = [r['special'] for r in results]
    special_counter = Counter(special_predictions)
    
    print(f"   實際開出: {ACTUAL_SPECIAL:02d}")
    print(f"   各方法預測分布: {dict(special_counter)}")
    print(f"   預測 01 的方法數: {special_counter.get(1, 0)}/{len(results)}")
    print(f"   預測 05 的方法數: {special_counter.get(5, 0)}/{len(results)}")
    
    # 分析為何沒預測到
    print(f"\n🔬 未能預測的可能原因:")
    
    # 1. 特殊模式檢查
    print(f"\n1️⃣ 本期特殊模式:")
    if actual_features['consecutive_pairs'] == 0:
        print(f"   ⚠️ 無連號 - 較少見的模式")
    if actual_features['zone_distribution']['Zone1_1-13'] == 2 and \
       actual_features['zone_distribution']['Zone2_14-25'] == 1 and \
       actual_features['zone_distribution']['Zone3_26-38'] == 3:
        print(f"   ⚠️ 高值區(26-38)集中 - 3個號碼在高區")
    if actual_features['sum'] < 90 or actual_features['sum'] > 150:
        print(f"   ⚠️ 和值 {actual_features['sum']} 偏離常見區間")
    
    # 2. 歷史頻率檢查
    print(f"\n2️⃣ 號碼歷史頻率 (近100期):")
    freq_counter = Counter()
    for d in history[:100]:
        freq_counter.update(d.get('numbers', []))
    
    total_draws = min(100, len(history))
    expected_freq = total_draws * 6 / 38
    
    for num in ACTUAL_NUMBERS:
        freq = freq_counter.get(num, 0)
        freq_pct = (freq / expected_freq - 1) * 100 if expected_freq > 0 else 0
        status = "熱門" if freq_pct > 20 else "冷門" if freq_pct < -20 else "正常"
        print(f"   {num:02d}: {freq:3d} 次 ({freq_pct:+6.1f}% vs期望值) [{status}]")
    
    # 3. 第二區分析
    print(f"\n3️⃣ 第二區 05 號分析:")
    special_05_freq = special_analysis['frequency'].get(5, 0)
    special_01_freq = special_analysis['frequency'].get(1, 0)
    print(f"   05 近50期出現: {special_05_freq} 次 ({special_analysis['probabilities'].get(5, 0)*100:.1f}%)")
    print(f"   01 近50期出現: {special_01_freq} 次 ({special_analysis['probabilities'].get(1, 0)*100:.1f}%)")
    
    if 5 in special_analysis['recent_10']:
        last_idx = special_analysis['recent_10'].index(5)
        print(f"   ⚠️ 05 在近10期內第 {last_idx+1} 次出現 - 可能被視為「短期重複」而排除")
    else:
        print(f"   ⚠️ 05 近10期未出現 - 可能被視為冷門號而排除")
    
    # 保存詳細結果
    output = {
        'draw': DRAW_NUMBER,
        'date': DRAW_DATE,
        'actual': {
            'numbers': ACTUAL_NUMBERS,
            'special': ACTUAL_SPECIAL,
            'features': actual_features
        },
        'predictions': results,
        'special_analysis': special_analysis,
        'conclusion': {
            'best_method': results[0]['method'] if results else None,
            'best_score': results[0]['score'] if results else 0,
            'special_predictions': dict(special_counter)
        }
    }
    
    output_file = os.path.join(project_root, 'tools', 'retrospective_115000005_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 詳細結果已保存至: {output_file}")
    print("=" * 100)

if __name__ == '__main__':
    main()
