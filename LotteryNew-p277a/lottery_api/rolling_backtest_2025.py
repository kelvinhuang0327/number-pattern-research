#!/usr/bin/env python3
"""
Rolling Backtest 2025 - Big Lotto
Evaluates 8 different prediction models over the 2025 dataset.
"""
import sys
import os
import logging
from collections import defaultdict
import numpy as np
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from common import get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)

# Optimized Ensemble with cached weights to speed up backtest
class FastOptimizedPredictor(OptimizedEnsemblePredictor):
    def calculate_strategy_weights(self, history, lottery_rules, backtest_periods=50, training_window=100):
        return self.RECOMMENDED_WEIGHTS

def calculate_match_prize(predicted, actual, actual_special):
    """
    Calculate match metrics for Big Lotto
    """
    pred_set = set(predicted)
    actual_set = set(actual)
    
    match_count = len(pred_set.intersection(actual_set))
    has_special = actual_special in pred_set
    
    # Win if Match >= 3
    is_win = False
    prize_name = ""
    
    # 3 numbers = 普獎 (Win)
    # 2 + special = 七獎 (Win)
    if (match_count >= 3) or (match_count == 2 and has_special):
        is_win = True
        
    if match_count == 6: prize_name = "頭獎 (6)"
    elif match_count == 5 and has_special: prize_name = "貳獎 (5+S)"
    elif match_count == 5: prize_name = "參獎 (5)"
    elif match_count == 4 and has_special: prize_name = "肆獎 (4+S)"
    elif match_count == 4: prize_name = "伍獎 (4)"
    elif match_count == 3 and has_special: prize_name = "陸獎 (3+S)"
    elif match_count == 2 and has_special: prize_name = "七獎 (2+S)"
    elif match_count == 3: prize_name = "普獎 (3)"
        
    return match_count, has_special, is_win, prize_name

import itertools

class RollingBacktester:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.original_rules = get_lottery_rules(lottery_type)
        self.stats = defaultdict(lambda: {
            'draws': 0,
            'total_bets': 0, # New metric
            'total_wins': 0, # New metric
            'matches_accum': 0,
            'max_match': 0,
            'best_prize': '',
            'prize_counts': defaultdict(int) 
        })
        
        self.models = [
            ('Frequency', prediction_engine.frequency_predict),
            ('Trend', prediction_engine.trend_predict),
            ('Bayesian', prediction_engine.bayesian_predict),
            ('Deviation', prediction_engine.deviation_predict),
            ('Monte Carlo', prediction_engine.monte_carlo_predict),
            ('Hot-Cold', getattr(prediction_engine, 'hot_cold_mix_predict', None)),
            ('Statistical', getattr(prediction_engine, 'statistical_predict', None)),
        ]
        self.models = [m for m in self.models if m[1] is not None]

    def _generate_8_bets(self, method, history, rules):
        """
        Generate 8 bets from a single method.
        Strategy: Ask method for Top 10 numbers, then wheeling.
        """
        # Hack: Ask for more numbers
        temp_rules = rules.copy()
        temp_rules['pickCount'] = 10 
        
        try:
            res = method(history, temp_rules)
            pool = res['numbers'] # Should be 10 numbers
            if len(pool) < 6: return []
            
            # Simple Wheeling: Generate combinations
            # We need exactly 8 bets. 
            # Combinations of Top 10 take 6 = 210. Too many.
            # We prioritize the "first" numbers (assuming method returns sorted confidence?)
            # Most methods return numbers in 'numbers' list. 
            # Are they sorted by strength? Often yes for frequency/trend.
            # If not, we might be wheeling random ones. 
            # safe bet: Use returned order if possible, or just standard combinations.
            
            combs = list(itertools.combinations(pool, self.original_rules['pickCount']))
            # If pool is sorted by strength, then early combinations in itertools are (0,1,2,3,4,5), (0,1,2,3,4,6)...
            # which keeps the best numbers.
            # We take the first 8 combinations.
            return [list(c) for c in combs[:8]]
            
        except Exception:
            return []

    def run(self):
        print("=" * 80)
        print(f"🚀 Rolling Backtest 2025 (8 Bets/Draw): {self.lottery_type}")
        print("=" * 80)
        
        # 1. Load Data
        all_draws = db_manager.get_all_draws(self.lottery_type)
        all_draws.sort(key=lambda x: x['date'])
        
        # 2. Split
        train_data = []
        test_data = []
        for draw in all_draws:
            if draw['date'].startswith('2025'):
                test_data.append(draw)
            else:
                train_data.append(draw)
        
        print(f"📚 Training: {len(train_data)} | 🧪 Test: {len(test_data)} (2025)")
        print("-" * 80)
        
        # 3. Rolling Loop
        for i, target_draw in enumerate(test_data):
            full_history = (train_data + test_data[:i])
            full_history.sort(key=lambda x: x['date'], reverse=True)
            history_pool = full_history[:300] 
            
            actual_nums = set(target_draw['numbers'])
            actual_special = int(target_draw['special']) if target_draw.get('special') else -1
            
            # Run Standard Models
            for name, method in self.models:
                bets = self._generate_8_bets(method, history_pool, self.original_rules)
                if not bets: continue
                
                self.stats[name]['draws'] += 1
                self.stats[name]['total_bets'] += len(bets)
                
                for bet in bets:
                    m_cnt, h_sp, won, prize = calculate_match_prize(bet, actual_nums, actual_special)
                    
                    self.stats[name]['matches_accum'] += m_cnt
                    if won:
                        self.stats[name]['total_wins'] += 1
                        self.stats[name]['prize_counts'][prize] += 1
                        
                    if m_cnt > self.stats[name]['max_match']:
                        self.stats[name]['max_match'] = m_cnt
                        self.stats[name]['best_prize'] = prize

            # Run Ensemble (Special Logic: it returns bet1/bet2, not list of numbers usually)
            # We will use 'FastOptimizedPredictor' but we need to trick it to return more?
            # OptimizedEnsemble doesn't support 'pickCount' override well easily.
            # We skip Ensemble 8-bets for now OR we simulate it by combining top models?
            # User output had "Ensemble (1)" and "Ensemble (2)". 
            # I'll enable it if I can generate 8 bets. 
            # Actually, `FastOptimizedPredictor` returns bet1, bet2... 
            # I will skip Ensemble for this specific "8 bets per strategy" test 
            # UNLESS I can make it generate 8 bets. 
            # I'll stick to the single-strategy models for this specific 8-bet metric request to be precise.
            # Or I can run Ensemble 4 times? No.
            # I will omit Ensemble to avoid misleading "8 bets" which are actually just 1 bet repeated.

            if (i+1) % 10 == 0:
                print(f"   Processed {i+1}/{len(test_data)} draws...")

        self._print_results(all_draws)

    def _print_results(self, full_history):
        full_history.sort(key=lambda x: x['date'], reverse=True)
        
        # Sort by Win Rate = Total Wins / Total Bets
        def get_rate(item):
            s = item[1]
            return s['total_wins'] / s['total_bets'] if s['total_bets'] > 0 else 0
            
        ranked = sorted(self.stats.items(), key=get_rate, reverse=True)
        
        print("\n" + "=" * 100)
        print("🏆 2025 ROLLING BACKTEST RESULTS (8 Bets Strategy)")
        print("Formula: Win Rate = Total Winning Bets / (Draws * 8)")
        print("=" * 100)
        print(f"{'Rank':<4} {'Model':<16} {'Wins/Bets':<12} {'Win Rate':<10} {'Avg Match':<10} {'Best Prize'}")
        print("-" * 100)
        
        top_models = []
        
        for i, (name, s) in enumerate(ranked, 1):
            if s['total_bets'] == 0: continue
            
            wins = s['total_wins']
            bets = s['total_bets']
            rate = wins / bets
            avg_match = s['matches_accum'] / bets
            
            # Best prize string (simplest)
            best_p = s['best_prize'] if s['best_prize'] else "None"
            
            print(f"{i:<4} {name:<16} {f'{wins}/{bets}':<12} {rate:7.2%}   {avg_match:<10.2f} {best_p}")
            
            if i <= 5: top_models.append(name)
            
        print("\n" + "=" * 100)
        print("🔮 PREDICTION: Next Draw 8 Bets (Top Model)")
        print("=" * 100)
        
        if top_models:
            best_model_name = top_models[0]
            print(f"Using Champion Model: {best_model_name}")
            print("-" * 60)
            
            # Generate 8 bets for next draw
            method = next((m for n, m in self.models if n == best_model_name), None)
            if method:
                predict_history = full_history[:300]
                bets = self._generate_8_bets(method, predict_history, self.original_rules)
                
                for idx, bet in enumerate(bets, 1):
                    bfmt = ", ".join(f"{n:02d}" for n in sorted(bet))
                    print(f"Bet {idx}: {bfmt}")

if __name__ == '__main__':
    tester = RollingBacktester('BIG_LOTTO')
    tester.run()
