import torch
import numpy as np
import os
import sys
import itertools
from typing import List, Dict

class OrthogonalPortfolio:
    """
    Stage 8: Orthogonal Expert Portfolio (Phase 23).
    A Multi-Bet strategy leveraging distinct expert signals.
    """
    def __init__(self, engine, ai_adapter):
        self.engine = engine
        self.ai_adapter = ai_adapter

    def predict_orthogonal_3bet(self, history: List[Dict], rules: Dict) -> Dict:
        # Expert 1: Structural AI (Momentum)
        from ai_lab.scripts.structural_ai_predictor import StructuralAIPredictor
        s_predictor = StructuralAIPredictor(self.engine, self.ai_adapter)
        bet1_res = s_predictor.predict_structural(history, rules)
        bet1 = bet1_res['numbers']
        
        # Expert 2: HPSB DMS (Reversion)
        from models.hpsb_optimizer import HPSBOptimizer
        hpsb = HPSBOptimizer(self.engine)
        bet2_res = hpsb.predict_hpsb_dms(history, rules)
        bet2 = bet2_res['numbers']
        
        # Expert 3: Hybrid Balance (Next Best)
        # We look at AI ranks 7-12 and DMS ranks 7-12
        ai_ranks = self.ai_adapter.last_top_candidates[6:12] if hasattr(self.ai_adapter, 'last_top_candidates') else []
        # Fallback if attribute not set (hacky but effective)
        if not ai_ranks:
             ai_res = self.ai_adapter.get_ai_prediction('transformer_v3', history, rules)
             ai_ranks = ai_res.get('top_candidates', [])[6:12]
             
        dms_ranks = bet2_res.get('hpsb_details', {}).get('top_candidates', [])[6:12]
        
        # Combine and picking structurally valid set with least overlap to Bet 1 & 2
        pool = list(set(ai_ranks + dms_ranks))
        
        # Greedy selection for Bet 3
        # Ideally, we want numbers that are NOT in Bet 1 or Bet 2 to maximize coverage
        used_nums = set(bet1 + bet2)
        candidates = [n for n in pool if n not in used_nums]
        
        # If not enough, fill from used_nums (unlikely with expanding pool)
        if len(candidates) < 6:
            candidates += [n for n in pool if n not in candidates]
            
        # Try to find a structurally valid combo from candidates
        bet3 = []
        best_score = -1
        
        # Simple scorer: prefer AI numbers slightly
        scores = {n: 1.2 if n in ai_ranks else 1.0 for n in pool}
        
        found = False
        for comb in itertools.combinations(candidates[:10], 6):
            b = sorted(list(comb))
            # Structural check
            if not (110 <= sum(b) <= 220): continue
            if s_predictor._calculate_ac(b) < 4: continue
            
            s = sum(scores.get(n, 1.0) for n in b)
            if s > best_score:
                best_score = s
                bet3 = b
                found = True
        
        if not found:
            bet3 = sorted(candidates[:6])
            
        return {
            'bets': [bet1, bet2, bet3],
            'method': 'AI-Lab Orthogonal 3-Bet (Ph 23)',
            'details': {
                'bet1': 'Structural AI',
                'bet2': 'HPSB DMS',
                'bet3': 'Hybrid Balance'
            }
        }
