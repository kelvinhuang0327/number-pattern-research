import os
import sys
import logging
from collections import Counter

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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('OrthogonalVerify')

def run_orthogonal_verification(periods: int = 500):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws('POWER_LOTTO'))
    
    rules = get_lottery_rules('POWER_LOTTO')
    optimizer = MultiBetOptimizer()
    
    hits = 0
    total_coverage = 0
    regime_counts = Counter()
    test_data = all_draws[-periods:]
    
    logger.info(f"🚀 Starting Orthogonal Ensemble (2-bet) Verification: {periods} periods")
    
    for i, target_draw in enumerate(test_data):
        target_idx = all_draws.index(target_draw)
        history = get_safe_backtest_slice(all_draws, target_idx)
        actual_numbers = set(target_draw['numbers'])
        actual_special = target_draw.get('special')
        
        # 使用 Orthogonal Ensemble 生成 2 注
        result = optimizer.generate_orthogonal_bets(history, rules, {}, num_bets=2)
        
        # 判定是否中獎 (任一注 M3+)
        won = False
        for bet in result['bets']:
            matches = len(set(bet['numbers']) & actual_numbers)
            if matches >= 3:
                won = True
                break
        
        if won:
            hits += 1
            
        total_coverage += result['coverage']
        regime_counts[result['regime']['regime']] += 1
        
        if (i+1) % 50 == 0:
            current_rate = (hits / (i+1)) * 100
            logger.info(f"Progress: {i+1}/{periods} | M3+ Hit Rate: {current_rate:.2f}% | Avg Coverage: {total_coverage/(i+1):.2f}")

    # Report
    rate = (hits / periods) * 100
    avg_cov = total_coverage / periods
    
    print("\n" + "="*60)
    print(f"🎯 POWER LOTTO ORTHOGONAL ENSEMBLE (2-BET) VERIFICATION")
    print(f"📊 Periods: {periods}")
    print(f"🎯 Hits (M3+): {hits}")
    print(f"📈 Hit Rate: {rate:.2f}%")
    print(f"📦 Avg Coverage: {avg_cov:.2f}")
    print(f"🌍 Regime Dist: {dict(regime_counts)}")
    print(f"🎲 Combined Random Baseline (2-bet): ~7.50%")
    print("-" * 60)
    
    if rate >= 10.0:
        print(f"✅ SUCCESS: Orthogonal Ensemble achieved {rate:.2f}% hit rate (Break-even Edge!)")
    else:
        print(f"⚠️ NEUTRAL: Hit rate at {rate:.2f}%")
    print("="*60)

if __name__ == "__main__":
    import sys
    periods = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    run_orthogonal_verification(periods)
