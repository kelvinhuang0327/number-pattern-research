#!/usr/bin/env python3
"""
將威力彩 115000005 期實際開獎數據加入數據庫
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    
    # 威力彩 115000005 期實際開獎數據
    draw_data = {
        'draw': '115000005',
        'date': '2026-01-15',  # 115/01/15 = 2026-01-15
        'lottery_type': 'POWER_LOTTO',
        'numbers': [8, 10, 16, 26, 31, 38],
        'special': 5
    }
    
    print(f"正在插入第 {draw_data['draw']} 期數據...")
    print(f"  第一區: {draw_data['numbers']}")
    print(f"  第二區: {draw_data['special']}")
    
    result = db.insert_draws([draw_data])
    print(f"插入結果: {result}")
    print("✓ 數據插入完成")

if __name__ == '__main__':
    main()
