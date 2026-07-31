#!/usr/bin/env python3
"""
Phase 34a: Negative Selection Predictor
First identifies numbers that are unlikely to appear (kill numbers),
then predicts from the remaining pool.
"""
from collections import Counter
from typing import List, Dict
import random

class NegativeSelectionPredictor:
    """
    Kill-then-Predict strategy.
    Step 1: Identify 10 numbers least likely to appear
    Step 2: Predict from remaining 39 numbers
    """
    KILL_COUNT = 10
    
    def identify_kill_numbers(self, history: List[Dict], max_num: int = 49) -> List[int]:
        """
        Identify numbers to exclude based on multiple signals.
        """
        kill_scores = {n: 0 for n in range(1, max_num + 1)}
        
        # Signal 1: Very recent hot numbers (likely to cool down)
        recent_5 = history[-5:]
        recent_freq = Counter([n for d in recent_5 for n in d['numbers']])
        for n, count in recent_freq.items():
            if count >= 3:  # Appeared 3+ times in last 5 draws
                kill_scores[n] += 3  # High kill priority
                
        # Signal 2: Last draw numbers (unlikely to repeat all)
        last_draw = history[-1]['numbers'] if history else []
        for n in last_draw:
            kill_scores[n] += 2
            
        # Signal 3: Consecutive pairs that just appeared
        for i in range(len(last_draw) - 1):
            if last_draw[i] + 1 == last_draw[i+1]:
                kill_scores[last_draw[i]] += 1
                kill_scores[last_draw[i+1]] += 1
                
        # Signal 4: Numbers in declining trend
        window_10 = history[-10:]
        window_20 = history[-20:-10] if len(history) >= 20 else history[:10]
        
        freq_10 = Counter([n for d in window_10 for n in d['numbers']])
        freq_20 = Counter([n for d in window_20 for n in d['numbers']])
        
        for n in range(1, max_num + 1):
            decline = freq_20.get(n, 0) - freq_10.get(n, 0)
            if decline >= 2:  # Was hot, now cold
                kill_scores[n] += 2
                
        # Select top KILL_COUNT numbers
        sorted_kills = sorted(kill_scores.items(), key=lambda x: x[1], reverse=True)
        return [n for n, s in sorted_kills[:self.KILL_COUNT]]
    
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        # Step 1: Kill numbers
        kill_numbers = set(self.identify_kill_numbers(history, max_num))
        remaining_pool = [n for n in range(1, max_num + 1) if n not in kill_numbers]
        
        # Step 2: Predict from remaining pool
        # Use weighted frequency on the reduced pool
        all_nums = [n for d in history[-50:] for n in d['numbers']]
        freq = Counter(all_nums)
        
        # Score remaining numbers
        scores = {}
        for n in remaining_pool:
            scores[n] = freq.get(n, 0) + 1  # Add 1 to avoid zero
            
        # Select top 6
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        bet = sorted([n for n, s in sorted_scores[:pick_count]])
        
        return {
            'numbers': bet,
            'method': 'Negative Selection (Kill-10)',
            'confidence': 0.75,
            'details': {
                'kill_numbers': list(kill_numbers),
                'pool_size': len(remaining_pool)
            }
        }
    
    def predict_2bets(self, history: List[Dict], rules: Dict) -> Dict:
        """Generate 2 orthogonal bets using negative selection."""
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        kill_numbers = set(self.identify_kill_numbers(history, max_num))
        remaining_pool = [n for n in range(1, max_num + 1) if n not in kill_numbers]
        
        # Bet 1: Top frequency from reduced pool
        all_nums = [n for d in history[-50:] for n in d['numbers']]
        freq = Counter(all_nums)
        
        scores = {n: freq.get(n, 0) for n in remaining_pool}
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        bet1 = sorted([n for n, s in sorted_scores[:pick_count]])
        
        # Bet 2: Gap recovery from reduced pool (opposite strategy)
        gaps = {}
        for n in remaining_pool:
            for i, d in enumerate(reversed(history)):
                if n in d['numbers']:
                    gaps[n] = i
                    break
            if n not in gaps:
                gaps[n] = len(history)
                
        sorted_gaps = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
        bet2_candidates = [n for n, g in sorted_gaps if n not in bet1][:pick_count]
        
        # Fill if needed
        random.seed(len(history))
        while len(bet2_candidates) < pick_count:
            n = random.choice(remaining_pool)
            if n not in bet1 and n not in bet2_candidates:
                bet2_candidates.append(n)
                
        bet2 = sorted(bet2_candidates[:pick_count])
        
        return {
            'bets': [bet1, bet2],
            'method': 'Negative Selection 2-Bet',
            'kill_numbers': list(kill_numbers),
            'pool_size': len(remaining_pool)
        }
