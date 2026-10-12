import os
import sys
import random
import numpy as np
import logging
from collections import Counter

# Set path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import db_manager
from common import get_lottery_rules

logging.basicConfig(level=logging.ERROR)

def audit_fast(periods=100, num_bets=3):
    lottery_type = 'POWER_LOTTO'
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    db_manager.db_path = db_path
    
    all_draws = sorted(db_manager.get_all_draws(lottery_type), key=lambda x: x['draw'])
    test_periods = min(periods, len(all_draws) - 200)
    test_draws = all_draws[-test_periods:]
    
    print(f"⚡ FAST MULTI-BET AUDIT ({test_periods} Periods, {num_bets} Bets)")
    print("-" * 60)
    
    random.seed(42)
    r_wins = 0
    ai_wins = 0
    
    engine = UnifiedPredictionEngine()
    rules = get_lottery_rules(lottery_type)
    
    # Define high-impact fast strategies
    # 這些策略不涉及耗時的模型訓練 (如 XGBoost/ARIMA)
    target_strats = ['lag_reversion_predict', 'sota_predict', 'markov_predict', 'statistical_predict']
    
    print("\nRunning Fast Simulation...")
    for idx, target in enumerate(test_draws):
        actual_m = set(target['numbers'])
        actual_s = target['special']
        
        # 1. Random N-Bets
        r_hit_any = False
        for _ in range(num_bets):
            rm = set(random.sample(range(1, 39), 6))
            rs = random.randint(1, 8)
            if len(rm & actual_m) >= 3 or rs == actual_s: r_hit_any = True
        if r_hit_any: r_wins += 1
        
        # 2. AI N-Bets (Simulated Multi-Bet from Top 4 Fast Strategies)
        target_pos = next(i for i, d in enumerate(all_draws) if d['draw'] == target['draw'])
        history = list(reversed(all_draws[:target_pos]))
        
        # 模擬多注：前三注分別由不同高權重策略主導
        ai_hit_any = False
        for i in range(num_bets):
            strat = target_strats[i % len(target_strats)]
            res = getattr(engine, strat)(history, rules)
            am = set(res.get('numbers', []))
            ash = (res.get('special') == actual_s)
            if len(am & actual_m) >= 3 or ash:
                ai_hit_any = True
                break
        
        if ai_hit_any: ai_wins += 1
        
        if (idx + 1) % 20 == 0:
            print(f"  Progress: {idx+1}/{test_periods} | AI WinRate: {(ai_wins/(idx+1))*100:.1f}% | Random: {(r_wins/(idx+1))*100:.1f}%")

    print("\n" + "=" * 60)
    r_rate = (r_wins / test_periods) * 100
    ai_rate = (ai_wins / test_periods) * 100
    print(f"Prize Coverage | Random: {r_rate:.2f}% | AI: {ai_rate:.2f}% | Edge: {ai_rate - r_rate:+.2f}%")
    print("=" * 60)

if __name__ == "__main__":
    audit_fast(100, 3)
