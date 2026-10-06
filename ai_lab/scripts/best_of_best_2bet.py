#!/usr/bin/env python3
"""
Phase 34c: Best-of-Best 2-Bet Predictor
Combines the two most effective experts from 7-Expert testing:
- Bet 1: AI-Structural (5 wins in 7-Expert)
- Bet 2: Anomaly Boost (9 wins in 7-Expert)
"""
import os
import sys
from typing import List, Dict

class BestOfBest2Bet:
    def __init__(self, engine, ai_adapter):
        self.engine = engine
        self.ai_adapter = ai_adapter
        
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        bets = []
        
        # Bet 1: AI-Structural (from best single-bet performer)
        try:
            from ai_lab.scripts.structural_ai_predictor import StructuralAIPredictor
            s = StructuralAIPredictor(self.engine, self.ai_adapter)
            res = s.predict_structural(history, rules)
            bets.append(res['numbers'])
        except:
            bets.append(self.engine.trend_predict(history, rules)['numbers'])
            
        # Bet 2: Anomaly Boost (from best 7-Expert contributor)
        try:
            from ai_lab.scripts.anomaly_boost_bet import AnomalyBoostBet
            a = AnomalyBoostBet()
            res = a.predict(history, rules)
            bets.append(res['numbers'])
        except:
            # Fallback: same-tail numbers
            bets.append([9, 19, 29, 39, 49, 2])
            
        return {
            'bets': bets,
            'method': 'Best-of-Best 2-Bet (AI + Anomaly)',
            'details': {
                'bet1': 'AI-Structural',
                'bet2': 'Anomaly Boost'
            }
        }
