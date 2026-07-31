#!/usr/bin/env python3
"""
Phase 33: Forced Orthogonal 2-Bet Predictor
Generates 2 bets with maximum coverage and minimal overlap (≤2 numbers).
Strategy:
- Bet 1: AI + Trend (momentum)
- Bet 2: Statistical + Reversion (forced orthogonal)
"""
import os
import sys
import itertools
from typing import List, Dict
import random

class ForcedOrthogonal2Bet:
    """
    Maximum coverage 2-bet strategy with forced orthogonality.
    """
    MAX_OVERLAP = 2  # Maximum allowed overlap between bets
    
    def __init__(self, engine, ai_adapter):
        self.engine = engine
        self.ai_adapter = ai_adapter
        
    def _calculate_ac(self, numbers):
        if len(numbers) < 2: return 0
        diffs = set()
        for a, b in itertools.combinations(numbers, 2):
            diffs.add(abs(a - b))
        return len(diffs) - (len(numbers) - 1)
    
    def _is_structurally_valid(self, bet, rules):
        """Check if bet meets structural constraints."""
        s = sum(bet)
        if not (100 <= s <= 230): return False
        if self._calculate_ac(bet) < 3: return False
        # Odd-even balance: 2-4 odd numbers
        odds = sum(1 for n in bet if n % 2 == 1)
        if not (2 <= odds <= 4): return False
        return True
        
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        bets = []
        
        # === Bet 1: AI + Best Statistical ===
        try:
            # Try AI first
            ai_res = self.ai_adapter.get_ai_prediction('transformer_v3', history, rules)
            if ai_res and ai_res.get('numbers'):
                bet1 = ai_res['numbers']
            else:
                # Fallback to trend
                bet1 = self.engine.trend_predict(history, rules)['numbers']
        except:
            bet1 = self.engine.trend_predict(history, rules)['numbers']
            
        bets.append(sorted(bet1[:pick_count]))
        
        # === Bet 2: Forced Orthogonal (Statistical Reversion) ===
        try:
            # Get candidates from multiple methods
            dev_res = self.engine.deviation_predict(history, rules)
            markov_res = self.engine.markov_predict(history, rules)
            
            # Combine candidates
            candidates = set(dev_res['numbers'] + markov_res['numbers'])
            
            # Remove numbers that are in bet1 to enforce orthogonality
            bet1_set = set(bets[0])
            orthogonal_candidates = [n for n in candidates if n not in bet1_set]
            
            # If not enough orthogonal candidates, add from gap recovery
            if len(orthogonal_candidates) < pick_count:
                # Add coldest numbers
                gaps = {}
                for num in range(1, max_num + 1):
                    for i, draw in enumerate(reversed(history)):
                        if num in draw['numbers']:
                            gaps[num] = i
                            break
                    if num not in gaps:
                        gaps[num] = len(history)
                        
                sorted_gaps = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
                for n, _ in sorted_gaps:
                    if n not in bet1_set and n not in orthogonal_candidates:
                        orthogonal_candidates.append(n)
                    if len(orthogonal_candidates) >= pick_count + 5:
                        break
            
            # Find best structurally valid combination from orthogonal candidates
            best_bet2 = None
            best_score = -1
            
            random.seed(len(history))
            
            for _ in range(500):  # Random search
                if len(orthogonal_candidates) >= pick_count:
                    sample = random.sample(orthogonal_candidates, pick_count)
                else:
                    sample = list(orthogonal_candidates)
                    while len(sample) < pick_count:
                        n = random.randint(1, max_num)
                        if n not in sample and n not in bet1_set:
                            sample.append(n)
                            
                sample = sorted(sample)
                
                # Check overlap constraint
                overlap = len(set(sample) & bet1_set)
                if overlap > self.MAX_OVERLAP:
                    continue
                    
                # Check structural validity
                if not self._is_structurally_valid(sample, rules):
                    continue
                    
                # Score: prefer diverse coverage
                coverage_score = len(set(sample) | bet1_set)  # Total unique numbers
                if coverage_score > best_score:
                    best_score = coverage_score
                    best_bet2 = sample
                    
            if best_bet2:
                bets.append(best_bet2)
            else:
                # Fallback: just use deviation with minimal overlap
                fallback = [n for n in dev_res['numbers'] if n not in bet1_set][:pick_count]
                while len(fallback) < pick_count:
                    n = random.randint(1, max_num)
                    if n not in fallback and n not in bet1_set:
                        fallback.append(n)
                bets.append(sorted(fallback))
                
        except Exception as e:
            bets.append(self.engine.deviation_predict(history, rules)['numbers'])
            
        # Calculate coverage
        total_coverage = len(set(bets[0]) | set(bets[1]))
        overlap = len(set(bets[0]) & set(bets[1]))
        
        return {
            'bets': bets,
            'method': 'Forced Orthogonal 2-Bet (Ph 33)',
            'coverage': total_coverage,
            'overlap': overlap,
            'details': {
                'bet1_source': 'AI/Trend',
                'bet2_source': 'Deviation/Markov (Orthogonal)'
            }
        }
