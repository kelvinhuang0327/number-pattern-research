"""
Data Loader - 從SQLite讀取大樂透歷史數據
"""
import sqlite3
import json
import numpy as np
import os

from pathlib import Path


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'lottery_api', 'data', 'lottery_v2.db')

def load_big_lotto_draws(db_path=None):
    """載入所有大樂透開獎記錄，回傳 numpy array (N, 6)"""
    _p291u_db_path = _p291u_resolve_db_path(db_path)
    path = db_path or DB_PATH
    conn = _p291u_connect_resolved(_p291u_db_path)
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
