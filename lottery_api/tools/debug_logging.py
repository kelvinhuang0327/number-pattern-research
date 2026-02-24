import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

from utils.csv_validator import csv_validator

# Test Case
case_sample = """
112000001
開獎日期:112/01/01
大小順序:01 02 03 04 05
""".strip().encode('utf-8')

print("--- Running Logging Verification ---")
csv_validator.validate(case_sample, "DAILY_539", "txt")
