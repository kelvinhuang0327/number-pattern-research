#!/usr/bin/env python3
import sys
import os
import io

# Add project root and lottery-api to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    db_path = os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    
    print(f"{'Type':<15} | {'Latest Date':<15} | {'Draw No.':<15} | {'Count'}")
    print("-" * 65)
    
    for lotto in ['BIG_LOTTO', 'POWER_LOTTO', 'SUPER_LOTTO', 'DAILY_539']:
        try:
            # page=1, page_size=1, default order is date DESC
            res = db.get_draws(lottery_type=lotto, page=1, page_size=1)
            draws = res.get('draws', [])
            total = res.get('total', 0)
            
            if draws:
                latest = draws[0]
                print(f"{lotto:<15} | {latest['date']:<15} | {latest['draw']:<15} | {total}")
            else:
                print(f"{lotto:<15} | {'No data':<15} | {'-':<15} | 0")
        except Exception as e:
            print(f"{lotto:<15} | Error: {e}")

if __name__ == '__main__':
    main()
