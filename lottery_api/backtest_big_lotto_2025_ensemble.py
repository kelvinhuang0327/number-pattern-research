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
from common import get_lottery_rules

# Disable detailed logging
logging.getLogger().setLevel(logging.ERROR)

def calculate_matches(predicted: List[int], actual: List[int]) -> int:
    return len(set(predicted) & set(actual))

# Optimized Ensemble with fixed weights to speed up backtest simulation
class FastOptimizedPredictor(OptimizedEnsemblePredictor):
    def calculate_strategy_weights(self, history, lottery_rules, **kwargs):
        # Directly use the recommended weights for the specific lottery
        lottery_name = lottery_rules.get('name', 'DEFAULT')
        if '威力彩' in lottery_name or 'POWER' in lottery_name:
            return self.RECOMMENDED_WEIGHTS.get('POWER_LOTTO')
        elif '大樂透' in lottery_name or 'BIG' in lottery_name:
            return self.RECOMMENDED_WEIGHTS.get('BIG_LOTTO')
        return self.RECOMMENDED_WEIGHTS.get('DEFAULT')

def main():
    lottery_type = 'BIG_LOTTO'
    engine = UnifiedPredictionEngine()
    lottery_rules = get_lottery_rules(lottery_type)
    
    # Load all draws
    all_draws = db_manager.get_all_draws(lottery_type)
    # Sort by date ascending for rolling backtest
    all_draws.sort(key=lambda x: x['date'])
    
    # Filter for 2025 draws (last 20 for speed)
    draws_2025 = [d for d in all_draws if '2025' in str(d.get('date', ''))][-20:]
    
    if not draws_2025:
        print("❌ 未找到 2025 年大樂透數據")
        return

    print("=" * 100)
    print(f"📊 BIG_LOTTO ROLLING BACKTEST: 2025 ENSEMBLE SIMULATION")
    print(f"Total draws to test: {len(draws_2025)}")
    print("Strategy: Optimized Ensemble (Top 2 Bets, Fixed Weights)")
    print("=" * 100)
    print(f"{'Draw':<12} | {'Actual':<25} | {'Bet 1':<25} | {'M1':<2} | {'Bet 2':<25} | {'M2':<2}")
    print("-" * 120)

    stats = {
        'total_draws': 0,
        'matches_b1': [],
        'matches_b2': [],
        'wins_b1': 0, # Match 3+
        'wins_b2': 0,
        'combined_wins': 0 # Either bet 1 or bet 2 wins
    }
    
    ensemble = FastOptimizedPredictor(engine)

    for target_draw in draws_2025:
        draw_id = target_draw['draw']
        
        # Find index in all_draws
        target_idx = -1
        for i, d in enumerate(all_draws):
            if d['draw'] == draw_id:
                target_idx = i
                break
        
        if target_idx == -1: continue
            
        # History is everything BEFORE target_idx (since all_draws is sorted ASC)
        # OptimizedEnsemble usually expects history in DESC order (newest first)
        history = all_draws[:target_idx]
        history.sort(key=lambda x: x['date'], reverse=True)
        
        if len(history) < 100: continue
            
        try:
            # Use 5 periods for faster backtest in simulation
            res = ensemble.predict(history, lottery_rules, backtest_periods=5)
            
            b1 = res['bet1']['numbers']
            b2 = res['bet2']['numbers']
            actual = target_draw['numbers']
            
            m1 = calculate_matches(b1, actual)
            m2 = calculate_matches(b2, actual)
            
            stats['total_draws'] += 1
            stats['matches_b1'].append(m1)
            stats['matches_b2'].append(m2)
            
            if m1 >= 3: stats['wins_b1'] += 1
            if m2 >= 3: stats['wins_b2'] += 1
            if m1 >= 3 or m2 >= 3: stats['combined_wins'] += 1
            
            # Print row
            actual_str = ",".join(map(str, sorted(actual)))
            b1_str = ",".join(map(str, sorted(b1)))
            b2_str = ",".join(map(str, sorted(b2)))
            
            print(f"{draw_id:<12} | {actual_str:<25} | {b1_str:<25} | {m1:<2} | {b2_str:<25} | {m2:<2}")
            
        except Exception as e:
            # print(f"Error drawing {draw_id}: {e}")
            continue

    if stats['total_draws'] == 0:
        print("沒有成功測試任何期數。")
        return

    print("-" * 120)
    print(f"📈 BACKTEST SUMMARY (2025 BIG LOTTO)")
    print("-" * 120)
    n = stats['total_draws']
    avg1 = sum(stats['matches_b1']) / n
    avg2 = sum(stats['matches_b2']) / n
    rate1 = stats['wins_b1'] / n
    rate2 = stats['wins_b2'] / n
    comb_rate = stats['combined_wins'] / n
    
    print(f"Total Tested: {n} draws")
    print(f"Bet 1: Avg Matches: {avg1:.2f} | Win Rate (3+): {rate1:7.2%}")
    print(f"Bet 2: Avg Matches: {avg2:.2f} | Win Rate (3+): {rate2:7.2%}")
    print(f"Combined (Dual Bet) Win Rate: {comb_rate:7.2%}")
    print("=" * 120)

if __name__ == '__main__':
    main()
