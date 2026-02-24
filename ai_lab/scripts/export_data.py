#!/usr/bin/env python3
import sys
import os
import json

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def export_data():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    
    # Get all draws in chronological order
    draws_raw = db.get_all_draws(lottery_type='BIG_LOTTO')
    # db.get_all_draws returns newest first usually, but check
    # Many scripts use reversed(db.get_all_draws(...)) to get chrono order
    draws = [d['numbers'] for d in reversed(draws_raw)]
    
    output_path = os.path.join(project_root, 'ai_lab', 'data', 'real_biglotto.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(draws, f)
        
    print(f"Successfully exported {len(draws)} real draws to {output_path}")

if __name__ == "__main__":
    export_data()
