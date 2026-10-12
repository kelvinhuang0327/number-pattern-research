#!/usr/bin/env python3
"""
Evaluate Success Rate of Buying 6 Bets Strategy for Big Lotto
"""
import sys
import os
import logging
from collections import defaultdict
import asyncio

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from common import get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def check_win(predicted_numbers: list, predicted_special: int, 
              actual_numbers: list, actual_special: int) -> bool:
    """
    Check if a single bet wins any prize in Big Lotto.
    Rules:
    - 3+ matches: Win (Pul Prize or higher)
    - 2 matches + Special: Win (7th Prize)
    """
    pred_set = set(predicted_numbers)
    actual_set = set(actual_numbers)
    
    matches = len(pred_set & actual_set)
    special_match = (predicted_special is not None) and (predicted_special == actual_special)
    
    # Check for Special match in normal numbers (in some variations) - 
    # but standard Big Lotto: Special number is separate.
    # Actually, in Big Lotto, you select 6 numbers. The special number is drawn from the remaining.
    # Your bet only has 6 numbers. You win if your 6 numbers match the draw's 6 numbers or special.
    # Wait, the bet has 6 numbers. The result has 6 normal + 1 special.
    # Matching N means matching N of the 6 normal numbers.
    # Matching Special means one of your 6 numbers matches the Special number?
    # No, usually "Special Number" is a separate thing in some lotteries, but in 6/49 Big Lotto:
    # Build a bet: You pick 6 numbers (1-49).
    # Draw: 6 Normal + 1 Special.
    # Prizes:
    # - 3 Normal: Win
    # - 2 Normal + Match Special (One of your remaining 4 numbers matches the special? Or does the special number have to be in your 6?)
    # YES, one of your 6 numbers matches the special number.
    # AND 2 of your other numbers match the normal numbers.
    
    # So:
    # 1. Count how many of my 6 numbers appear in the 6 Normal Result Numbers. (matches)
    # 2. Check if any of my 6 numbers equal the Special Result Number. (has_special)
    
    # Re-evaluating logic with this understanding:
    has_special = actual_special in pred_set
    
    if matches >= 3:
        return True
    if matches == 2 and has_special:
        return True
        
    return False

async def run_simulation():
    print("=" * 80)
    print("🚀 Big Lotto 6-Bet Strategy Success Rate Simulation")
    print("=" * 80)

    # 1. Fetch History
    lottery_type = 'BIG_LOTTO'
    all_draws = db_manager.get_all_draws(lottery_type)
    
    if not all_draws or len(all_draws) < 50:
        print(f"❌ Insufficient data. Need at least 50 draws, found {len(all_draws) if all_draws else 0}")
        return

    # 2. Setup Test Range
    # We will test on the last 50 draws (or max available - window)
    test_count = 50
    if len(all_draws) - 100 < test_count: # Ensure we have at least 100 draws for training
        test_count = max(0, len(all_draws) - 100)
    
    if test_count == 0:
        print("❌ Not enough history for valid training window.")
        return
        
    test_data = all_draws[:test_count] # Last N draws
    
    print(f"📊 Simulating last {test_count} draws...")
    print(f"   Training Window: Rolling (All history prior to target draw)")
    
    lottery_rules = get_lottery_rules(lottery_type)
    optimized_predictor = OptimizedEnsemblePredictor(prediction_engine)
    
    wins = 0
    total_spent = 0
    total_winnings = 0 # Rough estimate? Maybe just win rate is enough.
    
    # Prize amounts (Est.)
    prize_map = {
        "3_match": 400,
        "2_plus_s": 400
    }
    
    # Patch OptimizedEnsemblePredictor to use fixed weights for speed
    class FastOptimizedPredictor(OptimizedEnsemblePredictor):
        def calculate_strategy_weights(self, history, lottery_rules, backtest_periods=50, training_window=100):
            # Bypass expensive backtest, return fixed recommended weights
            return self.RECOMMENDED_WEIGHTS

    optimized_predictor = FastOptimizedPredictor(prediction_engine)
    
    for i in range(test_count):
        target_draw = all_draws[i] # Current target
        # History is everything AFTER i (since 0 is latest)
        training_history = all_draws[i+1:]
        
        # Skip if history too small
        if len(training_history) < 50:
            continue
            
        target_numbers = target_draw['numbers']
        target_special = int(target_draw['special']) if target_draw.get('special') else 0
        
        # Generate 6 Bets
        bets = []
        
        # 1. Frequency
        try:
            res = prediction_engine.frequency_predict(training_history, lottery_rules)
            bets.append(res['numbers'])
        except: pass
        
        # 2. Trend
        try:
            res = prediction_engine.trend_predict(training_history, lottery_rules)
            bets.append(res['numbers'])
        except: pass
        
        # 3. Bayesian
        try:
            res = prediction_engine.bayesian_predict(training_history, lottery_rules)
            bets.append(res['numbers'])
        except: pass
        
        # 4. Monte Carlo
        try:
            res = prediction_engine.monte_carlo_predict(training_history, lottery_rules)
            bets.append(res['numbers'])
        except: pass
        
        # 5 & 6. Optimized Ensemble (Fast)
        try:
            res = optimized_predictor.predict(training_history, lottery_rules)
            bets.append(res['bet1']['numbers'])
            bets.append(res['bet2']['numbers'])
        except Exception as e: 
            # logger.error(f"Ensemble failed: {e}")
            pass
        
        # Check Win
        round_win = False
        round_prizes = []
        
        for bet in bets:
            # Check bet
            matches = len(set(bet) & set(target_numbers))
            has_special = target_special in set(bet)
            
            is_win = False
            prize_val = 0
            
            if matches >= 3:
                is_win = True
                prize_val = 400 # Min prize
            
            # Big Lotto 7th prize: 2 normal + special
            # Actually checking official rules on Taiwan Lottery:
            # 普獎 (Prize 7): 3 numbers match.
            # 柒獎 (Prize 8?): 2 numbers + special.
            # wait, let's verify.
            # Official rules:
            # 普獎: Match 3.
            # 柒獎: Match 2 + Special.
            # Both represent a "Win".
            
            if matches >= 3:
                rounds_won = True
                is_win = True
            elif matches == 2 and has_special:
                is_win = True
            
            if is_win:
                round_win = True
                round_prizes.append(1)
        
        if round_win:
            wins += 1
            print(f"   Draw {target_draw['date']} (Draw {target_draw['draw']}): 🎉 WIN! Prizes: {len(round_prizes)}")
        else:
            # print(f"   Draw {target_draw.get('date')} (Draw {target_draw.get('draw')}): ❌ Loss")
            pass
            
    print("-" * 80)
    print(f"🏆 SIMULATION RESULTS ({test_count} Draws)")
    print(f"   Success Rate: {wins}/{test_count} ({wins/test_count:.2%})")
    print("-" * 80)

if __name__ == '__main__':
    asyncio.run(run_simulation())
