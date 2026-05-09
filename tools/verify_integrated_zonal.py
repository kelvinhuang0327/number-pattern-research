#!/usr/bin/env python3
"""
Final Verification for Phase 71 integration.
Ensures that MultiBetOptimizer now produces bets that pass Zonal Thermodynamics check.
"""

import sys
import os
import json
import sqlite3

# Ensure project root is in path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.common import get_lottery_rules

def verify_integration():
    print("=" * 60)
    print("🧪 PHASE 71 INTEGRATION VERIFICATION")
    print("=" * 60)
    
    optimizer = MultiBetOptimizer()
    
    # Test Data
    db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Test Big Lotto
    cursor.execute("SELECT numbers FROM draws WHERE lottery_type = 'BIG_LOTTO' ORDER BY draw DESC LIMIT 500")
    big_draws = [{'numbers': json.loads(r[0])} for r in cursor.fetchall()]
    big_rules = get_lottery_rules('BIG_LOTTO')
    
    print("\n[BIG LOTTO (Tri-Core)]")
    res_big = optimizer.generate_tri_core_3bets(big_draws, big_rules, {}, num_bets=3)
    for i, bet in enumerate(res_big['bets']):
        numbers = bet['numbers']
        is_valid = optimizer.check_zonal_thermodynamics(numbers, 49)
        print(f"Bet {i+1}: {numbers} | Zonal Valid: {'✅' if is_valid else '❌'}")

    # Test Power Lotto
    cursor.execute("SELECT numbers FROM draws WHERE lottery_type = 'POWER_LOTTO' ORDER BY draw DESC LIMIT 500")
    power_draws = [{'numbers': json.loads(r[0])} for r in cursor.fetchall()]
    power_rules = get_lottery_rules('POWER_LOTTO')
    
    print("\n[POWER LOTTO (Diversified Ensemble)]")
    res_power = optimizer.generate_diversified_bets(power_draws, power_rules, num_bets=5)
    for i, bet in enumerate(res_power['bets']):
        numbers = bet['numbers']
        is_valid = optimizer.check_zonal_thermodynamics(numbers, 38)
        print(f"Bet {i+1}: {numbers} | Zonal Valid: {'✅' if is_valid else '❌'}")
    
    conn.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    verify_integration()
