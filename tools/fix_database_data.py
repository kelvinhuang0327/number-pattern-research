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

def fix_db():
    db_path = _resolve_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # User provided data
    # 115000001	大樂透	2026/01/02	03 07 16 19 40 42	12
    # 115000002	大樂透	2026/01/06	02 23 33 38 39 45	06
    # 115000003	大樂透	2026/01/09	01 07 13 14 34 45	08
    
    updates = [
        (115000001, '2026-01-02', '3,7,16,19,40,42', 12),
        (115000002, '2026-01-06', '2,23,33,38,39,45', 6),
        (115000003, '2026-01-09', '1,7,13,14,34,45', 8)
    ]
    
    print("🛠️ Patching Database with 2026 Data...")
    
    # Check if table exists and schema
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='big_lotto_draws'")
    if not c.fetchone():
        print("Creating big_lotto_draws table...")
        c.execute('''CREATE TABLE IF NOT EXISTS big_lotto_draws (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        draw_period INTEGER,
                        date TEXT,
                        winning_numbers TEXT,
                        special_number INTEGER
                    )''')
    
    for draw_id, date, nums, special in updates:
        # Check if exists
        c.execute("SELECT id FROM big_lotto_draws WHERE draw_period = ?", (draw_id,))
        exists = c.fetchone()
        
        if exists:
            print(f"Updating Draw {draw_id}...")
            c.execute("UPDATE big_lotto_draws SET date=?, winning_numbers=?, special_number=? WHERE draw_period=?",
                      (date, nums, special, draw_id))
        else:
            print(f"Inserting Draw {draw_id}...")
            c.execute("INSERT INTO big_lotto_draws (draw_period, date, winning_numbers, special_number) VALUES (?, ?, ?, ?)",
                      (draw_id, date, nums, special))
            
    conn.commit()
    conn.close()
    print("✅ Database patch complete.")

if __name__ == "__main__":
    fix_db()
