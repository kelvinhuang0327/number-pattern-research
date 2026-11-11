"""
Big Lotto MMS Exact-Delete Multi-Ticket Candidate Strategy.
Strategy Name: BIGLOTTO_MMS_EXACT_DELETE_MULTI_TICKET_CANDIDATE_BATCH_R1
"""
from typing import List, Dict, Tuple, Set
import itertools
import random

from features.mms_features import MMSFeatures
from features.frequency_features import FrequencyFeatures
from features.gap_features import GapFeatures

class MMSExactDeleteStrategy:
    """
    Generates structured multi-ticket portfolios for Big Lotto based on
    Multiscale Markov Space (MMS) transition modeling, exact deletion pruning of
    anti-resonance numbers, and low-overlap geometric candidate generation.
    """
    
    STRATEGY_NAME = "BIGLOTTO_MMS_EXACT_DELETE_MULTI_TICKET_CANDIDATE_BATCH_R1"
    VERSION = "1.0.0"
    TOTAL_NUMBERS = 49
    PICK_COUNT = 6
    
    def __init__(
        self,
        k_delete: int = 12,
        windows: Tuple[int, ...] = (50, 300, 750),
        max_overlap_threshold: int = 3,
        seed: int = 42
    ):
        self.k_delete = k_delete
        self.windows = windows
        self.max_overlap_threshold = max_overlap_threshold
        self.seed = seed

    def get_exact_deletion_and_scores(self, draws: List[Dict]) -> Tuple[Set[int], List[int], Dict[int, float]]:
        """
        Execute Exact Deletion filter and calculate selection scores for surviving numbers.
        """
        deleted_set, surviving_pool = MMSFeatures.exact_delete_filter(
            draws,
            k_delete=self.k_delete,
            windows=self.windows
        )
        mms_scores = MMSFeatures.compute_multiscale_markov_scores(draws, self.windows)
        z10 = FrequencyFeatures.compute_zscores(draws, 10)
        z30 = FrequencyFeatures.compute_zscores(draws, 30)
        
        final_scores = {}
        for n in surviving_pool:
            # High transition probability + positive short-term momentum
            s = 0.50 * mms_scores.get(n, 0.5) + 0.30 * (z10.get(n, 0.0) * 0.1 + 0.5) + 0.20 * (z30.get(n, 0.0) * 0.1 + 0.5)
            final_scores[n] = float(s)
            
        return deleted_set, surviving_pool, final_scores

    def generate_ordered_portfolio(self, draws: List[Dict], n_tickets: int = 20) -> List[Tuple[int, ...]]:
        """
        Construct an ordered portfolio of `n_tickets` distinct 6-ball tickets exclusively
        drawn from the surviving candidate pool under pairwise bounded overlap.
        """
        if len(draws) < 10:
            rng = random.Random(self.seed)
            all_nums = list(range(1, self.TOTAL_NUMBERS + 1))
            res = []
            for _ in range(n_tickets):
                res.append(tuple(sorted(rng.sample(all_nums, self.PICK_COUNT))))
            return res

        deleted_set, surviving_pool, scores = self.get_exact_deletion_and_scores(draws)
        
        # Sort surviving pool by score descending
        ranked_survivors = sorted(surviving_pool, key=lambda n: scores[n], reverse=True)
        
        # Split surviving pool into 3 quantile tiers (Hot-Markov, Balanced, Diversified)
        tier_size = len(ranked_survivors) // 3
        tier1 = ranked_survivors[:tier_size]
        tier2 = ranked_survivors[tier_size: 2 * tier_size]
        tier3 = ranked_survivors[2 * tier_size:]
        
        tickets: List[Tuple[int, ...]] = []
        used_ticket_sets: Set[Tuple[int, ...]] = set()
        
        rng = random.Random(self.seed + len(draws))
        max_attempts = 3000
        attempt = 0
        
        # We generate tickets: 3 from Tier 1, 2 from Tier 2, 1 from Tier 3
        while len(tickets) < n_tickets and attempt < max_attempts:
            attempt += 1
            
            p1 = rng.sample(tier1, min(3, len(tier1)))
            p2 = rng.sample(tier2, min(2, len(tier2)))
            p3 = rng.sample(tier3, min(1, len(tier3))) if tier3 else []
            
            picked = list(set(p1 + p2 + p3))
            
            # Fill up to 6 if needed
            if len(picked) < self.PICK_COUNT:
                for cand in ranked_survivors:
                    if len(picked) == self.PICK_COUNT:
                        break
                    if cand not in picked:
                        picked.append(cand)
                        
            if len(picked) < self.PICK_COUNT:
                continue
                
            ticket = tuple(sorted(picked[:self.PICK_COUNT]))
            if ticket in used_ticket_sets:
                continue
                
            # Pairwise overlap constraint
            acceptable = True
            for prev_t in tickets:
                overlap = len(set(ticket) & set(prev_t))
                if overlap > self.max_overlap_threshold:
                    acceptable = False
                    break
                    
            if acceptable:
                tickets.append(ticket)
                used_ticket_sets.add(ticket)

        # Fallback combination generator if constraint was tight
        if len(tickets) < n_tickets:
            for comb in itertools.combinations(ranked_survivors[:20], self.PICK_COUNT):
                if len(tickets) >= n_tickets:
                    break
                t = tuple(sorted(comb))
                if t not in used_ticket_sets:
                    tickets.append(t)
                    used_ticket_sets.add(t)

        return tickets[:n_tickets]
