import os
import sys
import json
import logging
import numpy as np
from datetime import datetime
from collections import defaultdict

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from lottery_api.database import DatabaseManager
from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

# Suppress minor logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HyperparameterTuner:
    def __init__(self, lottery_type='BIG_LOTTO'):
        db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        self.db = DatabaseManager(db_path=db_path)
        self.lottery_type = lottery_type
        self.engine = UnifiedPredictionEngine()
        self.history = self.db.get_all_draws(lottery_type)
        if self.history and self.history[0]['date'] > self.history[-1]['date']:
            self.history = self.history[::-1]
            
        self.rules = {
            'name': lottery_type,
            'pickCount': 6,
            'minNumber': 1,
            'maxNumber': 49,
            'hasSpecialNumber': True
        }

    def evaluate_config(self, strategy_name, params, test_periods=50):
        """Evaluate a specific strategy with given parameters"""
        # Inject params into rules for the predictor to pick up
        eval_rules = self.rules.copy()
        if strategy_name == 'trend':
            eval_rules['trend_lambda'] = params.get('lambda')
        elif strategy_name == 'deviation':
            eval_rules['deviation_weights'] = params
        elif strategy_name == 'statistical':
            eval_rules['statistical_params'] = params
            
        predict_fn = getattr(self.engine, f"{strategy_name}_predict")
        
        match3_hits = 0
        total_bets = 0
        
        train_data = self.history[:-test_periods]
        test_data = self.history[-test_periods:]
        
        for i, target_draw in enumerate(test_data):
            current_history = train_data + test_data[:i]
            actual_numbers = set(target_draw['numbers'])
            
            # Use specific window if provided, else use default
            window = params.get('window', 300)
            sliced_history = current_history[-window:] if len(current_history) > window else current_history
            
            prediction = predict_fn(sliced_history, eval_rules)
            predicted_numbers = set(prediction.get('numbers', []))
            
            hits = len(predicted_numbers & actual_numbers)
            if hits >= 3:
                match3_hits += 1
            total_bets += 1
            
        win_rate = match3_hits / total_bets if total_bets > 0 else 0
        return win_rate

    def tune_trend(self):
        logger.info("🎯 Tuning Trend Predictor...")
        best_rate = -1
        best_lambda = None
        
        # Search space for lambda
        lambdas = [0.005, 0.01, 0.02, 0.05, 0.1, 0.2]
        
        for lb in lambdas:
            rate = self.evaluate_config('trend', {'lambda': lb})
            logger.info(f"  Lambda: {lb} -> Win Rate: {rate:.2%}")
            if rate > best_rate:
                best_rate = rate
                best_lambda = lb
        
        return {'lambda': best_lambda, 'win_rate': best_rate}

    def tune_deviation(self):
        logger.info("🎯 Tuning Deviation Predictor...")
        best_rate = -1
        best_weights = None
        
        # Test a few predefined weight profiles
        profiles = [
            {'frequency': 0.3, 'zone': 0.25, 'odd_even': 0.2, 'high_low': 0.15, 'gap': 0.1}, # Default
            {'frequency': 0.5, 'zone': 0.1, 'odd_even': 0.1, 'high_low': 0.1, 'gap': 0.2},  # Freq Focused
            {'frequency': 0.2, 'zone': 0.4, 'odd_even': 0.1, 'high_low': 0.1, 'gap': 0.2},  # Zone Focused
            {'frequency': 0.2, 'zone': 0.1, 'odd_even': 0.3, 'high_low': 0.3, 'gap': 0.1},  # Balance Focused
            {'frequency': 0.3, 'zone': 0.2, 'odd_even': 0.1, 'high_low': 0.1, 'gap': 0.3},  # Gap Focused
        ]
        
        for profile in profiles:
            rate = self.evaluate_config('deviation', profile)
            logger.info(f"  Weights: {profile} -> Win Rate: {rate:.2%}")
            if rate > best_rate:
                best_rate = rate
                best_weights = profile
                
        return {'weights': best_weights, 'win_rate': best_rate}

    def tune_statistical(self):
        logger.info("🎯 Tuning Statistical Predictor...")
        best_rate = -1
        best_params = None
        
        # Test variations of sum range and power
        mults = [0.4, 0.5, 0.6, 0.7]
        powers = [0.3, 0.5, 0.7, 1.0]
        
        for m in mults:
            for p in powers:
                params = {
                    'sum_range_mult': m,
                    'ac_min_mult': 0.15,
                    'ac_max_mult': 0.35,
                    'odd_tolerance': 2,
                    'spread_mult': 0.4,
                    'unique_last_digits_min': 4,
                    'weight_power': p
                }
                rate = self.evaluate_config('statistical', params)
                logger.info(f"  SumMult: {m}, Power: {p} -> Win Rate: {rate:.2%}")
                if rate > best_rate:
                    best_rate = rate
                    best_params = params
                    
        return {'params': best_params, 'win_rate': best_rate}

if __name__ == "__main__":
    tuner = HyperparameterTuner()
    
    results = {}
    results['trend'] = tuner.tune_trend()
    results['deviation'] = tuner.tune_deviation()
    results['statistical'] = tuner.tune_statistical()
    
    print("\n" + "="*50)
    print("🏆 PHASE 3: TUNING RESULTS")
    print("="*50)
    print(json.dumps(results, indent=2))
    
    with open('phase3_tuning_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\n✅ Results saved to phase3_tuning_results.json")
