#!/usr/bin/env python3
"""
Verify 4-bet Optimized Strategy (Window Variation) for Power Lotto 2025.
Target Hit Rate: 19-21%
"""

import sys
import os
import json
import logging
from typing import List, Dict
from collections import defaultdict
from pathlib import Path

# Set up paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'lottery_api'))

from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from common import get_lottery_rules

# Disable noisy logs
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def calculate_matches(predicted: List[int], actual: List[int]) -> int:
    return len(set(predicted) & set(actual))

def main():
    lottery_type = 'POWER_LOTTO'
    engine = UnifiedPredictionEngine()
    rules = get_lottery_rules(lottery_type)
    
    # Ensure database path is correct
    db_path = project_root / 'lottery_api' / 'data' / 'lottery_v2.db'
    if db_path.exists():
        db_manager.db_path = str(db_path)
    
    print(f"Loading {lottery_type} data...")
    all_draws = db_manager.get_all_draws(lottery_type)
    if not all_draws:
        print("Error: No data found.")
        return

    # Filter for 2025 draws
    draws_2025 = [d for d in all_draws if '2025' in str(d.get('date', ''))]
    draws_2025 = sorted(draws_2025, key=lambda x: x['draw'])
    
    if not draws_2025:
        print("Error: No 2025 draws found.")
        return

    print("=" * 80)
    print(f"POWER LOTTO 4-BET STRATEGY VALIDATION (2025)")
    print(f"Strategy: Window Variation (Scheme B)")
    print(f"Total draws to test: {len(draws_2025)}")
    print("=" * 80)
    
    hit_count = 0 # Periods with at least one winning bet
    total_bets_count = 0
    match_dist = defaultdict(int)
    special_hit_count = 0
    
    results_log = []

    for target_draw in draws_2025:
        draw_id = target_draw['draw']
        actual_numbers = target_draw['numbers']
        actual_special = int(target_draw['special'])
        
        # Find index in all_draws for history
        target_idx = -1
        for i, d in enumerate(all_draws):
            if d['draw'] == draw_id:
                target_idx = i
                break
        
        if target_idx == -1 or target_idx + 1 >= len(all_draws):
            continue
            
        history_full = all_draws[target_idx + 1 :]
        
        print(f"Predicting Draw {draw_id}... ", end='', flush=True)
        
        try:
            # Bet 1: Ensemble (100)
            pred1 = engine.ensemble_predict(history_full[:100], rules)
            
            # Bet 2: Ensemble (500)
            pred2 = engine.ensemble_predict(history_full[:500] if len(history_full) >= 500 else history_full, rules)
            
            # Bet 3: Zone Balance + Bayesian (200)
            h200 = history_full[:200] if len(history_full) >= 200 else history_full
            zb_res = engine.zone_balance_predict(h200, rules)
            bay_res = engine.bayesian_predict(h200, rules)
            # Combine or take top 6 from union? The documentation says "Fusion".
            # Usually means combining scores, but we'll take top 6 unique numbers prioritized by ZB then Bayesian.
            pred3_nums = list(set(zb_res['numbers']) | set(bay_res['numbers']))[:6]
            pred3_special = zb_res.get('special', bay_res.get('special', 1))
            pred3 = {'numbers': pred3_nums, 'special': pred3_special}
            
            # Bet 4: Trend + Frequency (300)
            h300 = history_full[:300] if len(history_full) >= 300 else history_full
            trend_res = engine.trend_predict(h300, rules)
            freq_res = engine.frequency_predict(h300, rules)
            pred4_nums = list(set(trend_res['numbers']) | set(freq_res['numbers']))[:6]
            pred4_special = trend_res.get('special', freq_res.get('special', 1))
            pred4 = {'numbers': pred4_nums, 'special': pred4_special}
            
            bets = [pred1, pred2, pred3, pred4]
            total_bets_count += len(bets)
            
            # Check for hits in any bet
            any_win = False
            best_m = 0
            best_s = False
            
            for bet in bets:
                m = calculate_matches(bet['numbers'], actual_numbers)
                s = (int(bet['special']) == actual_special)
                
                if m > best_m: best_m = m
                if s: best_s = True
                
                # Power Lotto Win Condition: Match 3 or (Match 2 + Special) or better
                if m >= 3 or (m >= 2 and s):
                    any_win = True
            
            if any_win:
                hit_count += 1
            
            match_dist[best_m] += 1
            if best_s: special_hit_count += 1
            
            status = "WIN" if any_win else "MISS"
            print(f"Best Match: {best_m} | Special: {'YES' if best_s else 'NO'} | Result: {status}")
            
            results_log.append({
                'draw': draw_id,
                'win': any_win,
                'best_m': best_m,
                'best_s': best_s
            })
            
        except Exception as e:
            print(f"FAILED: {e}")
            continue

    # Summary
    total_tested = len(results_log)
    if total_tested == 0:
        print("No draws were tested.")
        return

    hit_rate = (hit_count / total_tested) * 100
    print("\n" + "=" * 80)
    print(f"FINAL RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total Periods Tested: {total_tested}")
    print(f"Winning Periods:     {hit_count}")
    print(f"Overall Hit Rate:    {hit_rate:.2f}%")
    print("-" * 40)
    print(f"Match Distribution (Best in 4 bets):")
    for m in range(7):
        print(f"  Match {m}: {match_dist[m]:2d} draws ({(match_dist[m]/total_tested)*100:5.1f}%)")
    print(f"Special Hits:      {special_hit_count:2d} draws ({(special_hit_count/total_tested)*100:5.1f}%)")
    print("=" * 80)
    
    # Save results
    output = {
        'hit_rate': hit_rate,
        'winning_periods': hit_count,
        'total_periods': total_tested,
        'match_distribution': dict(match_dist),
        'special_hits': special_hit_count,
        'details': results_log
    }
    
    with open('4bet_validation_results_2025.json', 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to 4bet_validation_results_2025.json")

if __name__ == '__main__':
    main()
