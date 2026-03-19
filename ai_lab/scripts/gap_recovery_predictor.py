#!/usr/bin/env python3
"""
Phase 30a: Gap Recovery Predictor
Predicts numbers that are statistically 'due' based on historical appearance gaps.
"""
import os
import sys
from typing import List, Dict

class GapRecoveryPredictor:
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        # Calculate gap for each number (how many draws since last appearance)
        gaps = {}
        for num in range(1, max_num + 1):
            for i, draw in enumerate(reversed(history)):
                if num in draw['numbers']:
                    gaps[num] = i
                    break
            if num not in gaps:
                gaps[num] = len(history) # Never appeared = max gap
                
        # Sort by gap (highest first = most overdue)
        sorted_by_gap = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
        
        # Pick top 6 with highest gaps
        bet = sorted([n for n, _ in sorted_by_gap[:pick_count]])
        
        return {
            'numbers': bet,
            'method': 'Gap Recovery (Ph 30a)',
            'confidence': 0.75,
            'details': {
                'max_gap': sorted_by_gap[0][1] if sorted_by_gap else 0
            }
        }
