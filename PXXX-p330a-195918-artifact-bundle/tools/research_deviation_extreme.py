#!/usr/bin/env python3
"""
Research: Deviation Strategy Performance on Extreme Draws
目標: 驗證 Deviation 策略在「極端」牌局中的表現，是否有正期望值。
"""

import sys
import os
import json
import random
from collections import Counter
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

def is_extreme_draw(numbers: List[int], history_before: List[Dict]) -> Dict:
    """
    判斷是否為「極端」牌局
    Backtest criteria:
    1. Skewness: 3+ numbers in Zone 3 (26-38) OR Zone 1 (1-13).
    2. Clustering: At least one consecutive sequence_length >= 3 OR two pairs.
    3. Sum Deviation: Sum < 80 OR Sum > 150.
    4. Extreme Cold: Contains 2+ numbers with frequency < 10 in last 100 draws.
    """
    reasons = []
    sorted_nums = sorted(numbers)
    
    # 1. Skewness
    zones = [0, 0, 0] # 1-13, 14-25, 26-38
    for n in sorted_nums:
        if n <= 13: zones[0] += 1
        elif n <= 25: zones[1] += 1
        else: zones[2] += 1
        
    if zones[0] >= 3: reasons.append(f"Skewness: Zone1 has {zones[0]}")
    if zones[2] >= 3: reasons.append(f"Skewness: Zone3 has {zones[2]}")
    
    # 2. Clustering
    consecutive_pairs = 0
    max_sequence = 1
    current_sequence = 1
    for i in range(len(sorted_nums) - 1):
        if sorted_nums[i+1] - sorted_nums[i] == 1:
            consecutive_pairs += 1
            current_sequence += 1
        else:
            max_sequence = max(max_sequence, current_sequence)
            current_sequence = 1
    max_sequence = max(max_sequence, current_sequence)
    
    if max_sequence >= 3: reasons.append(f"Clustering: Sequence len {max_sequence}")
    if consecutive_pairs >= 2: reasons.append(f"Clustering: {consecutive_pairs} pairs")
    
    # 3. Sum Deviation
    total_sum = sum(sorted_nums)
    if total_sum < 80: reasons.append(f"Sum: {total_sum} < 80")
    if total_sum > 150: reasons.append(f"Sum: {total_sum} > 150")
    
    # 4. Extreme Cold
    # Need history to calculate coldness
    if len(history_before) >= 100:
        freq_counter = Counter()
        for d in history_before[:100]:
            # handle legacy data format if needed, assume list of ints
            nums = d.get('numbers', [])
            if isinstance(nums, str): # safety check
                try: nums = eval(nums)
                except: nums = []
            freq_counter.update(nums)
            
        cold_count = sum(1 for n in sorted_nums if freq_counter.get(n, 0) < 10)
        if cold_count >= 2:
            reasons.append(f"Cold: {cold_count} numbers < 10 freq")
            
    is_extreme = len(reasons) >= 2
    return {
        'is_extreme': is_extreme,
        'reasons': reasons,
        'features': {
            'zones': zones,
            'max_seq': max_sequence,
            'pairs': consecutive_pairs,
            'sum': total_sum
        }
    }

def calculate_matches(pred: List[int], actual: List[int]):
    return len(set(pred) & set(actual))

def main():
    print("=" * 80)
    print("🔬 Deviation 策略極端行情回測 (Verification)")
    print("=" * 80)
    
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = db.get_all_draws(lottery_type='POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    engine = UnifiedPredictionEngine()
    
    # 取最近 500 期進行回測
    test_draws = all_draws[0:500] 
    # 注意: all_draws 通常是新到舊，所以我們要倒過來遍歷，模擬時間推進
    # 但為了方便取得 "history_before", 我們維持列表，index 越小越新
    
    extreme_draw_count = 0
    deviation_hits = Counter() # 3, 4, 5, 6 matches
    random_hits = Counter()  # Kept for compatibility but not used for main score
    global_random_score_total = 0
    
    deviation_cluster_pred_count = 0 # How often does it predict clusters?
    deviation_cold_picked_count = 0 # How often does it pick cold numbers?
    
    results = []
    
    print(f"總樣本數: {len(test_draws)} 期")
    print("正在篩選極端牌局並進行回測...\n")
    
    # 我們需要足夠的歷史數據來預測，所以從 test_draws 的尾端開始往回走，但保留足夠的 history
    # 假設我們至少需要 100 期歷史
    
    # test_draws[i] is current target
    # history is test_draws[i+1:] + remaining all_draws
    
    start_idx = 0
    end_idx = 400 # Leave 100 buffer if needed, or just iterate all valid
    
    for i in range(start_idx, end_idx):
        if i % 50 == 0:
            print(f"Progress: {i}/{end_idx}")
            
        target_draw = test_draws[i]
        history = test_draws[i+1:] + all_draws[500:] # Complete history roughly
        
        if len(history) < 150: break # Safety break
        
        actual_nums = target_draw['numbers']
        if isinstance(actual_nums, str):
            try: actual_nums = eval(actual_nums)
            except: continue
        actual_nums = sorted(actual_nums)
        
        # Check if extreme
        extreme_info = is_extreme_draw(actual_nums, history)
        
        if extreme_info['is_extreme']:
            extreme_draw_count += 1
            
            # Run Prediction
            # 1. Deviation
            try:
                dev_pred = engine.deviation_predict(history, rules)
                dev_nums = sorted(dev_pred['numbers'][:6])
            except:
                dev_nums = []
                
            # 2. Random (Baseline) - Run 100 times to get stable average
            rand_matches = []
            for _ in range(100):
                r_nums = sorted(random.sample(range(1, 39), 6))
                rand_matches.append(calculate_matches(r_nums, actual_nums))
            
            # Evaluate
            dev_match = calculate_matches(dev_nums, actual_nums)
            
            # Store counts
            deviation_hits[dev_match] += 1
            
            # For random, we store the *average* distribution or just total score
            # Let's add to a total random score accumulator
            # And for hit distribution, we can't easily add partial hits to Counter integers
            # So we'll track "average random score" separately
            
            current_draw_rand_score = sum(
                (100000000 if m==6 else 20000 if m==5 else 2000 if m==4 else 400 if m==3 else 0) 
                for m in rand_matches
            ) / 100
            
            global_random_score_total += current_draw_rand_score

            results.append({
                'draw': target_draw['draw'],
                'actual': actual_nums,
                'type': extreme_info['reasons'],
                'deviation_pred': dev_nums,
                'dev_match': dev_match,
                'avg_rand_score': current_draw_rand_score
            })
            
    print("\n" + "="*80)
    print("📊 回測結果摘要 (修正版: Random 跑 100 次平均)")
    print("="*80)
    print(f"回測範圍: 近 {end_idx} 期")
    print(f"極端牌局數: {extreme_draw_count} (佔比 {extreme_draw_count/end_idx*100:.1f}%)")
    
    print("\n[命中率比較 - 極端局 (Deviation)]")
    for m in range(7):
        if deviation_hits[m] > 0:
            print(f"Match {m}: {deviation_hits[m]} 次")
            
    # Calculate scores
    def calc_score_from_hits(hits_dict):
        return hits_dict[3] * 400 + hits_dict[4] * 2000 + hits_dict[5] * 20000 + hits_dict[6] * 100000000
    
    dev_score = calc_score_from_hits(deviation_hits)
    rand_score = global_random_score_total # Already summed expectations
    
    cost = extreme_draw_count * 100
    dev_roi = (dev_score - cost) / cost * 100 if cost > 0 else 0
    rand_roi = (rand_score - cost) / cost * 100 if cost > 0 else 0

    print("\n[投資效益分析 (模擬)]")
    print(f"Deviation Score: {dev_score:.0f}")
    print(f"Random Score:    {rand_score:.0f} (Expected Value)")
    print(f"Cost:            {cost}")
    print(f"Deviation ROI:   {dev_roi:+.1f}%")
    print(f"Random ROI:      {rand_roi:+.1f}%")
    
    relative_edge = (dev_score - rand_score) / rand_score * 100 if rand_score > 0 else 0
    print(f"\nDeviation 相對 Random 優勢: {relative_edge:+.1f}%")

    # Output detailed JSON
    with open('tools/deviation_extreme_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n詳細報告已存至 tools/deviation_extreme_results.json")

    # Conclusion
    print("\n[結論]")
    if dev_score > rand_score:
        print("✅ Deviation 在極端局表現優於隨機 (驗證成功)")
    else:
        print("❌ Deviation 在極端局表現未優於隨機 (驗證失敗)")

if __name__ == '__main__':
    main()
