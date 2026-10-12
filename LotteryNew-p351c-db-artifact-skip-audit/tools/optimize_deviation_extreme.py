#!/usr/bin/env python3
"""
Optimization: Deviation Strategy for Extreme Draws (Black Swan Mode)
目標: 優化 Deviation 策略，強制執行「極端」特徵（群聚、偏態），以捕捉黑天鵝。
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

class DeviationExtremePredictor:
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
        
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        """
        Deviation Extreme Strategy (Black Swan Mode)
        1. Base: Uses standard Deviation scoring matrix.
        2. Enforcement: FILTERS candidates that do not meet 'Extreme' criteria.
           - Must have Cluster (seq >= 2 or 2 pairs)
           - Must be Skewed (Zone bias)
        3. Cold Bias: Bonus weight for cold numbers.
        """
        # 1. Get Base Scores from Standard Deviation Logic
        # (We recreate the scoring logic here to access raw scores)
        pick_count = rules.get('pickCount', 6)
        min_num = rules.get('minNumber', 1)
        max_num = rules.get('maxNumber', 38) # Power Lotto
        
        # Calculate standard deviation scores
        scores = self._calculate_deviation_scores(history, min_num, max_num)
        
        # 2. Add Cold Bias (Explicitly boost cold numbers)
        freq_counter = Counter()
        for d in history[:100]:
            nums = d.get('numbers', [])
            if isinstance(nums, str): nums = eval(nums)
            freq_counter.update(nums)
            
        for n in range(min_num, max_num + 1):
            if freq_counter.get(n, 0) < 10:
                scores[n] *= 1.5 # 50% boost for cold numbers
        
        # 3. Generate Candidates & Filter
        # Instead of just picking top 6, we sample based on weights to generate many candidates
        # and keep only those that are "Extreme".
        
        total_score = sum(scores.values())
        probs = [scores[n]/total_score for n in range(min_num, max_num+1)]
        nums = list(range(min_num, max_num+1))
        
        best_candidate = []
        best_extreme_score = -1
        
        for _ in range(1000): # Try 1000 combinations
            candidate = sorted(np.random.choice(nums, size=6, replace=False, p=probs))
            
            # Check Extreme Criteria
            is_extreme, extreme_score = self._evaluate_extreme_quality(candidate)
            
            if is_extreme:
                # If valid extreme, calculate its 'Deviation Score' (sum of individual scores)
                cand_score = sum(scores[n] for n in candidate)
                
                # We want a balance: High Deviation Score AND High Extremeness
                final_score = cand_score + extreme_score * 5 # specific weight
                
                if final_score > best_extreme_score:
                    best_extreme_score = final_score
                    best_candidate = candidate
                    
        if not best_candidate:
            # Fallback to top scores if no extreme found (unlikely)
            best_candidate = sorted(sorted(range(min_num, max_num+1), key=lambda n: scores[n], reverse=True)[:6])
            
        return {
            'numbers': best_candidate,
            'special': random.randint(1, 8) # Placeholder
        }

    def _evaluate_extreme_quality(self, numbers):
        """
        Returns (is_extreme: bool, score: float)
        Score higher for more extreme features.
        """
        reasons = 0
        score = 0
        
        # 1. Clustering
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
            score += 2.0 # Huge bonus for triplets
        if consecutive_pairs >= 2:
            reasons += 1
            score += 1.0
            
        # 2. Skewness
        zones = [0, 0, 0]
        for n in numbers:
            if n <= 13: zones[0] += 1
            elif n <= 25: zones[1] += 1
            else: zones[2] += 1
            
        if max(zones) >= 4: # Very skewed (4+ in one zone)
            reasons += 1
            score += 1.5
            
        return (reasons >= 1), score

    def _calculate_deviation_scores(self, history, min_num, max_num):
        # Simplified standard deviation scoring from unified_predictor logic
        # (Re-implemented for standalone power)
        scores = {n: 1.0 for n in range(min_num, max_num + 1)}
        
        # Frequency Deviation
        all_nums = [n for d in history[:200] for n in (eval(d['numbers']) if isinstance(d['numbers'], str) else d['numbers'])]
        freq = Counter(all_nums)
        avg_freq = len(all_nums) / (max_num - min_num + 1)
        
        for n in scores:
            z = (freq[n] - avg_freq) / (avg_freq**0.5) # approx z
            if z < -1.5: scores[n] += 1.0 # Cold
            elif z > 2.0: scores[n] += 0.2 # Very Hot
            else: scores[n] += 0.5
            
        return scores

def run_backtest():
    print("="*80)
    print("🚀 Optimization Backtest: Deviation Extreme (Black Swan Mode)")
    print("="*80)
    
    # Load previously identified extreme draws
    try:
        with open('tools/deviation_extreme_results.json', 'r') as f:
            extreme_data = json.load(f)
    except:
        print("❌ 找不到極端局數據，請先執行 research_deviation_extreme.py")
        return

    predictor = DeviationExtremePredictor()
    rules = get_lottery_rules('POWER_LOTTO')
    
    results = []
    engine = UnifiedPredictionEngine()
    
    hits = Counter()
    total_score = 0
    
    # DB for history lookup
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws('POWER_LOTTO')
    draw_map = {d['draw']: d for d in all_draws}
    all_draw_ids = [d['draw'] for d in all_draws]
    
    print(f"Testing on {len(extreme_data)} extreme draws...")
    
    for item in extreme_data:
        draw_id = item['draw']
        actual = item['actual']
        
        # Reconstruct history
        try:
            curr_idx = all_draw_ids.index(draw_id)
            history = all_draws[curr_idx+1:] 
        except:
            continue
            
        # Run Optimized Prediction
        pred_res = predictor.predict(history, rules)
        pred_nums = pred_res['numbers']
        
        # Calculate Match
        match = len(set(pred_nums) & set(actual))
        hits[match] += 1
        
        # Score
        score = (100000000 if match==6 else 20000 if match==5 else 2000 if match==4 else 400 if match==3 else 0)
        total_score += score
        
        if match >= 3:
            print(f"🎯 Draw {draw_id}: Match {match} | Pred: {pred_nums} | Actual: {actual}")

    print("\n" + "="*80)
    print("📊 Black Swan Mode 結果")
    print("="*80)
    
    print("[命中分布]")
    for m in range(7):
        if hits[m] > 0:
            print(f"Match {m}: {hits[m]}")
            
    # Baseline comparison (from previous run)
    prev_dev_score = 2400 # From previous context
    prev_rand_score = 2168
    
    print(f"\n[得分比較]")
    print(f"Optimized Deviation: {total_score}")
    print(f"Standard  Deviation: {prev_dev_score}")
    print(f"Random EV          : {prev_rand_score}")
    
    improvement = (total_score - prev_dev_score) / prev_dev_score * 100 if prev_dev_score else 0
    print(f"\n相對標準 Deviation 優化幅度: {improvement:+.1f}%")
    
    roi = (total_score - len(extreme_data)*100) / (len(extreme_data)*100) * 100
    print(f"New ROI: {roi:+.1f}%")

if __name__ == '__main__':
    run_backtest()
