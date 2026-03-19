import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.csv_validator import csv_validator

# Mock content based on expected format
mock_539_content = """
112000001期
開獎日期:112/01/01
大小順序:01 02 03 04 05
開出順序:05 04 03 02 01
01 02 03 04 05
""".strip().encode('utf-8')

mock_big_lotto_content = """
112000001期
開獎日期:112/01/01
大小順序:01 02 03 04 05 06
開出順序:06 05 04 03 02 01
01 02 03 04 05 06 07
""".strip().encode('utf-8')

# Mock 3 Star (Assuming 3 digits)
mock_3star_content = """
112000001期
開獎日期:112/01/01
大小順序:1 2 3
開出順序:3 2 1
1 2 3
""".strip().encode('utf-8')

def test_type(name, l_type, content):
    print(f"--- Testing {name} ({l_type}) ---")
    try:
        result = csv_validator.validate(content, l_type, 'txt')
        if result['valid']:
            print(f"✅ Valid - Processed {result['stats']['valid_rows']} rows")
            # print(result['parsed_data'][0])
        else:
            print("❌ Invalid")
            for e in result['errors']:
                print(f"   Line {e['line']}: {e['message']}")
    except Exception as e:
        print(f"💥 Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test Daily 539 (Standard)
    test_type("Daily 539", "DAILY_539", mock_539_content)
    
    # Test Big Lotto (Standard)
    # test_type("Big Lotto", "BIG_LOTTO", mock_big_lotto_content)
    
    # Test 3 Star
    test_type("3 Star", "3_STAR", mock_3star_content)
