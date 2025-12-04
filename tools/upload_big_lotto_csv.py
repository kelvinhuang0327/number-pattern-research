#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接從 CSV 檔案上傳大樂透數據到資料庫
跳過前端，避免 payload 太大的問題
"""

import sys
import os
import csv
import sqlite3
import json
from pathlib import Path

# 資料庫路徑（後端）
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery-api', 'data', 'lottery.db')

def parse_csv_file(file_path):
    """解析 CSV 檔案（台灣彩券官方格式）"""
    draws = []

    with open(file_path, 'r', encoding='utf-8-sig') as f:
        # 跳過 BOM
        content = f.read()
        if content.startswith('\ufeff'):
            content = content[1:]

        lines = content.strip().split('\n')

        # 跳過標題行
        for i, line in enumerate(lines):
            if i == 0:  # 跳過標題
                continue

            parts = line.split(',')
            if len(parts) < 13:  # 至少要有 13 欄
                continue

            try:
                # 格式：遊戲名稱,期別,開獎日期,銷售總額,銷售注數,總獎金,獎號1-6,特別號
                draw = parts[1].strip()  # 期別（第2欄）
                date = parts[2].strip()  # 開獎日期（第3欄）

                # 號碼（第7-12欄）
                numbers = []
                for i in range(6, 12):  # 獎號1到獎號6
                    num = int(parts[i].strip())
                    numbers.append(num)

                # 特別號（第13欄）
                special = int(parts[12].strip())

                draws.append({
                    'draw': draw,
                    'date': date,
                    'lotteryType': 'BIG_LOTTO',
                    'numbers': numbers,
                    'special': special
                })
            except (ValueError, IndexError) as e:
                print(f"  ⚠️  跳過無效行: {line[:50]}... (錯誤: {e})")
                continue

    return draws

def insert_draws_to_db(draws):
    """插入數據到資料庫"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    duplicates = 0

    try:
        for draw in draws:
            try:
                numbers_json = json.dumps(draw['numbers'])

                cursor.execute("""
                    INSERT INTO draws (draw, date, lottery_type, numbers, special)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    draw['draw'],
                    draw['date'],
                    draw['lotteryType'],
                    numbers_json,
                    draw['special']
                ))
                inserted += 1

            except sqlite3.IntegrityError:
                # 重複記錄
                duplicates += 1
                continue

        conn.commit()
        print(f"\n✅ 插入成功: {inserted} 筆新數據")
        print(f"⚠️  重複跳過: {duplicates} 筆")
        print(f"📊 總計: {inserted + duplicates} 筆")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 插入失敗: {e}")
        raise
    finally:
        conn.close()

def main():
    print("=" * 60)
    print("📤 大樂透 CSV 上傳工具")
    print("=" * 60)
    print()

    # 尋找所有大樂透 CSV 檔案
    csv_path = Path('/Users/kelvin/Downloads/number')
    csv_files = []

    # 遞迴搜尋所有子資料夾
    print(f"🔍 搜尋目錄: {csv_path}")
    for file in csv_path.glob('**/大樂透*.csv'):
        # 排除「加開」檔案
        if '加開' not in file.name:
            csv_files.append(file)
            print(f"  ✓ 找到: {file.name}")

    print(f"\n📊 搜尋結果: 找到 {len(csv_files)} 個檔案")

    if not csv_files:
        print("❌ 找不到大樂透 CSV 檔案")
        print("請將檔案放在專案根目錄，檔名格式：大樂透_YYYY.csv")
        return

    print(f"📁 找到 {len(csv_files)} 個大樂透檔案：")
    for f in sorted(csv_files):
        print(f"  • {f.name}")
    print()

    # 解析所有檔案
    all_draws = []
    for csv_file in sorted(csv_files):
        print(f"📂 解析 {csv_file.name}...")
        draws = parse_csv_file(csv_file)
        all_draws.extend(draws)
        print(f"  ✓ 解析 {len(draws)} 筆")

    print(f"\n📊 總共解析: {len(all_draws)} 筆數據")

    # 插入資料庫
    print(f"\n📤 上傳到資料庫...")
    insert_draws_to_db(all_draws)

    # 驗證
    print(f"\n🔍 驗證資料庫...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM draws WHERE lottery_type = 'BIG_LOTTO'")
    count = cursor.fetchone()[0]
    conn.close()

    print(f"✅ 資料庫中大樂透數據: {count} 筆")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ 操作已中斷")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
