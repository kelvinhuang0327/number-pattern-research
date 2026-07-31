#!/usr/bin/env python3
"""
Phase 35: Power Lotto Tuned Anomaly Boost
Specifically optimized for Power Lotto's 38-number pool.
"""
from collections import Counter
from typing import List, Dict
import random
import itertools

class PowerLottoTunedAnomalyBoost:
    """
    Anomaly detection optimized for Power Lotto (38 numbers, zone 2: 1-8).
    Key adjustments:
    - Tail range: 0-7 for main pool (since 38 % 10 = 8, max last digit is 8)
    - Arithmetic differences: 3-8 (smaller range than Big Lotto)
    - Gap threshold: 8 draws (smaller pool = faster turnover)
    """
    
    # Power Lotto specific parameters
    MAX_NUM = 38
    TAIL_WINDOW = 8  # Shorter window for smaller pool
    GAP_THRESHOLD = 8  # Lower threshold for faster turnover
    ARITHMETIC_DIFFS = [3, 4, 5, 6, 7]  # Smaller differences for 38-pool
    
    def _analyze_tail_patterns(self, history: List[Dict]) -> Dict[int, float]:
        """
        Analyze tail digit patterns with recency weighting.
        In 38-number pool: tails range from 0-8.
        """
        recent = history[-self.TAIL_WINDOW:]
        tail_scores = Counter()
        
        for i, draw in enumerate(recent):
            weight = 1.0 + i * 0.15  # Recent draws weighted more
            nums = draw.get('numbers', draw.get('first_zone', []))
            for num in nums:
                tail = num % 10
                tail_scores[tail] += weight
                
        return dict(tail_scores)
    
    def _find_hot_sequences(self, history: List[Dict]) -> List[tuple]:
        """
        Find arithmetic sequences that appeared recently.
        """
        recent = history[-10:]
        sequences = []
        
        for draw in recent:
            nums = sorted(draw.get('numbers', draw.get('first_zone', [])))
            for combo in itertools.combinations(nums, 3):
                a, b, c = combo
                d = b - a
                if c - b == d and d in self.ARITHMETIC_DIFFS:
                    sequences.append((a, b, c, d))
                    
        return sequences[-5:]  # Last 5 sequences
    
    def _get_gap_numbers(self, history: List[Dict]) -> List[int]:
        """
        Find numbers with gaps >= threshold (due for reappearance).
        """
        gaps = {}
        for num in range(1, self.MAX_NUM + 1):
            for i, draw in enumerate(reversed(history)):
                nums = draw.get('numbers', draw.get('first_zone', []))
                if num in nums:
                    gaps[num] = i
                    break
            if num not in gaps:
                gaps[num] = len(history)
                
        # Return numbers with gap >= threshold
        return [n for n, g in sorted(gaps.items(), key=lambda x: x[1], reverse=True) 
                if g >= self.GAP_THRESHOLD][:10]
    
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        pick_count = rules.get('pickCount', 6)
        
        bet = []
        random.seed(len(history))
        
        # Strategy 1: Tail Cluster (3 numbers)
        tail_scores = self._analyze_tail_patterns(history)
        sorted_tails = sorted(tail_scores.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_tails:
            # Pick top 2 hot tails
            hot_tails = [t for t, s in sorted_tails[:2]]
            for tail in hot_tails:
                candidates = [n for n in range(1, self.MAX_NUM + 1) 
                            if n % 10 == tail and n not in bet]
                if candidates:
                    # Pick based on frequency
                    all_nums = [n for d in history[-20:] 
                               for n in d.get('numbers', d.get('first_zone', []))]
                    freq = Counter(all_nums)
                    best = max(candidates, key=lambda x: freq.get(x, 0))
                    bet.append(best)
                    if len(bet) >= 2:
                        break
        
        # Fill to 3 with any high-frequency same-tail
        while len(bet) < 3:
            all_nums = [n for d in history[-30:] 
                       for n in d.get('numbers', d.get('first_zone', []))]
            freq = Counter(all_nums)
            for n, _ in freq.most_common():
                if n not in bet:
                    bet.append(n)
                    break
        
        # Strategy 2: Arithmetic Sequence (2 numbers)
        sequences = self._find_hot_sequences(history)
        if sequences:
            # Use most recent sequence's pattern
            last_seq = sequences[-1]
            d = last_seq[3]
            
            # Find continuation candidates
            for start in range(1, 20):
                seq = [start, start + d, start + 2*d]
                if all(1 <= n <= self.MAX_NUM for n in seq):
                    available = [n for n in seq if n not in bet]
                    if len(available) >= 2:
                        bet.extend(available[:2])
                        break
        
        # Fill if needed
        while len(bet) < 5:
            gap_nums = self._get_gap_numbers(history)
            for n in gap_nums:
                if n not in bet:
                    bet.append(n)
                    break
            else:
                n = random.randint(1, self.MAX_NUM)
                if n not in bet:
                    bet.append(n)
        
        # Strategy 3: Gap Recovery (1 number)
        gap_nums = self._get_gap_numbers(history)
        for n in gap_nums:
            if n not in bet:
                bet.append(n)
                break
        
        # Fill to 6
        while len(bet) < pick_count:
            n = random.randint(1, self.MAX_NUM)
            if n not in bet:
                bet.append(n)
        
        # Zone 2 prediction (hot + moderate)
        z2_counts = Counter()
        for draw in history[-15:]:
            z2 = draw.get('special', draw.get('second_zone'))
            if z2:
                z2_counts[z2] += 1
        
        sorted_z2 = sorted(z2_counts.items(), key=lambda x: x[1], reverse=True)
        zone2 = sorted_z2[1][0] if len(sorted_z2) > 1 else 6
        
        return {
            'numbers': sorted(bet[:pick_count]),
            'special': zone2,
            'method': 'Power Lotto Tuned Anomaly (Ph 35)',
            'details': {
                'hot_tails': [t for t, s in sorted_tails[:3]],
                'gap_candidates': gap_nums[:5]
            }
        }


class PowerLottoOptimized2Bet:
    """
    Optimized 2-Bet combining:
    - Bet 1: Statistical + Frequency (best from optimization: 10.67%)
    - Bet 2: Tuned Anomaly Boost
    """
    
    def __init__(self, engine):
        self.engine = engine
        self.anomaly = PowerLottoTunedAnomalyBoost()
        
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        bets = []
        
        # Bet 1: Statistical (from best combination)
        try:
            res = self.engine.statistical_predict(history, rules)
            bet1 = res['numbers'][:6]
            zone2_1 = res.get('special', 6)
        except:
            bet1 = list(range(1, 7))
            zone2_1 = 6
            
        bets.append({'numbers': sorted(bet1), 'special': zone2_1})
        
        # Bet 2: Tuned Anomaly Boost
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
            'method': 'Power Lotto Optimized 2-Bet (Statistical + Tuned Anomaly)'
        }
