#!/usr/bin/env python3
"""
Level 2 Strategy Benchmark: Zone Split vs Core-Satellite
========================================================

Focuses on the structural distribution of numbers into 2-3 bets.
Level 1 (Selection) is fixed as RANDOM to isolate Level 2 effects.

Strategies:
1. Zone Split (Orthogonal): Minimize overlap to maximize space coverage.
2. Core-Satellite (Anchored): Shared Core numbers across all bets.
3. Pure Random: Baseline.
"""

import random
import numpy as np
from typing import List, Set

def simulate_draw(total_nums=49, pick=6):
    return set(random.sample(range(1, total_nums + 1), pick))

def get_hits(bet: List[int], draw: Set[int]) -> int:
    return len(set(bet).intersection(draw))

def calculate_payout(hits: int) -> float:
    # Big Lotto (Approximate simplifed payouts)
    if hits == 6: return 100000000 / 100 # Jackpot (relative)
    if hits == 5: return 50000 / 100
    if hits == 4: return 2000 / 100
    if hits == 3: return 400 / 100
    return 0

class StrategyBenchmarker:
    def __init__(self, periods=1000, num_bets=3, total_nums=49, pick=6):
        self.periods = periods
        self.num_bets = num_bets
        self.total_nums = total_nums
        self.pick = pick
        self.history = [simulate_draw(total_nums, pick) for _ in range(periods)]

    def run_zone_split(self):
        """Orthogonal: Maximize coverage."""
        all_hits = 0
        all_payout = 0
        total_unique = 0
        
        for draw in self.history:
            # Level 2 Logic: Pick non-overlapping zones
            pool = list(range(1, self.total_nums + 1))
            random.shuffle(pool)
            bets = []
            for i in range(self.num_bets):
                bets.append(pool[i*self.pick : (i+1)*self.pick])
            
            # Evaluate
            hits_per_bet = [get_hits(b, draw) for b in bets]
            all_hits += sum(1 for h in hits_per_bet if h >= 3)
            all_payout += sum(calculate_payout(h) for h in hits_per_bet)
            total_unique += len(set().union(*bets))
            
        return all_hits, all_payout, total_unique / self.periods

    def run_core_satellite(self, core_size=2):
        """Anchored: Shared numbers across bets."""
        all_hits = 0
        all_payout = 0
        total_unique = 0
        
        for draw in self.history:
            # Level 1: Random selection of core and satellites
            pool = list(range(1, self.total_nums + 1))
            random.shuffle(pool)
            
            core = pool[:core_size]
            satellites_needed = self.num_bets * (self.pick - core_size)
            satellites = pool[core_size : core_size + satellites_needed]
            
            bets = []
            for i in range(self.num_bets):
                bet = core + satellites[i*(self.pick-core_size) : (i+1)*(self.pick-core_size)]
                bets.append(bet)
                
            # Evaluate
            hits_per_bet = [get_hits(b, draw) for b in bets]
            all_hits += sum(1 for h in hits_per_bet if h >= 3)
            all_payout += sum(calculate_payout(h) for h in hits_per_bet)
            total_unique += len(set().union(*bets))
            
        return all_hits, all_payout, total_unique / self.periods

    def report(self):
        print(f"Benchmark Configuration: {self.num_bets} bets, {self.periods} periods, {self.total_nums} numbers")
        print("-" * 65)
        print(f"{'Strategy':<20} | {'Hits (3+)':<10} | {'ROI/Bet':<10} | {'Coverage':<10}")
        print("-" * 65)
        
        # Zone Split
        z_hits, z_pay, z_cov = self.run_zone_split()
        print(f"{'Zone Split':<20} | {z_hits:<10} | {z_pay/(self.periods*self.num_bets):.4f} | {z_cov:<10.2f}")
        
        # Core-Satellite (Core 1)
        c1_hits, c1_pay, c1_cov = self.run_core_satellite(core_size=1)
        print(f"{'C-S (Core 1)':<20} | {c1_hits:<10} | {c1_pay/(self.periods*self.num_bets):.4f} | {c1_cov:<10.2f}")
        
        # Core-Satellite (Core 2)
        c2_hits, c2_pay, c2_cov = self.run_core_satellite(core_size=2)
        print(f"{'C-S (Core 2)':<20} | {c2_hits:<10} | {c2_pay/(self.periods*self.num_bets):.4f} | {c2_cov:<10.2f}")
        
        # Core-Satellite (Core 3)
        c3_hits, c3_pay, c3_cov = self.run_core_satellite(core_size=3)
        print(f"{'C-S (Core 3)':<20} | {c3_hits:<10} | {c3_pay/(self.periods*self.num_bets):.4f} | {c3_cov:<10.2f}")

if __name__ == "__main__":
    bench = StrategyBenchmarker(periods=10000, num_bets=3)
    bench.report()
    
    print("\n--- 2 Bets Analysis ---")
    bench2 = StrategyBenchmarker(periods=10000, num_bets=2)
    bench2.report()
