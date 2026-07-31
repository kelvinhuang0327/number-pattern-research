#!/usr/bin/env python3
import os
import sys
import sqlite3
import json

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

def sync_main_db():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
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
