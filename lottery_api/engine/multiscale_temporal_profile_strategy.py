"""
Big Lotto Multiscale Temporal Profile Cluster Multi-Ticket Candidate Strategy.
Strategy Name: BIGLOTTO_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MULTI_TICKET_CANDIDATE_BATCH_R1
"""
from typing import List, Dict, Tuple, Set, Any
import itertools
import math
import random

from features.frequency_features import FrequencyFeatures
from features.gap_features import GapFeatures
from features.temporal_profile_clustering import TemporalProfileClusterer

class MultiscaleTemporalProfileStrategy:
    """
    Generates structured multi-ticket portfolios for Big Lotto based on
    multiscale temporal activity profile clustering and low-overlap geometric diversification.
    """
    
    STRATEGY_NAME = "BIGLOTTO_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MULTI_TICKET_CANDIDATE_BATCH_R1"
    VERSION = "1.0.0"
    TOTAL_NUMBERS = 49
    PICK_COUNT = 6
    
    def __init__(
        self,
        n_clusters: int = 5,
        scales: Tuple[int, ...] = (10, 30, 100, 300),
        max_overlap_threshold: int = 2,
        seed: int = 42
    ):
        self.n_clusters = n_clusters
        self.scales = scales
        self.max_overlap_threshold = max_overlap_threshold
        self.seed = seed
        self.clusterer = TemporalProfileClusterer(
            n_clusters=n_clusters,
            scales=scales,
            random_seed=seed
        )

    def score_candidates(self, draws: List[Dict]) -> Dict[int, float]:
        """
        Assign a composite priority score to each ball 1..49 based on:
        - short-term momentum (10-draw z-score)
        - medium-term hazard readiness (30-draw gap hazard)
        - long-term baseline stability (100-draw frequency)
        """
        z10 = FrequencyFeatures.compute_zscores(draws, 10)
        z30 = FrequencyFeatures.compute_zscores(draws, 30)
        f100 = FrequencyFeatures.compute_frequencies(draws, 100)
        gaps = GapFeatures.compute_current_gaps(draws)
        
        scores = {}
        for n in range(1, self.TOTAL_NUMBERS + 1):
            gap_norm = gaps[n] / (49.0 / 6.0)
            # Favorable hazard profile: neither immediately repeated nor ultra-cold (> 4x expected)
            hazard_score = 1.0 / (1.0 + abs(gap_norm - 1.0))
            
            score = (
                0.35 * z10[n] +
                0.25 * z30[n] +
                0.20 * (f100[n] / (6.0 / 49.0)) +
                0.20 * hazard_score
            )
            scores[n] = float(score)
        return scores

    def generate_ordered_portfolio(self, draws: List[Dict], n_tickets: int = 20) -> List[Tuple[int, ...]]:
        """
        Construct an ordered portfolio of `n_tickets` distinct 6-ball tickets.
        Prefixes of lengths (5, 10, 15, 20) form valid nested portfolios.
        """
        if len(draws) < 10:
            # Fallback for insufficient history
            rng = random.Random(self.seed)
            all_nums = list(range(1, self.TOTAL_NUMBERS + 1))
            res = []
            for _ in range(n_tickets):
                res.append(tuple(sorted(rng.sample(all_nums, self.PICK_COUNT))))
            return res

        # 1. Extract features and cluster
        feat_matrix = self.clusterer.extract_feature_matrix(draws)
        clustering_res = self.clusterer.cluster_profiles(feat_matrix)
        cluster_groups = clustering_res['clusters']
        scores = self.score_candidates(draws)

        # Rank members within each cluster by composite score
        ranked_clusters = []
        for k in range(self.n_clusters):
            members = [item['number'] for item in cluster_groups[k]]
            members.sort(key=lambda n: scores[n], reverse=True)
            ranked_clusters.append(members)

        tickets: List[Tuple[int, ...]] = []
        used_ticket_sets: Set[Tuple[int, ...]] = set()
        
        # We generate tickets iteratively with low overlap constraints
        # Ensure round-robin cluster representation: 1 number from top 4-5 clusters + high-scoring fillers
        rng = random.Random(self.seed + len(draws))
        
        # Build a pool of high-quality candidate combinations
        max_attempts = 2000
        attempt = 0
        
        while len(tickets) < n_tickets and attempt < max_attempts:
            attempt += 1
            picked = []
            
            # Select 1 number from each of the first min(5, n_clusters) clusters
            # with probability proportional to rank within cluster
            cluster_order = list(range(self.n_clusters))
            rng.shuffle(cluster_order)
            
            for c_idx in cluster_order[:5]:
                members = ranked_clusters[c_idx]
                if members:
                    # Pick from top-tier members with higher probability
                    top_k = members[:max(3, len(members)//2)]
                    chosen = rng.choice(top_k)
                    if chosen not in picked:
                        picked.append(chosen)
                        
            # Fill remaining balls up to 6 from highest overall scored numbers not yet picked
            all_sorted_by_score = sorted(range(1, self.TOTAL_NUMBERS + 1), key=lambda n: scores[n], reverse=True)
            for cand in all_sorted_by_score:
                if len(picked) == self.PICK_COUNT:
                    break
                if cand not in picked:
                    picked.append(cand)
                    
            if len(picked) < self.PICK_COUNT:
                continue
                
            ticket = tuple(sorted(picked[:self.PICK_COUNT]))
            if ticket in used_ticket_sets:
                continue
                
            # Check overlap constraint with previously accepted tickets
            # For 20 tickets, allow overlap up to 3 (standard min-overlap geometry for 6/49)
            acceptable = True
            for prev_t in tickets:
                overlap = len(set(ticket) & set(prev_t))
                if overlap > 3:  # Bounded pairwise intersection
                    acceptable = False
                    break
                    
            if acceptable:
                tickets.append(ticket)
                used_ticket_sets.add(ticket)

        # Fallback if constraint was too strict to reach n_tickets
        if len(tickets) < n_tickets:
            for cand_comb in itertools.combinations(all_sorted_by_score[:18], self.PICK_COUNT):
                if len(tickets) >= n_tickets:
                    break
                t = tuple(sorted(cand_comb))
                if t not in used_ticket_sets:
                    tickets.append(t)
                    used_ticket_sets.add(t)

        return tickets[:n_tickets]
