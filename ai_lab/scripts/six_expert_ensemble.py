#!/usr/bin/env python3
"""
Phase 30: 6-Expert Ensemble Portfolio
Uses all 6 distinct predictors to maximize coverage.
Tests the hypothesis that orthogonal stacking continues to add value.
"""
import os
import sys
import itertools
from typing import List, Dict

class SixExpertEnsemble:
    def __init__(self, engine, ai_adapter):
        self.engine = engine
        self.ai_adapter = ai_adapter
        
    def _calculate_ac(self, numbers):
        if len(numbers) < 2: return 0
        diffs = set()
        for a, b in itertools.combinations(numbers, 2):
            diffs.add(abs(a - b))
        return len(diffs) - (len(numbers) - 1)
        
    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        bets = []
        
        # Bet 1: Structural AI (Momentum)
        try:
            from ai_lab.scripts.structural_ai_predictor import StructuralAIPredictor
            s = StructuralAIPredictor(self.engine, self.ai_adapter)
            res = s.predict_structural(history, rules)
            bets.append(res['numbers'])
        except: 
            bets.append(self.engine.trend_predict(history, rules)['numbers'])
        
        # Bet 2: HPSB DMS (Reversion)
        try:
            from models.hpsb_optimizer import HPSBOptimizer
            dms = HPSBOptimizer(self.engine)
            res = dms.predict_hpsb_dms(history, rules)
            bets.append(res['numbers'])
        except: 
            bets.append(self.engine.deviation_predict(history, rules)['numbers'])
        
        # Bet 3: Co-occurrence Graph (Structure)
        try:
            from ai_lab.scripts.graph_predictor import CooccurrenceGraphPredictor
            g = CooccurrenceGraphPredictor()
            res = g.predict(history, rules)
            bets.append(res['numbers'])
        except: 
            bets.append(self.engine.markov_predict(history, rules)['numbers'])
            
        # Bet 4: Hybrid Balance (Original Orthogonal Bet 3)
        try:
            ai_res = self.ai_adapter.get_ai_prediction('transformer_v3', history, rules)
            ai_ranks = ai_res.get('top_candidates', [])[6:12] if ai_res else []
            
            from models.hpsb_optimizer import HPSBOptimizer
            dms2 = HPSBOptimizer(self.engine)
            dms_res = dms2.predict_hpsb_dms(history, rules)
            dms_ranks = dms_res.get('hpsb_details', {}).get('top_candidates', [])[6:12]
            
            pool = list(set(ai_ranks + dms_ranks))
            used_nums = set()
            for b in bets:
                used_nums.update(b)
            candidates = [n for n in pool if n not in used_nums]
            
            if len(candidates) < 6:
                candidates += [n for n in pool if n not in candidates]
                
            bet4 = []
            best_score = -1
            scores = {n: 1.2 if n in ai_ranks else 1.0 for n in pool}
            
            for comb in itertools.combinations(candidates[:10], 6):
                b = sorted(list(comb))
                if not (110 <= sum(b) <= 220): continue
                if self._calculate_ac(b) < 4: continue
                
                sc = sum(scores.get(n, 1.0) for n in b)
                if sc > best_score:
                    best_score = sc
                    bet4 = b
                    
            if not bet4:
                bet4 = sorted(candidates[:6])
                
            bets.append(bet4)
        except:
            bets.append(self.engine.hot_cold_mix_predict(history, rules)['numbers'])
            
        # Bet 5: Gap Recovery (Overdue Numbers)
        try:
            from ai_lab.scripts.gap_recovery_predictor import GapRecoveryPredictor
            gap = GapRecoveryPredictor()
            res = gap.predict(history, rules)
            bets.append(res['numbers'])
        except:
            bets.append(self.engine.frequency_predict(history, rules)['numbers'])
            
        # Bet 6: Tail Number Analysis
        try:
            from ai_lab.scripts.tail_number_predictor import TailNumberPredictor
            tail = TailNumberPredictor()
            res = tail.predict(history, rules)
            bets.append(res['numbers'])
        except:
            bets.append(self.engine.bayesian_predict(history, rules)['numbers'])
            
        return {
            'bets': bets,
            'method': '6-Expert Ensemble (Ph 30)',
            'details': {
                'experts': ['AI-Structural', 'HPSB-DMS', 'Graph', 'Hybrid', 'Gap', 'Tail']
            }
        }
