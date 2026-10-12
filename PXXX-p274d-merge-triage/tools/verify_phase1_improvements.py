#!/usr/bin/env python3
"""
Phase 1 Verification Script
Test the consecutive filter improvements and gap_hunter weight changes
"""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from config_loader import config, get_consecutive_penalty, get_strategy_weight

def test_consecutive_penalties():
    """Test the新 gradual consecutive penalty system"""
    print("=" * 70)
    print("Phase 1 Verification: Consecutive Number Filter")
    print("=" * 70)
    
    print("\n1. Configuration Loaded:")
    print(f"   Use Gradual Penalties: {config.get('consecutive_filter.use_gradual_penalties')}")
    print(f"   Config Available: {config._config is not None}")
    
    print("\n2. Penalty Multipliers:")
    test_cases = [
        (1, "No consecutive (e.g., 02,07,26,41)"),
        (2, "2-consecutive (e.g., 44,45)"),
        (3, "3-consecutive (e.g., 44,45,46) ⚠️"),
        (4, "4-consecutive (e.g., 01,02,03,04)"),
    ]
    
    for count, description in test_cases:
        penalty = get_consecutive_penalty(count)
        print(f"   {description}")
        print(f"     Consecutive Count: {count}")
        print(f"     Penalty Multiplier: {penalty}")
        if penalty < 1.0:
            print(f"     Effect: Score reduced to {penalty*100:.0f}%")
        elif penalty > 1.0:
            print(f"     Effect: Add {penalty} penalty points (old system)")
        else:
            print(f"     Effect: No penalty applied")
        print()
    
    print("\n3. Real-World Example: Draw 115000006 (44-45-46)")
    print("   Old System: 300 penalty points → Likely rejected")
    penalty_3_consecutive = get_consecutive_penalty(3)
    if penalty_3_consecutive < 1.0:
        print(f"   New System: Score × {penalty_3_consecutive} → Reduced but still possible!")
        print(f"   ✅ Improvement: Rare patterns can now appear in predictions")
    else:
        print(f"   Warning: Still using old hard penalty system ({penalty_3_consecutive})")
    

def test_strategy_weights():
    """Test the upgraded strategy weights"""
    print("\n" + "=" * 70)
    print("Phase 1 Verification: Strategy Weights")
    print("=" * 70)
    
    print("\n1. Core Methods:")
    core_methods = ['frequency', 'trend', 'bayesian', 'markov', 'deviation']
    for method in core_methods:
        weight = get_strategy_weight(method)
        print(f"   {method:20s}: {weight:.2f}")
    
    print("\n2. Gap Analysis Methods (Phase 1 Upgrade ⬆️):")
    gap_methods = ['gap_analysis', 'gap_hunter', 'cold_comeback']
    for method in gap_methods:
        weight = get_strategy_weight(method)
        if method in ['gap_analysis', 'gap_hunter']:
            print(f"   {method:20s}: {weight:.2f}  ⬆️ (upgraded from 0.6 to 1.2)")
        else:
            print(f"   {method:20s}: {weight:.2f}")
    
    print("\n3. Weight Comparison:")
    gap_weight = get_strategy_weight('gap_analysis')
    freq_weight = get_strategy_weight('frequency')
    print(f"   Gap Analysis: {gap_weight:.2f}")
    print(f"   Frequency: {freq_weight:.2f}")
    if gap_weight >= 1.0:
        print(f"   ✅ Gap Analysis now has mainstream-level influence!")
    else:
        print(f"   ⚠️  Gap Analysis still has low weight")


def test_draw_115000006_scenario():
    """Simulate how the new system would handle draw 115000006"""
    print("\n" + "=" * 70)
    print("Phase 1 Scenario Test: Draw 115000006")
    print("=" * 70)
    
    actual_numbers = [2, 7, 26, 41, 44, 45, 46]
    consecutive_patterns = [
        ([44, 45, 46], 3, "Triple consecutive (actual draw)"),
        ([7, 8], 2, "Double consecutive"),
        ([2, 7, 26, 41], 1, "No consecutive"),
    ]
    
    print("\nActual Draw: 02, 07, 26, 41, 44, 45, 46")
    print("Challenge: Contains 44-45-46 (triple consecutive)")
    
    print("\n1. How different patterns would be scored:")
    for numbers, count, description in consecutive_patterns:
        penalty = get_consecutive_penalty(count)
        base_score = 100.0  # Hypothetical base score
        
        if penalty < 1.0:
            final_score = base_score * penalty
            print(f"\n   {description}:")
            print(f"     Numbers: {numbers}")
            print(f"     Base Score: {base_score:.1f}")
            print(f"     Penalty Multiplier: {penalty}")
            print(f"     Final Score: {final_score:.1f} ({final_score/base_score*100:.0f}%)")
        else:
            print(f"\n   {description}:")
            print(f"     Numbers: {numbers}")
            print(f"     Using old penalty system")
    
    print("\n2. Expected Improvement:")
    triple_penalty = get_consecutive_penalty(3)
    if triple_penalty < 1.0:
        print(f"   ✅ Numbers like (44,45,46) will have {triple_penalty*100:.0f}% of original score")
        print(f"   ✅ Still unlikely but NOT impossible")
        print(f"   ✅ Should improve coverage of rare but valid patterns")
    
    print("\n3. Gap Hunter Improvement:")
    gap_weight = get_strategy_weight('gap_analysis')
    print(f"   ✅ Gap methods weight: {gap_weight:.1f}x")
    print(f"   ✅ Better chance to catch cold numbers like 07")


def main():
    """Run all verifications"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "Phase 1 Emergency Fixes Verification" + " " * 16 + "║")
    print("║" + " " * 10 + "Big Lotto Prediction System Improvements" + " " * 16 + "║")
    print("╚" + "═" * 68 + "╝")
    
    test_consecutive_penalties()
    test_strategy_weights()
    test_draw_115000006_scenario()
    
    print("\n" + "=" * 70)
    print("Verification Summary")
    print("=" * 70)
    
    # Check if improvements are active
    gradual_enabled = config.get('consecutive_filter.use_gradual_penalties', False)
    gap_weight = get_strategy_weight('gap_analysis')
    triple_penalty = get_consecutive_penalty(3)
    
    improvements = []
    issues = []
    
    if gradual_enabled and triple_penalty < 1.0:
        improvements.append("✅ Gradual consecutive penalties: ACTIVE")
    else:
        issues.append("⚠️  Gradual consecutive penalties: NOT ACTIVE")
    
    if gap_weight >= 1.2:
        improvements.append("✅ Gap Analysis weight upgrade: ACTIVE (1.2x)")
    else:
        issues.append(f"⚠️  Gap Analysis weight: {gap_weight:.1f}x (target: 1.2x)")
    
    print("\nImprovements:")
    for imp in improvements:
        print(f"  {imp}")
    
    if issues:
        print("\nIssues Found:")
        for issue in issues:
            print(f"  {issue}")
    
    print("\n" + "=" * 70)
    print("Next Steps:")
    print("  1. Run backtest to verify Match-3+ rate improvement")
    print("  2. Generate prediction for draw 115000007")
    print("  3. Monitor consecutive number coverage in next 10 draws")
    print("=" * 70)
    print()


if __name__ == '__main__':
    main()
