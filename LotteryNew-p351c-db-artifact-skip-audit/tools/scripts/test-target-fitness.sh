#!/bin/bash

echo "🎯 測試目標適應度早停功能"
echo "================================"
echo ""

# 測試 1: 設定目標適應度為 5%
echo "📌 測試 1: 設定目標適應度為 5%"
curl -s -X POST http://127.0.0.1:5001/api/auto-learning/set-target-fitness \
  -H "Content-Type: application/json" \
  -d '{"target_fitness": 0.05}' | python3 -m json.tool
echo ""

# 測試 2: 查看狀態
echo "📌 測試 2: 查看當前狀態"
curl -s http://127.0.0.1:5001/api/auto-learning/schedule/status | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"目標適應度: {data.get('target_fitness', 'None')}\")
print(f\"排程狀態: {data.get('is_running', False)}\")
print(f\"優化中: {data.get('is_optimizing', False)}\")
"
echo ""

# 測試 3: 禁用目標適應度
echo "📌 測試 3: 禁用目標適應度（null）"
curl -s -X POST http://127.0.0.1:5001/api/auto-learning/set-target-fitness \
  -H "Content-Type: application/json" \
  -d '{"target_fitness": null}' | python3 -m json.tool
echo ""

# 測試 4: 再次查看狀態
echo "📌 測試 4: 確認已禁用"
curl -s http://127.0.0.1:5001/api/auto-learning/schedule/status | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"目標適應度: {data.get('target_fitness', 'None')}\")
"
echo ""

echo "✅ 測試完成！"
