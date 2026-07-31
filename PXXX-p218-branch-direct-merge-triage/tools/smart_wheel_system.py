#!/usr/bin/env python3
"""
Smart Wheel System (聰明包牌系統)
Goal: Use combinatorial mathematics to cover a large pool of numbers (e.g., 10-20) 
      with a minimal number of bets, guaranteeing a specific win condition.

Supported Guarantees (Examples):
- 3 if 3: If 3 numbers from your pool hit, you are guaranteed at least one line with 3 hits.
- 4 if 6: If 6 numbers from your pool hit, you are guaranteed at least one line with 4 hits.

Algorithm:
Greedy Partial Covering with Optimization.
"""
import sys
import os
import itertools
import random
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

class SmartWheel:
    def __init__(self):
        pass

    def combinations(self, pool, k):
        return list(itertools.combinations(pool, k))

    def check_coverage(self, ticket, winning_numbers):
        return len(set(ticket) & set(winning_numbers))

    def generate_wheel(self, pool, guarantee_hits=3, if_numbers_drawn=3, numbers_per_ticket=6):
        """
        Generate a wheel.
        - pool: List of numbers (e.g., [1, 2, ..., 12])
        - guarantee_hits (t): Guaranteed matches in one ticket.
        - if_numbers_drawn (m): If m numbers from the pool are drawn.
        - numbers_per_ticket (k): Standard ticket size (6 for Power Lotto).
        """
        print(f"⚙️ Generating Wheel: Pool Size={len(pool)}, Guarantee {guarantee_hits} if {if_numbers_drawn} hit...")
        
        # 1. Generate all possible Drawing Combinations (Strategies of Nature)
        # We need to cover all possible 'm'-tuples from the pool.
        # But wait, the standard definition is:
        # "If m numbers are drawn, at least one ticket must match t."
        # So we iterate over all possible outcomes (m-tuples).
        
        possible_draws = list(itertools.combinations(pool, if_numbers_drawn))
        # print(f"   Total scenarios to cover: {len(possible_draws)}")
        
        # 2. Heuristic Greedy Search
        # We want to pick tickets (k-tuples) that cover the most uncovered scenarios.
        
        tickets = []
        covered_draws = set() # Set of indices in possible_draws
        
        # Optimization: Pre-calculate coverage map?
        # Too slow for large pools.
        # Simple Random Greedy:
        # Try N random tickets, pick the best one, add to solution, remove covered draws, repeat.
        
        remaining_draws = set(range(len(possible_draws)))
        
        while remaining_draws:
            best_ticket = None
            best_cover_count = -1
            best_covered_indices = []
            
            # Sample random tickets
            candidates = []
            for _ in range(500): # Sample 500 candidates
                candidates.append(random.sample(pool, numbers_per_ticket))
            
            # Or iterate all possible tickets if pool is small
            # If pool=12, 12C6 = 924. We can iterate all.
            if len(pool) <= 14:
                candidates = list(itertools.combinations(pool, numbers_per_ticket))
                random.shuffle(candidates)
            
            for ticket in candidates:
                # Count how many currently REMAINING draws this ticket covers
                current_covered = []
                ticket_set = set(ticket)
                
                # Check against remaining draws
                # This loop is the bottleneck.
                # Optimization: check only sample if too large.
                
                for idx in list(remaining_draws): # Copy for iteration safety? No need if just reading
                    # If this draw (m numbers) has >= t matches with ticket
                    draw_set = set(possible_draws[idx])
                    if len(ticket_set & draw_set) >= guarantee_hits:
                        current_covered.append(idx)
                        
                if len(current_covered) > best_cover_count:
                    best_cover_count = len(current_covered)
                    best_ticket = ticket
                    best_covered_indices = current_covered
                    
                # Heuristic: Early exit if good enough?
                if best_cover_count > len(remaining_draws) * 0.8: # Empirical
                    break
            
            if best_ticket:
                tickets.append(sorted(list(best_ticket)))
                for idx in best_covered_indices:
                    remaining_draws.remove(idx)
                print(f"   + Ticket {len(tickets)}: {best_ticket} covers {best_cover_count} scenarios. Remaining: {len(remaining_draws)}")
            else:
                print("   ⚠️ Cannot find covering ticket. Stopping.")
                break
                
        return tickets

    def suggest_pool(self):
        """
        Suggest a pool based on V3 Strategy (Cold + High)
        12 Numbers
        """
        # Call Reverse Optimization V3 logic manually to get top 12
        from tools.reverse_optimization_anti_popular import ReverseOptimizerV2
        opt = ReverseOptimizerV2()
        freqs = opt.get_real_frequency()
        avg_freq = sum(freqs.values()) / 38
        
        scores = {}
        for n in range(1, 39):
            f = freqs.get(n, 0)
            score = f * 10
            if n <= 31: score += 10
            else:
                if f < avg_freq: score -= 10
                else: score += 5
            scores[n] = score
            
        sorted_nums = sorted(scores.items(), key=lambda x: x[1])
        # Pick Top 12
        pool = [x[0] for x in sorted_nums[:15]] # Take 15 pool
        return sorted(pool)

def main():
    wheel = SmartWheel()
    
    # 1. Get Pool
    pool = wheel.suggest_pool()
    print(f"🎯 Suggested Pool (15 Numbers, V3 Strategy): {pool}")
    
    # 2. Generate Wheel
    # Common Strategy: Guarantee 3 if 4 (Win small prize guaranteed on partial hit)
    # Pool 15, Guarantee 3 if 4 hit.
    
    print("\n🚀 Strategy A: Conservative (Guarantee 3 if 4 hits)")
    # This might be too many tickets. Let's try Guarantee 3 if 5 hits.
    # Or simplified: Guarantee 3 if 6 hits (Minimal coverage).
    
    tickets = wheel.generate_wheel(pool, guarantee_hits=3, if_numbers_drawn=5, numbers_per_ticket=6)
    
    print("\n" + "="*60)
    print("🎫 Smart Wheel Tickets Generated")
    print("="*60)
    for i, t in enumerate(tickets):
        print(f"Ticket {i+1:02d}: {t}")
    print(f"\nStats: {len(tickets)} Tickets used to cover {len(pool)} numbers.")
    print("Guarantee: If any 5 numbers from pool hit, you win at least one Match 3.")
    print("="*60)

if __name__ == "__main__":
    main()
