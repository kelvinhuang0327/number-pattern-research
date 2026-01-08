import sys
import os
import json

# Setup path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.multi_bet_optimizer import MultiBetOptimizer

def predict():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api/data/lottery_v2.db'))
    # Load all draws - assuming we are predicting for the NEXT draw after the last one in DB
    all_draws = db.get_all_draws('POWER_LOTTO') 
    rules = get_lottery_rules('POWER_LOTTO')
    optimizer = MultiBetOptimizer()
    
    if not all_draws:
        print("Error: No data found for POWER_LOTTO")
        return

    last_draw = all_draws[0]
    print(f"📅 Latest Historical Draw: {last_draw['date']} (Issue: {last_draw['draw']})")
    print(f"🔢 Numbers: {last_draw['numbers']} Special: {last_draw['special']}")
    print("-" * 50)
    
    # Generate 4 bets with the "King Strategy"
    try:
        res = optimizer.generate_diversified_bets(
            all_draws, rules, num_bets=4, 
            meta_config={
                'method': 'cluster_pivot',
                'forced_anchors': [7, 15],
                'anchor_count': 2,
                'resilience': True,
                'bypass_hybrid': True 
            }
        )
        
        print("\n🚀 Power Lotto 4-Bet Prediction (ClusterPivot [07, 15])")
        print("=" * 60)
        for i, bet in enumerate(res['bets'], 1):
            nums = ", ".join(f"{n:02d}" for n in bet['numbers'])
            spec = f"{bet['special']:02d}"
            print(f"💰 Bet {i}: [{nums}]   Special: {spec}")
        print("=" * 60)
        
        # Simple analysis of the bets
        all_nums = [n for b in res['bets'] for n in b['numbers']]
        print(f"\n🔍 Analysis:")
        print(f"   - Forced Anchors: 07, 15 (Included in all bets)")
        print(f"   - Unique Numbers Covered: {len(set(all_nums))}")
        
    except Exception as e:
        print(f"Error during prediction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    predict()
