#!/usr/bin/env python3
import sys
import os
import logging
from typing import List, Dict

# Setup path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from models.prediction_optimizer import optimize_power_lotto_prediction
from common import load_backend_history, get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_diversified_8_bets():
    lottery_type = 'POWER_LOTTO'
    history, rules = load_backend_history(lottery_type)
    
    engine = UnifiedPredictionEngine()
    ensemble = OptimizedEnsemblePredictor(engine)
    
    logger.info("🎯 Generating 8 Diversified Bets for Power Lotto...")
    
    # 1. Consensus Bets (Top 4 from Ensemble)
    # ensemble.predict returns bet1 and bet2. We need to get more.
    # Modified predict logic: we can get top scores and form bets.
    
    weights = ensemble.calculate_strategy_weights(history, rules, backtest_periods=5)
    all_preds = {}
    for name, method in ensemble.strategy_methods.items():
        try:
            all_preds[name] = method(history, rules)
        except: continue
        
    # Calculate number scores
    scores = {}
    for name, pred in all_preds.items():
        if not pred: continue
        w = weights.get(name, 0.05)
        for i, num in enumerate(pred.get('numbers', [])):
            rank_score = (rules['pickCount'] - i) / rules['pickCount']
            scores[num] = scores.get(num, 0) + w * rank_score * 10
            
    sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    
    consensus_bets = []
    for i in range(4):
        start = i * rules['pickCount']
        nums = sorted_nums[start : start + rules['pickCount']]
        # Fill if not enough
        if len(nums) < rules['pickCount']:
             for n in range(rules['minNumber'], rules['maxNumber']+1):
                 if n not in nums: nums.append(n)
                 if len(nums) >= rules['pickCount']: break
        consensus_bets.append(sorted(nums))

    # 2. Pattern-Hedge Bets (2 from MAML)
    pattern_bets = []
    try:
        maml_res = engine.maml_predict(history, rules)
        maml_nums = maml_res['numbers']
        pattern_bets.append(maml_nums)
        # Shift slightly for the second one
        shifted = sorted([(n + 1) if n < rules['maxNumber'] else rules['minNumber'] for n in maml_nums])
        pattern_bets.append(shifted)
    except Exception as e:
        logger.warning(f"MAML failed: {e}")
        # Fallback to bayesian
        bayesian_res = engine.bayesian_predict(history, rules)
        pattern_bets.extend([bayesian_res['numbers'], sorted([(n+1) for n in bayesian_res['numbers']])])

    # 3. Black-Swan Bets (2 from Anomaly)
    anomaly_bets = []
    try:
        from models.anomaly_predictor import AnomalyPredictor
        predictor = AnomalyPredictor(max_num=rules['maxNumber'])
        # Get 2 most anomaly combinations
        res = predictor.predict_anomaly(history, pick_count=rules['pickCount'], top_k=2)
        for combo, score in res:
            anomaly_bets.append(sorted(combo))
    except Exception as e:
        logger.warning(f"Anomaly detection failed: {e}")
        # Fallback to cold numbers
        from models.smart_multi_bet import SmartMultiBetSystem
        smart = SmartMultiBetSystem()
        cold_bets = smart.generate_smart_bets(history, rules, num_bets=2)
        for b in cold_bets['bets']: anomaly_bets.append(b['numbers'])

    all_8_bets = consensus_bets + pattern_bets[:2] + anomaly_bets[:2]
    
    # 4. Optimize and Predict Specials
    from models.special_predictor import get_enhanced_special_prediction
    
    final_results = []
    for i, nums in enumerate(all_8_bets, 1):
        # Predict special
        spec = get_enhanced_special_prediction(history, rules, nums)
        # Optimize main numbers
        opt_nums, opt_spec = optimize_power_lotto_prediction(nums, spec, history, rules)
        
        final_results.append({
            'index': i,
            'numbers': opt_nums,
            'special': opt_spec,
            'type': 'Consensus' if i <= 4 else ('Pattern-Hedge' if i <= 6 else 'Black-Swan')
        })
        
    return final_results

if __name__ == '__main__':
    results = generate_diversified_8_bets()
    print("\n" + "="*50)
    print("🚀 POWER LOTTO DIVERSIFIED 8-BET RECOMMENDATIONS")
    print("="*50)
    for res in results:
        print(f"Bet {res['index']} [{res['type']}]: {res['numbers']} + Special: {res['special']}")
    print("="*50)
