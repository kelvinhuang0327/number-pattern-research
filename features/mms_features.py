"""
Multiscale Markov Space (MMS) Feature Engineering & Exact Deletion Filter for Big Lotto (6/49).

Implements:
1. Multiscale transition matrix counting over causal windows W in (50, 300, 750).
2. Anchor-conditioned transition probability scores given the latest completed draw.
3. Multi-window rank normalization and fused Markov scores.
4. Exact Deletion Filter identifying and eliminating the lowest-probability/anti-resonance numbers.
"""
from typing import List, Dict, Tuple, Set
import math

class MMSFeatures:
    """Multiscale Markov Space feature extractor and exact deletion filter."""
    
    TOTAL_NUMBERS = 49
    PICK_COUNT = 6
    DEFAULT_WINDOWS = (50, 300, 750)
    
    @classmethod
    def compute_transition_counts(cls, draws: List[Dict], window: int) -> Dict[int, Dict[int, int]]:
        """
        Count ordered number-to-number transitions between adjacent completed draws.
        For adjacent draws (D_{j}, D_{j+1}), if a in D_{j} and n in D_{j+1}, count pair (a, n).
        """
        counts = {a: {n: 0 for n in range(1, cls.TOTAL_NUMBERS + 1)} for a in range(1, cls.TOTAL_NUMBERS + 1)}
        effective_draws = draws[-(window + 1):] if len(draws) >= (window + 1) else draws
        
        if len(effective_draws) < 2:
            return counts
            
        for j in range(len(effective_draws) - 1):
            d_curr = effective_draws[j]['numbers']
            d_next = effective_draws[j + 1]['numbers']
            for a in d_curr:
                if 1 <= a <= cls.TOTAL_NUMBERS:
                    for n in d_next:
                        if 1 <= n <= cls.TOTAL_NUMBERS:
                            counts[a][n] += 1
        return counts

    @classmethod
    def compute_conditional_probabilities(cls, draws: List[Dict], window: int) -> Dict[int, Dict[int, float]]:
        """
        Compute P_W(n | a) = TransitionCount_W(a, n) / OutgoingCount_W(a).
        If OutgoingCount_W(a) == 0, returns 0.0.
        """
        counts = cls.compute_transition_counts(draws, window)
        probs = {a: {n: 0.0 for n in range(1, cls.TOTAL_NUMBERS + 1)} for a in range(1, cls.TOTAL_NUMBERS + 1)}
        
        for a in range(1, cls.TOTAL_NUMBERS + 1):
            outgoing = sum(counts[a].values())
            if outgoing > 0:
                for n in range(1, cls.TOTAL_NUMBERS + 1):
                    probs[a][n] = counts[a][n] / outgoing
        return probs

    @classmethod
    def compute_window_markov_score(cls, draws: List[Dict], window: int) -> Dict[int, float]:
        """
        Condition Markov score on the latest anchor draw:
        MarkovScore_W(n) = (1/6) * SUM_{a in Anchor} P_W(n | a)
        """
        if not draws:
            return {n: 1.0 / cls.TOTAL_NUMBERS for n in range(1, cls.TOTAL_NUMBERS + 1)}
            
        anchor = draws[-1]['numbers']
        probs = cls.compute_conditional_probabilities(draws, window)
        
        scores = {}
        for n in range(1, cls.TOTAL_NUMBERS + 1):
            s = sum(probs[a][n] for a in anchor if 1 <= a <= cls.TOTAL_NUMBERS) / len(anchor) if anchor else 0.0
            scores[n] = float(s)
        return scores

    @classmethod
    def compute_multiscale_markov_scores(
        cls,
        draws: List[Dict],
        windows: Tuple[int, ...] = (50, 300, 750)
    ) -> Dict[int, float]:
        """
        Compute fused multiscale Markov score across windows using rank normalization:
        NormalizedRank_W(n) = (49 - Position_W(n)) / 48
        FusedScore(n) = MEAN_W(NormalizedRank_W(n))
        """
        if len(draws) < 2:
            return {n: 0.5 for n in range(1, cls.TOTAL_NUMBERS + 1)}
            
        window_ranks = []
        for w in windows:
            scores_w = cls.compute_window_markov_score(draws, w)
            # Rank descending by score, tie-break ascending by number
            sorted_nums = sorted(
                range(1, cls.TOTAL_NUMBERS + 1),
                key=lambda n: (scores_w[n], -n),
                reverse=True
            )
            # Position is 0-indexed (0 = top, 48 = bottom)
            pos_map = {num: (48.0 - pos) / 48.0 for pos, num in enumerate(sorted_nums)}
            window_ranks.append(pos_map)
            
        fused = {}
        for n in range(1, cls.TOTAL_NUMBERS + 1):
            fused[n] = sum(wr[n] for wr in window_ranks) / len(window_ranks)
        return fused

    @classmethod
    def exact_delete_filter(
        cls,
        draws: List[Dict],
        k_delete: int = 12,
        windows: Tuple[int, ...] = (50, 300, 750)
    ) -> Tuple[Set[int], List[int]]:
        """
        Exact Deletion Operator:
        Ranks all 49 numbers using multiscale Markov transitions combined with recency penalty.
        Deterministically selects the bottom k_delete numbers to eliminate.
        Returns:
            deleted_set: Set of eliminated numbers (size k_delete)
            surviving_pool: Sorted list of surviving numbers (size 49 - k_delete)
        """
        if len(draws) < 2:
            deleted = set(range(cls.TOTAL_NUMBERS - k_delete + 1, cls.TOTAL_NUMBERS + 1))
            surviving = [n for n in range(1, cls.TOTAL_NUMBERS + 1) if n not in deleted]
            return deleted, surviving
            
        mms_scores = cls.compute_multiscale_markov_scores(draws, windows)
        
        # Compute gap decay
        gaps = {n: len(draws) for n in range(1, cls.TOTAL_NUMBERS + 1)}
        for idx, d in enumerate(reversed(draws)):
            for num in d['numbers']:
                if 1 <= num <= cls.TOTAL_NUMBERS and gaps[num] == len(draws):
                    gaps[num] = idx
                    
        composite_scores = {}
        for n in range(1, cls.TOTAL_NUMBERS + 1):
            # Penalty for extreme coldness or zero Markov attraction
            gap_penalty = 1.0 / (1.0 + max(0, gaps[n] - 30) * 0.05)
            composite_scores[n] = mms_scores[n] * 0.7 + gap_penalty * 0.3
            
        # Sort ascending by composite score (lowest first -> to delete)
        sorted_lowest_first = sorted(
            range(1, cls.TOTAL_NUMBERS + 1),
            key=lambda n: (composite_scores[n], n)
        )
        
        deleted_set = set(sorted_lowest_first[:k_delete])
        surviving_pool = sorted([n for n in range(1, cls.TOTAL_NUMBERS + 1) if n not in deleted_set])
        return deleted_set, surviving_pool
