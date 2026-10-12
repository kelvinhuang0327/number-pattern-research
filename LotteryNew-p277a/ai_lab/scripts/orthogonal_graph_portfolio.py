#!/usr/bin/env python3
"""
Phase 28: Orthogonal + Graph Portfolio
Combines the proven Orthogonal structure with the new Graph predictor.
"""
import os
import sys
from typing import List, Dict

class OrthogonalGraphPortfolio:
    def __init__(self, engine, ai_adapter):
        self.engine = engine
        self.ai_adapter = ai_adapter
        
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        bets = []
        
        # Bet 1: Structural AI (Momentum)
        try:
            from ai_lab.scripts.structural_ai_predictor import StructuralAIPredictor
            s = StructuralAIPredictor(self.engine, self.ai_adapter)
            res = s.predict_structural(history, rules)
            bets.append(res['numbers'])
        except Exception as e:
            bets.append(self.engine.trend_predict(history, rules)['numbers'])
        
        # Bet 2: HPSB DMS (Reversion)
        try:
            from models.hpsb_optimizer import HPSBOptimizer
            dms = HPSBOptimizer(self.engine)
            res = dms.predict_hpsb_dms(history, rules)
            bets.append(res['numbers'])
        except Exception as e:
            bets.append(self.engine.deviation_predict(history, rules)['numbers'])
        
        # Bet 3: Co-occurrence Graph (Structure)
        try:
            from ai_lab.scripts.graph_predictor import CooccurrenceGraphPredictor
            g = CooccurrenceGraphPredictor()
            res = g.predict(history, rules)
            bets.append(res['numbers'])
        except Exception as e:
            bets.append(self.engine.markov_predict(history, rules)['numbers'])
            
        return {
            'bets': bets,
            'method': 'Orthogonal + Graph 3-Bet (Ph 28)',
            'details': {
                'bet1': 'Structural AI',
                'bet2': 'HPSB DMS',
                'bet3': 'Graph Clique'
            }
        }
