import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.csv_validator import csv_validator

# 1. Standard 539 (UTF-8)
case_539_utf8 = """
第112000001期
開獎日期:112/01/01
大小順序:01 02 03 04 05
開出順序:05 04 03 02 01
01 02 03 04 05
""".strip().encode('utf-8')

# 2. Standard 539 (Big5)
case_539_big5 = """
第112000001期
開獎日期:112/01/01
大小順序:01 02 03 04 05
開出順序:05 04 03 02 01
01 02 03 04 05
""".strip().encode('big5')

# 3. No "第" prefix
case_no_prefix = """
112000001期
開獎日期:112/01/01
大小順序:01 02 03 04 05
開出順序:05 04 03 02 01
01 02 03 04 05
""".strip().encode('utf-8')

# 4. Big Lotto (6 numbers + 1 special)
case_lotto_utf8 = """
第112000001期
開獎日期:112/01/01
大小順序:01 02 03 04 05 06
開出順序:06 05 04 03 02 01
01 02 03 04 05 06 07
""".strip().encode('utf-8')

# 5. Missing "期" suffix (Test failure case)
case_no_suffix = """
第112000001
開獎日期:112/01/01
大小順序:01 02 03 04 05
開出順序:05 04 03 02 01
01 02 03 04 05
""".strip().encode('utf-8')

# 6. Short Draw Number (Regression check)
case_short_draw = """
第123456期
開獎日期:112/01/01
大小順序:01 02 03 04 05
開出順序:05 04 03 02 01
01 02 03 04 05
""".strip().encode('utf-8')

def test(name, l_type, content):
    print(f"\n--- Testing {name} ({l_type}) ---")
    try:
        result = csv_validator.validate(content, l_type, 'txt')
        if result['valid'] and result['stats']['valid_rows'] > 0:
            print(f"✅ PASS: {result['stats']['valid_rows']} rows")
        else:
            print(f"❌ FAIL: Valid={result['valid']}, Rows={result['stats']['valid_rows']}")
            for e in result['errors']:
                print(f"   Line {e['line']}: {e['message']}")
    except Exception as e:
        print(f"💥 EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test("539 UTF-8", "DAILY_539", case_539_utf8)
    test("539 Big5", "DAILY_539", case_539_big5)
    test("No Prefix", "DAILY_539", case_no_prefix)
    test("Big Lotto", "BIG_LOTTO", case_lotto_utf8)
    test("No Suffix (Should likely fail)", "DAILY_539", case_no_suffix)
    test("Short Draw (Regression Check)", "DAILY_539", case_short_draw)
