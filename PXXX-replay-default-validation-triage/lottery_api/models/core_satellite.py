#!/usr/bin/env python3
"""
Core-Satellite Strategy: Anchored Construction for Level 2 Optimization.
========================================================================

Focuses on creating inter-bet dependencies to stabilize payouts.
"""

import random
from typing import List, Dict, Tuple, Optional

class CoreSatelliteStrategy:
    """
    Implements the Core-Satellite strategy for multi-bet generation.
    Uses shared 'Anchor' numbers across all bets to focus hit probability.
    """
    
    def __init__(self, min_num: int = 1, max_num: int = 49, pick_count: int = 6):
        self.min_num = min_num
        self.max_num = max_num
        self.pick_count = pick_count
    
    def generate_bets(self, 
                      num_bets: int, 
                      candidate_pool: List[int] = None,
                      core_size: int = 2) -> List[List[int]]:
        """
        Generate num_bets with a shared core.
        
        Args:
            num_bets: Number of bets (2 or 3).
            candidate_pool: Sorted list of numbers from Level 1.
            core_size: Number of shared anchor numbers.
        """
        if num_bets <= 0: return []
        
        # If no pool provided, use random numbers from full range
        if not candidate_pool:
            candidate_pool = list(range(self.min_num, self.max_num + 1))
            random.shuffle(candidate_pool)
            
        # 1. Select the Core (Top N from pool)
        core = sorted(candidate_pool[:core_size])
        
        # 2. Select Satellites (Unique for each bet)
        sat_pool = candidate_pool[core_size:]
        sat_needed_per_bet = self.pick_count - core_size
        
        bets = []
        for i in range(num_bets):
            start_idx = i * sat_needed_per_bet
            end_idx = (i + 1) * sat_needed_per_bet
            
            # Ensure we don't exceed pool size
            if end_idx > len(sat_pool):
                sat_subset = random.sample(sat_pool, sat_needed_per_bet)
            else:
                sat_subset = sat_pool[start_idx:end_idx]
                
            bet = sorted(core + sat_subset)
            bets.append(bet)
            
        return bets

    def get_structure_meta(self, bets: List[List[int]]) -> Dict:
        """Calculate structural metadata."""
        all_nums = set()
        for bet in bets:
            all_nums.update(bet)
            
        # Find intersection
        if not bets: return {}
        core_nums = set(bets[0])
        for b in bets[1:]:
            core_nums = core_nums.intersection(b)
            
        return {
            "core_numbers": sorted(list(core_nums)),
            "core_size": len(core_nums),
            "total_unique_numbers": len(all_nums),
            "num_bets": len(bets),
            "philosophy": "核心-衛星 (Core-Satellite): 通過共享錨點穩定收益分佈。"
        }

def get_core_satellite_predictor(lottery_type: str, num_bets: int = 3, core_size: int = 2):
    """Factory function for Core-Satellite prediction."""
    if lottery_type == "POWER_LOTTO":
        max_num = 38
    else:
        max_num = 49
        
    # In a real system, we would get a sorted pool from a Level 1 predictor here.
    # For now, we simulate Level 1 with a random shuffle (Zero Signal Assumption).
    pool = list(range(1, max_num + 1))
    random.shuffle(pool)
    
    strategy = CoreSatelliteStrategy(max_num=max_num)
    bets = strategy.generate_bets(num_bets, pool, core_size=core_size)
    meta = strategy.get_structure_meta(bets)
    
    return {
        "bets": bets,
        "metadata": meta,
        "method": f"核心-衛星策略 (Core-Satellite x{core_size})",
        "description": f"使用 {core_size} 個共享號碼作為核心，衛星號碼各注獨立。"
    }

if __name__ == "__main__":
    # Test
    for n in [2, 3]:
        result = get_core_satellite_predictor("BIG_LOTTO", num_bets=n, core_size=2)
        print(f"\n--- {n} Bets Example ---")
        print(f"Core: {result['metadata']['core_numbers']}")
        for i, bet in enumerate(result['bets'], 1):
            print(f"Bet {i}: {bet}")
