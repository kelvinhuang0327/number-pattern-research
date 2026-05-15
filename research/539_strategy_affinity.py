
import os
import sys
import numpy as np
import pandas as pd
from collections import Counter

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def analyze_number_strategy_affinity():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    n_days = 1000
    affinities = {n: Counter() for n in range(1, 40)}
    
    for i in range(len(history) - n_days, len(history)):
        curr = set(history[i]['numbers'])
        prev = set(history[i-1]['numbers'])
        
        # Strategies for EACH number in the winning set
        for n in curr:
            # Did it echo?
            if n in prev: affinities[n]['Echo'] += 1
            # Was it cold? (Gap > 15)
            gap = 0
            for d in reversed(history[:i]):
                if n in d['numbers']: break
                gap += 1
            if gap > 15: affinities[n]['Cold'] += 1
            # Was it a neighbor?
            if (n-1 in prev) or (n+1 in prev): affinities[n]['Neighbor'] += 1

    res = []
    for n in range(1, 40):
        total = sum(affinities[n].values())
        res.append({
            'num': n,
            'Echo_Prob': (affinities[n]['Echo'] / total if total > 0 else 0),
            'Cold_Prob': (affinities[n]['Cold'] / total if total > 0 else 0),
            'Neighbor_Prob': (affinities[n]['Neighbor'] / total if total > 0 else 0),
            'Total_Strat_Hits': total
        })
        
    df = pd.DataFrame(res)
    print("Number Strategy Affinities:")
    print(df.sort_values('Echo_Prob', ascending=False).head(5))
    print(df.sort_values('Cold_Prob', ascending=False).head(5))

    # Match 062 numbers
    print("\n062 Numbers Affinity:")
    print(df[df['num'].isin([11, 12, 14, 17, 32])])

if __name__ == "__main__":
    analyze_number_strategy_affinity()
