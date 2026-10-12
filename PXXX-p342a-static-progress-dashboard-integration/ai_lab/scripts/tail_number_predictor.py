#!/usr/bin/env python3
"""
Phase 30b: Tail Number Predictor (尾數分析)
Analyzes the last digit patterns of winning numbers.
"""
import os
import sys
from collections import Counter
from typing import List, Dict

class TailNumberPredictor:
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        # Analyze tail (last digit) distribution in recent 30 draws
        recent = history[-30:]
        tail_counts = Counter()
        
        for draw in recent:
            for num in draw['numbers']:
                tail = num % 10
                tail_counts[tail] += 1
                
        # Find hot tails (appeared more) and cold tails (appeared less)
        # Strategy: Mix of hot (momentum) and cold (reversion)
        sorted_tails = sorted(tail_counts.items(), key=lambda x: x[1], reverse=True)
        hot_tails = [t for t, c in sorted_tails[:3]] # Top 3 hot
        cold_tails = [t for t, c in sorted_tails[-3:]] # Top 3 cold
        
        # Select numbers with these tails
        hot_candidates = [n for n in range(1, max_num + 1) if n % 10 in hot_tails]
        cold_candidates = [n for n in range(1, max_num + 1) if n % 10 in cold_tails]
        
        # Mix: 4 from hot, 2 from cold
        import random
        random.seed(len(history)) # Deterministic based on history length
        
        bet = []
        if len(hot_candidates) >= 4:
            bet.extend(random.sample(hot_candidates, 4))
        else:
            bet.extend(hot_candidates)
            
        remaining = pick_count - len(bet)
        cold_filtered = [c for c in cold_candidates if c not in bet]
        if len(cold_filtered) >= remaining:
            bet.extend(random.sample(cold_filtered, remaining))
        else:
            bet.extend(cold_filtered)
            
        # Fill if needed
        while len(bet) < pick_count:
            n = random.randint(1, max_num)
            if n not in bet:
                bet.append(n)
                
        return {
            'numbers': sorted(bet[:pick_count]),
            'method': 'Tail Number Analysis (Ph 30b)',
            'confidence': 0.72,
            'details': {
                'hot_tails': hot_tails,
                'cold_tails': cold_tails
            }
        }
