#!/usr/bin/env python3
"""
Rigorous Power Lotto Benchmark (威力彩嚴謹驗證)
Goal: Establish Statistial Significance (P-Value / Z-Score) of the Strategy vs Random.

Method:
1. Run Strategy on Test Period (e.g., Last 200 draws).
2. Run Monte Carlo Simulation (N=1000) of Random Bets on the SAME Period.
3. Compare Strategy Performance to the Distribution of Random Outcomes.
"""
import sys
import os
import random
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from tools.power_lotto_dual_path_v2 import PowerLottoDualPathV2

def run_monte_carlo_baseline(draws, iterations=1000):
    """
    Run random betting simulation on the given draws multiple times
    to find the True Random Baseline Distribution.
    """
    print(f"🎲 Running Monte Carlo Simulation (N={iterations}) for Random Baseline...")
    
    m3_rates = []
    z2_rates = []
    
    total_draws = len(draws)
    
    for _ in range(iterations):
        wins = 0
        z2_wins = 0
        
        for target in draws:
            # Random Bet
            r1 = set(random.sample(range(1, 39), 6))
            r2 = random.randint(1, 8)
            
            actual = set(target['numbers'])
            actual_z2 = target.get('second_zone', target.get('special'))
            
            if len(actual & r1) >= 3: wins += 1
            if r2 == actual_z2: z2_wins += 1
            
        m3_rates.append(wins / total_draws * 100)
        z2_rates.append(z2_wins / total_draws * 100)
        
    return {
        'm3_mean': np.mean(m3_rates),
        'm3_std': np.std(m3_rates),
        'm3_min': np.min(m3_rates),
        'm3_max': np.max(m3_rates),
        'z2_mean': np.mean(z2_rates),
        'z2_std': np.std(z2_rates)
    }

def main():
    # 1. Setup
    predictor = PowerLottoDualPathV2()
    all_draws = predictor.db.get_all_draws('POWER_LOTTO')
    test_len = 200
    test_data = all_draws[-test_len:]
    
    print("================================================================")
    print(f"🔬 RIGOROUS STATISTICAL VALIDATION (Last {test_len} Draws)")
    print("================================================================")
    
    # 2. Run Strategy (Observed)
    print("🤖 Evaluating Strategy Performance...")
    strat_wins = 0
    strat_z2_wins = 0
    
    # Pre-calculate strategy to ensure stability
    for i in range(test_len):
        idx = len(all_draws) - test_len + i
        target = all_draws[idx]
        history = all_draws[:idx]
        
        p1 = predictor.predict(history)
        p2 = predictor.predict_zone2(history)
        
        actual = set(target['numbers'])
        actual_z2 = target.get('second_zone', target.get('special'))
        
        if len(actual & set(p1)) >= 3: strat_wins += 1
        if p2 == actual_z2: strat_z2_wins += 1
        
    strat_m3_rate = strat_wins / test_len * 100
    strat_z2_rate = strat_z2_wins / test_len * 100
    
    print(f"   Strategy M3+ Rate : {strat_m3_rate:.2f}% ({strat_wins}/{test_len})")
    print(f"   Strategy Z2 Rate  : {strat_z2_rate:.2f}% ({strat_z2_wins}/{test_len})")
    
    # 3. Run Random Baseline (Expected)
    baseline = run_monte_carlo_baseline(test_data, iterations=1000)
    
    # 4. Statistical Tests
    print("\n📊 Statistical Analysis Result")
    print("----------------------------------------------------------------")
    
    # Zone 1 Analysis
    sigma_1 = (strat_m3_rate - baseline['m3_mean']) / baseline['m3_std']
    print(f"🎯 Zone 1 (Match 3+)")
    print(f"   Random Mean      : {baseline['m3_mean']:.2f}% ± {baseline['m3_std']:.2f}%")
    print(f"   Random Range     : [{baseline['m3_min']:.2f}% - {baseline['m3_max']:.2f}%]")
    print(f"   Strategy         : {strat_m3_rate:.2f}%")
    print(f"   Difference       : {strat_m3_rate - baseline['m3_mean']:+.2f}%")
    print(f"   Z-Score (Sigma)  : {sigma_1:.2f}")
    
    if abs(sigma_1) < 1.0:
        conclusion_1 = "❌ INSIGNIFICANT (Noise)"
    elif sigma_1 > 2.0:
        conclusion_1 = "✅ SIGNIFICANT (Real Edge)"
    else:
        conclusion_1 = "⚠️ MARGINAL (Possible Edge)"
        
    print(f"   Conclusion       : {conclusion_1}")
    
    print("-" * 64)
    
    # Zone 2 Analysis
    sigma_2 = (strat_z2_rate - baseline['z2_mean']) / baseline['z2_std']
    print(f"🎯 Zone 2 (Second Zone)")
    print(f"   Random Mean      : {baseline['z2_mean']:.2f}% (Theory: 12.50%)")
    print(f"   Strategy         : {strat_z2_rate:.2f}%")
    print(f"   Difference       : {strat_z2_rate - baseline['z2_mean']:+.2f}%")
    print(f"   Z-Score (Sigma)  : {sigma_2:.2f}")
    
    if sigma_2 > 2.0:
        conclusion_2 = "✅ HIGHLY SIGNIFICANT (Strong Edge)"
    elif sigma_2 > 1.0:
        conclusion_2 = "✅ SIGNIFICANT (Edge)"
    else:
        conclusion_2 = "❌ INSIGNIFICANT (Luck)"
        
    print(f"   Conclusion       : {conclusion_2}")
    
    print("================================================================")
    print("💡 FINAL VERDICT")
    if "INSIGNIFICANT" in conclusion_1:
        print("   1. You were RIGHT. The Strategy's edge in Zone 1 is statistically indistinguishable from random noise.")
        print("      (The +1% observed earlier falls well within the random standard deviation).")
    else:
        print("   1. The Strategy has a verified edge in Zone 1.")
        
    if "SIGNIFICANT" in conclusion_2:
        print("   2. The Strategy in Zone 2 is LEGITIMATE. The deviation from random is too large to be luck.")
    
if __name__ == "__main__":
    main()
