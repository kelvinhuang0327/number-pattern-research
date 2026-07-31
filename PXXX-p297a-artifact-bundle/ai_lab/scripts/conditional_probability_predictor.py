#!/usr/bin/env python3
"""
Phase 34b: Conditional Probability Predictor
Uses conditional probabilities P(B|A) to predict.
If certain numbers appeared in the last draw, what numbers are most likely next?
"""
from collections import defaultdict, Counter
from typing import List, Dict, Set
import random

class ConditionalProbabilityPredictor:
    """
    Uses conditional probability transitions between draws.
    """
    
    def build_transition_matrix(self, history: List[Dict], max_num: int = 49) -> Dict:
        """
        Build P(next_num | prev_num) matrix.
        For each number that appeared in draw N, what numbers tend to appear in draw N+1?
        """
        transitions = defaultdict(lambda: defaultdict(int))
        
        for i in range(len(history) - 1):
            prev_nums = set(history[i]['numbers'])
            next_nums = set(history[i+1]['numbers'])
            
            for p in prev_nums:
                for n in next_nums:
                    transitions[p][n] += 1
                    
        # Normalize to probabilities
        prob_matrix = {}
        for p, nexts in transitions.items():
            total = sum(nexts.values())
            prob_matrix[p] = {n: count/total for n, count in nexts.items()}
            
        return prob_matrix
    
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        if not history:
            return {'numbers': list(range(1, pick_count+1)), 'method': 'Fallback'}
            
        # Build transition matrix
        prob_matrix = self.build_transition_matrix(history, max_num)
        
        # Get last draw
        last_draw = set(history[-1]['numbers'])
        
        # Calculate expected probability for each number
        scores = defaultdict(float)
        
        for prev_num in last_draw:
            if prev_num in prob_matrix:
                for next_num, prob in prob_matrix[prev_num].items():
                    scores[next_num] += prob
                    
        # Add baseline frequency for numbers not covered
        all_nums = [n for d in history[-30:] for n in d['numbers']]
        freq = Counter(all_nums)
        total_freq = sum(freq.values())
        
        for n in range(1, max_num + 1):
            if n not in scores or scores[n] < 0.01:
                scores[n] = freq.get(n, 1) / total_freq * 0.5  # Lower weight for baseline
                
        # Select top numbers
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        bet = sorted([n for n, s in sorted_scores[:pick_count]])
        
        return {
            'numbers': bet,
            'method': 'Conditional Probability Chain',
            'confidence': 0.78,
            'details': {
                'trigger_nums': list(last_draw),
                'top_transitions': sorted_scores[:10]
            }
        }
    
    def predict_2bets(self, history: List[Dict], rules: Dict) -> Dict:
        """Generate 2 bets using conditional probability."""
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        prob_matrix = self.build_transition_matrix(history, max_num)
        last_draw = set(history[-1]['numbers'])
        
        # Bet 1: Direct conditional probability
        scores1 = defaultdict(float)
        for prev_num in last_draw:
            if prev_num in prob_matrix:
                for next_num, prob in prob_matrix[prev_num].items():
                    scores1[next_num] += prob
                    
        sorted1 = sorted(scores1.items(), key=lambda x: x[1], reverse=True)
        bet1 = sorted([n for n, s in sorted1[:pick_count]])
        
        # Bet 2: Inverse conditional (numbers NOT triggered by last draw)
        all_nums = [n for d in history[-50:] for n in d['numbers']]
        freq = Counter(all_nums)
        
        scores2 = {}
        for n in range(1, max_num + 1):
            if n not in bet1:
                # Prefer numbers with high overall frequency but low conditional trigger
                conditional_score = scores1.get(n, 0)
                base_freq = freq.get(n, 0) / sum(freq.values())
                # Inverse: high base freq, low conditional = cold transition
                scores2[n] = base_freq * (1 - min(conditional_score, 1))
                
        sorted2 = sorted(scores2.items(), key=lambda x: x[1], reverse=True)
        bet2 = sorted([n for n, s in sorted2[:pick_count]])
        
        return {
            'bets': [bet1, bet2],
            'method': 'Conditional Probability 2-Bet',
            'details': {
                'bet1': 'Direct Transition',
                'bet2': 'Inverse Transition'
            }
        }
