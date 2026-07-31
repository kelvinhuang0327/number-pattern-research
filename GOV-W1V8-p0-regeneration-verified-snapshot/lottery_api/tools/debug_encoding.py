import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.csv_validator import csv_validator

# Mock content based on expected format (Big5 encoded)
mock_539_content_big5 = """
112000001期
開獎日期:112/01/01
大小順序:01 02 03 04 05
開出順序:05 04 03 02 01
01 02 03 04 05
""".strip().encode('big5')

def test_encoding(name, l_type, content):
    print(f"--- Testing {name} ({l_type}) ---")
    try:
        result = csv_validator.validate(content, l_type, 'txt')
        if result['valid']:
            print(f"✅ Valid - Processed {result['stats']['valid_rows']} rows")
        else:
            print("❌ Invalid")
            for e in result['errors']:
                print(f"   Line {e['line']}: {e['message']}")
    except Exception as e:
        print(f"💥 Exception: {e}")

if __name__ == "__main__":
    print("Testing Big5 Encoding...")
    test_encoding("Daily 539 (Big5)", "DAILY_539", mock_539_content_big5)
