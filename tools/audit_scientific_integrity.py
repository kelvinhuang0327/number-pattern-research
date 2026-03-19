import os
import sys
import logging
from collections import Counter
import numpy as np

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.advanced_strategies import AdvancedStrategies
from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.utils.backtest_safety import (
    validate_chronological_order, 
    get_safe_backtest_slice
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger('ScientificAudit')

def calculate_match_3plus(prediction_bets, actual_nums):
    pick_count = len(actual_nums)
    actual_set = set(actual_nums)
    for bet in prediction_bets:
        if not bet: continue
        match_count = len(set(bet[:pick_count]) & actual_set)
        if match_count >= 3:
            return True
    return False

def cluster_pivot_4bet(history, rules):
    from itertools import combinations
    max_num = rules.get('maxNumber', 49)
    pick_count = rules.get('pickCount', 6)
    cooccur = Counter()
    for draw in history[-100:]:
        nums = draw['numbers']
        for pair in combinations(sorted(nums), 2):
            cooccur[pair] += 1
    num_scores = Counter()
    for (a, b), count in cooccur.items():
        num_scores[a] += count
        num_scores[b] += count
    centers = [num for num, _ in num_scores.most_common(8)]
    bets = []
    used = set()
    for i in range(4):
        anchor = centers[i]
        candidates = Counter()
        for (a, b), count in cooccur.items():
            if a == anchor and b not in used: candidates[b] += count
            elif b == anchor and a not in used: candidates[a] += count
        bet = [anchor]
        for num, _ in candidates.most_common(pick_count - 1):
            if num not in bet: bet.append(num)
        while len(bet) < pick_count:
            for n in range(1, max_num + 1):
                if n not in bet and n not in used:
                    bet.append(n)
                    break
        bets.append(sorted(bet[:pick_count]))
        used.update(bet[:1])
    return {'details': {'bets': bets}}

def run_audit(lottery_type, strategy_name, periods=1500, split_point=1000):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws(lottery_type))
    rules = get_lottery_rules(lottery_type)
    adv = AdvancedStrategies()
    engine = UnifiedPredictionEngine()
    
    test_data = all_draws[-periods:]
    hits = 0
    special_hits = 0
    train_hits = 0
    test_hits = 0
    
    # Baselines (Match-3+)
    if lottery_type == 'BIG_LOTTO':
        baseline_1bet = 1.86
    else:
        baseline_1bet = 3.87
        
    num_bets = 1 if 'single' in strategy_name else (2 if '2bet' in strategy_name else (7 if strategy_name in ['v11', 'defensive_ev_7bet', 'system_7_7bet', 'sniper_sweep_7bet'] else 4))
    baseline = (1 - (1 - baseline_1bet/100)**num_bets) * 100
    
    print(f"\n🔍 AUDITING: {lottery_type} | STRATEGY: {strategy_name} ({num_bets} Bets)")
    print(f"📊 Total Periods: {periods} (Train: {split_point}, Test: {periods - split_point})")
    
    for i, target_draw in enumerate(test_data):
        target_idx = all_draws.index(target_draw)
        history = get_safe_backtest_slice(all_draws, target_idx)
        actual_nums = target_draw.get('numbers')
        actual_special = target_draw.get('special')
        
        try:
            if strategy_name == 'v11':
                if lottery_type == 'BIG_LOTTO':
                    res = adv.anomaly_cluster_v11_predict(history, rules)
                else:
                    res = adv.power_anomaly_cluster_v11_predict(history, rules)
            elif strategy_name == 'cluster_pivot':
                res = cluster_pivot_4bet(history, rules)
            elif strategy_name == 'markov_v1_single':
                res = engine.markov_predict(history, rules)
            elif strategy_name in ['defensive_ev_7bet', 'defensive_ev_2bet']:
                from lottery_api.models.prize_optimizer import PrizeOptimizer
                optimizer = PrizeOptimizer(rules)
                anchor_res = engine.markov_predict(history, rules)
                anchor_bet = anchor_res.get('numbers')
                bets = optimizer.generate_defensive_bets([anchor_bet], total_required=num_bets)
                res = {'details': {'bets': bets}}
            elif strategy_name == 'system_7_7bet':
                from lottery_api.models.prize_optimizer import PrizeOptimizer
                optimizer = PrizeOptimizer(rules)
                anchor_res = engine.markov_predict(history, rules)
                anchor_base = anchor_res.get('numbers')
                # Guarantee 7 unique numbers (System 7)
                pool = sorted(list(set(anchor_base[:5])) + [i for i in range(32, 50) if i not in anchor_base][:2])
                bets = optimizer.generate_system_7_bets(pool)
                res = {'details': {'bets': bets}}
            elif strategy_name == 'sniper_sweep_7bet':
                # Power Lotto Sniper: 1 Main Set + Top 7 Specials
                from lottery_api.models.special_predictor import PowerLottoSpecialPredictor
                from lottery_api.models.prize_optimizer import PrizeOptimizer
                sp = PowerLottoSpecialPredictor(rules)
                optimizer = PrizeOptimizer(rules)
                
                main_res = engine.markov_predict(history, rules)
                main_numbers = main_res.get('numbers')
                top_specials = sp.predict_top_n(history, n=7)
                
                sweep_bets = optimizer.generate_sniper_sweep_bets(main_numbers, top_specials)
                bets = [b['numbers'] for b in sweep_bets]
                res = {'details': {'bets': bets}, 'specials': top_specials}
                
                # SPECIAL ZONE TRACKING
                if actual_special in top_specials:
                    special_hits += 1
            elif strategy_name == 'special_v4_single':
                # Power Lotto Special V4 Single Audit
                from lottery_api.models.special_predictor import PowerLottoSpecialPredictor
                sp = PowerLottoSpecialPredictor(rules)
                # We need some main numbers for the joint probability
                main_numbers = [1, 2, 3, 4, 5, 6] # Neutral set
                top_1 = sp.predict_top_n(history, n=1, main_numbers=main_numbers)[0]
                res = {'numbers': [1,2,3,4,5,6], 'special': top_1}
                if actual_special == top_1:
                    special_hits += 1
            elif strategy_name == 'frequency_single':
                res = engine.frequency_predict(history, rules)
            else:
                continue

            bets = res.get('details', {}).get('bets')
            if not bets:
                bets = [res.get('numbers')] if 'numbers' in res else []
            
            if not bets or not bets[0]:
                continue
                
            is_hit = calculate_match_3plus(bets, actual_nums)
            if is_hit:
                hits += 1
                if i < split_point: train_hits += 1
                else: test_hits += 1
                
        except Exception as e:
            print(f"Error at period {i}: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        if (i+1) % 500 == 0:
            print(f"   Progress: {i+1}/{periods}...")

    total_rate = (hits / periods) * 100
    train_rate = (train_hits / split_point) * 100
    test_rate = (test_hits / (periods - split_point)) * 100
    overfit_delta = train_rate - test_rate
    edge = total_rate - baseline
        
    print(f"\n--- {lottery_type} Audit Results ---")
    print(f"📈 Total Hit Rate: {total_rate:.2f}% (Baseline: {baseline:.2f}%)")
    print(f"🎓 Training Rate: {train_rate:.2f}%")
    print(f"🧪 Testing Rate: {test_rate:.2f}%")
    print(f"⚠️ Overfit Delta: {overfit_delta:+.2f}%")
    print(f"🎯 Net Edge vs Random: {edge:+.2f}%")
    
    if strategy_name == 'sniper_sweep_7bet':
        spec_rate = (special_hits / periods) * 100
        spec_baseline = 87.50
        print(f"🎯 Sniper Special Zone Hit Rate: {spec_rate:.2f}% (Baseline: {spec_baseline:.2f}%)")
    elif strategy_name == 'special_v4_single':
        spec_rate = (special_hits / periods) * 100
        spec_baseline = 12.50
        print(f"🎯 Special V6 (MAB) Top-1 Hit Rate: {spec_rate:.2f}% (Baseline: {spec_baseline:.2f}%)")
    
    status = "✅ GENUINE EDGE" if edge > 0.5 and overfit_delta < 2.5 else "❌ FAILED / OVERFITTED"
    print(f"⚖️ Final Verdict: {status}")
    print("-" * 40)

if __name__ == "__main__":
    # Final 1000-period Audit for Special V4 Top-1
    run_audit('POWER_LOTTO', 'special_v4_single', periods=1000, split_point=500)
