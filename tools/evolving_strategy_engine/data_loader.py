"""
Data Loader - 從SQLite讀取大樂透歷史數據
"""
import sqlite3
import json
import numpy as np
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'lottery_api', 'data', 'lottery_v2.db')

def load_big_lotto_draws(db_path=None):
    """載入所有大樂透開獎記錄，回傳 numpy array (N, 6)"""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("""
        SELECT draw, date, numbers, special 
        FROM draws 
        WHERE lottery_type='BIG_LOTTO' 
        ORDER BY id ASC
    """)
    rows = c.fetchall()
    conn.close()
    
    draws = []
    meta = []
    for draw_id, date, nums_str, special in rows:
        try:
            nums = json.loads(nums_str)
            if len(nums) == 6 and all(1 <= n <= 49 for n in nums):
                draws.append(sorted(nums))
                meta.append({'draw': draw_id, 'date': date, 'special': special})
        except:
            continue
    
    return np.array(draws, dtype=np.int32), meta


def build_binary_matrix(draws):
    """轉換為二元矩陣 (N, 49) - 每個號碼是否出現"""
    N = len(draws)
    mat = np.zeros((N, 49), dtype=np.int8)
    for i, draw in enumerate(draws):
        for n in draw:
            mat[i, n - 1] = 1
    return mat


def compute_gaps(draws):
    """計算每個號碼的間隔期數矩陣"""
    binary = build_binary_matrix(draws)
    N, K = binary.shape
    gaps = np.full((N, K), -1, dtype=np.int32)
    last_seen = np.full(K, -1, dtype=np.int32)
    
    for i in range(N):
        for j in range(K):
            if last_seen[j] >= 0:
                gaps[i, j] = i - last_seen[j]
            if binary[i, j]:
                last_seen[j] = i
    return gaps


if __name__ == '__main__':
    draws, meta = load_big_lotto_draws()
    print(f"Loaded {len(draws)} Big Lotto draws")
    print(f"Latest: Draw {meta[-1]['draw']} on {meta[-1]['date']}: {draws[-1]}")
    print(f"Range: {meta[0]['draw']} ~ {meta[-1]['draw']}")
