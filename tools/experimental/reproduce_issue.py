import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'lottery-api'))

from utils.csv_validator import csv_validator
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)

def test_validation(content, name):
    print(f"\n--- Testing {name} ---")
    # Using 'daily_cash' or similar generic? No, user said '大樂透' (BIG_LOTTO)
    result = csv_validator.validate(content.encode('utf-8'), 'BIG_LOTTO', 'txt')
    if result['valid']:
        print("✅ Valid")
        for row in result['parsed_data']:
            print(f"  Parses: {row['date']} - {row['draw']}")
    else:
        print("❌ Invalid")
        for err in result['errors']:
            print(f"  Error: {err['message']} (Line {err['line']})")

# Case 1: Standard ROC format (Old style)
content_roc = """
113000001期
開獎日期:113/01/01
01,02,03,04,05,06,07
"""
test_validation(content_roc, "Standard ROC (113)")

# Case 2: 2025 ROC format (114)
content_roc_114 = """
114000001期
開獎日期:114/01/01
01,02,03,04,05,06,07
"""
test_validation(content_roc_114, "ROC 2025 (114)")

# Case 3: AD Year format (User might have this)
content_ad = """
114000001期
開獎日期:2025/01/01
01,02,03,04,05,06,07
"""
test_validation(content_ad, "AD Year 2025")

# Case 4: No '期' suffix in draw
content_no_suffix = """
114000001
開獎日期:114/01/01
01,02,03,04,05,06,07
"""
test_validation(content_no_suffix, "No '期' Suffix")

# Case 5: Missing '開獎日期:' prefix
content_missing_prefix = """
114000001期
日期:114/01/01
01,02,03,04,05,06,07
"""
test_validation(content_missing_prefix, "Missing '開獎日期:' Prefix")

# Case 6: Space after colon
content_space = """
114000001期
開獎日期: 2025/01/01
01,02,03,04,05,06,07
"""
test_validation(content_space, "Space after colon")

# Case 7: Fullwidth colon
content_fullwidth = """
114000001期
開獎日期：2025/01/01
01,02,03,04,05,06,07
"""
test_validation(content_fullwidth, "Fullwidth colon")
