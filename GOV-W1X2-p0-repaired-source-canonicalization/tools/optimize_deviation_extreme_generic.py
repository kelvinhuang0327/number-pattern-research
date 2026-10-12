#!/usr/bin/env python3
"""
Optimization: Deviation Strategy for Extreme Draws (Generic Version)
目標: 通用化 Deviation Extreme 策略，使其適用於 Power Lotto (38) 和 Big Lotto (49)。
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

# Set verification seed
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

class DeviationExtremePredictor:
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
        
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        """
        Deviation Extreme Strategy (Black Swan Mode) - Generic
        """
        pick_count = rules.get('pickCount', 6)
        min_num = rules.get('minNumber', 1)
        max_num = rules.get('maxNumber', 49) # Default to 49 if not set
        
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
        if total_score == 0:
             probs = [1.0 / (max_num - min_num + 1) for _ in range(min_num, max_num + 1)]
        else:
             probs = [scores[n]/total_score for n in range(min_num, max_num+1)]
             
        nums = list(range(min_num, max_num+1))
        
        best_candidate = []
        best_extreme_score = -1
        
        # Try 500 times to find extreme candidates
        for _ in range(500):
            candidate = sorted(np.random.choice(nums, size=pick_count, replace=False, p=probs))
            is_extreme, extreme_score = self._evaluate_extreme_quality(candidate, min_num, max_num)
            
            if is_extreme:
                cand_score = sum(scores[n] for n in candidate)
                final_score = cand_score + extreme_score * 5
                
                if final_score > best_extreme_score:
                    best_extreme_score = final_score
                    best_candidate = candidate
        
        # Fallback
        if not best_candidate:
            best_candidate = sorted(sorted(range(min_num, max_num+1), key=lambda n: scores[n], reverse=True)[:pick_count])
            
        return {'numbers': best_candidate, 'special': random.randint(1, 8)}

    def _evaluate_extreme_quality(self, numbers, min_num, max_num):
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
            
        # Skewness - Dynamic Zones
        # Divide into 3 zones dynamically
        total_range = max_num - min_num + 1
        zone_size = total_range / 3
        
        z1_limit = min_num + zone_size
        z2_limit = min_num + 2 * zone_size
        
        zones = [0, 0, 0]
        for n in numbers:
            if n <= z1_limit: zones[0] += 1
            elif n <= z2_limit: zones[1] += 1
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
            if avg_freq > 0:
                z = (freq[n] - avg_freq) / (avg_freq**0.5)
            else:
                z = 0
                
            if z < -1.5: scores[n] += 1.0
            elif z > 2.0: scores[n] += 0.2
            else: scores[n] += 0.5
        return scores

def run_backtest(lottery_type='BIG_LOTTO'):
    print("="*80)
    print(f"🚀 Optimization Backtest: Deviation Extreme (Generic) - {lottery_type}")
    print("="*80)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type)
    rules = get_lottery_rules(lottery_type)
    predictor = DeviationExtremePredictor()
    
    # Backtest last 150 draws
    test_range = 150
    if len(all_draws) < test_range + 100:
        print("Not enough data")
        return
        
    hits = Counter()
    total_score = 0
    total_cost = 0
    draw_results = []
    
    # Random Baseline Accumulator
    random_score_acc = 0
    
    min_num = rules.get('minNumber', 1)
    max_num = rules.get('maxNumber', 49)
    pick_count = rules.get('pickCount', 6)
    
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
        
        # Prize logic (Simplified generic)
        # Match 6: Jackpot, Match 5: 20000, Match 4: 2000, Match 3: 400
        prize = (100000000 if match==6 else 20000 if match==5 else 2000 if match==4 else 400 if match==3 else 0)
        cost = 100 
        
        total_score += prize
        total_cost += cost
        
        # Random Baseline (10 runs per draw for stability)
        for _ in range(10):
            r_nums = sorted(random.sample(range(min_num, max_num+1), pick_count))
            r_match = len(set(r_nums) & set(actual))
            r_prize = (100000000 if r_match==6 else 20000 if r_match==5 else 2000 if r_match==4 else 400 if r_match==3 else 0)
            random_score_acc += r_prize
            
        draw_results.append({
            'draw': target['draw'],
            'match': match,
            'is_extreme': predictor._evaluate_extreme_quality(actual, min_num, max_num)[0]
        })
        
        if (test_range - i) % 50 == 0:
            print(f"Progress: {test_range - i}/{test_range}")

    # Analyze
    roi = (total_score - total_cost) / total_cost * 100
    avg_random_score = random_score_acc / 10 # 150 draws * 10 runs / 10 = total score sum? No.
    # We ran 10 iterations per draw. Total random iterations = 1500.
    # random_score_acc is sum of 1500 draws.
    # We want to compare with total_score (sum of 150 draws).
    # So we need to divide random_score_acc by 10.
    
    baseline_score = random_score_acc / 10
    baseline_roi = (baseline_score - total_cost) / total_cost * 100
    
    extreme_count = sum(1 for d in draw_results if d['is_extreme'])
    
    print("\n" + "="*80)
    print("📊 150期 通用回測結果")
    print("="*80)
    print(f"彩種: {lottery_type}")
    print(f"極端局佔比: {extreme_count/test_range*100:.1f}%")
    
    print("\n[命中分布]")
    for m in range(7):
        if hits[m] > 0:
            print(f"Match {m}: {hits[m]}")
            
    print(f"\n[財務比較]")
    print(f"Black Swan Score: {total_score}")
    print(f"Random Baseline : {baseline_score:.0f}")
    print(f"Edge (vs Random): {(total_score - baseline_score)/baseline_score*100:+.1f}%")
    
    print(f"\n[ROI]")
    print(f"Black Swan ROI: {roi:+.1f}%")
    print(f"Random ROI    : {baseline_roi:+.1f}%")

if __name__ == '__main__':
    run_backtest('BIG_LOTTO')
