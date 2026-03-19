#!/usr/bin/env python3
"""
Comprehensive verification of all Wheel Tables.
"""

import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

from models.wheel_tables import WheelGenerator, WHEEL_TABLES

def main():
    generator = WheelGenerator(ticket_size=6)
    
    print("=" * 70)
    print("🔬 WHEEL TABLES COMPREHENSIVE VERIFICATION")
    print("=" * 70)
    
    all_passed = True
    
    for key in WHEEL_TABLES:
        pool_size, guarantee_t, condition_m, ticket_k = key
        
        # Create a dummy pool
        pool = list(range(1, pool_size + 1))
        
        result = generator.generate(pool, guarantee_t, condition_m)
        
        status = "✅ PASS" if result['coverage_verified'] else "❌ FAIL"
        if not result['coverage_verified']:
            all_passed = False
        
        print(f"{status} | Pool={pool_size:2d} | G={guarantee_t} if {condition_m} | Tickets={result['ticket_count']:2d} | Source: {result['source']}")
    
    print("=" * 70)
    if all_passed:
        print("✅ ALL TABLES VERIFIED - 100% Coverage Guaranteed!")
    else:
        print("❌ SOME TABLES FAILED VERIFICATION")
    print("=" * 70)
    
    # Demo a real use case
    print("\n📋 DEMO: Generating wheel for real numbers...")
    real_pool = [2, 7, 11, 15, 18, 22, 25, 28, 31, 33, 35, 38]
    result = generator.generate(real_pool, 3, 4)
    
    print(f"Pool: {result['pool']}")
    print(f"Guarantee: {result['guarantee_description']}")
    print(f"Tickets needed: {result['ticket_count']}")
    print(f"Verified: {'✅' if result['coverage_verified'] else '❌'}")
    print("\nGenerated Tickets:")
    for i, ticket in enumerate(result['tickets'], 1):
        print(f"  {i:2d}. {ticket}")

if __name__ == "__main__":
    main()
