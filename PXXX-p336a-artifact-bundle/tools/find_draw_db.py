import sys
import os
import json
import sqlite3

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    
    target_numbers = {3, 7, 16, 19, 40, 42}
    target_special = 12
    
    print(f"Searching for Main: {sorted(list(target_numbers))} Special: {target_special}")
    
    draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    
    found = False
    for draw in draws:
        numbers = set(draw['numbers'])
        special = draw['special']
        
        if numbers == target_numbers and special == target_special:
            print(f"✅ FOUND MATCH!")
            print(f"Draw: {draw['draw']}")
            print(f"Date: {draw['date']}")
            print(f"Numbers: {draw['numbers']}")
            print(f"Special: {draw['special']}")
            found = True
            break
            
    if not found:
        print("❌ No match found in database.")
        # Print latest draw for context
        if draws:
            latest = draws[0]
            print(f"Latest Draw in DB: {latest['draw']} ({latest['date']}) -> {latest['numbers']} Special: {latest['special']}")

if __name__ == "__main__":
    main()
