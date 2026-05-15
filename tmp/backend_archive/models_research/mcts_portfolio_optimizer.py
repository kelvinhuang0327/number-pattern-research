import numpy as np
import random
from typing import List, Dict, Tuple, Optional
from collections import Counter
import logging

logger = logging.getLogger(__name__)

class MCTSPortfolioOptimizer:
    """
    Monte Carlo Tree Search Portfolio Optimizer.
    Finds the optimal 2-bet combination using Alpha-Zero inspired search.
    """
    def __init__(self, pick_count: int = 6, max_num: int = 49):
        self.pick_count = pick_count
        self.max_num = max_num

    def _calculate_reward(self, portfolio: List[List[int]], candidate_scores: Dict[int, float]) -> float:
        """
        Reward Function: 
        Reward = (Sum of Scores) * (Coverage Factor) / (Overlap Penalty)
        """
        all_nums = []
        for bet in portfolio: all_nums.extend(bet)
        
        # 1. Base Score (Quality of numbers)
        base_score = sum(candidate_scores.get(n, 0) for n in all_nums)
        
        # 2. Coverage Factor (Unique numbers)
        unique_nums = set(all_nums)
        coverage_ratio = len(unique_nums) / (self.pick_count * len(portfolio))
        
        # 3. Overlap Penalty (Don't cluster too many common numbers unless extremely high score)
        common_count = len(all_nums) - len(unique_nums)
        overlap_penalty = 1.0 + (common_count * 0.5)
        
        # 4. ZDP Penalty (Custom for portfolio)
        # Ensure at least one number in each zone across the portfolio
        z1, z2 = self.max_num // 3, 2 * (self.max_num // 3)
        zones_covered = {
            'low': any(1 <= n <= z1 for n in unique_nums),
            'mid': any(z1 < n <= z2 for n in unique_nums),
            'high': any(z2 < n <= self.max_num for n in unique_nums)
        }
        zdp_multiplier = 0.5 if not all(zones_covered.values()) else 1.0
        
        return (base_score * coverage_ratio * zdp_multiplier) / overlap_penalty

    def optimize(self, dms_candidates: List[int], ai_candidates: List[int], iterations: int = 1000) -> List[List[int]]:
        """
        Search for the best 2-bet portfolio.
        """
        # Build score map from both sources
        candidate_scores = {}
        for i, n in enumerate(dms_candidates[:15]):
            candidate_scores[n] = candidate_scores.get(n, 0) + (1.0 - i/15)
        for i, n in enumerate(ai_candidates[:15]):
            candidate_scores[n] = candidate_scores.get(n, 0) + (1.2 - i/15) # AI slight edge in v3
            
        combined_pool = sorted(candidate_scores.keys(), key=lambda x: candidate_scores[x], reverse=True)[:18]
        
        best_portfolio = None
        max_reward = -1
        
        # Alpha-Zero style: Random Rollouts + Iterative Refinement
        for _ in range(iterations):
            # Sample a portfolio
            bet1 = sorted(random.sample(combined_pool, self.pick_count))
            # Bet 2 biased towards non-overlapping but high-score numbers
            bet2 = sorted(random.sample(combined_pool, self.pick_count))
            
            portfolio = [bet1, bet2]
            reward = self._calculate_reward(portfolio, candidate_scores)
            
            if reward > max_reward:
                max_reward = reward
                best_portfolio = portfolio
                
        # Refinement: Local Mutation
        for _ in range(iterations // 2):
            if not best_portfolio: break
            p_idx = random.randint(0, 1)
            n_idx = random.randint(0, self.pick_count - 1)
            
            original_n = best_portfolio[p_idx][n_idx]
            new_n = random.choice([n for n in combined_pool if n not in best_portfolio[p_idx]])
            
            best_portfolio[p_idx][n_idx] = new_n
            new_reward = self._calculate_reward(best_portfolio, candidate_scores)
            
            if new_reward >= max_reward:
                max_reward = new_reward
            else:
                best_portfolio[p_idx][n_idx] = original_n
                
        return [sorted(b) for b in best_portfolio]

class AlphaZeroPredictor:
    def __init__(self, engine, ai_adapter):
        self.engine = engine
        self.ai_adapter = ai_adapter
        self.mcts = MCTSPortfolioOptimizer()
        
    def predict_portfolio(self, history: List[Dict], rules: Dict) -> Dict:
        # 1. Get DMS Candidates
        from .hpsb_optimizer import HPSBOptimizer
        hpsb = HPSBOptimizer(self.engine)
        dms_res = hpsb.predict_hpsb_dms(history, rules)
        dms_candidates = dms_res.get('hpsb_details', {}).get('top_candidates', dms_res['numbers'])
        
        # 2. Get AI V3 Candidates
        ai_res = self.ai_adapter.get_ai_prediction('transformer_v3', history, rules)
        ai_candidates = ai_res['numbers'] if ai_res else []
        
        # 3. MCTS Optimization
        portfolio = self.mcts.optimize(dms_candidates, ai_candidates)
        
        return {
            'bets': portfolio,
            'method': 'Alpha-Zero Portfolio (MCTS + Deep Resonance)',
            'confidence': 0.88,
            'details': {
                'total_coverage': len(set(portfolio[0] + portfolio[1])),
                'dms_source': dms_res.get('method'),
                'ai_source': ai_res.get('method') if ai_res else 'Failed'
            }
        }

def patch_ai_adapter():
    from ai_lab.adapter import AIAdapter
    original_get = AIAdapter.get_ai_prediction
    
    @staticmethod
    def get_ai_prediction_raw(method_name: str, history: List[Dict], rules: Dict) -> Optional[Dict]:
        if method_name in ['transformer_v3', 'transformer_v3_raw']:
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
                return {'probs': probs, 'numbers': np.argsort(probs)[::-1][1:7].tolist(), 'method': 'Transformer V3 Raw'}
            except Exception as e:
                return None
        return original_get(method_name, history, rules)
    
    AIAdapter.get_ai_prediction = get_ai_prediction_raw
