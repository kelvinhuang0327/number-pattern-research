import sys
import os
import json

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    
    # Draw data for 2026/01/02
    new_draw = {
        'draw': '115000001',
        'date': '2026/01/02',
        'lotteryType': 'BIG_LOTTO',
        'numbers': [3, 7, 16, 19, 40, 42],
        'special': 12
    }
    
    inserted, duplicates = db.insert_draws([new_draw])
    if inserted > 0:
        print(f"✅ Successfully inserted draw {new_draw['draw']}")
    else:
        print(f"⚠️ Draw {new_draw['draw']} already exists or insertion failed.")

if __name__ == "__main__":
    main()
