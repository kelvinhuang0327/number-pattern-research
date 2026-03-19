import sys
import os

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def update_db():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    
    # Check if draw exists
    draw_id = "115000002"
    existing = None
    all_draws = db.get_all_draws('BIG_LOTTO')
    for d in all_draws:
        if d['draw'] == draw_id:
            existing = d
            break
            
    if existing:
        print(f"Draw {draw_id} already exists. Skipping.")
        return

    # Insert new draw
    try:
        import json
        date = "2026-01-06" 
        numbers = [2, 23, 33, 38, 39, 45]
        numbers_json = json.dumps(numbers) # Ensure JSON format
        special = 6
        
        query = """
        INSERT INTO draws (lottery_type, draw, date, numbers, special)
        VALUES (?, ?, ?, ?, ?)
        """
        
        # Access internal connection for manual insert
        conn = db._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(query, ('BIG_LOTTO', draw_id, date, numbers_json, special))
        conn.commit()
        print(f"✅ Successfully inserted Draw {draw_id}: {numbers} Special: {special}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_db()
