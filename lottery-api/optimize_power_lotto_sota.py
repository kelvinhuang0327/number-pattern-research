#!/usr/bin/env python3
"""
SOTA Power Lotto Success Rate Optimizer
Uses Genetic Algorithms to find the most accurate ensemble weights for Power Lotto.
"""
import sys
import os
import json
import logging
import numpy as np
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import create_optimized_ensemble_predictor
from models.genetic_optimizer import GeneticWeightOptimizer
from common import get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    lottery_type = 'POWER_LOTTO'
    rules = get_lottery_rules(lottery_type)
    today_date = '2025/12/21' # Fixed date for reproducible testing if needed
    
    # Fix database path
    import os
    db_path = os.path.join(os.getcwd(), 'lottery-api', 'data', 'lottery_v2.db')
    if os.path.exists(db_path):
        db_manager.db_path = db_path
        logger.info(f"DEBUG: Updated DB path to {db_path}")
    
    all_draws = db_manager.get_all_draws(lottery_type)
    
    if not all_draws or len(all_draws) < 100:
        logger.error(f"❌ Insufficient data for optimization. Found {len(all_draws) if all_draws else 0}")
        return

    logger.info("=" * 80)
    logger.info(f"🧬 SOTA POWER LOTTO OPTIMIZER")
    logger.info(f"Targeting: Overall Success Rate Improvement")
    logger.info(f"Data: {len(all_draws)} historical draws")
    logger.info("=" * 80)

    ensemble = create_optimized_ensemble_predictor(prediction_engine)
    strategies = list(ensemble.strategy_methods.keys())
    
    # We want to optimize over a recent window to capture current trends
    # but large enough to be statistically significant
    optimization_window = 100 
    validation_window = 50
    
    # Fitness Function: Focus on match count and win rate for Match 2+ or 3+
    def fitness_fn(weights: dict) -> float:
        total_score = 0
        tests = 30 # Number of rolling tests for fitness evaluation
        
        for i in range(tests):
            test_idx = validation_window + i
            train_data = all_draws[test_idx + 1 : test_idx + 1 + 150]
            actual = set(all_draws[test_idx]['numbers'])
            actual_special = all_draws[test_idx].get('special')
            
            # Simple weighted sum prediction for speed during optimization
            number_scores = {}
            for name, method in ensemble.strategy_methods.items():
                try:
                    res = method(train_data, rules)
                    w = weights.get(name, 0)
                    for num in res['numbers']:
                        number_scores[num] = number_scores.get(num, 0) + w
                except:
                    continue
            
            if not number_scores: continue
            
            # Take top 6
            top_nums = sorted(number_scores.keys(), key=lambda x: number_scores[x], reverse=True)[:6]
            matches = len(set(top_nums) & actual)
            
            # Scoring logic: 
            # Match 0-1: 0 points
            # Match 2: 1 point
            # Match 3: 5 points
            # Match 4+: 20 points
            if matches == 2: total_score += 1
            elif matches == 3: total_score += 5
            elif matches >= 4: total_score += 20
            
        return total_score / tests

    logger.info(f"Running Genetic Algorithm with {len(strategies)} strategies...")
    optimizer = GeneticWeightOptimizer(strategies, population_size=15, generations=5)
    best_weights = optimizer.optimize(fitness_fn)
    
    logger.info("\n🏆 OPTIMIZATION COMPLETE")
    logger.info("-" * 40)
    for name, weight in sorted(best_weights.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {name:20s}: {weight:.1%}")
    logger.info("-" * 40)
    
    # Save results
    result_path = os.path.join("data", "power_lotto_optimized_weights.json")
    os.makedirs("data", exist_ok=True)
    
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({
            "lottery_type": lottery_type,
            "optimized_at": datetime.now().isoformat(),
            "weights": best_weights,
            "sample_size": len(all_draws)
        }, f, indent=2, ensure_ascii=False)
        
    logger.info(f"✅ Optimized weights saved to {result_path}")

if __name__ == "__main__":
    main()
