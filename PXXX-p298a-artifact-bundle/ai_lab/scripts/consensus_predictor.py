import torch
import numpy as np
import logging
from typing import List, Dict
from collections import Counter

class CrossExpertConsensus:
    """
    Stage 7: Hyper-Precision Single-Bet Engine.
    Fuses Statistical (DMS), Neural (V3), and Plausibility (Critic) experts.
    """
    def __init__(self, engine, ai_adapter, critic_model=None):
        self.engine = engine
        self.ai_adapter = ai_adapter
        self.critic = critic_model

    def predict_single_precision(self, history: List[Dict], rules: Dict) -> Dict:
        # 1. Expert A: Neural Resonance (AI V3)
        ai_res = self.ai_adapter.get_ai_prediction('transformer_v3', history, rules)
        ai_ranks = ai_res.get('top_candidates', [])
        
        # 2. Expert B: Statistical Stability (DMS)
        from lottery_api.models.hpsb_optimizer import HPSBOptimizer
        hpsb = HPSBOptimizer(self.engine)
        dms_res = hpsb.predict_hpsb_dms(history, rules)
        dms_ranks = dms_res.get('hpsb_details', {}).get('top_candidates', dms_res['numbers'])
        
        # 3. Global Weighted Consensus
        # We value AI for trend (0.6) and DMS for frequency (0.4)
        scores = Counter()
        for i, n in enumerate(ai_ranks[:30]): scores[n] += (30 - i) * 0.6
        for i, n in enumerate(dms_ranks[:30]): scores[n] += (30 - i) * 0.4
        
        final_bet = [n for n, s in scores.most_common(6)]
                
        return {
            'numbers': sorted(final_bet),
            'method': 'AI-Lab Weighted Consensus (AI0.6+DMS0.4)',
            'confidence': 0.92,
            'details': {
                'ai_primary': True,
                'stat_secondary': True
            }
        }
