#!/usr/bin/env python3
"""
Phase 36: High Prize Trend Optimizer
Focuses on optimizing the Trend method for Match-4+ (high prize) prediction.
Based on finding that Trend achieved the only Match-5 in Power Lotto history.
"""
import os
import sys
import numpy as np
from collections import defaultdict, Counter
from typing import List, Dict

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

class HighPrizeTrendOptimizer:
    """
    Optimized Trend predictor focused on high prizes.
    Key insight: Trend with lambda=0.05 found Match-5 in Power Lotto.
    """
    
    def __init__(self, lambda_val: float = 0.05):
        self.lambda_val = lambda_val
        
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        pick_count = rules.get('pickCount', 6)
        min_num = rules.get('minNumber', 1)
        max_num = rules.get('maxNumber', 49)
        
        weighted_freq = defaultdict(float)
        
        for i, draw in enumerate(reversed(history)):
            age = i
            weight = np.exp(-self.lambda_val * age)
            
            nums = draw.get('numbers', draw.get('first_zone', []))
            for num in nums:
                weighted_freq[num] += weight
                
        total = sum(weighted_freq.values())
        probs = {n: weighted_freq.get(n, 0) / total for n in range(min_num, max_num + 1)}
        
        sorted_nums = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        predicted = sorted([n for n, _ in sorted_nums[:pick_count]])
        
        return {
            'numbers': predicted,
            'method': f'High Prize Trend (λ={self.lambda_val})',
            'confidence': 0.80
        }


def test_lambda_values():
    """Test different lambda values to find optimal for Match-4+."""
    from database import DatabaseManager
    from common import get_lottery_rules
    
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    
    for lottery_type in ['POWER_LOTTO', 'BIG_LOTTO']:
        all_draws = list(reversed(db.get_all_draws(lottery_type=lottery_type)))
        rules = get_lottery_rules(lottery_type)
        
        print(f"\n{'='*70}")
        print(f"🔬 Lambda Optimization for {lottery_type}")
        print(f"{'='*70}")
        
        lambdas = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15]
        
        for lam in lambdas:
            optimizer = HighPrizeTrendOptimizer(lambda_val=lam)
            
            m4_plus = 0
            m3_plus = 0
            total = 0
            
            for i in range(100, len(all_draws)):
                target = all_draws[i]
                history = all_draws[:i]
                actual = set(target.get('numbers', target.get('first_zone', [])))
                
                try:
                    res = optimizer.predict(history, rules)
                    match = len(set(res['numbers']) & actual)
                    
                    if match >= 4: m4_plus += 1
                    if match >= 3: m3_plus += 1
                    total += 1
                except:
                    continue
                    
            m4_rate = m4_plus / total * 100 if total > 0 else 0
            m3_rate = m3_plus / total * 100 if total > 0 else 0
            
            marker = "⭐" if m4_rate > 0.1 else ""
            print(f"λ={lam:.2f}: M4+={m4_plus} ({m4_rate:.2f}%), M3+={m3_plus} ({m3_rate:.1f}%) {marker}")


class TrendFocusedHighPrize2Bet:
    """
    2-Bet strategy focused on high prizes using Trend variants.
    Bet 1: Standard Trend (λ=0.05) - proved for Match-5
    Bet 2: Aggressive Trend (λ=0.03) - more recent focus
    """
    
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        bets = []
        
        # Bet 1: Standard Trend (the one that hit Match-5)
        t1 = HighPrizeTrendOptimizer(lambda_val=0.05)
        bets.append(t1.predict(history, rules)['numbers'])
        
        # Bet 2: Slower decay (more emphasis on recent hot numbers)
        t2 = HighPrizeTrendOptimizer(lambda_val=0.03)
        res2 = t2.predict(history, rules)['numbers']
        
        # Ensure some difference between bets
        if set(res2) == set(bets[0]):
            # Use frequency-based backup
            max_num = rules.get('maxNumber', 49)
            pick_count = rules.get('pickCount', 6)
            
            all_nums = [n for d in history[-30:] for n in d.get('numbers', d.get('first_zone', []))]
            freq = Counter(all_nums)
            
            # Pick numbers NOT in bet1
            bet2 = [n for n, _ in freq.most_common() if n not in bets[0]][:pick_count]
            bets.append(sorted(bet2))
        else:
            bets.append(res2)
            
        return {
            'bets': bets,
            'method': 'Trend-Focused High Prize 2-Bet',
            'details': {
                'bet1_lambda': 0.05,
                'bet2_lambda': 0.03
            }
        }


if __name__ == "__main__":
    test_lambda_values()
