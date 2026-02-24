#!/usr/bin/env python3
"""
Verify and debug the wheel coverage tables.
"""

from itertools import combinations

# 12 numbers, guarantee 3 if 4 hit - the table we're testing
POOL_SIZE = 12
GUARANTEE_T = 3
CONDITION_M = 4
TICKET_K = 6

# Current table (0-indexed positions)
CURRENT_TABLE = [
    [0, 1, 2, 3, 4, 5],
    [0, 1, 6, 7, 8, 9],
    [2, 3, 6, 7, 10, 11],
    [4, 5, 8, 9, 10, 11],
    [0, 2, 4, 6, 8, 10],
    [1, 3, 5, 7, 9, 11],
]

def verify_wheel(tickets, pool_size, guarantee_t, condition_m):
    """Check if wheel covers all scenarios."""
    all_draws = list(combinations(range(pool_size), condition_m))
    uncovered = []
    
    for draw in all_draws:
        draw_set = set(draw)
        found = False
        for ticket in tickets:
            ticket_set = set(ticket)
            if len(ticket_set & draw_set) >= guarantee_t:
                found = True
                break
        if not found:
            uncovered.append(draw)
    
    return uncovered

def main():
    print(f"Verifying wheel: {POOL_SIZE} numbers, guarantee {GUARANTEE_T} if {CONDITION_M} hit")
    print(f"Number of tickets: {len(CURRENT_TABLE)}")
    
    uncovered = verify_wheel(CURRENT_TABLE, POOL_SIZE, GUARANTEE_T, CONDITION_M)
    
    if uncovered:
        print(f"\n❌ FAILED: {len(uncovered)} scenarios NOT covered:")
        for scenario in uncovered[:20]:  # Show first 20
            print(f"   Draw {scenario} - no ticket covers {GUARANTEE_T}+ matches")
    else:
        print("\n✅ PASSED: All scenarios covered!")
    
    # Total possible scenarios
    total = len(list(combinations(range(POOL_SIZE), CONDITION_M)))
    coverage = (total - len(uncovered)) / total * 100
    print(f"\nCoverage: {coverage:.1f}% ({total - len(uncovered)}/{total} scenarios)")

if __name__ == "__main__":
    main()
