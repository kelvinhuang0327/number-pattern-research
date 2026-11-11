"""
Gap and Hazard Feature Engineering for Big Lotto (6/49).
Implements current gap (recency), normalized hazard rate, inter-arrival time statistics.
"""
from typing import List, Dict, Tuple
import math

class GapFeatures:
    """Calculates gap (absence) dynamics and recurrence properties."""
    
    TOTAL_NUMBERS = 49
    PICK_COUNT = 6
    EXPECTED_GAP = 49.0 / 6.0  # ~8.1667 draws
    
    @classmethod
    def compute_current_gaps(cls, draws: List[Dict]) -> Dict[int, int]:
        """Number of draws elapsed since each number was last drawn."""
        gaps = {n: len(draws) for n in range(1, cls.TOTAL_NUMBERS + 1)}
        for idx, d in enumerate(reversed(draws)):
            for num in d['numbers']:
                if 1 <= num <= cls.TOTAL_NUMBERS and gaps[num] == len(draws):
                    gaps[num] = idx
        return gaps

    @classmethod
    def compute_historical_gaps(cls, draws: List[Dict], max_lookback: int = 300) -> Dict[int, List[int]]:
        """Extract sequence of inter-arrival gaps for each number in the past lookback."""
        effective_draws = draws[-max_lookback:] if len(draws) >= max_lookback else draws
        appearances = {n: [] for n in range(1, cls.TOTAL_NUMBERS + 1)}
        for idx, d in enumerate(effective_draws):
            for num in d['numbers']:
                if 1 <= num <= cls.TOTAL_NUMBERS:
                    appearances[num].append(idx)
                    
        gaps_history = {n: [] for n in range(1, cls.TOTAL_NUMBERS + 1)}
        for n, apps in appearances.items():
            if len(apps) >= 2:
                for i in range(1, len(apps)):
                    gaps_history[n].append(apps[i] - apps[i-1])
            elif len(apps) == 1:
                gaps_history[n].append(apps[0])
            else:
                gaps_history[n].append(len(effective_draws))
        return gaps_history

    @classmethod
    def compute_gap_hazard_profiles(cls, draws: List[Dict]) -> Dict[int, List[float]]:
        """
        Compute gap metrics:
        - normalized current gap (gap / expected_gap)
        - gap survival probability (under memoryless null (43/49)^gap)
        - empirical mean gap / expected gap ratio
        - gap variance / volatility
        """
        current_gaps = cls.compute_current_gaps(draws)
        hist_gaps = cls.compute_historical_gaps(draws, max_lookback=300)
        
        profiles = {}
        for n in range(1, cls.TOTAL_NUMBERS + 1):
            cg = current_gaps[n]
            norm_gap = cg / cls.EXPECTED_GAP
            survival_p = ((43.0 / 49.0) ** cg) if cg < 100 else 0.0
            
            hg = hist_gaps[n]
            mean_hg = sum(hg) / len(hg) if hg else cls.EXPECTED_GAP
            var_hg = sum((x - mean_hg)**2 for x in hg) / len(hg) if len(hg) > 1 else 1.0
            std_hg = math.sqrt(var_hg)
            
            profiles[n] = [norm_gap, survival_p, mean_hg / cls.EXPECTED_GAP, std_hg]
            
        return profiles
