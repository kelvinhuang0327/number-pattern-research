
import os
import sys
import json

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

def update():
    db_path = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db'
    db = DatabaseManager(db_path)
    # Big Lotto 115000012
    draw_data = {
        'draw': '115000012',
        'date': '2026/02/10',
        'lotteryType': 'BIG_LOTTO',
        'numbers': [6, 16, 20, 21, 24, 35],
        'special': 13
    }
    
    # Check if exists
    existing = db.get_draw('BIG_LOTTO', '115000012')
    if not existing:
        db.insert_draws([draw_data])
        print(f"Successfully added BIG_LOTTO 115000012 to {db_path}")
    else:
        print("BIG_LOTTO 115000012 already exists.")

if __name__ == "__main__":
    update()
