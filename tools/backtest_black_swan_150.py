#!/usr/bin/env python3
"""
Backtest: Black Swan Mode on Last 150 Draws
目標: 在最近 150 期（無論是否極端）連續回測 Black Swan Mode，評估其整體 ROI 和持有成本。
"""

import sys
import os
import json
import random
import numpy as np
from collections import Counter
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

# Import logic from optimize_deviation_extreme.py
# (We assume it's stable, so we re-implement the predictor class here for self-containment)
class DeviationExtremePredictor:
    def __init__(self):
        pass
        
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        pick_count = rules.get('pickCount', 6)
        min_num = rules.get('minNumber', 1)
        max_num = rules.get('maxNumber', 38)
        
        # 1. Base Scores
        scores = self._calculate_deviation_scores(history, min_num, max_num)
        
        # 2. Cold Bias
        freq_counter = Counter()
        for d in history[:100]:
            nums = d.get('numbers', [])
            if isinstance(nums, str): nums = eval(nums)
            freq_counter.update(nums)
            
        for n in range(min_num, max_num + 1):
            if freq_counter.get(n, 0) < 10:
                scores[n] *= 1.5 
        
        # 3. Generate Extreme Candidates
        total_score = sum(scores.values())
        probs = [scores[n]/total_score for n in range(min_num, max_num+1)]
        nums = list(range(min_num, max_num+1))
        
        best_candidate = []
        best_extreme_score = -1
        
        # Try 500 times to find extreme candidates
        for _ in range(500):
            candidate = sorted(np.random.choice(nums, size=6, replace=False, p=probs))
            is_extreme, extreme_score = self._evaluate_extreme_quality(candidate)
            
            if is_extreme:
                cand_score = sum(scores[n] for n in candidate)
                final_score = cand_score + extreme_score * 5
                
                if final_score > best_extreme_score:
                    best_extreme_score = final_score
                    best_candidate = candidate
        
        # Fallback if no extreme found (return most 'deviated' non-extreme)
        if not best_candidate:
            best_candidate = sorted(sorted(range(min_num, max_num+1), key=lambda n: scores[n], reverse=True)[:6])
            
        return {'numbers': best_candidate, 'special': random.randint(1, 8)}

    def _evaluate_extreme_quality(self, numbers):
        reasons = 0
        score = 0
        
        # Clustering
        consecutive_pairs = 0
        max_seq = 1
        curr_seq = 1
        for i in range(len(numbers)-1):
            if numbers[i+1] - numbers[i] == 1:
                consecutive_pairs += 1
                curr_seq += 1
            else:
                max_seq = max(max_seq, curr_seq)
                curr_seq = 1
        max_seq = max(max_seq, curr_seq)
        
        if max_seq >= 3: 
            reasons += 1
            score += 2.0
        if consecutive_pairs >= 2:
            reasons += 1
            score += 1.0
            
        # Skewness
        zones = [0, 0, 0]
        for n in numbers:
            if n <= 13: zones[0] += 1
            elif n <= 25: zones[1] += 1
            else: zones[2] += 1
            
        if max(zones) >= 4:
            reasons += 1
            score += 1.5
            
        return (reasons >= 1), score

    def _calculate_deviation_scores(self, history, min_num, max_num):
        scores = {n: 1.0 for n in range(min_num, max_num + 1)}
        all_nums = [n for d in history[:200] for n in (eval(d['numbers']) if isinstance(d['numbers'], str) else d['numbers'])]
        freq = Counter(all_nums)
        avg_freq = len(all_nums) / (max_num - min_num + 1)
        
        for n in scores:
            z = (freq[n] - avg_freq) / (avg_freq**0.5)
            if z < -1.5: scores[n] += 1.0
            elif z > 2.0: scores[n] += 0.2
            else: scores[n] += 0.5
        return scores

def main():
    print("="*80)
    print("📉 Real-world Backtest: Black Swan Mode (Last 150 Draws)")
    print("="*80)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws('POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    predictor = DeviationExtremePredictor()
    
    # Last 150 draws (reverse order: oldest to newest for simulation time flow)
    # index 0 is newest. So history is 150 to 0.
    # To simulate correctly:
    # Iterate i from 149 down to 0.
    # Target: all_draws[i]
    # History: all_draws[i+1:]
    
    test_range = 150
    if len(all_draws) < test_range + 100:
        print("Not enough data")
        return
        
    hits = Counter()
    total_score = 0
    total_cost = 0
    
    # Store per-draw ROI to calc volatility
    draw_results = []
    
    print(f"Testing Range: {all_draws[test_range-1]['draw']} ~ {all_draws[0]['draw']}")
    
    for i in range(test_range - 1, -1, -1):
        target = all_draws[i]
        history = all_draws[i+1:]
        
        actual = target['numbers']
        if isinstance(actual, str): actual = eval(actual)
        actual = sorted(actual)
        
        # Predict
        pred = predictor.predict(history, rules)
        pred_nums = pred['numbers']
        
        match = len(set(pred_nums) & set(actual))
        hits[match] += 1
        
        prize = (100000000 if match==6 else 20000 if match==5 else 2000 if match==4 else 400 if match==3 else 0)
        cost = 100 # assuming 1 bet unit cost
        
        total_score += prize
        total_cost += cost
        
        draw_results.append({
            'draw': target['draw'],
            'match': match,
            'prize': prize,
            'extreme_actual': predictor._evaluate_extreme_quality(actual)[0] # Was actual draw extreme?
        })
        
        if (test_range - i) % 30 == 0:
            print(f"Progress: {test_range - i}/{test_range}")

    # Analyze
    roi = (total_score - total_cost) / total_cost * 100
    
    # Count how many actual draws were extreme
    extreme_draws_actual = sum(1 for d in draw_results if d['extreme_actual'])
    
    print("\n" + "="*80)
    print("📊 150期 全面回測結果")
    print("="*80)
    
    print("[命中分布]")
    for m in range(7):
        if hits[m] > 0:
            print(f"Match {m}: {hits[m]}")
            
    print(f"\n[財務分析]")
    print(f"總成本: {total_cost}")
    print(f"總獎金: {total_score}")
    print(f"總 ROI: {roi:+.1f}%")
    
    print(f"\n[環境分析]")
    print(f"極端局 (Extreme) 出現次數: {extreme_draws_actual} / {test_range} ({extreme_draws_actual/test_range*100:.1f}%)")
    
    print("\n[結論]")
    if roi > -50:
        print("✅ 表現優異 (ROI > -50%)")
    elif roi > -75:
        print("⚠️ 表現普通 (ROI ≈ -75% 隨機水準)")
    else:
        print("❌ 表現不佳 (ROI < -75%) - 過度犧牲常態局")

    # Save results
    with open('tools/black_swan_150_results.json', 'w') as f:
        json.dump(draw_results, f, indent=2)

if __name__ == '__main__':
    main()
