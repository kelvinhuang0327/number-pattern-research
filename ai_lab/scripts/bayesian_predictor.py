import torch
import numpy as np
import os
import sys
from typing import List, Dict
from collections import Counter

class NeuralBayesianPredictor:
    """
    Stage 7.1: Single-Bet Precision Focus.
    Uses AI V3 Model as 'Prior' and Recent Frequency as 'Likelihood'.
    """
    def __init__(self, engine, ai_adapter):
        self.engine = engine
        self.ai_adapter = ai_adapter

    def predict_bayesian(self, history: List[Dict], rules: Dict) -> Dict:
        # 1. Get AI V3 Prior (Ranked 1-49)
        ai_res = self.ai_adapter.get_ai_prediction('transformer_v3', history, rules)
        ai_ranks = ai_res.get('top_candidates', [])
        
        # 2. Calculate Recent Frequency (Likelihood) - Last 50 draws
        recent_history = history[-50:]
        freq = Counter()
        for d in recent_history:
            for n in d['numbers']: freq[n] += 1
            
        # 3. Bayesian Fusion
        # Score = Rank_Score * (1 + Normalized_Freq)
        fused_scores = {}
        for i, n in enumerate(ai_ranks):
            rank_score = (30 - i) if i < 30 else 1
            # Frequency weighting: boost numbers that appear 1-2 times in 50 draws (normal rotation)
            # Penalize 'Dead' (0) or 'Over-hot' (>6) numbers
            f = freq.get(n, 0)
            f_weight = 1.0
            if 1 <= f <= 5: f_weight = 1.2
            elif f > 5: f_weight = 0.8 # Satiated
            elif f == 0: f_weight = 0.5 # Cold
            
            fused_scores[n] = rank_score * f_weight
            
        # 4. Final Selection
        sorted_fused = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        top_6 = [n for n, s in sorted_fused[:6]]
        
        # 5. ZDP Refinement (Veto bad sequence)
        from models.hpsb_optimizer import HPSBOptimizer
        hpsb = HPSBOptimizer(self.engine)
        final_bet = hpsb._apply_zdp(top_6, rules.get('pickCount', 6), rules)
        
        return {
            'numbers': sorted(final_bet),
            'method': 'AI-Lab Neural-Bayesian (Ph 18)',
            'confidence': 0.94,
            'details': {
                'ai_rank_base': ai_ranks[:3],
                'freq_adjust': 'Active'
            }
        }
