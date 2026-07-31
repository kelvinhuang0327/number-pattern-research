import os
import sys
import logging
import numpy as np

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules

def inspect_5bet():
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws('POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    
    optimizer = MultiBetOptimizer()
    # 測試最近一期
    history = all_draws[:-1]
    actual = set(all_draws[-1]['numbers'])
    
    print(f"🚀 Inspecting 5-bet Synergy for Draw: {all_draws[-1]['draw']}")
    print(f"Actual Numbers: {sorted(list(actual))}")
    
    result = optimizer.generate_diversified_bets(
        history, rules, num_bets=5,
        meta_config={'high_precision': True}
    )
    
    print(f"\nTotal Coverage: {result['coverage']:.2%}")
    print(f"Total Unique Numbers: {result['total_unique_numbers']}")
    
    all_matched = []
    for i, bet in enumerate(result['bets']):
        nums = set(bet['numbers'])
        matches = nums & actual
        all_matched.extend(list(matches))
        print(f"Bet {i+1} [{bet['source']}]: {sorted(list(nums))} | Hits: {len(matches)} {list(matches)}")
        
    unique_hits = len(set(all_matched))
    print(f"\nUnique Global Hits across all bets: {unique_hits}")
    
    # Check GNN synergy bet explicitly
    synergy_bet = next((b for b in result['bets'] if b['source'] == 'gnn_synergy_gap_filler'), None)
    if synergy_bet:
        print(f"✅ GNN Synergy Bet was present.")
    else:
        print(f"❌ GNN Synergy Bet was NOT present.")

if __name__ == "__main__":
    inspect_5bet()
