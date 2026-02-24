
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.config_loader import PredictionConfig
from lottery_api.database import DatabaseManager
from lottery_api.utils.backtest_safety import (
    validate_chronological_order, 
    get_safe_backtest_slice, 
    isolate_mab_state, 
    cleanup_backtest_state
)

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Phase2Performance')

class NpEncoder(json.JSONEncoder):
    """Fix for int64 JSON serialization error"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)

class Phase2PerformanceTester:
    def __init__(self, lottery_type: str = 'BIG_LOTTO'):
        self.db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        self.db = DatabaseManager(db_path=self.db_path)
        self.lottery_type = lottery_type
        
        # Load and validate chronological order
        raw_history = self.db.get_all_draws(lottery_type)
        self.history = validate_chronological_order(raw_history, lottery_type)
            
        # Standard Rules
        if lottery_type == 'BIG_LOTTO':
            self.rules = {
                'name': 'BIG_LOTTO',
                'pickCount': 6,
                'minNumber': 1,
                'maxNumber': 49,
                'hasSpecialNumber': True 
            }
        elif lottery_type == 'POWER_LOTTO':
            self.rules = {
                'name': 'POWER_LOTTO',
                'pickCount': 6,
                'minNumber': 1,
                'maxNumber': 38,
                'hasSpecialNumber': True,
                'specialMaxNumber': 8
            }
        else:
            # Fallback
            from lottery_api.common import get_lottery_rules
            self.rules = get_lottery_rules(lottery_type)

    def run_backtest(self, test_periods: int = 50, offset: int = 0, use_mab: bool = True, use_anomaly: bool = True):
        """運行回測"""
        if len(self.history) < test_periods + 10:
             logger.warning(f"Not enough data for {self.lottery_type}. History size: {len(self.history)}")
             return None

        start_date = self.history[-test_periods]['date']
        end_date = self.history[-1]['date']
        logger.info(f"📅 Test Range ({self.lottery_type}): {start_date} ~ {end_date} (Last {test_periods} draws)")
        logger.info(f"🚀 Starting Backtest: Periods={test_periods}, MAB={use_mab}, Anomaly={use_anomaly}")
        
        # Use lottery-specific MAB state
        state_dir = os.path.join(project_root, 'data')
        os.makedirs(state_dir, exist_ok=True)
        state_path = os.path.join(state_dir, f'mab_state_{self.lottery_type.lower()}.json')
        
        # Safety: Use isolated MAB state to prevent cross-run leakage
        temp_state_path = isolate_mab_state(optimizer.engine, self.lottery_type)
        
        # Initialize Optimizer
        optimizer = MultiBetOptimizer()
        
        # MAB reset already handled by isolate_mab_state

        # Split data
        if offset > 0:
            train_data = self.history[:-(test_periods + offset)]
            test_data = self.history[-(test_periods + offset):-offset]
            start_date = test_data[0]['date']
            end_date = test_data[-1]['date']
            logger.info(f"📅 Test Range ({self.lottery_type}): {start_date} ~ {end_date} (Offset {offset}, Size {test_periods})")
        else:
            train_data = self.history[:-test_periods]
            test_data = self.history[-test_periods:]
            start_date = test_data[0]['date']
            end_date = test_data[-1]['date']
            logger.info(f"📅 Test Range ({self.lottery_type}): {start_date} ~ {end_date} (Last {test_periods} draws)")
        
        results = []
        total_hits = 0
        match3_plus_hits = 0
        total_bets = 0
        
        start_time = datetime.now()
        
        for i, target_draw in enumerate(test_data):
            # Combined training data + recent test data slice
            target_idx = self.history.index(target_draw)
            current_history = get_safe_backtest_slice(self.history, target_idx)
            
            try:
                # Use 7-Bet Strategy or custom if needed
                num_bets = 7 if self.lottery_type == 'BIG_LOTTO' else 4 # As per action plan
                bet_result = optimizer.generate_diversified_bets(
                    current_history, 
                    self.rules, 
                    num_bets=num_bets
                )
                
                actual_numbers = set(target_draw['numbers'])
                bets = bet_result['bets']
                
                period_hits = 0
                max_hit = 0
                
                for bet in bets:
                    pred_nums = set(bet['numbers'])
                    hits = len(pred_nums & actual_numbers)
                    
                    if hits > max_hit:
                        max_hit = hits
                    
                    if hits >= 3:
                        match3_plus_hits += 1
                    
                    total_hits += hits
                    total_bets += 1
                
                results.append({
                    'draw': target_draw['draw'],
                    'max_hit': max_hit,
                    'bet_count': len(bets),
                    'strategies': [b.get('group', 'unknown') for b in bets]
                })
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i+1}/{test_periods} | Last Max Hit: {max_hit}")

                # MAB Learning
                if use_mab and hasattr(optimizer.engine, 'mab_predictor') and optimizer.engine.mab_predictor:
                     mab = optimizer.engine.mab_predictor
                     mab_result = mab.predict(current_history, self.rules)
                     if 'metadata' in mab_result and 'strategy_predictions' in mab_result['metadata']:
                         strategy_preds = mab_result['metadata']['strategy_predictions']
                         mab.update_with_result(strategy_preds, list(actual_numbers))
                         if (i + 1) % 10 == 0:
                             stats = mab.mab.get_statistics()
                             logger.info(f"MAB [{self.lottery_type}] Update: {stats['total_predictions']} rounds trained")

            except Exception as e:
                logger.error(f"Error processing {self.lottery_type} draw {target_draw['draw']}: {e}")
        
        duration = datetime.now() - start_time
        avg_hits = total_hits / total_bets if total_bets > 0 else 0
        match3_rate = match3_plus_hits / total_bets if total_bets > 0 else 0
        win_rate_per_period = len([r for r in results if r['max_hit'] >= 3]) / len(results) if results else 0
        
        logger.info("-" * 50)
        logger.info(f"📊 {self.lottery_type} Results (MAB={use_mab}, Anomaly={use_anomaly})")
        logger.info(f"Periods: {test_periods} | Total Bets: {total_bets}")
        logger.info(f"Match-3+ Hits: {match3_plus_hits} | Rate: {match3_rate:.2%}")
        logger.info(f"Win Rate (Per Period): {win_rate_per_period:.2%}")
        logger.info(f"Avg Hits: {avg_hits:.4f}")
        logger.info("-" * 50)
        
        # Cleanup safety context
        cleanup_backtest_state(temp_state_path)

        return {
            'lottery_type': self.lottery_type,
            'config': {'periods': test_periods, 'mab': use_mab, 'anomaly': use_anomaly},
            'metrics': {
                'match3_rate': match3_rate,
                'win_rate_period': win_rate_per_period,
                'avg_hits': avg_hits,
                'total_match3': match3_plus_hits
            },
            'details': results
        }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', type=str, default='BIG_LOTTO', help='BIG_LOTTO or POWER_LOTTO')
    parser.add_argument('--periods', type=int, default=50)
    parser.add_argument('--offset', type=int, default=0, help='Offset from the most recent draw')
    args = parser.parse_args()
    
    tester = Phase2PerformanceTester(lottery_type=args.type)
    results = tester.run_backtest(test_periods=args.periods, offset=args.offset, use_mab=True, use_anomaly=True)
    
    if results:
        report = {
            'timestamp': datetime.now().isoformat(),
            'results': results
        }
        filename = f'phase2_performance_{args.type.lower()}.json'
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, cls=NpEncoder)
        print(f"✅ Report saved to {filename}")
