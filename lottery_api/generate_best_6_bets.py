#!/usr/bin/env python3
"""
Generate Top 6 High Confidence Bets (Generic)
Supports different lottery types via command line argument.
"""
import sys
import os
import logging
import json
from collections import defaultdict
import argparse

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import OptimizedEnsemblePredictor, create_optimized_ensemble_predictor
from common import get_lottery_rules, normalize_lottery_type

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)

def run_generation(lottery_type_arg='BIG_LOTTO'):
    # Normalize input
    lottery_type = normalize_lottery_type(lottery_type_arg)
    
    print("=" * 80)
    print(f"🚀 High Confidence Bet Generator: {lottery_type}")
    print("=" * 80)
    
    # 1. Load Rules (Critical for verification)
    lottery_rules = get_lottery_rules(lottery_type)
    print("📋 Game Rules Verification:")
    print(f"   - Name: {lottery_rules.get('name')}")
    print(f"   - Range: {lottery_rules.get('minNumber')} ~ {lottery_rules.get('maxNumber')}")
    print(f"   - Pick Count: {lottery_rules.get('pickCount')}")
    print(f"   - Special Number: {'Yes' if lottery_rules.get('hasSpecialNumber') else 'No'}")
    print("-" * 80)

    # 1. Fetch History
    all_draws = db_manager.get_all_draws(lottery_type)
    
    if not all_draws or len(all_draws) < 50: # Adjust min req
        print(f"❌ Insufficient data. Found {len(all_draws) if all_draws else 0} draws.")
        # If DB is empty, maybe we should try to load from scheduler cache if available, but usually DB is source of truth.
        return

    print(f"📊 Analyzing {len(all_draws)} historical draws...")
    print(f"   Latest Draw: {all_draws[0]['date']} (Draw {all_draws[0]['draw']})")
    print("-" * 80)
    
    
    # 2. Initialize Predictors
    # We will use individual methods from prediction_engine and the ensemble
    
    available_methods = [
        ('Frequency Analysis', prediction_engine.frequency_predict),
        ('Trend Analysis', prediction_engine.trend_predict),
        ('Bayesian Probability', prediction_engine.bayesian_predict),
        ('Monte Carlo Simulation', prediction_engine.monte_carlo_predict),
        ('Deviation Tracking', prediction_engine.deviation_predict),
        ('Markov Chain', prediction_engine.markov_predict),
    ]
    
    # Try to access advanced strategies if possible
    try:
        if hasattr(prediction_engine, 'entropy_predict'):
            available_methods.append(('Entropy Analysis', prediction_engine.entropy_predict))
        if hasattr(prediction_engine, 'hot_cold_mix_predict'):
            available_methods.append(('Hot-Cold Mixed', prediction_engine.hot_cold_mix_predict))
        if hasattr(prediction_engine, 'statistical_predict'):
            available_methods.append(('Statistical Model', prediction_engine.statistical_predict))
    except:
        pass

    # 3. Generate Candidates
    candidates = []
    
    print("🔍 Running prediction models...")
    for name, method in available_methods:
        try:
            result = method(all_draws, lottery_rules)
            bet = sorted(result['numbers'])
            confidence = result.get('confidence', 0.5)
            
            candidates.append({
                'method': name,
                'numbers': bet,
                'confidence': confidence,
                'special': result.get('special')
            })
            print(f"   ✓ {name:20s}: Confidence {confidence:.2%}")
        except Exception as e:
            # logger.error(f"Error in {name}: {e}")
            print(f"   ❌ {name:20s}: Failed")

    # 4. Also use Optimized Ensemble (Fast Mode - Recommended Weights)
    try:
        ensemble = create_optimized_ensemble_predictor(prediction_engine)
        result = ensemble.predict(all_draws, lottery_rules)
        
        candidates.append({
            'method': 'Ensemble (Bet 1)',
            'numbers': sorted(result['bet1']['numbers']),
            'confidence': result['bet1']['confidence'],
            'special': None
        })
        candidates.append({
            'method': 'Ensemble (Bet 2)',
            'numbers': sorted(result['bet2']['numbers']),
            'confidence': result['bet2']['confidence'],
            'special': None
        })
        print(f"   ✓ {'Ensemble Analysis':20s}: Generated 2 bets")
        
    except Exception as e:
         print(f"   ❌ Ensemble Analysis   : Failed ({str(e)})")

    # 5. Sort and Select Top 6
    # Sort by confidence descending
    sorted_candidates = sorted(candidates, key=lambda x: x['confidence'], reverse=True)
    
    top_6 = []
    seen_bets = set()
    
    for cand in sorted_candidates:
        # Tuple for hashing
        bet_tuple = tuple(cand['numbers'])
        if bet_tuple in seen_bets:
            continue
        
        # Verify length matches rule
        if len(cand['numbers']) != lottery_rules['pickCount']:
             # print(f"Skipping invalid length bet: {cand['numbers']}")
             continue
             
        seen_bets.add(bet_tuple)
        top_6.append(cand)
            
    top_n = 6
    if len(sys.argv) > 2:
        try:
            top_n = int(sys.argv[2])
        except:
            pass
            
    # 6. Output
    print("=" * 80)
    print(f"🏆 TOP {len(top_6[:top_n])} HIGH CONFIDENCE BETS (No Backtest) - {lottery_rules.get('name')}")
    print("=" * 80)
    
    for i, bet in enumerate(top_6[:top_n], 1):
        nums_str = ", ".join(f"{n:02d}" for n in bet['numbers'])
        
        special_str = ""
        if bucket_has_special:= lottery_rules.get('hasSpecialNumber'):
             if bet['special']:
                 special_str = f" (Special: {bet['special']})"
             else:
                 special_str = " (No Special Pred)"
        
        print(f"#{i} [{bet['method']}]")
        print(f"   Numbers   : {nums_str}{special_str}")
        print(f"   Confidence: {bet['confidence']:.2%}")
        print("-" * 40)

if __name__ == '__main__':
    # Parse args
    target = 'BIG_LOTTO'
    if len(sys.argv) > 1:
        target = sys.argv[1]
    
    run_generation(target)
