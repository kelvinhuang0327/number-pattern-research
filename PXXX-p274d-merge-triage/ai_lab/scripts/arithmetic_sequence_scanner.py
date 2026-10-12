#!/usr/bin/env python3
"""
Phase 32: Arithmetic Sequence Scanner
Detects and predicts based on arithmetic progression patterns.
Example: 02, 10, 18 (d = 8)
"""
from collections import Counter
from typing import List, Dict, Tuple
import itertools
import random

class ArithmeticSequenceScanner:
    """
    Scans for arithmetic sequences in lottery numbers and predicts based on them.
    """
    
    def find_sequences_in_draw(self, numbers: List[int]) -> List[Tuple[int, int, int]]:
        """
        Find all 3-number arithmetic sequences in a draw.
        Returns: List of (a, b, c) where b - a = c - b
        """
        sequences = []
        sorted_nums = sorted(numbers)
        
        for combo in itertools.combinations(sorted_nums, 3):
            a, b, c = combo
            if b - a == c - b:  # Arithmetic progression
                sequences.append((a, b, c))
                
        return sequences
    
    def analyze_recent_sequences(self, history: List[Dict], window: int = 20) -> Dict:
        """
        Analyze common differences (d values) in recent draws.
        """
        recent = history[-window:]
        diff_counts = Counter()
        sequence_examples = []
        
        for draw in recent:
            seqs = self.find_sequences_in_draw(draw['numbers'])
            for a, b, c in seqs:
                d = b - a
                diff_counts[d] += 1
                sequence_examples.append((a, b, c, d))
                
        return {
            'diff_distribution': dict(diff_counts),
            'most_common_diffs': diff_counts.most_common(5),
            'examples': sequence_examples[-10:]  # Last 10 examples
        }
    
    def predict_with_sequence(self, history: List[Dict], rules: Dict) -> Dict:
        """
        Generate a bet that includes a likely arithmetic sequence.
        Strategy: 
        1. Find the most common difference values
        2. Start with a 'hot' low number as anchor
        3. Extend the sequence
        4. Fill remaining slots with high-probability numbers
        """
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        analysis = self.analyze_recent_sequences(history)
        hot_diffs = [d for d, count in analysis['most_common_diffs'] if 3 <= d <= 12]
        
        if not hot_diffs:
            hot_diffs = [6, 7, 8]  # Default common differences
            
        # Find hot anchor numbers (low numbers that start sequences)
        all_nums = [n for draw in history[-30:] for n in draw['numbers']]
        freq = Counter(all_nums)
        
        # Pick a starting point in low range (1-15)
        low_candidates = sorted(
            [(n, freq.get(n, 0)) for n in range(1, 16)],
            key=lambda x: x[1],
            reverse=True
        )
        
        random.seed(len(history))
        
        bet = []
        
        # Try to build a 3-number sequence
        for anchor, _ in low_candidates[:5]:
            for d in hot_diffs:
                seq = [anchor, anchor + d, anchor + 2*d]
                if all(1 <= n <= max_num for n in seq):
                    if len(set(seq)) == 3:  # All unique
                        bet = seq
                        break
            if bet:
                break
                
        if not bet:
            bet = [2, 10, 18]  # Fallback to common pattern
            
        # Fill with high-frequency numbers not in sequence
        candidates = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        for n, _ in candidates:
            if n not in bet and len(bet) < pick_count:
                bet.append(n)
                
        # Fill remaining with random
        while len(bet) < pick_count:
            n = random.randint(1, max_num)
            if n not in bet:
                bet.append(n)
                
        return {
            'numbers': sorted(bet[:pick_count]),
            'method': 'Arithmetic Sequence Scanner (Ph 32)',
            'confidence': 0.72,
            'details': {
                'sequence_base': bet[:3],
                'hot_diffs': hot_diffs,
                'analysis': analysis
            }
        }
