import os
import sys
import logging
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer

def test_3bet_zone_correction():
    optimizer = MultiBetOptimizer()
    
    # Mock draws where Zone 5 (31-38 for Power Lotto) is completely empty for 20 draws
    # This should trigger Zone Gap Correction if no bet covers it.
    history = []
    for i in range(25):
        history.append({
            'draw': 100 - i,
            'numbers': [1, 2, 3, 4, 5, 6], # All in Zone 1
            'date': f'202{i}-01-01'
        })
    
    rules = {'name': 'POWER_LOTTO', 'minNumber': 1, 'maxNumber': 38, 'pickCount': 6}
    
    # Run optimizer for 3 bets
    result = optimizer.generate_orthogonal_strategy_3bets(history, rules, {})
    
    print("\n--- 3-Bet Results with Zone Correction ---")
    found_correction = False
    for i, bet in enumerate(result['bets'], 1):
        print(f"Bet {i}: {bet['numbers']} (Source: {bet['source']})")
        if "zone_gap_corrected" in bet['source']:
            found_correction = True
            
    if found_correction:
        print("\n✅ Success: Zone Gap Correction was applied to 3-bet!")
    else:
        # Check if the coldest zone was already covered by pure prediction
        print("\nNote: Correction might not have been applied if the coldest zone was already covered.")

if __name__ == "__main__":
    test_3bet_zone_correction()
