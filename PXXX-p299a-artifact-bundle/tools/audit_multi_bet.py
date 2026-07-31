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
from models.optimized_ensemble import OptimizedEnsemblePredictor
from database import db_manager
from common import get_lottery_rules

logging.basicConfig(level=logging.ERROR)

def calculate_matches(predicted, actual):
    return len(set(predicted) & set(actual))

def audit_multi(periods=200, num_bets=3, bt_periods=3):
    lottery_type = 'POWER_LOTTO'
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    db_manager.db_path = db_path
    
    all_draws = sorted(db_manager.get_all_draws(lottery_type), key=lambda x: x['draw'])
    test_periods = min(periods, len(all_draws) - 200)
    test_draws = all_draws[-test_periods:]
    
    print(f"🔬 MULTI-BET AUDIT ({test_periods} Periods, {num_bets} Bets, BT={bt_periods})")
    print("-" * 60)
    
    random.seed(42)
    
    r_wins = 0
    ai_wins = 0
    
    r_m3_hits = 0
    ai_m3_hits = 0
    
    r_spec_hits = 0
    ai_spec_hits = 0
    
    engine = UnifiedPredictionEngine()
    ensemble = OptimizedEnsemblePredictor(engine)
    rules = get_lottery_rules(lottery_type)
    
    print("\nRunning Simulation...")
    for idx, target in enumerate(test_draws):
        actual_m = set(target['numbers'])
        actual_s = target['special']
        
        # 1. Random N-Bets
        r_hit_any = False
        r_m3_any = False
        r_s_any = False
        for _ in range(num_bets):
            rm = set(random.sample(range(1, 39), 6))
            rs = random.randint(1, 8)
            match = len(rm & actual_m)
            shit = (rs == actual_s)
            if match >= 3: 
                r_m3_any = True
                r_hit_any = True
            if shit: 
                r_s_any = True
                r_hit_any = True
        
        if r_hit_any: r_wins += 1
        if r_m3_any: r_m3_hits += 1
        if r_s_any: r_spec_hits += 1
        
        # 2. AI N-Bets
        target_pos = next(i for i, d in enumerate(all_draws) if d['draw'] == target['draw'])
        history = list(reversed(all_draws[:target_pos]))
        
        res = ensemble.predict(history, rules, num_bets=num_bets, backtest_periods=bt_periods)
        
        # Extract bets
        bets = []
        if 'bets' in res: bets = res['bets']
        else:
            for k in sorted(res.keys()):
                if k.startswith('bet') and k[3:].isdigit():
                    bets.append(res[k])
        
        ai_hit_any = False
        ai_m3_any = False
        ai_s_any = False
        for bet in bets:
            am = set(bet['numbers'])
            ash = (bet['special'] == actual_s)
            match = len(am & actual_m)
            if match >= 3:
                ai_m3_any = True
                ai_hit_any = True
            if ash:
                ai_s_any = True
                ai_hit_any = True
        
        if ai_hit_any: ai_wins += 1
        if ai_m3_any: ai_m3_hits += 1
        if ai_s_any: ai_spec_hits += 1
        
        if (idx + 1) % 10 == 0:
            ai_rate = (ai_wins / (idx + 1)) * 100
            r_rate = (r_wins / (idx + 1)) * 100
            print(f"  Progress: {idx+1}/{test_periods} | AI: {ai_rate:.1f}% | Random: {r_rate:.1f}% | Edge: {ai_rate - r_rate:+.1f}%")

    print("\n" + "=" * 60)
    print(f"🏆 FINAL VERIFICATION: {num_bets}-BET CONFIG")
    print("-" * 60)
    
    r_rate = (r_wins / test_periods) * 100
    ai_rate = (ai_wins / test_periods) * 100
    
    r_m3_rate = (r_m3_hits / test_periods) * 100
    ai_m3_rate = (ai_m3_hits / test_periods) * 100
    
    r_s_rate = (r_spec_hits / test_periods) * 100
    ai_s_rate = (ai_spec_hits / test_periods) * 100
    
    print(f"Prize Cov (Any) | {r_rate:14.2f}% | {ai_rate:8.2f}% | {ai_rate - r_rate:+6.2f}%")
    print(f"M3+ Cov (Any)   | {r_m3_rate:14.2f}% | {ai_m3_rate:8.2f}% | {ai_m3_rate - r_m3_rate:+6.2f}%")
    print(f"Spec Cov (Any)  | {r_s_rate:14.2f}% | {ai_s_rate:8.2f}% | {ai_s_rate - r_s_rate:+6.2f}%")
    print("-" * 60)
    
    if ai_rate > r_rate:
        print(f"✅ STATISTICAL EDGE CONFIRMED: {ai_rate - r_rate:.2f}% improvement")
    else:
        print(f"❌ EDGE NOT ACHIEVED")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--periods", type=int, default=100)
    parser.add_argument("--bets", type=int, default=3)
    parser.add_argument("--bt", type=int, default=3)
    args = parser.parse_args()
    
    audit_multi(args.periods, args.bets, args.bt)
