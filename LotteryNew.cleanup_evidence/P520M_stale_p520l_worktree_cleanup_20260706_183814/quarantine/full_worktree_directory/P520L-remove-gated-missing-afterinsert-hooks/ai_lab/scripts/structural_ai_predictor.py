import torch
import numpy as np
import os
import sys
import itertools
from typing import List, Dict

class StructuralAIPredictor:
    """
    Stage 7.3: AI-V3 with Structural Guardrails.
    Trusts the AI's trend detection but enforces hard statistical validity.
    """
    def __init__(self, engine, ai_adapter):
        self.engine = engine
        self.ai_adapter = ai_adapter

    def _calculate_ac(self, numbers):
        """Calculate Arithmetic Complexity (AC) value."""
        if len(numbers) < 2: return 0
        diffs = set()
        for a, b in itertools.combinations(numbers, 2):
            diffs.add(abs(a - b))
        return len(diffs) - (len(numbers) - 1)

    def predict_structural(self, history: List[Dict], rules: Dict) -> Dict:
        # 1. Get AI V3 Raw Ranking (Top 12)
        ai_res = self.ai_adapter.get_ai_prediction('transformer_v3', history, rules)
        ai_ranks = ai_res.get('top_candidates', [])[:12] # Expanded pool for filtering
        
        if not ai_ranks:
            return self.engine.markov_predict(history, rules)

        # 2. Assign Scores based on Rank (Simple Linear Decay)
        scores = {n: (12 - i) for i, n in enumerate(ai_ranks)}
        
        # 3. Generate Valid Combinations
        # We look for a 6-number set from these 12 that satisfies structural rules
        # and maximizes the summed score.
        
        valid_bets = []
        
        for comb in itertools.combinations(ai_ranks, 6):
            bet = sorted(list(comb))
            
            # --- Guardrail 1: Sum Range ---
            s = sum(bet)
            if not (110 <= s <= 220): continue # Standard Big Lotto Range
            
            # --- Guardrail 2: Odd/Even ---
            odds = sum(1 for n in bet if n % 2 != 0)
            if odds == 0 or odds == 6: continue # Avoid extremes
            
            # --- Guardrail 3: AC Value ---
            ac = self._calculate_ac(bet)
            if ac < 4: continue # Too simple
            
            # Score this valid bet
            bet_score = sum(scores[n] for n in bet)
            valid_bets.append((bet, bet_score))
            
        if valid_bets:
            valid_bets.sort(key=lambda x: x[1], reverse=True)
            best_bet = valid_bets[0][0]
            confidence = 0.95
        else:
            best_bet = sorted(ai_ranks[:6])
            confidence = 0.85
                
        return {
            'numbers': best_bet,
            'method': 'AI-Lab Structural V3 (Ph 22)',
            'confidence': confidence,
            'details': {
                'pool_size': 12,
                'guardrails': 'Sum, Odd/Even, AC'
            }
        }

    def predict_portfolio(self, history: List[Dict], rules: Dict, num_bets: int = 3) -> Dict:
        # Reuse the core logic to get valid bets
        ai_res = self.ai_adapter.get_ai_prediction('transformer_v3', history, rules)
        ai_ranks = ai_res.get('top_candidates', [])[:14] # Expand slightly to 14 for better 3-bet diversity
        
        if not ai_ranks:
            return {'bets': [], 'method': 'Fail'}

        scores = {n: (14 - i) for i, n in enumerate(ai_ranks)}
        valid_bets = []
        
        for comb in itertools.combinations(ai_ranks, 6):
            bet = sorted(list(comb))
            
            # Guardrails
            if not (110 <= sum(bet) <= 220): continue
            odds = sum(1 for n in bet if n % 2 != 0)
            if odds == 0 or odds == 6: continue
            if self._calculate_ac(bet) < 4: continue
            
            bet_score = sum(scores[n] for n in bet)
            valid_bets.append((bet, bet_score))
            
        # Greedy Selection with Diversity
        valid_bets.sort(key=lambda x: x[1], reverse=True)
        selected_bets = []
        
        for bet, score in valid_bets:
            if len(selected_bets) >= num_bets: break
            
            # Check overlap
            is_diverse = True
            for chosen in selected_bets:
                if len(set(bet) & set(chosen)) > 4: # Max 4 overlap allowed (allow key pairs)
                    is_diverse = False
                    break
            
            if is_diverse:
                selected_bets.append(bet)
                
        # Fill if not enough
        if len(selected_bets) < num_bets and valid_bets:
            # Relax diversity if needed
            for bet, score in valid_bets:
                if len(selected_bets) >= num_bets: break
                if bet not in selected_bets: selected_bets.append(bet)
        
        return {
            'bets': selected_bets,
            'method': f'AI-Lab Structural 3-Bet (Ph 22)',
            'details': {'pool': 14}
        }
