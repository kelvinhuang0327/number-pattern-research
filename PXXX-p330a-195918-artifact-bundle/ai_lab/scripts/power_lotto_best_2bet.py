#!/usr/bin/env python3
"""
Power Lotto Anomaly Boost Predictor
Adapted for 38-number pool (zone 1) + 8-number zone 2.
"""
from collections import Counter
from typing import List, Dict
import random
import itertools

class PowerLottoAnomalyBoost:
    """
    Anomaly detection predictor adapted for Power Lotto.
    Zone 1: 38 numbers
    Zone 2: 1-8
    """
    
    def _analyze_tail_clusters(self, history: List[Dict], max_num: int = 38, window: int = 10) -> Dict:
        """Analyze tail digit frequency."""
        recent = history[-window:]
        tail_counts = Counter()
        
        for draw in recent:
            nums = draw.get('numbers', draw.get('first_zone', []))
            for num in nums:
                tail = num % 10
                tail_counts[tail] += 1
                
        return dict(tail_counts)
    
    def _find_arithmetic_sequences(self, history: List[Dict], window: int = 10) -> List[int]:
        """Find common arithmetic progression differences."""
        recent = history[-window:]
        diff_counts = Counter()
        
        for draw in recent:
            nums = sorted(draw.get('numbers', draw.get('first_zone', [])))
            for combo in itertools.combinations(nums, 3):
                a, b, c = combo
                if b - a == c - b:
                    diff_counts[b - a] += 1
                    
        return [d for d, c in diff_counts.most_common(3)]
    
    def _predict_zone2(self, history: List[Dict]) -> int:
        """Predict zone 2 (1-8)."""
        recent = history[-20:]
        z2_counts = Counter()
        
        for draw in recent:
            z2 = draw.get('special', draw.get('second_zone'))
            if z2:
                z2_counts[z2] += 1
                
        # Balance between hot and cold
        sorted_z2 = sorted(z2_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Return moderately hot number
        if len(sorted_z2) >= 3:
            return sorted_z2[1][0]  # Second most common
        elif sorted_z2:
            return sorted_z2[0][0]
        else:
            return 6  # Default
    
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        max_num = rules.get('maxNumber', 38)
        pick_count = rules.get('pickCount', 6)
        
        bet = []
        
        # 1. Tail Cluster: Get 3 numbers from hot tail
        tail_counts = self._analyze_tail_clusters(history, max_num)
        sorted_tails = sorted(tail_counts.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_tails:
            hot_tail = sorted_tails[0][0]
            same_tail_nums = [n for n in range(1, max_num + 1) if n % 10 == hot_tail]
            random.seed(len(history))
            if len(same_tail_nums) >= 3:
                bet.extend(random.sample(same_tail_nums, 3))
            else:
                bet.extend(same_tail_nums)
        
        # 2. Arithmetic Sequence: Add 2 numbers from sequence
        hot_diffs = self._find_arithmetic_sequences(history)
        if not hot_diffs:
            hot_diffs = [5, 6, 7]
            
        # Find sequence starting point
        all_nums = [n for d in history[-30:] for n in d.get('numbers', d.get('first_zone', []))]
        freq = Counter(all_nums)
        
        for anchor in range(1, 15):
            for d in hot_diffs:
                seq = [anchor, anchor + d, anchor + 2*d]
                if all(1 <= n <= max_num for n in seq):
                    for n in seq[:2]:
                        if n not in bet:
                            bet.append(n)
                            if len(bet) >= 5:
                                break
            if len(bet) >= 5:
                break
        
        # 3. Gap Recovery: Add 1 coldest number
        gaps = {}
        for num in range(1, max_num + 1):
            for i, draw in enumerate(reversed(history)):
                nums = draw.get('numbers', draw.get('first_zone', []))
                if num in nums:
                    gaps[num] = i
                    break
            if num not in gaps:
                gaps[num] = len(history)
                
        sorted_gaps = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
        for n, gap in sorted_gaps:
            if n not in bet and gap >= 10:
                bet.append(n)
                break
        
        # Fill remaining
        random.seed(len(history))
        while len(bet) < pick_count:
            n = random.randint(1, max_num)
            if n not in bet:
                bet.append(n)
                
        # Zone 2 prediction
        zone2 = self._predict_zone2(history)
        
        return {
            'numbers': sorted(bet[:pick_count]),
            'special': zone2,
            'method': 'Power Lotto Anomaly Boost',
            'confidence': 0.70
        }


class PowerLottoBestOfBest2Bet:
    """
    Best-of-Best 2-Bet for Power Lotto.
    Bet 1: Markov (best single-bet for Power Lotto per CLAUDE.md)
    Bet 2: Anomaly Boost
    """
    
    def __init__(self, engine):
        self.engine = engine
        self.anomaly = PowerLottoAnomalyBoost()
        
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        bets = []
        
        # Bet 1: Markov (documented as best single-bet for Power Lotto at 3.50%)
        try:
            res = self.engine.markov_predict(history, rules)
            bet1 = res['numbers'][:6]
            zone2_1 = res.get('special', 6)
        except:
            bet1 = list(range(1, 7))
            zone2_1 = 6
            
        bets.append({'numbers': sorted(bet1), 'special': zone2_1})
        
        # Bet 2: Anomaly Boost
        try:
            res = self.anomaly.predict(history, rules)
            bet2 = res['numbers']
            zone2_2 = res.get('special', 6)
        except:
            bet2 = list(range(7, 13))
            zone2_2 = 6
            
        bets.append({'numbers': sorted(bet2), 'special': zone2_2})
        
        return {
            'bets': bets,
            'method': 'Power Lotto Best-of-Best 2-Bet (Markov + Anomaly)'
        }
