"""
Multiscale Temporal Profile Clustering for Big Lotto (6/49).
Constructs multiscale feature representations and performs deterministic clustering.
"""
from typing import List, Dict, Tuple, Any
import math
import random

from .frequency_features import FrequencyFeatures
from .gap_features import GapFeatures

class TemporalProfileClusterer:
    """
    Builds temporal feature matrices across multiple scales and clusters
    the 49 lottery numbers into distinct temporal activity regimes.
    """
    
    TOTAL_NUMBERS = 49
    PICK_COUNT = 6
    
    def __init__(self, n_clusters: int = 5, scales: Tuple[int, ...] = (10, 30, 100, 300), random_seed: int = 42):
        self.n_clusters = n_clusters
        self.scales = scales
        self.random_seed = random_seed

    def extract_feature_matrix(self, draws: List[Dict]) -> Dict[int, List[float]]:
        """Extract multiscale temporal feature vector for each number 1..49."""
        freq_vecs = FrequencyFeatures.compute_multiscale_frequency_vector(draws, self.scales)
        gap_vecs = GapFeatures.compute_gap_hazard_profiles(draws)
        
        # Also compute short-vs-long velocity (ratio of 10-draw freq to 100-draw freq)
        velocity = {}
        f10 = FrequencyFeatures.compute_frequencies(draws, 10)
        f100 = FrequencyFeatures.compute_frequencies(draws, 100)
        for n in range(1, self.TOTAL_NUMBERS + 1):
            base_100 = f100[n] if f100[n] > 0 else (6.0 / 49.0)
            velocity[n] = f10[n] / base_100
            
        full_vectors = {}
        for n in range(1, self.TOTAL_NUMBERS + 1):
            full_vectors[n] = freq_vecs[n] + gap_vecs[n] + [velocity[n]]
            
        # Standardize features across the 49 numbers (zero-mean, unit-variance)
        n_features = len(full_vectors[1])
        norm_vectors = {n: [] for n in range(1, self.TOTAL_NUMBERS + 1)}
        for j in range(n_features):
            vals = [full_vectors[n][j] for n in range(1, self.TOTAL_NUMBERS + 1)]
            mean_v = sum(vals) / len(vals)
            var_v = sum((v - mean_v)**2 for v in vals) / len(vals)
            std_v = math.sqrt(var_v) if var_v > 1e-9 else 1.0
            for n in range(1, self.TOTAL_NUMBERS + 1):
                norm_vectors[n].append((full_vectors[n][j] - mean_v) / std_v)
                
        return norm_vectors

    @staticmethod
    def _euclidean_dist(v1: List[float], v2: List[float]) -> float:
        return math.sqrt(sum((a - b)**2 for a, b in zip(v1, v2)))

    def cluster_profiles(self, feature_matrix: Dict[int, List[float]]) -> Dict[str, Any]:
        """
        Deterministic K-Means clustering of temporal profiles into `n_clusters`.
        """
        rng = random.Random(self.random_seed)
        all_numbers = list(range(1, self.TOTAL_NUMBERS + 1))
        
        # Deterministic initialization of centroids (K-Means++ style or fixed seed)
        initial_indices = sorted(rng.sample(all_numbers, self.n_clusters))
        centroids = [list(feature_matrix[n]) for n in initial_indices]
        
        assignments = {n: 0 for n in all_numbers}
        max_iters = 50
        
        for _ in range(max_iters):
            # Assignment step
            new_assignments = {}
            for n in all_numbers:
                vec = feature_matrix[n]
                dists = [self._euclidean_dist(vec, c) for c in centroids]
                best_cluster = int(dists.index(min(dists)))
                new_assignments[n] = best_cluster
                
            if new_assignments == assignments:
                break
            assignments = new_assignments
            
            # Update centroids
            for k in range(self.n_clusters):
                cluster_members = [n for n, c in assignments.items() if c == k]
                if cluster_members:
                    dim = len(feature_matrix[1])
                    new_c = [0.0] * dim
                    for m in cluster_members:
                        for d_i in range(dim):
                            new_c[d_i] += feature_matrix[m][d_i]
                    centroids[k] = [x / len(cluster_members) for x in new_c]
                    
        # Organize clusters and score members
        cluster_groups = {k: [] for k in range(self.n_clusters)}
        for n, c in assignments.items():
            dist_to_c = self._euclidean_dist(feature_matrix[n], centroids[c])
            cluster_groups[c].append({'number': n, 'centroid_dist': dist_to_c})
            
        # Sort members within each cluster by closeness to centroid / profile coherence
        for k in range(self.n_clusters):
            cluster_groups[k].sort(key=lambda x: x['centroid_dist'])
            
        return {
            'assignments': assignments,
            'centroids': centroids,
            'clusters': cluster_groups
        }
