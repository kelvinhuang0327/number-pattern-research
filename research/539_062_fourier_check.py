
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import _539_fourier_scores

def check_062_fourier():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    hb = [d for d in history if int(d['draw']) < 115000062]
    sc = _539_fourier_scores(hb)
    
    sorted_f = sorted(sc.items(), key=lambda x: -x[1])[:30]
    print("Top 30 Fourier for 062:")
    for i, (n, s) in enumerate(sorted_f):
        print(f"Rank {i+1}: {n:02d} (Score: {s:.3f})")

    missing = [11, 12, 14, 17, 32]
    print("\nRanks of 062 numbers in Fourier:")
    all_sorted = sorted(sc.keys(), key=lambda n: -sc[n])
    for n in missing:
        rank = all_sorted.index(n) + 1
        print(f"Number {n:02d}: Rank {rank}")

if __name__ == "__main__":
    check_062_fourier()
