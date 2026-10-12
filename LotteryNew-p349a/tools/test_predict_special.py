#!/usr/bin/env python3
"""測試後端預測是否包含特別號碼"""

import requests
import json

url = "http://127.0.0.1:5001/api/predict"

payload = {
    "history": [
        {"draw": "114000001", "date": "2025-01-01", "numbers": [1, 10, 15, 23, 30, 42], "special": 35},
        {"draw": "114000002", "date": "2025-01-04", "numbers": [5, 12, 18, 27, 33, 49], "special": 8},
        {"draw": "114000003", "date": "2025-01-08", "numbers": [2, 9, 17, 24, 31, 45], "special": 12}
    ],
    "lotteryRules": {
        "pickCount": 6,
        "minNumber": 1,
        "maxNumber": 49,
        "hasSpecialNumber": True,
        "specialMinNumber": 1,
        "specialMaxNumber": 49
    },
    "method": "frequency"
}

print("🧪 測試後端預測是否包含特別號碼...\n")

try:
    response = requests.post(url, json=payload, timeout=10)
    result = response.json()

    print("📊 預測結果:")
    print(f"主號碼: {result.get('numbers')}")
    print(f"特別號碼: {result.get('special')}")
    print(f"方法: {result.get('method')}")
    print(f"信心度: {result.get('confidence')}")
    print()

    if 'special' in result and result['special'] is not None:
        print(f"✅ 成功！後端返回了特別號碼: {result['special']}")
    else:
        print("❌ 失敗！後端沒有返回特別號碼")
        print("\n完整響應:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

except Exception as e:
    print(f"❌ 請求失敗: {e}")
    print("\n請確認後端服務運行正常: http://127.0.0.1:5001")
