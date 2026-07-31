#!/usr/bin/env python3
"""
Phase 27: Meta-Ensemble Predictor
Combines multiple expert predictors with a confidence-gated voting mechanism.
"""
import os
import sys
from collections import Counter
from typing import List, Dict

class MetaEnsemblePredictor:
    def __init__(self, engine, ai_adapter):
        self.engine = engine
        self.ai_adapter = ai_adapter
        
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        pick_count = rules.get('pickCount', 6)
        
        # Gather Expert Predictions
        experts = []
        
        # 1. AI V3 (Structural)
        try:
            from ai_lab.scripts.structural_ai_predictor import StructuralAIPredictor
            s = StructuralAIPredictor(self.engine, self.ai_adapter)
            res = s.predict_structural(history, rules)
            experts.append(('AI-Structural', res['numbers'], 0.90))
        except: pass
        
        # 2. DMS
        try:
            from models.hpsb_optimizer import HPSBOptimizer
            dms = HPSBOptimizer(self.engine)
            res = dms.predict_hpsb_dms(history, rules)
            experts.append(('DMS', res['numbers'], 0.80))
        except: pass
        
        # 3. Graph
        try:
            from ai_lab.scripts.graph_predictor import CooccurrenceGraphPredictor
            g = CooccurrenceGraphPredictor()
            res = g.predict(history, rules)
            experts.append(('Graph', res['numbers'], 0.85))
        except: pass
        
        # 4. Attention Replay
        try:
            from ai_lab.scripts.attention_replay_predictor import AttentionReplayPredictor
            a = AttentionReplayPredictor()
            res = a.predict(history, rules)
            if res:
                experts.append(('Attention', res['numbers'], 0.82))
        except: pass
        
        if not experts:
            return self.engine.markov_predict(history, rules)
        
        # Confidence-Gated Voting
        # If any expert has > 0.90 confidence, trust it alone
        for name, nums, conf in experts:
            if conf > 0.92:
                return {
                    'numbers': nums,
                    'method': f'Meta-Ensemble (Gated: {name})',
                    'confidence': conf
                }
        
        # Otherwise, use weighted voting
        votes = Counter()
        total_weight = 0
        for name, nums, conf in experts:
            for n in nums:
                votes[n] += conf
            total_weight += conf
            
        # Top 6 by vote
        sorted_votes = sorted(votes.items(), key=lambda x: x[1], reverse=True)
        final_bet = sorted([n for n, _ in sorted_votes[:pick_count]])
        
        return {
            'numbers': final_bet,
            'method': 'Meta-Ensemble (Confidence Voting)',
            'confidence': 0.88,
            'details': {
                'experts': [e[0] for e in experts]
            }
        }
    
    def predict_portfolio(self, history: List[Dict], rules: Dict, num_bets: int = 3) -> Dict:
        """
        Generate a diversified 3-bet portfolio using all experts.
        Each bet is the top pick from a different expert.
        """
        bets = []
        
        # 1. AI-Structural
        try:
            from ai_lab.scripts.structural_ai_predictor import StructuralAIPredictor
            s = StructuralAIPredictor(self.engine, self.ai_adapter)
            res = s.predict_structural(history, rules)
            bets.append(res['numbers'])
        except: pass
        
        # 2. Graph
        try:
            from ai_lab.scripts.graph_predictor import CooccurrenceGraphPredictor
            g = CooccurrenceGraphPredictor()
            res = g.predict(history, rules)
            bets.append(res['numbers'])
        except: pass
        
        # 3. DMS 
        try:
            from models.hpsb_optimizer import HPSBOptimizer
            dms = HPSBOptimizer(self.engine)
            res = dms.predict_hpsb_dms(history, rules)
            bets.append(res['numbers'])
        except: pass
        
        # Fill if needed
        while len(bets) < num_bets:
            res = self.engine.markov_predict(history, rules)
            bets.append(res['numbers'])
            
        return {
            'bets': bets[:num_bets],
            'method': 'Meta-Ensemble 3-Bet (Ph 27)',
            'details': {'experts': ['AI-Structural', 'Graph', 'DMS']}
        }
