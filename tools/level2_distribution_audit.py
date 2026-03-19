#!/usr/bin/env python3
"""
Phase 77: Level 2 Strategy Distribution Audit
==============================================

Verifies the Risk Profile (Variance) and Coverage for:
1. Zone Split (Lower Variance, Smooth Distribution)
2. Core-Satellite (Higher Variance, Bimodal Distribution)
"""

import random
import numpy as np
import collections

def simulate_draw(total_nums=49, pick=6):
    return set(random.sample(range(1, total_nums + 1), pick))

def get_hits(bet, draw):
    return len(set(bet).intersection(draw))

class DistributionAudit:
    def __init__(self, periods=20000, num_bets=3, total_nums=49, pick=6):
        self.periods = periods
        self.num_bets = num_bets
        self.total_nums = total_nums
        self.pick = pick
        self.history = [simulate_draw(total_nums, pick) for _ in range(periods)]

    def run_zone_split(self):
        """Orthogonal: Distributed bits."""
        hist_total_hits = []
        coverage_counts = []
        
        for draw in self.history:
            pool = list(range(1, self.total_nums + 1))
            random.shuffle(pool)
            
            bets = [pool[i*self.pick : (i+1)*self.pick] for i in range(self.num_bets)]
            
            # Total hits across ALL 3 bets this period
            hits = sum(get_hits(b, draw) for b in bets)
            hist_total_hits.append(hits)
            coverage_counts.append(len(set().union(*bets)))
            
        return hist_total_hits, np.mean(coverage_counts)

    def run_core_satellite(self, core_size=3):
        """Anchored: Clustered bits."""
        hist_total_hits = []
        coverage_counts = []
        
        for draw in self.history:
            pool = list(range(1, self.total_nums + 1))
            random.shuffle(pool)
            
            core = pool[:core_size]
            sat_needed = self.num_bets * (self.pick - core_size)
            sats = pool[core_size : core_size + sat_needed]
            
            bets = [core + sats[i*(self.pick-core_size):(i+1)*(self.pick-core_size)] 
                    for i in range(self.num_bets)]
            
            hits = sum(get_hits(b, draw) for b in bets)
            hist_total_hits.append(hits)
            coverage_counts.append(len(set().union(*bets)))
            
        return hist_total_hits, np.mean(coverage_counts)

    def analyze(self):
        zs_hits, zs_cov = self.run_zone_split()
        cs_hits, cs_cov = self.run_core_satellite(core_size=3)
        
        print(f"--- Level 2 Strategy Audit ({self.periods} periods) ---")
        print(f"Configuration: {self.num_bets} Bets, {self.total_nums} Numbers")
        print("-" * 50)
        
        for name, hits, cov in [("Zone Split", zs_hits, zs_cov), ("Core-Satellite (3-core)", cs_hits, cs_cov)]:
            mean = np.mean(hits)
            std = np.std(hits)
            var = np.var(hits)
            
            # Frequency of specific hit counts (Total hits in 3 bets)
            counts = collections.Counter(hits)
            p0 = counts[0] / self.periods * 100
            p1 = counts[1] / self.periods * 100
            p_high = sum(v for k, v in counts.items() if k >= 6) / self.periods * 100  # Multi-hit cluster
            
            print(f"Strategy: {name}")
            print(f"  Coverage:  {cov:.1f} numbers ({cov/self.total_nums*100:.1f}%)")
            print(f"  Mean Hits: {mean:.4f} (E[X] remains constant)")
            print(f"  Variance:  {var:.4f} (The REAL difference)")
            print(f"  Probability of 0 hits across all bets: {p0:.1f}%")
            print(f"  Probability of 6+ combined hits (Cluster): {p_high:.2f}%")
            print("-" * 50)

if __name__ == "__main__":
    audit = DistributionAudit(periods=50000)
    audit.analyze()
