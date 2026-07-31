import sys
import os
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

def check_draws():
    db_path = os.path.join(project_root, 'lottery-api/data/lottery_v2.db')
    print(f"Checking DB at: {db_path}")
    if os.path.exists(db_path):
        print("DB file exists.")
    else:
        print("DB file NOT found!")
        # Try alternate path
        db_path_alt = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
        print(f"Checking alt DB at: {db_path_alt}")
        if os.path.exists(db_path_alt):
             print("Alt DB file exists.")
             db_path = db_path_alt
        else:
             print("Alt DB file NOT found!")

    try:
        db = DatabaseManager(db_path=db_path)
        draws = db.get_all_draws('BIG_LOTTO')
        print(f"Draws found for BIG_LOTTO: {len(draws)}")
        if len(draws) > 0:
            print(f"First draw: {draws[0]}")
    except Exception as e:
        print(f"Error accessing DB: {e}")

if __name__ == "__main__":
    check_draws()
