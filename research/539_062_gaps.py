
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def get_062_gaps():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    target_nums = [11, 12, 14, 17, 32]
    
    # Draw 062 is at some index
    idx_062 = -1
    for i, d in enumerate(history):
        if d['draw'] == 115000062:
            idx_062 = i
            break
            
    if idx_062 == -1:
        print("Draw 115000062 not found in DB.")
        # Try to find the latest
        idx_062 = len(history)
        print(f"Analyzing for NEXT draw after {history[-1]['draw']}")
    else:
        print(f"Found Draw 062 at index {idx_062}. Historical analysis:")

    last_seen = {}
    for i in range(idx_062):
        for n in history[i]['numbers']:
            last_seen[n] = i
            
    print("\nGaps for Draw 062 numbers:")
    for n in target_nums:
        last = last_seen.get(n, -1)
        gap = (idx_062 - 1 - last) if last != -1 else 999
        print(f"Number {n:02d}: Gap {gap}")

if __name__ == "__main__":
    get_062_gaps()
