#!/usr/bin/env python3
"""
Full History Jackpot Analysis
Analyzes ALL historical draws to find if any method could have predicted Match-5+ (jackpot).
"""
import os
import sys
from collections import Counter, defaultdict

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

def analyze_jackpot_hits(lottery_type='BIG_LOTTO'):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type=lottery_type)))
    rules = get_lottery_rules(lottery_type)
    
    engine = UnifiedPredictionEngine()
    
    print("=" * 80)
    print(f"🔬 Full History Jackpot Analysis - {lottery_type}")
    print(f"   Total draws: {len(all_draws)}")
    print("=" * 80)
    
    methods = {
        'markov': engine.markov_predict,
        'deviation': engine.deviation_predict,
        'statistical': engine.statistical_predict,
        'trend': engine.trend_predict,
        'frequency': engine.frequency_predict,
    }
    
    # Track high matches
    high_matches = defaultdict(list)  # method -> list of (draw_idx, match_count, draw_info)
    
    # Need at least 50 draws for meaningful history
    start_idx = 50
    
    for i in range(start_idx, len(all_draws)):
        target_draw = all_draws[i]
        history = all_draws[:i]
        actual = set(target_draw.get('numbers', []))
        draw_date = target_draw.get('date', 'Unknown')
        draw_id = target_draw.get('draw_period', target_draw.get('draw_id', i))
        
        for method_name, method_func in methods.items():
            try:
                result = method_func(history, rules)
                predicted = set(result['numbers'][:6])
                match_count = len(predicted & actual)
                
                if match_count >= 5:
                    high_matches[method_name].append({
                        'draw_idx': i,
                        'draw_id': draw_id,
                        'date': draw_date,
                        'match_count': match_count,
                        'predicted': sorted(list(predicted)),
                        'actual': sorted(list(actual)),
                        'matched_numbers': sorted(list(predicted & actual))
                    })
                    
            except Exception as e:
                continue
                
        if (i - start_idx + 1) % 500 == 0:
            print(f"Processed {i - start_idx + 1}/{len(all_draws) - start_idx} draws...")
    
    # Report results
    print("\n" + "=" * 80)
    print("📊 JACKPOT (Match-5+) ANALYSIS RESULTS")
    print("=" * 80)
    
    total_analyzed = len(all_draws) - start_idx
    
    if not any(high_matches.values()):
        print(f"\n❌ No Match-5+ found across {total_analyzed} draws with any method.")
        print("   This is statistically expected given:")
        print(f"   - Match-6 probability: 1 in 13,983,816")
        print(f"   - Match-5 probability: 1 in 2,330,636")
        print(f"   - Total predictions: {total_analyzed * len(methods)}")
    else:
        for method_name, hits in high_matches.items():
            if hits:
                print(f"\n🎯 {method_name.upper()} - {len(hits)} high matches:")
                for hit in hits:
                    print(f"   Draw {hit['draw_id']} ({hit['date']}): Match-{hit['match_count']}")
                    print(f"      Predicted: {hit['predicted']}")
                    print(f"      Actual:    {hit['actual']}")
                    print(f"      Matched:   {hit['matched_numbers']}")
    
    # Also check for Match-4 distribution
    print("\n" + "-" * 80)
    print("📈 Match-4+ Distribution Summary:")
    
    match4_counts = defaultdict(int)
    
    for i in range(start_idx, len(all_draws)):
        target_draw = all_draws[i]
        history = all_draws[:i]
        actual = set(target_draw.get('numbers', []))
        
        for method_name, method_func in methods.items():
            try:
                result = method_func(history, rules)
                predicted = set(result['numbers'][:6])
                match_count = len(predicted & actual)
                
                if match_count >= 4:
                    match4_counts[method_name] += 1
            except:
                continue
    
    print(f"{'Method':<15} | Match-4+ Count | Rate")
    print("-" * 45)
    for method_name in methods.keys():
        count = match4_counts[method_name]
        rate = count / total_analyzed * 100
        print(f"{method_name:<15} | {count:<14} | {rate:.2f}%")
    
    print("=" * 80)

if __name__ == "__main__":
    # Analyze Big Lotto
    analyze_jackpot_hits('BIG_LOTTO')
    
    print("\n\n")
    
    # Analyze Power Lotto
    analyze_jackpot_hits('POWER_LOTTO')
