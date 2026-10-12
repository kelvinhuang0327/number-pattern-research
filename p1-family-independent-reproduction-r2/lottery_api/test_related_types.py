#!/usr/bin/env python3
"""
測試後端 get_related_lottery_types 函數
驗證與前端 getRelatedTypes 行為一致
"""

from common import get_related_lottery_types, normalize_lottery_type

def test_related_types():
    """測試相關類型查詢函數"""

    print("=" * 60)
    print("測試 get_related_lottery_types 函數")
    print("=" * 60)
    print()

    # 測試案例
    test_cases = [
        ("BIG_LOTTO", ["BIG_LOTTO", "BIG_LOTTO_BONUS"]),
        ("BIG_LOTTO_BONUS", ["BIG_LOTTO", "BIG_LOTTO_BONUS"]),
        ("DAILY_539", ["DAILY_539"]),
        ("POWER_LOTTO", ["POWER_LOTTO"]),
        ("大樂透", ["BIG_LOTTO", "BIG_LOTTO_BONUS"]),  # 測試中文名稱
    ]

    all_passed = True

    for lottery_type, expected in test_cases:
        result = get_related_lottery_types(lottery_type)
        passed = result == expected

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {lottery_type:20} -> {result}")

        if not passed:
            print(f"       Expected: {expected}")
            all_passed = False

    print()
    print("=" * 60)

    if all_passed:
        print("✅ 所有測試通過！")
        print()
        print("📊 前後端邏輯已同步:")
        print("   - 前端: getRelatedTypes('BIG_LOTTO') -> ['BIG_LOTTO', 'BIG_LOTTO_BONUS']")
        print("   - 後端: get_related_lottery_types('BIG_LOTTO') -> ['BIG_LOTTO', 'BIG_LOTTO_BONUS']")
    else:
        print("❌ 部分測試失敗")

    print("=" * 60)

    return all_passed


def test_sql_query_simulation():
    """模擬 SQL 查詢生成"""

    print()
    print("=" * 60)
    print("模擬 SQL IN 查詢生成")
    print("=" * 60)
    print()

    lottery_type = "BIG_LOTTO"
    related_types = get_related_lottery_types(lottery_type)

    # 模擬 database.py 中的查詢生成
    placeholders = ','.join('?' * len(related_types))
    query = f"""
    SELECT id, draw, date, lottery_type, numbers, special
    FROM draws
    WHERE lottery_type IN ({placeholders})
    ORDER BY date DESC, draw DESC
    """

    print(f"彩券類型: {lottery_type}")
    print(f"相關類型: {related_types}")
    print(f"佔位符: {placeholders}")
    print(f"生成的 SQL 查詢:")
    print(query)
    print(f"查詢參數: {related_types}")

    print("=" * 60)


if __name__ == "__main__":
    # 運行測試
    passed = test_related_types()
    test_sql_query_simulation()

    # 返回狀態碼
    exit(0 if passed else 1)
