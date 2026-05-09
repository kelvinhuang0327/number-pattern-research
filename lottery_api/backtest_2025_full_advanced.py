#!/usr/bin/env python3
"""
Full 2025 Rolling Backtest - Big Lotto (Advanced Engine)
Evaluates the performance of the AdvancedAutoLearningEngine across all 2025 draws.
"""
import sys
import os
import logging
import json
import itertools
from collections import defaultdict
from typing import List, Dict
import numpy as np

# Setup path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.advanced_auto_learning import AdvancedAutoLearningEngine
from common import load_backend_history, get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)

def calculate_match_prize(predicted, actual, actual_special):
    """Calculate match metrics for Big Lotto"""
    pred_set = set(predicted)
    actual_set = set(actual)
    
    match_count = len(pred_set.intersection(actual_set))
    has_special = actual_special in pred_set
    
    # Win if Match >= 3 OR (Match == 2 AND Special)
    is_win = (match_count >= 3) or (match_count == 2 and has_special)
    
    prize_name = ""
    if match_count == 6: prize_name = "頭獎 (6)"
    elif match_count == 5 and has_special: prize_name = "貳獎 (5+S)"
    elif match_count == 5: prize_name = "參獎 (5)"
    elif match_count == 4 and has_special: prize_name = "肆獎 (4+S)"
    elif match_count == 4: prize_name = "伍獎 (4)"
    elif match_count == 3 and has_special: prize_name = "陸獎 (3+S)"
    elif match_count == 2 and has_special: prize_name = "七獎 (2+S)"
    elif match_count == 3: prize_name = "普獎 (3)"
        
    return match_count, has_special, is_win, prize_name

class FullBacktester:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.rules = get_lottery_rules(lottery_type)
        self.engine = AdvancedAutoLearningEngine()
        self.stats = {
            'draws': 0,
            'total_bets': 0,
            'total_wins': 0,
            'matches_accum': 0,
            'max_match': 0,
            'best_prize': '',
            'prize_counts': defaultdict(int)
        }
        
    def _get_best_config(self):
        """Get the latest best configuration from history"""
        history = self.engine.get_optimization_history()
        if not history:
            return None
        return history[-1]['config']

    def _generate_dual_bets(self, config, history, rules):
        """
        Generate 2 bets (Dual Bet) using the learned config.
        """
        # We can take the absolute top 2 combinations from the predicted pool
        temp_rules = rules.copy()
        temp_rules['pickCount'] = 10
        
        pool = self.engine._predict_with_config(
            config, history, 
            temp_rules['pickCount'], temp_rules['minNumber'], temp_rules['maxNumber']
        )
        
        if len(pool) < 6: return []
        
        combs = list(itertools.combinations(pool, rules['pickCount']))
        return [list(c) for c in combs[:2]]

    def run(self):
        print("=" * 80)
        print(f"🚀 FULL 2025 ROLLING BACKTEST (Dual Bet / 2 Bets): {self.lottery_type}")
        print("=" * 80)
        
        # 1. Load All Data
        all_draws = db_manager.get_all_draws(self.lottery_type)
        all_draws.sort(key=lambda x: x['date'])
        
        # 2. Split into Pre-2025 and 2025
        train_data = [d for d in all_draws if '2025' not in str(d['date'])]
        test_data = [d for d in all_draws if '2025' in str(d['date'])]
        
        if not test_data:
            print("❌ No 2025 data found!")
            return

        # 3. Get Optimal Config
        config = self._get_best_config()
        if not config:
            print("❌ No optimized config found. Please run optimization first.")
            return

        print(f"📚 Pre-2025 History: {len(train_data)} draws")
        print(f"🧪 2025 Test Pool: {len(test_data)} draws")
        print("-" * 80)
        print(f"{'Draw':<10} | {'Date':<10} | {'Actual':<20} | {'Bet 1':<20} | {'M1':<2} | {'Bet 2':<20} | {'M2':<2} | {'Win'}")
        print("-" * 80)

        # 4. Rolling Loop
        for i, target in enumerate(test_data):
            rolling_history = train_data + test_data[:i]
            rolling_history.sort(key=lambda x: x['date'], reverse=True)
            
            # Predict 2 bets (Dual Bet)
            bets = self._generate_dual_bets(config, rolling_history, self.rules)
            if not bets: continue
            
            actual_nums = set(target['numbers'])
            actual_special = int(target['special']) if target.get('special') else -1
            
            matches = []
            won_this_draw = False
            
            self.stats['draws'] += 1
            self.stats['total_bets'] += len(bets)
            
            for bet in bets:
                m_cnt, h_sp, won, prize = calculate_match_prize(bet, actual_nums, actual_special)
                matches.append(m_cnt)
                self.stats['matches_accum'] += m_cnt
                
                if won:
                    won_this_draw = True
                    self.stats['total_wins'] += 1
                    self.stats['prize_counts'][prize] += 1
                    if m_cnt > self.stats['max_match']:
                        self.stats['max_match'] = m_cnt
                        self.stats['best_prize'] = prize
            
            # Print row
            actual_str = ",".join(f"{n:02d}" for n in sorted(list(actual_nums)))
            b1_str = ",".join(f"{n:02d}" for n in sorted(bets[0]))
            b2_str = ",".join(f"{n:02d}" for n in sorted(bets[1])) if len(bets) > 1 else ""
            win_mark = "✅" if won_this_draw else ""
            print(f"{target['draw']:<10} | {target['date']:<10} | {actual_str:<20} | {b1_str:<20} | {matches[0]:<2} | {b2_str:<20} | {matches[1]:<2} | {win_mark}")

        self._print_summary()

    def _print_summary(self):
        n = self.stats['draws']
        total_bets = self.stats['total_bets']
        total_wins = self.stats['total_wins']
        
        if total_bets == 0: return

        print("-" * 80)
        print(f"📈 2025 BACKTEST SUMMARY")
        print("-" * 80)
        print(f"Total Draws Tested: {n}")
        print(f"Total Bets Placed: {total_bets} (8 per draw)")
        print(f"Total Winning Bets: {total_wins}")
        print(f"Overall Win Rate (Match 3+): {total_wins / total_bets:.2%}")
        print(f"Average Match Count: {self.stats['matches_accum'] / total_bets:.2f}")
        print(f"Max Matches in 2025: {self.stats['max_match']}")
        print(f"Best Prize Found: {self.stats['best_prize']}")
        print("-" * 80)
        print("Prize Breakdown:")
        for prize, count in sorted(self.stats['prize_counts'].items()):
            print(f"  - {prize}: {count}")
        print("=" * 80)

if __name__ == '__main__':
    tester = FullBacktester('BIG_LOTTO')
    tester.run()
