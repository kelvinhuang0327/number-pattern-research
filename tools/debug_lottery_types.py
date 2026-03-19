import sys
import os
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

def list_lottery_types():
    db_path = os.path.join(project_root, 'lottery-api/data/lottery_v2.db')
    try:
        db = DatabaseManager(db_path=db_path)
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT lottery_type FROM draws")
        rows = cursor.fetchall()
        print(f"Found {len(rows)} distinct lottery types:")
        for row in rows:
            print(f"- {row['lottery_type']}")
            
        # Also check count for BIG_LOTTO-like strings
        cursor.execute("SELECT lottery_type, count(*) as c FROM draws WHERE lottery_type LIKE '%BIG%' OR lottery_type LIKE '%Lotto%' GROUP BY lottery_type")
        print("\nBreakdown for 'Big'/'Lotto' types:")
        for row in cursor.fetchall():
             print(f"- {row['lottery_type']}: {row['c']}")

        conn.close()
    except Exception as e:
        print(f"Error accessing DB: {e}")

if __name__ == "__main__":
    list_lottery_types()
