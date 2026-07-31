import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.csv_validator import csv_validator

# Case: Only has "大小順序" line, no standalone number line
case_only_order = """
112000001
開獎日期:112/01/01
大小順序:01 02 03 04 05
""".strip().encode('utf-8')

# Case: Standard (has standalone line)
case_standard = """
112000001
開獎日期:112/01/01
大小順序:01 02 03 04 05
01 02 03 04 05
""".strip().encode('utf-8')

def test(name, l_type, content):
    print(f"\n--- Testing {name} ({l_type}) ---")
    try:
        result = csv_validator.validate(content, l_type, 'txt')
        if result['valid']:
            print(f"✅ PASS: Valid={result['valid']}, Rows={result['stats']['valid_rows']}")
        else:
            print(f"❌ FAIL: Valid={result['valid']}, Rows={result['stats']['valid_rows']}")
            for e in result['errors']:
                print(f"   Error: {e['message']}")
    except Exception as e:
        print(f"💥 EXCEPTION: {e}")

if __name__ == "__main__":
    test("Only Order Line", "DAILY_539", case_only_order)
    test("Standard", "DAILY_539", case_standard)
