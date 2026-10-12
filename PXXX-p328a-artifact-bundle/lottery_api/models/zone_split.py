#!/usr/bin/env python3
"""
Zone Split Strategy: Spatial Diversification for Multi-Bet Optimization.
========================================================================

This is the production implementation of the Zone Split strategy, 
which was identified in Phase 74 as the most sensible engineering 
choice for multi-bet coverage, given the i.i.d. nature of lotteries.

Philosophy: Diversification > Prediction.
"""

import random
from typing import List, Dict, Tuple, Optional

class ZoneSplitStrategy:
    """
    Implements the Zone Split strategy for multi-bet generation.
    Divides the number space into orthogonal zones to maximize coverage.
    """
    
    def __init__(self, min_num: int = 1, max_num: int = 49, pick_count: int = 6):
        self.min_num = min_num
        self.max_num = max_num
        self.pick_count = pick_count
    
    def generate_bets(self, num_bets: int, overlap_size: int = 2) -> List[List[int]]:
        """
        Generate num_bets that cover different zones of the number space.
        
        Args:
            num_bets: Number of bets to generate (typically 2 or 3).
            overlap_size: Number of extra numbers on each side of the zone to 
                         allow slight overlap for better coverage.
        """
        if num_bets <= 0:
            return []
            
        full_range = self.max_num - self.min_num + 1
        zone_size = full_range // num_bets
        
        bets = []
        for i in range(num_bets):
            # Calculate zone boundaries
            start = self.min_num + i * zone_size
            end = self.min_num + (i + 1) * zone_size - 1
            
            # Last zone takes the remainder
            if i == num_bets - 1:
                end = self.max_num
            
            # Create the candidate pool for this zone with slight overlap
            zone_pool = list(range(
                max(self.min_num, start - overlap_size), 
                min(self.max_num, end + overlap_size) + 1
            ))
            
            # If the zone pool is too small, extend it
            if len(zone_pool) < self.pick_count:
                zone_pool = list(range(self.min_num, self.max_num + 1))
            
            # Select numbers from the zone pool
            bet = sorted(random.sample(zone_pool, self.pick_count))
            bets.append(bet)
            
        return bets

    def get_coverage_meta(self, bets: List[List[int]]) -> Dict:
        """Calculate coverage metadata for the generated bets."""
        all_nums = set()
        for bet in bets:
            all_nums.update(bet)
            
        coverage_rate = len(all_nums) / (self.max_num - self.min_num + 1)
        
        return {
            "total_unique_numbers": len(all_nums),
            "coverage_rate": round(coverage_rate, 4),
            "num_bets": len(bets),
            "max_possible_unique": min(len(bets) * self.pick_count, self.max_num)
        }

def get_zone_split_predictor(lottery_type: str, num_bets: int = 3):
    """Factory function for Zone Split prediction."""
    if lottery_type == "POWER_LOTTO":
        max_num = 38
    else:
        max_num = 49
        
    strategy = ZoneSplitStrategy(max_num=max_num)
    bets = strategy.generate_bets(num_bets)
    meta = strategy.get_coverage_meta(bets)
    
    return {
        "bets": bets,
        "metadata": meta,
        "method": "正交型區間分散策略 (Zone Split)",
        "philosophy": "最大化號碼空間覆蓋，不依賴不可靠的歷史信號。"
    }

if __name__ == "__main__":
    # Test
    for lt in ["POWER_LOTTO", "BIG_LOTTO"]:
        result = get_zone_split_predictor(lt, 3)
        print(f"\n--- {lt} ---")
        print(f"Method: {result['method']}")
        for i, bet in enumerate(result['bets'], 1):
            print(f"Bet {i}: {bet}")
        print(f"Coverage: {result['metadata']['coverage_rate']:.2%}")
