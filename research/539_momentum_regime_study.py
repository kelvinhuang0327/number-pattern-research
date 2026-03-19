
import os
import sys
import numpy as np
from collections import Counter
import pandas as pd

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def calculate_regime_metrics(history, window=10):
    """
    計算滾動窗口內的序列性指標：
    1. Repetition Rate (回頭號率): 本期與上期重複的號碼比例
    2. Neighbor Rate (鄰號率): 本期是上期號碼 +/- 1 的比例
    3. Zone Concentration (區域集中度): 號碼是否集中在 1-13, 14-26, 27-39 其中之一
    4. Odd/Even Ratio Stability (奇偶比穩定性)
    """
    metrics = []
    
    for i in range(1, len(history)):
        curr = set(history[i]['numbers'])
        prev = set(history[i-1]['numbers'])
        
        # 1. Repetition
        repeats = len(curr & prev)
        
        # 2. Neighbor
        prev_neighbors = set()
        for n in prev:
            for d in [-1, 1]:
                nn = n + d
                if 1 <= nn <= 39:
                    prev_neighbors.add(nn)
        neighbors = len(curr & prev_neighbors)
        
        # 3. Zone
        zones = [0, 0, 0] # 1-13, 14-26, 27-39
        for n in curr:
            if n <= 13: zones[0] += 1
            elif n <= 26: zones[1] += 1
            else: zones[2] += 1
        max_zone_count = max(zones)
        
        metrics.append({
            'draw': history[i]['draw'],
            'repeats': repeats,
            'neighbors': neighbors,
            'max_zone': max_zone_count,
            'date': history[i]['date']
        })
        
    df = pd.DataFrame(metrics)
    # 計算滾動平均
    df['rolling_repeats'] = df['repeats'].rolling(window=window).mean()
    df['rolling_neighbors'] = df['neighbors'].rolling(window=window).mean()
    df['rolling_max_zone'] = df['max_zone'].rolling(window=window).mean()
    
    return df

def analyze_539_momentum():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    print(f"Total draws: {len(history)}")
    
    df = calculate_regime_metrics(history, window=10)
    
    # 查找特定期號 115000062 的背景
    target_draw = '115000062'
    # 注意：如果資料庫還沒更新到 115000062，我們計算到最新的
    
    print("\n=== 最近 20 期序列性指標監控 ===")
    print(df.tail(20)[['draw', 'repeats', 'neighbors', 'max_zone', 'rolling_repeats', 'rolling_neighbors']])
    
    # 分析回頭號 (Repeats) 的分佈
    print("\n=== 回頭號出現頻率分佈 (全歷史) ===")
    print(df['repeats'].value_counts(normalize=True).sort_index())
    
    # 分析動量態勢：當 rolling_repeats > 1.0 時，是否代表進入「強序列區間」？
    high_momentum = df[df['rolling_repeats'] > 1.0]
    print(f"\n強動量區間比例 (Rolling Repeats > 1.0): {len(high_momentum)/len(df):.2%}")
    
    # 儲存結果供後續參考
    output_path = os.path.join(project_root, 'research', '539_momentum_stats.csv')
    df.to_csv(output_path, index=False)
    print(f"\nStats saved to {output_path}")

if __name__ == "__main__":
    analyze_539_momentum()
