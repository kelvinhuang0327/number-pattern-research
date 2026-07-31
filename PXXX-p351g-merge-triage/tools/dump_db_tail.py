#!/usr/bin/env python3
import os
import sys

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def dump_tail():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    # Get raw connection to verify schema and data directly
    # But db.get_all_draws uses the wrapper. Let's trust the manager first.
    
    draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    
    print(f"Total Records: {len(draws)}")
    print("Last 10 Records:")
    for d in draws[-10:]:
        print(f"Draw: {d.get('draw_period', 'N/A')} | ID: {d.get('id', 'N/A')} | Date: {d.get('date', 'N/A')} | Nums: {d.get('numbers')}")

if __name__ == "__main__":
    dump_tail()
