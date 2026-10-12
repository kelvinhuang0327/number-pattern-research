#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理資料庫 - 僅保留大樂透數據
刪除所有非大樂透的彩券數據（包括大樂透加開）
"""

import sqlite3
import os
import sys

# 資料庫路徑
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery.db')

def clean_database():
    """清理資料庫，只保留大樂透數據"""

    if not os.path.exists(DB_PATH):
        print(f"❌ 資料庫不存在: {DB_PATH}")
        return

    print("=" * 60)
    print("🗄️  資料庫清理工具 - 僅保留大樂透數據")
    print("=" * 60)
    print()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 查詢當前數據統計
    print("📊 當前數據統計：")
    print("-" * 60)

    cursor.execute("""
        SELECT lottery_type, COUNT(*) as count
        FROM draws
        GROUP BY lottery_type
        ORDER BY count DESC
    """)

    stats_before = {}
    total_before = 0

    for row in cursor.fetchall():
        lottery_type = row[0]
        count = row[1]
        stats_before[lottery_type] = count
        total_before += count
        print(f"  {lottery_type}: {count:,} 筆")

    print(f"\n  總計: {total_before:,} 筆")
    print()

    # 2. 確認要刪除的類型
    types_to_keep = ['BIG_LOTTO']  # 只保留大樂透
    types_to_delete = [t for t in stats_before.keys() if t not in types_to_keep]

    if not types_to_delete:
        print("✅ 資料庫已經是乾淨的（只有大樂透數據）")
        conn.close()
        return

    print("🗑️  將刪除以下彩券類型：")
    print("-" * 60)
    delete_count = 0
    for lottery_type in types_to_delete:
        count = stats_before[lottery_type]
        delete_count += count
        print(f"  ❌ {lottery_type}: {count:,} 筆")

    print(f"\n  將刪除總計: {delete_count:,} 筆")
    print()

    # 3. 確認操作
    print("⚠️  此操作無法復原！")
    response = input("確定要繼續嗎？ (yes/no): ").strip().lower()

    if response not in ['yes', 'y']:
        print("\n❌ 操作已取消")
        conn.close()
        return

    print()
    print("🔧 開始清理...")

    # 4. 執行刪除
    for lottery_type in types_to_delete:
        cursor.execute("""
            DELETE FROM draws WHERE lottery_type = ?
        """, (lottery_type,))
        print(f"  ✓ 已刪除 {lottery_type}")

    # 5. 提交更改
    conn.commit()

    # 6. 清理資料庫（VACUUM）
    print("\n🧹 壓縮資料庫...")
    cursor.execute("VACUUM")

    # 7. 查詢清理後統計
    print("\n📊 清理後數據統計：")
    print("-" * 60)

    cursor.execute("""
        SELECT lottery_type, COUNT(*) as count
        FROM draws
        GROUP BY lottery_type
        ORDER BY count DESC
    """)

    stats_after = {}
    total_after = 0

    for row in cursor.fetchall():
        lottery_type = row[0]
        count = row[1]
        stats_after[lottery_type] = count
        total_after += count
        print(f"  {lottery_type}: {count:,} 筆")

    print(f"\n  總計: {total_after:,} 筆")
    print()

    # 8. 顯示結果
    print("=" * 60)
    print("✅ 清理完成！")
    print("=" * 60)
    print(f"刪除前: {total_before:,} 筆")
    print(f"刪除後: {total_after:,} 筆")
    print(f"已刪除: {total_before - total_after:,} 筆 ({((total_before - total_after) / total_before * 100):.1f}%)")
    print()

    # 9. 顯示資料庫大小
    db_size = os.path.getsize(DB_PATH)
    print(f"資料庫大小: {db_size / 1024:.1f} KB")
    print()

    conn.close()

if __name__ == '__main__':
    try:
        clean_database()
    except KeyboardInterrupt:
        print("\n\n❌ 操作已中斷")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
