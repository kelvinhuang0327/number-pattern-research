#!/usr/bin/env python3
"""
Test Heuristic Wheeling for 24 Numbers
======================================
Check if we can generate a (24, 3, 5, 6) wheel in reasonable time.
"""
import sys
import os
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))

from models.wheel_tables import WheelGenerator

def test_24_number_wheel():
    pool = list(range(1, 25))
    generator = WheelGenerator(ticket_size=6)
    
    print(f"🚀 Testing Wheeling for 24 numbers (Guarantee 3-if-5)...")
    start_time = time.time()
    
    # Guarantee 3 if 5 matches
    result = generator.generate(pool, guarantee_t=3, condition_m=5)
    
    duration = time.time() - start_time
    print(f"✅ Generated in {duration:.2f} seconds.")
    print(f"🎫 Tickets: {result['ticket_count']}")
    print(f"🔍 Verified: {result['coverage_verified']}")
    print(f"💡 Source: {result['source']}")
    
    if result.get('uncovered_count'):
        print(f"⚠️ Uncovered Scenarios: {result['uncovered_count']}")

if __name__ == "__main__":
    test_24_number_wheel()
