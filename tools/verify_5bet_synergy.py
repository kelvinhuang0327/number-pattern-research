import os
import sys
import logging

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.utils.backtest_safety import (
    validate_chronological_order, 
    get_safe_backtest_slice
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('MultiBetVerify')

def run_5bet_verification(periods: int = 500):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws('POWER_LOTTO'))
    
    rules = get_lottery_rules('POWER_LOTTO')
    optimizer = MultiBetOptimizer()
    
    hits = 0
    test_data = all_draws[-periods:]
    
    print(f"🚀 Starting 5-bet GNN Synergy Verification: {periods} periods")
    
    for i, target_draw in enumerate(test_data):
        target_idx = all_draws.index(target_draw)
        history = get_safe_backtest_slice(all_draws, target_idx)
        actual_numbers = set(target_draw['numbers'])
        
        # 使用 MultiBetOptimizer 生成 5 注
        result = optimizer.generate_diversified_bets(
            history, rules, num_bets=5, 
            meta_config={'high_precision': True}
        )
        
        # 檢查是否任一注中 3+
        matched_any = False
        for bet in result['bets']:
            if len(set(bet['numbers']) & actual_numbers) >= 3:
                matched_any = True
                break
        
        if matched_any:
            hits += 1
            
        if (i+1) % 50 == 0:
            current_rate = (hits / (i+1)) * 100
            print(f"Progress: {i+1}/{periods} | M3+ Hit Rate: {current_rate:.2f}%", flush=True)

    # Report
    rate = (hits / periods) * 100
    # Baseline for 5-bet (approx 5 * 3.87% = 19.35%, but hypergeometric overlap reduces it slightly)
    # Corrected baseline for 5 random bets: ~18.0-18.5%
    baseline = 18.20 
    
    print("\n" + "="*60, flush=True)
    print(f"🎯 POWER LOTTO 5-BET GNN SYNERGY VERIFICATION", flush=True)
    print(f"📊 Periods: {periods}", flush=True)
    print(f"🎯 Hits (M3+): {hits}", flush=True)
    print(f"📈 Hit Rate: {rate:.2f}%", flush=True)
    print(f"🎲 Corrected Baseline (5-bet): {baseline}%", flush=True)
    print("-" * 60, flush=True)
    
    edge = rate - baseline
    if edge > 0:
        print(f"✅ SUCCESS: GNN Synergy achieved {rate:.2f}% hit rate (+{edge:.2f}% Edge)", flush=True)
    else:
        print(f"❌ FAILURE: Hit rate at {rate:.2f}% ({edge:.2f}% Edge)", flush=True)
    print("="*60, flush=True)

if __name__ == "__main__":
    import sys
    periods = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    run_5bet_verification(periods)
