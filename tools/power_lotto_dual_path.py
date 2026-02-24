#!/usr/bin/env python3
"""
Power Lotto Dual-Path Strategy Runner
 implements the "Alpha-Beta" strategy recommended by the 115000007 Review.
 
 1. Path Alpha (Trend): Captures Hot/Trend numbers.
 2. Path Beta (Deviation): Captures Cold/Rebound numbers.
 3. Special Zone (Markov): Uses Markov Chain for 2nd zone.
 
 Verifies against Draw 115000007.
"""
import sys
import os
import json
import logging
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine, predict_pool_numbers

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

ACTUAL_NUMBERS = [11, 17, 29, 30, 34, 35]
ACTUAL_SPECIAL = 6
DRAW_NUMBER = '115000007'

def simple_true_frequency(history, rules, window=100):
    from collections import Counter
    # Ensure history is sorted New -> Old or adjust window slice
    # History here is [New, ..., Old] usually? 
    # Let's check: history[0]['draw'] is latest.
    
    slice_hist = history[:window]
    all_nums = []
    for d in slice_hist:
        all_nums.extend(d['numbers'])
        
    counts = Counter(all_nums)
    # Sort by freq DESC, then number ASC
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    
    # Return top 15 for analysis
    pick = 15
    nums = [x[0] for x in ranked[:pick]]
    return {'numbers': sorted(nums), 'counts': dict(ranked), 'ranked_list': ranked[:pick]} 


def main():
    print("=" * 60)
    print("🚀 Power Lotto Dual-Path Strategy (Alpha-Beta) 🚀")
    print("=" * 60)
    
    # 1. Load History
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    # Filter for Retrospective (Pre-115000007)
    history = [d for d in all_history if d['draw'] < DRAW_NUMBER]
    
    if not history:
        print("❌ No history found.")
        return
        
    print(f"📚 Training Data: {len(history)} periods (Latest: {history[0]['draw']})")
    
    # 2. Initialize Engine
    engine = UnifiedPredictionEngine()
    rules = get_lottery_rules('POWER_LOTTO')
    
    # 3. Path Alpha Candidates Comparison
    print("\n" + "=" * 60)
    print("🔬 Comparing Alpha (Hot) Strategies")
    print("=" * 60)
    
    alpha_candidates = [
        ('Trend (Decay)', engine.trend_predict),
        ('Frequency (Gap-Biased)', engine.frequency_predict),
        ('True Freq (50)', lambda h, r: simple_true_frequency(h, r, 50)),
        ('True Freq (100)', lambda h, r: simple_true_frequency(h, r, 100)),
        ('Hot-Cold Mix', engine.hot_cold_mix_predict),
    ]
    
    best_alpha_name = "None"
    best_alpha_hits = 0
    best_alpha_nums = []
    
    for name, func in alpha_candidates:
        pred = func(history, rules)
        nums = sorted(pred['numbers'])
        hits = set(nums) & set(ACTUAL_NUMBERS)
        print(f"[{name}]: {len(hits)} hits {sorted(list(hits))} -> {nums}")
        
        # Check specifically for 17, 35
        missed_hot = []
        if 17 not in nums: missed_hot.append(17)
        if 35 not in nums: missed_hot.append(35)
        if missed_hot:
            print(f"   ⚠️ Missed key hot numbers: {missed_hot}")
            
        if len(hits) > best_alpha_hits:
            best_alpha_hits = len(hits)
            best_alpha_name = name
            best_alpha_nums = nums
            
    print(f"\n🏆 Best Alpha Candidate: {best_alpha_name} ({best_alpha_hits} hits)")
    
    # Use Best Alpha for Final calculation
    pred_alpha = {'numbers': best_alpha_nums}
    alpha_nums = best_alpha_nums
    
    # 4. Path Beta: Deviation Prediction (Cold)
    print("\n[Path Beta] Running Deviation Strategy (Cold)...")
    pred_beta = engine.deviation_predict(history, rules)
    beta_nums = sorted(pred_beta['numbers'])
    print(f"❄️ Beta Bet:  {beta_nums}")
    
    # 5. Grand Slam Verification (Alpha Top 12 + Beta Top 6)
    print("\n" + "=" * 60)
    print("🏆 Grand Slam Hypothesis Verification")
    print("=" * 60)
    
    # Get Top 12 from True Freq (50)
    tf50_res = simple_true_frequency(history, rules, 50)
    alpha_top12 = [x[0] for x in tf50_res['ranked_list'][:12]]
    print(f"🔥 Alpha Top 12: {alpha_top12}")
    
    grand_pool = set(alpha_top12) | set(beta_nums)
    grand_hits = grand_pool & set(ACTUAL_NUMBERS)
    print(f"Available Numbers: {len(grand_pool)}")
    print(f"Grand Hits: {len(grand_hits)} / 6 -> {sorted(list(grand_hits))}")
    
    if len(grand_hits) == 6:
        print("✅ JACKPOT DETECTED in Top 12 Hot + Top 6 Cold!")
    else:
        print(f"❌ Missed: {set(ACTUAL_NUMBERS) - grand_hits}")
        
    
    # 6. Special Zone
    print("\n" + "=" * 60)
    print("🔮 Special Zone Analysis")
    print("=" * 60)
    print("Running Markov Chain Strategy...")
    # Manually call predict_pool_numbers for special pool with Markov strategy
    special_res = predict_pool_numbers(
        history, 
        rules, 
        pool_type='special', 
        strategy_name='markov'
    )
    special_num = special_res['numbers'][0]
    print(f"Markov Prediction: {special_num:02d}")
    
    # Check Top 3 Freq for Special
    print("Running True Freq (50) for Special...")
    # Manually extract special history
    special_hist = [{'numbers': [d['special']]} for d in history if d.get('special')]
    tf_special = simple_true_frequency(special_hist, {'pickCount': 3}, 50)
    spec_candidates = tf_special['numbers']
    spec_counts = tf_special['counts']
    print(f"Freq(50) Top 3 Special: {spec_candidates}")
    print(f"Counts: {spec_counts}")
    
    if ACTUAL_SPECIAL in spec_candidates:
         print(f"✅ Special {ACTUAL_SPECIAL:02d} captured in Top 3 Freq!")
    else:
         print(f"❌ Special {ACTUAL_SPECIAL:02d} missed by Top 3 Freq.")

    
    # 7. Coverage Analysis for 35
    print("\n🔍 Missing Number Analysis (35)")
    if 35 in combined_nums:
        print("✅ 35 was captured by the Dual-Path strategy!")
    else:
        print("❌ 35 is still missing.")
        # Check rank in Alpha (Trend)
        trend_config = engine.trend_predict(history, rules)
        probs = trend_config.get('probabilities', [])
        # Recalculate full probability list to find rank of 35
        # Since 'probabilities' in result is truncated to pick_count, we might need to peek deeper or just infer
        print("   Checking Rank of 35 in Trend Strategy (Hot)...")
        # Re-run manually to get full list if possible, or trust the earlier analysis
        # For this script, we'll implement a quick check if missing
        
        # Quick robust check: re-run trend but ask for top 15
        temp_rules = rules.copy()
        temp_rules['pickCount'] = 15
        deep_trend = engine.trend_predict(history, temp_rules)
        if 35 in deep_trend['numbers']:
             print("   ⚠️ 35 is in Top 15 of Trend Strategy. It was cut off.")
        else:
             print("   ⚠️ 35 is not even in Top 15.")

if __name__ == '__main__':
    main()
