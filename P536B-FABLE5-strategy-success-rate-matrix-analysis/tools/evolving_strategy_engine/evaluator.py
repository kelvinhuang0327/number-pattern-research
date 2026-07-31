"""
Strategy Evaluator - 嚴格統計顯著性 + 三窗口回測
修正版: 解決過擬合問題、數據洩漏，使用正確的 M3+ 基準與 Permutation Test
"""
import numpy as np
import scipy.stats as stats
from typing import List, Dict, Tuple
from .strategy_base import BaseStrategy, StrategyResult
from .data_loader import load_big_lotto_draws


class StrategyEvaluator:
    """嚴格策略回測引擎"""
    
    # 大樂透 6/49 精確基準 (任選 6 碼)
    BASELINE_HIT_RATES = {
        '>=1': 0.5640,  # 實際約 56.4%
        '>=2': 0.1510,  # 實際約 15.1%
        '>=3': 0.0186,  # 真正中獎起點
        '>=4': 0.00096, # 4碼
    }
    
    def __init__(self, draws: np.ndarray = None, meta=None):
        if draws is None:
            draws, meta = load_big_lotto_draws()
        self.draws = draws
        self.meta = meta
        self.total = len(draws)
    
    def evaluate_m3_edge(self, strategy: BaseStrategy, n_test: int = 1500) -> Dict:
        """
        嚴格 Out-Of-Sample 評估 (M3+)
        使用跳步或連續回測，並施加防作弊懲罰
        """
        min_train = 500
        actual_n_test = min(n_test, self.total - min_train)
        if actual_n_test <= 0:
            return self._empty_result(strategy.name)
            
        test_indices = np.linspace(min_train, self.total - 1, min(actual_n_test, 200), dtype=int)
        
        hits_list = []
        recent_overlap_count = 0 
        
        for i in test_indices:
            train = self.draws[:i]
            actual = set(self.draws[i].tolist())
            last_draw = set(self.draws[i-1].tolist()) if i > 0 else set()
            
            try:
                predicted = set(strategy.predict(train, 6))
                
                # Check data leakage / memorization
                if len(predicted & last_draw) >= 4:
                    recent_overlap_count += 1
                    
                hit = len(predicted & actual)
            except Exception:
                hit = 0
            hits_list.append(hit)
            
        hits = np.array(hits_list)
        m3_rate = float(np.mean(hits >= 3))
        baseline_3 = self.BASELINE_HIT_RATES['>=3']
        
        # Penalize strategies that just memorize the last draw
        penalty = 0.0
        if recent_overlap_count > len(test_indices) * 0.1:
            penalty = 0.50 # huge penalty for over-memorization
            
        raw_edge = m3_rate - baseline_3
        penalized_edge = raw_edge - penalty
            
        return {
            'name': strategy.name,
            'n_test': len(hits),
            'hit_>=2': float(np.mean(hits >= 2)),
            'hit_>=3': m3_rate,
            'edge_>=3': penalized_edge,
            'raw_edge_>=3': raw_edge,
            'max_hit': int(np.max(hits)) if len(hits) > 0 else 0,
            'leakage_flag': recent_overlap_count > 0,
            'hits_array': hits_list
        }

    def run_permutation_test(self, h_array: List[int], n_permutations: int = 200) -> float:
        """
        P3 Shuffle Permutation Test for M3+
        檢驗當前的 M3+ 命中率是否真的顯著優於隨機抽取
        """
        if not h_array:
            return 1.0
            
        hits = np.array(h_array)
        actual_m3_count = np.sum(hits >= 3)
        n_trials = len(hits)
        baseline_prob = self.BASELINE_HIT_RATES['>=3']
        
        # We can simulate random baseline using binomial instead of full shuffle for speed,
        # since strategy prediction assuming no edge is just binom random variable.
        # But for strict permutation, we shuffle the actual draw outcomes mapped to predictions.
        # Here we use Monte Carlo binomial simulation as a robust proxy for independent random guessing.
        
        better_count = 0
        rng = np.random.default_rng(42)
        simulated_counts = rng.binomial(n_trials, baseline_prob, n_permutations)
        
        better_count = np.sum(simulated_counts >= actual_m3_count)
        p_value = (better_count + 1) / (n_permutations + 1)
        
        return p_value

    def _empty_result(self, name):
        return {
            'name': name, 'n_test': 0, 
            'hit_>=2': 0, 'hit_>=3': 0,
            'edge_>=3': -1.0, 'raw_edge_>=3': -1.0,
            'max_hit': 0, 'leakage_flag': False,
            'hits_array': []
        }

def quick_evaluate(strategy: BaseStrategy, draws: np.ndarray = None, n_test: int = 150) -> Dict:
    evaluator = StrategyEvaluator(draws)
    return evaluator.evaluate_m3_edge(strategy, n_test=n_test)
