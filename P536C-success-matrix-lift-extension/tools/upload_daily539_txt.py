#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接從 TXT 檔案上傳今彩539數據到資料庫
支援今彩539官方格式
"""

import sys
import os
import re
import sqlite3
import json
from pathlib import Path

# 資料庫路徑（後端）
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'lottery.db')

def parse_txt_file(file_path):
    """解析 TXT 檔案（今彩539官方格式）"""
    draws = []

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines()]

    i = 0
    while i < len(lines):
        line = lines[i]

        # 跳過空行
        if not line:
            i += 1
            continue

        # 解析一筆記錄（5行一組）
        if line.startswith('第') and '期' in line:
            try:
                # 第1行：期號
                draw_match = re.search(r'第(\d+)期', line)
                if not draw_match:
                    print(f"  ⚠️  期號格式錯誤: {line}")
                    i += 1
                    continue
                draw = draw_match.group(1)

                # 第2行：開獎日期
                i += 1
                if i >= len(lines):
                    print(f"  ⚠️  期號 {draw} 缺少開獎日期")
                    break

                date_line = lines[i]
                date_match = re.search(r'開獎日期:(\d+)/(\d+)/(\d+)', date_line)
                if not date_match:
                    print(f"  ⚠️  日期格式錯誤: {date_line}")
                    i += 1
                    continue

                # 轉換民國年為西元年
                roc_year = int(date_match.group(1))
                month = date_match.group(2).zfill(2)
                day = date_match.group(3).zfill(2)
                ad_year = roc_year + 1911
                date_str = f"{ad_year}/{month}/{day}"

                # 第3行：大小順序（跳過）
                i += 1

                # 第4行：開出順序（跳過）
                i += 1

                # 第5行：號碼
                i += 1
                if i >= len(lines):
                    print(f"  ⚠️  期號 {draw} 缺少號碼數據")
                    break

                numbers_line = lines[i]
                if len(numbers_line) != 10:  # 今彩539是5個號碼，每個2位數
                    print(f"  ⚠️  期號 {draw} 號碼長度錯誤: {numbers_line}")
                    i += 1
                    continue

                # 每2個字元為一個號碼
                numbers = []
                for j in range(0, 10, 2):
                    num_str = numbers_line[j:j+2]
                    try:
                        num = int(num_str)
                        if not (1 <= num <= 39):
                            print(f"  ⚠️  期號 {draw} 號碼 {num} 超出範圍 (1-39)")
                            continue
                        numbers.append(num)
                    except ValueError:
                        print(f"  ⚠️  期號 {draw} 號碼格式錯誤: {num_str}")
                        continue

                if len(numbers) == 5 and len(set(numbers)) == 5:
                    draws.append({
                        'draw': draw,
                        'date': date_str,
                        'lotteryType': 'DAILY_539',
                        'numbers': sorted(numbers),
                        'special': None
                    })
                else:
                    print(f"  ⚠️  期號 {draw} 號碼數量或重複問題")

            except Exception as e:
                print(f"  ⚠️  解析錯誤: {line[:50]}... (錯誤: {e})")

        i += 1

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
    print("📤 今彩539 TXT 上傳工具")
    print("=" * 60)
    print()

    # 尋找所有今彩539 TXT 檔案
    txt_path = Path('/Users/kelvin/Downloads/number')
    txt_files = []

    # 遞迴搜尋所有子資料夾
    print(f"🔍 搜尋目錄: {txt_path}")
    for file in txt_path.glob('**/今彩539*.txt'):
        txt_files.append(file)
        print(f"  ✓ 找到: {file.name}")

    print(f"\n📊 搜尋結果: 找到 {len(txt_files)} 個檔案")

    if not txt_files:
        print("❌ 找不到今彩539 TXT 檔案")
        print("請將檔案放在 /Users/kelvin/Downloads/number 目錄下")
        print("檔名格式：今彩539_YYYY_MM.txt")
        return

    print(f"📁 找到 {len(txt_files)} 個今彩539檔案：")
    for f in sorted(txt_files):
        print(f"  • {f.name}")
    print()

    # 解析所有檔案
    all_draws = []
    for txt_file in sorted(txt_files):
        print(f"📂 解析 {txt_file.name}...")
        draws = parse_txt_file(txt_file)
        all_draws.extend(draws)
        print(f"  ✓ 解析 {len(draws)} 筆")

    print(f"\n📊 總共解析: {len(all_draws)} 筆數據")

    if not all_draws:
        print("❌ 沒有成功解析任何數據")
        return

    # 插入資料庫
    print(f"\n📤 上傳到資料庫...")
    insert_draws_to_db(all_draws)

    # 驗證
    print(f"\n🔍 驗證資料庫...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM draws WHERE lottery_type = 'DAILY_539'")
    count = cursor.fetchone()[0]
    conn.close()

    print(f"✅ 資料庫中今彩539數據: {count} 筆")
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
