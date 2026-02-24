import torch
import numpy as np
import os
import sys
from typing import List, Dict
from collections import Counter

class AIDominantPredictor:
    """
    Stage 7.2: Single-Bet Precision Focus.
    Primary Expert: AI-Lab U-HPE V3 (Deep Resonance).
    secondary Filter: Neural Critic (Plausibility).
    """
    def __init__(self, engine, ai_adapter):
        self.engine = engine
        self.ai_adapter = ai_adapter

    def predict_precision(self, history: List[Dict], rules: Dict) -> Dict:
        # 1. Get AI V3 Raw Ranking (Prioritize Resonance)
        ai_res = self.ai_adapter.get_ai_prediction('transformer_v3', history, rules)
        ai_ranks = ai_res.get('top_candidates', [])
        
        if not ai_ranks:
            # Fallback to standard AI top-6 if ranks are missing
            return ai_res if ai_res else self.engine.markov_predict(history, rules)

        # 2. Refinement Pool: Top 10 high-resonance numbers
        pool = ai_ranks[:10]
        
        # 3. Use Neural Critic to pick the most 'natural' 6-number set from this pool
        # This keeps the AI's core logic but prevents 'weird' bets that often fail.
        from ai_lab.scripts.elite_portfolio_optimizer import ElitePortfolioOptimizer
        optimizer = ElitePortfolioOptimizer()
        
        import random
        best_bet = pool[:6] 
        max_critic = -1.0
        
        # Test 100 permutations of the AI's top 10
        for _ in range(100):
            candidate = sorted(random.sample(pool, 6))
            score = optimizer.get_bet_score(candidate)
            
            if score > max_critic:
                max_critic = score
                best_bet = candidate
                
        return {
            'numbers': sorted(best_bet),
            'method': 'AI-Lab Dominant (Ph 21)',
            'confidence': ai_res.get('confidence', 0.90),
            'details': {
                'ai_primary_pool': pool[:3],
                'critic_verification': 'Active'
            }
        }
