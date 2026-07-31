import os
import sys
import logging
from collections import defaultdict

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules

def debug_gnn_synergy():
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws('POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    
    optimizer = MultiBetOptimizer()
    history = all_draws[-600:-100] # Use some history
    
    print("🚀 Debugging GNN Synergy Selection")
    
    result = optimizer.generate_diversified_bets(
        history, rules, num_bets=5,
        meta_config={'high_precision': True}
    )
    
    print(f"\nRegime detected: {result.get('regime', 'N/A')}")
    print(f"Total Unique Numbers Covered: {result['total_unique_numbers']}")
    print(f"Coverage: {result['coverage']:.2%}")
    
    print("\nBets Generated:")
    for i, bet in enumerate(result['bets']):
        print(f"Bet {i+1}: {bet['numbers']} (Source: {bet['source']})")
        
    # Check if gnn_synergy_gap_filler was used
    sources = [b['source'] for b in result['bets']]
    if 'gnn_synergy_gap_filler' in sources:
        print("\n✅ SUCCESS: GNN Synergy Gap Filler was utilized.")
    else:
        print("\n⚠️ NOTE: GNN Synergy Gap Filler was NOT utilized (likely enough strategies available).")

if __name__ == "__main__":
    debug_gnn_synergy()
