#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用彩券數據上傳工具
支援所有彩券類型和格式：
- CSV: 大樂透、威力彩 (標準格式)
- TXT: 今彩539 (官方格式)
"""

import sys
import os
import re
import csv
import sqlite3
import json
from pathlib import Path

# 資料庫路徑
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery-api', 'data', 'lottery.db')

# 搜尋路徑
SEARCH_PATH = Path('/Users/kelvin/Downloads/number')

# 彩券規則配置
LOTTERY_RULES = {
    'BIG_LOTTO': {
        'name': '大樂透',
        'file_pattern': '大樂透*.csv',
        'exclude_pattern': '加開',
        'format': 'csv'
    },
    'POWER_LOTTO': {
        'name': '威力彩',
        'file_pattern': '威力彩*.csv',
        'exclude_pattern': '加開',
        'format': 'csv'
    },
    'DAILY_539': {
        'name': '今彩539',
        'file_pattern': '今彩539*.txt',
        'exclude_pattern': None,
        'format': 'txt'
    }
}

def parse_csv_file(file_path, lottery_type):
    """解析 CSV 檔案（台灣彩券官方格式）"""
    draws = []

    with open(file_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        if content.startswith('\ufeff'):
            content = content[1:]

        lines = content.strip().split('\n')

        for i, line in enumerate(lines):
            if i == 0:  # 跳過標題
                continue

            parts = line.split(',')
            if len(parts) < 13:
                continue

            try:
                draw = parts[1].strip()
                date = parts[2].strip()

                # 號碼（第7-12欄）
                numbers = []
                for i in range(6, 12):
                    num = int(parts[i].strip())
                    numbers.append(num)

                # 特別號（第13欄）
                special = int(parts[12].strip())

                draws.append({
                    'draw': draw,
                    'date': date,
                    'lotteryType': lottery_type,
                    'numbers': sorted(numbers),
                    'special': special
                })
            except (ValueError, IndexError) as e:
                print(f"  ⚠️  跳過無效行: {line[:50]}... (錯誤: {e})")
                continue

    return draws

def parse_txt_file(file_path, lottery_type):
    """解析 TXT 檔案（今彩539官方格式）"""
    draws = []

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines()]

    i = 0
    while i < len(lines):
        line = lines[i]

        if not line:
            i += 1
            continue

        if line.startswith('第') and '期' in line:
            try:
                # 期號
                draw_match = re.search(r'第(\d+)期', line)
                if not draw_match:
                    i += 1
                    continue
                draw = draw_match.group(1)

                # 日期
                i += 1
                if i >= len(lines):
                    break

                date_line = lines[i]
                date_match = re.search(r'開獎日期:(\d+)/(\d+)/(\d+)', date_line)
                if not date_match:
                    i += 1
                    continue

                # 轉換民國年為西元年
                roc_year = int(date_match.group(1))
                month = date_match.group(2).zfill(2)
                day = date_match.group(3).zfill(2)
                ad_year = roc_year + 1911
                date_str = f"{ad_year}/{month}/{day}"

                # 跳過兩行（大小順序、開出順序）
                i += 2

                # 號碼
                i += 1
                if i >= len(lines):
                    break

                numbers_line = lines[i]
                if len(numbers_line) != 10:
                    i += 1
                    continue

                numbers = []
                for j in range(0, 10, 2):
                    num_str = numbers_line[j:j+2]
                    num = int(num_str)
                    numbers.append(num)

                if len(numbers) == 5 and len(set(numbers)) == 5:
                    draws.append({
                        'draw': draw,
                        'date': date_str,
                        'lotteryType': lottery_type,
                        'numbers': sorted(numbers),
                        'special': None
                    })

            except Exception as e:
                print(f"  ⚠️  解析錯誤: {line[:50]}... (錯誤: {e})")

        i += 1

    return draws

def insert_draws_to_db(draws):
    """插入數據到資料庫"""
    if not draws:
        return 0, 0

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
                duplicates += 1
                continue

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 插入失敗: {e}")
        raise
    finally:
        conn.close()

    return inserted, duplicates

def process_lottery_type(lottery_type, rules):
    """處理特定彩券類型"""
    print(f"\n{'='*60}")
    print(f"📋 處理: {rules['name']}")
    print(f"{'='*60}")

    # 搜尋檔案
    files = []
    for file in SEARCH_PATH.glob(f"**/{rules['file_pattern']}"):
        if rules['exclude_pattern'] and rules['exclude_pattern'] in file.name:
            continue
        files.append(file)
        print(f"  ✓ 找到: {file.name}")

    if not files:
        print(f"  ⚠️  未找到 {rules['name']} 檔案")
        return 0, 0

    print(f"\n📊 找到 {len(files)} 個檔案")

    # 解析檔案
    all_draws = []
    for file in sorted(files):
        print(f"📂 解析 {file.name}...")

        if rules['format'] == 'csv':
            draws = parse_csv_file(file, lottery_type)
        else:
            draws = parse_txt_file(file, lottery_type)

        all_draws.extend(draws)
        print(f"  ✓ 解析 {len(draws)} 筆")

    print(f"\n📊 總共解析: {len(all_draws)} 筆數據")

    if not all_draws:
        print("  ⚠️  沒有成功解析任何數據")
        return 0, 0

    # 插入資料庫
    print(f"📤 上傳到資料庫...")
    inserted, duplicates = insert_draws_to_db(all_draws)

    print(f"  ✅ 新增: {inserted} 筆")
    print(f"  ⚠️  重複: {duplicates} 筆")
    print(f"  📊 總計: {inserted + duplicates} 筆")

    return inserted, duplicates

def main():
    print("=" * 60)
    print("📤 彩券數據上傳工具")
    print("=" * 60)
    print(f"搜尋目錄: {SEARCH_PATH}")
    print()

    if not SEARCH_PATH.exists():
        print(f"❌ 目錄不存在: {SEARCH_PATH}")
        return

    total_inserted = 0
    total_duplicates = 0

    # 處理每種彩券類型
    for lottery_type, rules in LOTTERY_RULES.items():
        inserted, duplicates = process_lottery_type(lottery_type, rules)
        total_inserted += inserted
        total_duplicates += duplicates

    # 總結
    print(f"\n{'='*60}")
    print(f"✅ 上傳完成")
    print(f"{'='*60}")
    print(f"總新增: {total_inserted} 筆")
    print(f"總重複: {total_duplicates} 筆")
    print(f"總處理: {total_inserted + total_duplicates} 筆")
    print()

    # 驗證資料庫
    print(f"🔍 驗證資料庫...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for lottery_type, rules in LOTTERY_RULES.items():
        cursor.execute("SELECT COUNT(*) FROM draws WHERE lottery_type = ?", (lottery_type,))
        count = cursor.fetchone()[0]
        print(f"  {rules['name']}: {count} 筆")

    cursor.execute("SELECT COUNT(*) FROM draws")
    total = cursor.fetchone()[0]
    print(f"  總計: {total} 筆")

    conn.close()
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
