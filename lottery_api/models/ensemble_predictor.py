import logging
import os
import sys
import numpy as np
from typing import List, Dict, Optional
from collections import Counter

# Add necessary paths
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '../..'))
sys.path.insert(0, os.path.join(current_dir, '../../ai_lab'))

from .hpsb_optimizer import HPSBOptimizer
from .unified_predictor import UnifiedPredictionEngine

logger = logging.getLogger(__name__)

class EnsemblePredictor:
    """
    Universal Consensus Predictor: Fuses AI and Statistical methods.
    """
    def __init__(self, engine: UnifiedPredictionEngine = None):
        self.engine = engine or UnifiedPredictionEngine()
        self.hpsb = HPSBOptimizer(self.engine)
        
    def predict_ensemble(self, history: List[Dict], rules: Dict, ai_weight: float = 0.4) -> Dict:
        """
        AI-Statistical Fusion (Universal Consensus).
        ai_weight: Proportion of weight given to the AI V3 model (0.0 to 1.0).
        """
        pick_count = rules.get('pickCount', 6)
        max_num = rules.get('maxNumber', 49)
        
        # 1. Get Statistical Scores (DMS)
        # We perform a mini-audit to find the best method, then get its numbers
        dms_res = self.hpsb.predict_hpsb_dms(history, rules)
        dms_nums = dms_res['numbers']
        
        # Convert DMS numbers to a score vector
        dms_scores = np.zeros(max_num + 1)
        for i, num in enumerate(dms_nums):
            # Rank-based scoring: Top number gets higher score
            dms_scores[num] = (pick_count - i) / pick_count
            
        # 2. Get AI Scores (U-HPE V3)
        ai_scores = np.zeros(max_num + 1)
        try:
            from ai_lab.adapter import AIAdapter
            ai_res = AIAdapter.get_ai_prediction('transformer_v3_raw', history, rules)
            if ai_res and 'probs' in ai_res:
                # Use raw probabilities if available
                probs = ai_res['probs']
                # Normalize probabilities to [0, 1] range within the valid range
                valid_probs = probs[1:max_num+1]
                p_min, p_max = valid_probs.min(), valid_probs.max()
                if p_max > p_min:
                    ai_scores[1:max_num+1] = (probs[1:max_num+1] - p_min) / (p_max - p_min)
                else:
                    ai_scores[1:max_num+1] = probs[1:max_num+1]
            elif ai_res and 'numbers' in ai_res:
                # Fallback to rank-based if only numbers returned
                for i, num in enumerate(ai_res['numbers']):
                    ai_scores[num] = (pick_count - i) / pick_count
        except Exception as e:
            logger.warning(f"Ensemble: AI V3 prediction failed: {e}")
            ai_weight = 0.0 # Ignore AI if it fails
            
        # 3. Weighted Fusion
        dms_weight = 1.0 - ai_weight
        final_scores = (ai_weight * ai_scores) + (dms_weight * dms_scores)
        
        # 4. Filter and Sort
        candidates = []
        for n in range(1, max_num + 1):
            if final_scores[n] > 0:
                candidates.append((n, final_scores[n]))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        sorted_nums = [c[0] for c in candidates]
        
        # 5. Apply ZDP
        final_numbers = self.hpsb._apply_zdp(sorted_nums, pick_count, rules)
        
        return {
            'numbers': final_numbers,
            'confidence': float(0.75 + (ai_weight * 0.10)), # Weighted confidence estimate
            'method': f'Universal Consensus (AI:{ai_weight:.1f}, Stat:{dms_weight:.1f})',
            'ensemble_details': {
                'ai_weight': ai_weight,
                'stat_weight': dms_weight,
                'selected_method_dms': dms_res.get('dms_details', {}).get('selected_method')
            }
        }

# Temporary tweak to AIAdapter to return raw probabilities for ensembling
def patch_ai_adapter():
    from ai_lab.adapter import AIAdapter
    original_get = AIAdapter.get_ai_prediction
    
    @staticmethod
    def get_ai_prediction_raw(method_name: str, history: List[Dict], rules: Dict) -> Optional[Dict]:
        if method_name == 'transformer_v3_raw':
            try:
                import torch
                import numpy as np
                import os
                from ai_lab.ai_models.transformer_v2 import HybridLotteryTransformer
                from ai_lab.scripts.train_v3 import HybridV3Dataset
                
                ai_lab_path = os.path.join(os.getcwd(), 'ai_lab')
                model_path = os.path.join(ai_lab_path, 'ai_models', 'v3_deep_resonance.pth')
                if not os.path.exists(model_path): return None
                
                model = HybridLotteryTransformer()
                model.load_state_dict(torch.load(model_path, map_location='cpu'))
                model.eval()
                
                dataset = HybridV3Dataset(os.path.join(ai_lab_path, 'data', 'real_biglotto.json'))
                context_draws = [d['numbers'] for d in history[-15:]]
                while len(context_draws) < 15: context_draws.insert(0, [0]*6)
                
                stats = []
                for i in range(len(context_draws)):
                    prev = context_draws[i-1] if i > 0 else None
                    stats.append(dataset._extract_v3_stats(context_draws[i], prev))
                
                x = torch.tensor([context_draws], dtype=torch.long)
                s = torch.tensor([stats], dtype=torch.float)
                with torch.no_grad():
                    logits = model(x, s)
                    probs = torch.softmax(logits, dim=1).numpy()[0]
                return {'probs': probs, 'method': 'Transformer V3 Raw'}
            except Exception as e:
                return None
        return original_get(method_name, history, rules)
    
    AIAdapter.get_ai_prediction = get_ai_prediction_raw

if __name__ == "__main__":
    # Test script
    pass
