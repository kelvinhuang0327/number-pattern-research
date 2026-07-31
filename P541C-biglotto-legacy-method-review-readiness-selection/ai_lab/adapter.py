import logging
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class AIAdapter:
    """
    Bridge between the legacy statistical engine and the new AI-Lab models.
    Ensures zero interference with existing production code.
    """
    
    @staticmethod
    def get_ai_prediction(method_name: str, history: List[Dict], rules: Dict) -> Optional[Dict]:
        """
        Dynamically loads and runs an AI model from the ai_lab module.
        If the model or environment (PyTorch) is not ready, it fails gracefully.
        """
        try:
            # Lazy import to avoid dependency issues in production environment
            if method_name == 'transformer_v3':
                try:
                    import torch
                    import numpy as np
                    from .ai_models.transformer_v2 import HybridLotteryTransformer
                    from .scripts.train_v3 import HybridV3Dataset
                    
                    model_path = os.path.join(os.path.dirname(__file__), 'ai_models', 'v3_deep_resonance.pth')
                    if not os.path.exists(model_path):
                        return None
                        
                    model = HybridLotteryTransformer()
                    model.load_state_dict(torch.load(model_path, map_location='cpu'))
                    model.eval()
                    
                    dataset = HybridV3Dataset(os.path.join(os.path.dirname(__file__), 'data', 'real_biglotto.json'))
                    
                    # Context and Stats (9 Features)
                    context_draws = [d['numbers'] for d in history[-15:]]
                    while len(context_draws) < 15:
                        context_draws.insert(0, [0]*6)
                        
                    stats = []
                    for i in range(len(context_draws)):
                        prev = context_draws[i-1] if i > 0 else None
                        stats.append(dataset._extract_v3_stats(context_draws[i], prev))
                        
                    x = torch.tensor([context_draws], dtype=torch.long)
                    s = torch.tensor([stats], dtype=torch.float)
                    with torch.no_grad():
                        logits = model(x, s)
                        probs = torch.softmax(logits, dim=1).numpy()[0]
                    
                    probs[0] = -1
                    sorted_nums = np.argsort(probs)[::-1]
                    
                    from models.hpsb_optimizer import HPSBOptimizer
                    from models.unified_predictor import UnifiedPredictionEngine
                    hpsb = HPSBOptimizer(UnifiedPredictionEngine())
                    
                    final_nums = hpsb._apply_zdp(sorted_nums.tolist(), rules.get('pickCount', 6), rules)
                    return {
                        'numbers': final_nums, 
                        'top_candidates': sorted_nums.tolist()[:30],
                        'confidence': float(np.max(probs)),
                        'method': 'AI-Lab U-HPE V3'
                    }
                except Exception as e:
                    import traceback
                    print(f"❌ AI V3 CRITICAL FAILURE: {e}")
                    traceback.print_exc()
                    logger.error(f"AI V3 failed: {e}")
                    return None
                
            return None
        except Exception as e:
            logger.error(f"AI-Lab: Failed to load {method_name}: {e}")
            return None

def integrate_ai_to_engine(engine_instance):
    """
    Optional 'Monkey Patch' or registration function to add AI capabilities 
    to a UnifiedPredictionEngine instance without modifying its source file.
    """
    def ai_predict(history, rules):
        # Default to Transformer if available
        res = AIAdapter.get_ai_prediction('transformer', history, rules)
        if res:
            return res
        # Fallback to standard statistical prediction if AI fails
        return engine_instance.markov_predict(history, rules)
        
    engine_instance.ai_predict = ai_predict
    logger.info("AI-Lab Capabilties Injected into Prediction Engine.")
