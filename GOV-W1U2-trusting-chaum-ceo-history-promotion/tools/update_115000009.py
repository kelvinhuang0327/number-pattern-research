import sys
import os
import json

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def update_db():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    
    # Check if draw exists
    draw_id = "115000009"
    
    # Insert new draw
    try:
        date = "2026/01/30"
        numbers = [9, 13, 27, 31, 32, 39]
        special = 19
        
        numbers_json = json.dumps(numbers)
        
        query = """
        INSERT INTO draws (draw, date, lottery_type, numbers, special)
        VALUES (?, ?, ?, ?, ?)
        """
        
        # Access internal connection for manual insert
        conn = db._get_connection()
        cursor = conn.cursor()
        
        # Check if already exists just in case
        cursor.execute("SELECT id FROM draws WHERE draw = ? AND lottery_type = 'BIG_LOTTO'", (draw_id,))
        if cursor.fetchone():
            print(f"Draw {draw_id} already exists. Skipping.")
            return

        cursor.execute(query, (draw_id, date, 'BIG_LOTTO', numbers_json, special))
        conn.commit()
        print(f"✅ Successfully inserted Draw {draw_id}: {numbers} Special: {special}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_db()
