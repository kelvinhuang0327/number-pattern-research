#!/usr/bin/env python3
"""
Phase 32: Tail Cluster Detector
Detects and predicts based on same-tail number clustering patterns.
Example: 19, 39, 49 (all end in 9)
"""
from collections import Counter
from typing import List, Dict
import random

class TailClusterDetector:
    """
    Detects hot tail digits and generates bets with clustered tails.
    """
    
    def analyze_tail_distribution(self, history: List[Dict], window: int = 10) -> Dict:
        """
        Analyze which tail digits are 'hot' in recent draws.
        """
        recent = history[-window:]
        tail_counts = Counter()
        
        for draw in recent:
            for num in draw['numbers']:
                tail = num % 10
                tail_counts[tail] += 1
                
        # Expected per tail = window * 6 / 10 = 6
        expected = len(recent) * 6 / 10
        
        hot_tails = []
        for tail, count in tail_counts.most_common():
            if count > expected * 1.5:  # 50% above expected
                hot_tails.append((tail, count))
                
        return {
            'tail_counts': dict(tail_counts),
            'hot_tails': hot_tails,
            'expected': expected
        }
    
    def predict_tail_cluster(self, history: List[Dict], rules: Dict) -> Dict:
        """
        Generate a bet with numbers that share hot tail digits.
        Strategy: Pick 3 numbers from the hottest tail, 2 from second, 1 from third
        """
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        analysis = self.analyze_tail_distribution(history)
        tail_counts = analysis['tail_counts']
        
        # Sort tails by frequency
        sorted_tails = sorted(tail_counts.items(), key=lambda x: x[1], reverse=True)
        
        bet = []
        
        # Get all numbers for each tail
        def get_numbers_for_tail(tail: int) -> List[int]:
            return [n for n in range(1, max_num + 1) if n % 10 == tail]
        
        # Strategy: Take 3 from hottest, 2 from second, 1 from third
        allocation = [3, 2, 1]
        
        random.seed(len(history))  # Deterministic
        
        for i, count in enumerate(allocation):
            if i < len(sorted_tails):
                tail = sorted_tails[i][0]
                candidates = [n for n in get_numbers_for_tail(tail) if n not in bet]
                if len(candidates) >= count:
                    bet.extend(random.sample(candidates, count))
                else:
                    bet.extend(candidates)
                    
        # Fill if needed
        while len(bet) < pick_count:
            n = random.randint(1, max_num)
            if n not in bet:
                bet.append(n)
                
        return {
            'numbers': sorted(bet[:pick_count]),
            'method': 'Tail Cluster Detector (Ph 32)',
            'confidence': 0.70,
            'details': {
                'hot_tails': [t for t, c in sorted_tails[:3]],
                'tail_analysis': analysis
            }
        }
