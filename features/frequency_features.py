"""
Frequency Feature Engineering for Big Lotto (6/49).
Implements multiscale frequency counting, standardized z-scores, and rolling momentum.
"""
from typing import List, Dict, Tuple
import math

class FrequencyFeatures:
    """Calculates multiscale frequency profiles for Big Lotto numbers 1..49."""
    
    TOTAL_NUMBERS = 49
    PICK_COUNT = 6
    P_BASE = PICK_COUNT / TOTAL_NUMBERS  # 6 / 49 ~= 0.12244898
    
    @classmethod
    def compute_frequencies(cls, draws: List[Dict], window: int) -> Dict[int, float]:
        """Compute empirical frequency in the last  draws."""
        counts = {n: 0 for n in range(1, cls.TOTAL_NUMBERS + 1)}
        effective_draws = draws[-window:] if len(draws) >= window else draws
        n_draws = len(effective_draws)
        if n_draws == 0:
            return {n: cls.P_BASE for n in range(1, cls.TOTAL_NUMBERS + 1)}
            
        for d in effective_draws:
            for num in d['numbers']:
                if 1 <= num <= cls.TOTAL_NUMBERS:
                    counts[num] += 1
                    
        return {n: counts[n] / n_draws for n in range(1, cls.TOTAL_NUMBERS + 1)}

    @classmethod
    def compute_zscores(cls, draws: List[Dict], window: int) -> Dict[int, float]:
        """
        Standardized z-score against binomial null:
        Mean = window * (6/49)
        Variance = window * (6/49) * (43/49)
        """
        counts = {n: 0 for n in range(1, cls.TOTAL_NUMBERS + 1)}
        effective_draws = draws[-window:] if len(draws) >= window else draws
        n_draws = len(effective_draws)
        if n_draws == 0:
            return {n: 0.0 for n in range(1, cls.TOTAL_NUMBERS + 1)}
            
        for d in effective_draws:
            for num in d['numbers']:
                if 1 <= num <= cls.TOTAL_NUMBERS:
                    counts[num] += 1
                    
        mu = n_draws * cls.P_BASE
        var = n_draws * cls.P_BASE * (1.0 - cls.P_BASE)
        std = math.sqrt(var) if var > 0 else 1.0
        
        return {n: (counts[n] - mu) / std for n in range(1, cls.TOTAL_NUMBERS + 1)}

    @classmethod
    def compute_multiscale_frequency_vector(cls, draws: List[Dict], windows: Tuple[int, ...] = (10, 30, 100, 300)) -> Dict[int, List[float]]:
        """Compute frequency features across multiple scales."""
        vecs = {n: [] for n in range(1, cls.TOTAL_NUMBERS + 1)}
        for w in windows:
            freqs = cls.compute_frequencies(draws, w)
            zscores = cls.compute_zscores(draws, w)
            for n in range(1, cls.TOTAL_NUMBERS + 1):
                vecs[n].extend([freqs[n], zscores[n]])
        return vecs
