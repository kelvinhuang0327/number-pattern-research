#!/usr/bin/env python3
import os
import sys
import sqlite3
import json
from pathlib import Path


def _repo_root():
    return Path(__file__).resolve().parent.parent


def _canonical_db_path():
    return _repo_root() / "lottery_api" / "data" / "lottery_v2.db"


def _resolve_db_path(db_path=None):
    candidate = _canonical_db_path() if db_path is None else Path(db_path)
    if db_path is not None and not candidate.is_absolute():
        raise ValueError("db_path must be absolute; use None for the canonical lottery_v2.db")
    if not candidate.exists():
        raise FileNotFoundError(f"Lottery DB path does not exist: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Lottery DB path is not a regular file: {candidate}")
    return str(candidate)

def sync_main_db():
    db_path = _resolve_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Data to sync
    updates = [
        ('115000001', 'BIG_LOTTO', '2026-01-02', '[3, 7, 16, 19, 40, 42]', 12),
        ('115000002', 'BIG_LOTTO', '2026-01-06', '[2, 23, 33, 38, 39, 45]', 6),
        ('115000003', 'BIG_LOTTO', '2026-01-09', '[1, 7, 13, 14, 34, 45]', 8)
    ]
    
    print("🛠️ Syncing 2026 Data to Main 'draws' Table...")
    
    for draw, l_type, date, nums, special in updates:
        # Check if exists in main table
        c.execute("SELECT id FROM draws WHERE draw = ? AND lottery_type = ?", (draw, l_type))
        exists = c.fetchone()
        
        if exists:
            print(f"Updating Main Table Draw {draw}...")
            c.execute("""UPDATE draws 
                         SET date=?, numbers=?, special=? 
                         WHERE draw=? AND lottery_type=?""",
                      (date, nums, special, draw, l_type))
        else:
            print(f"Inserting Main Table Draw {draw}...")
            c.execute("""INSERT INTO draws (draw, lottery_type, date, numbers, special) 
                         VALUES (?, ?, ?, ?, ?)""",
                      (draw, l_type, date, nums, special))
            
    conn.commit()
    conn.close()
    print("✅ Main Database Sync Complete.")

if __name__ == "__main__":
    sync_main_db()
