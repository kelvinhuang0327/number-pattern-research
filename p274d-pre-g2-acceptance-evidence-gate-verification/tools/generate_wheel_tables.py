#!/usr/bin/env python3
"""
Generate Optimal Wheel Tables
Uses greedy algorithm to find minimal ticket sets with 100% coverage.
"""

from itertools import combinations
import random

def generate_optimal_wheel(pool_size, guarantee_t, condition_m, ticket_k=6, max_tickets=50):
    """
    Generate a wheel with 100% coverage guarantee.
    Returns list of tickets (0-indexed positions).
    """
    random.seed(42)  # Reproducibility
    
    all_draws = list(combinations(range(pool_size), condition_m))
    remaining = set(range(len(all_draws)))
    
    tickets = []
    
    while remaining and len(tickets) < max_tickets:
        best_ticket = None
        best_coverage = []
        
        # Generate all possible tickets if feasible
        if pool_size <= 15:
            candidates = list(combinations(range(pool_size), ticket_k))
        else:
            candidates = [tuple(sorted(random.sample(range(pool_size), ticket_k))) 
                          for _ in range(2000)]
        
        for ticket in candidates:
            ticket_set = set(ticket)
            covered = []
            for idx in remaining:
                draw = all_draws[idx]
                if len(ticket_set & set(draw)) >= guarantee_t:
                    covered.append(idx)
            
            if len(covered) > len(best_coverage):
                best_coverage = covered
                best_ticket = ticket
        
        if best_ticket and best_coverage:
            tickets.append(list(best_ticket))
            remaining -= set(best_coverage)
            print(f"  Ticket {len(tickets)}: {best_ticket} covers {len(best_coverage)} scenarios. Remaining: {len(remaining)}")
        else:
            break
    
    return tickets, len(remaining) == 0

def format_for_code(tickets):
    """Format tickets for copy-paste into wheel_tables.py"""
    lines = []
    for t in tickets:
        lines.append(f"        {t},")
    return "\n".join(lines)

def main():
    configs = [
        (8, 3, 4),
        (10, 3, 3),
        (10, 3, 4),
        (12, 3, 3),
        (12, 3, 4),
        (12, 4, 6),
        (14, 3, 4),
        (15, 3, 4),
    ]
    
    results = {}
    
    for pool_size, guarantee_t, condition_m in configs:
        print(f"\n{'='*60}")
        print(f"Generating: Pool={pool_size}, Guarantee={guarantee_t} if {condition_m}")
        print('='*60)
        
        tickets, is_complete = generate_optimal_wheel(pool_size, guarantee_t, condition_m)
        
        print(f"\nResult: {len(tickets)} tickets, Complete: {'✅' if is_complete else '❌'}")
        
        if is_complete:
            results[(pool_size, guarantee_t, condition_m, 6)] = tickets
            print("\nCode:")
            print(f"    ({pool_size}, {guarantee_t}, {condition_m}, 6): [")
            print(format_for_code(tickets))
            print("    ],")
    
    return results

if __name__ == "__main__":
    main()
