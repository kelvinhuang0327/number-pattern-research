import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.csv_validator import csv_validator

# 1. 4-Star Joined (Parse "1234" -> [1,2,3,4])
case_4star = """
112000001
開獎日期:112/01/01
大小順序:1234
開出順序:4321
1234
""".strip().encode('utf-8')

# 2. 49 Lotto (Should pass without play mode)
case_49_lotto = """
112000001
開獎日期:112/01/01
01 02 03 04 05 06
""".strip().encode('utf-8')

# 3. 539 with extra lines
case_539_spaced = """
112000001
開獎日期:112/01/01
(Some junk line)
(Another junk line)
01 02 03 04 05
""".strip().encode('utf-8')

def test(name, l_type, content, expected_valid=True):
    print(f"\n--- Testing {name} ({l_type}) ---")
    try:
        result = csv_validator.validate(content, l_type, 'txt')
        if result['valid'] == expected_valid:
            print(f"✅ PASS: Valid={result['valid']}, Rows={result['stats']['valid_rows']}")
            if result['stats']['valid_rows'] > 0:
                 print(f"   Sample: {result['parsed_data'][0]['numbers']}")
        else:
            print(f"❌ FAIL: Expected {expected_valid}, Got {result['valid']}")
            for e in result['errors']:
                print(f"   Error: {e['message']}")
    except Exception as e:
        print(f"💥 EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test("4 Star Joined", "4_STAR", case_4star)
    test("49 Lotto (No Play Mode)", "49_LOTTO", case_49_lotto)
    test("539 Spaced", "DAILY_539", case_539_spaced)
