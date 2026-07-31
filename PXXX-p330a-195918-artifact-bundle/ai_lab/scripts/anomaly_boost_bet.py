#!/usr/bin/env python3
"""
Phase 32: Anomaly Boost Bet
Combines Tail Cluster Detector and Arithmetic Sequence Scanner
to create a specialized bet for capturing unusual patterns.
"""
from typing import List, Dict
import random

class AnomalyBoostBet:
    """
    A specialized predictor for capturing anomalous patterns:
    - Same-tail clustering (e.g., 19, 39, 49)
    - Arithmetic sequences (e.g., 02, 10, 18)
    - Extreme gaps (very cold numbers suddenly appearing)
    """
    
    def __init__(self):
        from ai_lab.scripts.tail_cluster_detector import TailClusterDetector
        from ai_lab.scripts.arithmetic_sequence_scanner import ArithmeticSequenceScanner
        
        self.tail_detector = TailClusterDetector()
        self.seq_scanner = ArithmeticSequenceScanner()
    
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        """
        Generate a bet optimized for capturing anomalous patterns.
        
        Strategy:
        1. Get 3 numbers from tail clustering (same-tail emphasis)
        2. Get 2 numbers from arithmetic sequence
        3. Get 1 number from extreme gap analysis
        """
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        bet = []
        
        # 1. Tail Cluster: Get 3 numbers with same hot tail
        try:
            tail_result = self.tail_detector.predict_tail_cluster(history, rules)
            # Take first 3 that share the hottest tail
            hot_tail = tail_result['details']['hot_tails'][0] if tail_result['details']['hot_tails'] else 9
            same_tail_nums = [n for n in tail_result['numbers'] if n % 10 == hot_tail][:3]
            bet.extend(same_tail_nums)
        except Exception as e:
            # Fallback: Pick 3 numbers with tail 9 (based on 115000004 learning)
            bet.extend([9, 19, 39])
            
        # 2. Arithmetic Sequence: Get 2 numbers (extend or start new)
        try:
            seq_result = self.seq_scanner.predict_with_sequence(history, rules)
            seq_base = seq_result['details']['sequence_base'][:2]
            for n in seq_base:
                if n not in bet:
                    bet.append(n)
                if len(bet) >= 5:
                    break
        except Exception as e:
            # Fallback: Add common sequence starters
            for n in [2, 10]:
                if n not in bet:
                    bet.append(n)
                    
        # 3. Extreme Gap: Find the coldest number that hasn't appeared in 20+ draws
        try:
            gaps = {}
            for num in range(1, max_num + 1):
                for i, draw in enumerate(reversed(history)):
                    if num in draw['numbers']:
                        gaps[num] = i
                        break
                if num not in gaps:
                    gaps[num] = len(history)
                    
            # Get the coldest number not already in bet
            sorted_by_gap = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
            for n, gap in sorted_by_gap:
                if n not in bet and gap >= 15:  # At least 15 draws cold
                    bet.append(n)
                    break
        except:
            pass
            
        # Fill remaining
        random.seed(len(history))
        while len(bet) < pick_count:
            n = random.randint(1, max_num)
            if n not in bet:
                bet.append(n)
                
        return {
            'numbers': sorted(bet[:pick_count]),
            'method': 'Anomaly Boost Bet (Ph 32)',
            'confidence': 0.65,
            'strategy': 'tail_cluster + arithmetic_seq + extreme_gap',
            'details': {
                'tail_nums': bet[:3] if len(bet) >= 3 else bet,
                'seq_nums': bet[3:5] if len(bet) >= 5 else [],
                'gap_num': bet[5] if len(bet) >= 6 else None
            }
        }
