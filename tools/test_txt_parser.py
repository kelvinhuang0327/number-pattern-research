#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 TXT 格式解析功能
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lottery_api'))

from utils.csv_validator import csv_validator

def test_txt_file(file_path):
    """測試 TXT 檔案解析"""
    print("=" * 60)
    print(f"📋 測試檔案: {file_path}")
    print("=" * 60)

    with open(file_path, 'rb') as f:
        content = f.read()

    result = csv_validator.validate(content, 'DAILY_539', 'txt')

    print(f"\n✅ 驗證結果: {'通過' if result['valid'] else '失敗'}")
    print(f"\n📊 統計:")
    print(f"  總行數: {result['stats']['total_rows']}")
    print(f"  有效行數: {result['stats']['valid_rows']}")
    print(f"  錯誤行數: {result['stats']['error_rows']}")

    if result['errors']:
        print(f"\n❌ 錯誤列表:")
        for error in result['errors']:
            print(f"  行 {error['line']}: {error['message']}")

    if result['parsed_data']:
        print(f"\n✅ 解析數據 (顯示前 5 筆):")
        for i, draw in enumerate(result['parsed_data'][:5], 1):
            print(f"  {i}. 期號: {draw['draw']}, 日期: {draw['date']}, 號碼: {draw['numbers']}")

    print()
    return result

if __name__ == '__main__':
    file_path = '/Users/kelvin/Downloads/number/2025/今彩539_2025_12.txt'

    if not os.path.exists(file_path):
        print(f"❌ 檔案不存在: {file_path}")
        sys.exit(1)

    result = test_txt_file(file_path)

    if result['valid']:
        print("✅ 測試通過！")
        sys.exit(0)
    else:
        print("❌ 測試失敗！")
        sys.exit(1)
