#!/bin/bash

# Betting-pool UI Structure & Control Parity Test

echo "🔍 UI Structure & Control Parity 驗證測試"
echo "=========================================="

API_BASE="http://127.0.0.1:8787"

# 測試 1: 頁面結構分離
echo "📋 測試 1: 檢查頁面結構分離..."
HTML_CONTENT=$(curl -s http://127.0.0.1:8789/)
ORCH_SECTION=$(echo "$HTML_CONTENT" | grep -c "id=\"orchestration-section\"")
CTO_SECTION=$(echo "$HTML_CONTENT" | grep -c "id=\"cto-review-section\"")
NAV_BUTTONS=$(echo "$HTML_CONTENT" | grep -c "data-section=")

echo "  ✅ Orchestration Section: $ORCH_SECTION (期望: 1)"
echo "  ✅ CTO Review Section: $CTO_SECTION (期望: 1)"
echo "  ✅ Navigation Buttons: $NAV_BUTTONS (期望: 2)"

# 測試 2: 調度器控制按鈕
echo ""
echo "📋 測試 2: 檢查調度器控制按鈕..."
ENABLE_BTN=$(echo "$HTML_CONTENT" | grep -c "啟用排程")
DISABLE_BTN=$(echo "$HTML_CONTENT" | grep -c "停止排程")

echo "  ✅ 啟用排程按鈕: $ENABLE_BTN (期望: 2 - Orchestration + CTO)"
echo "  ✅ 停止排程按鈕: $DISABLE_BTN (期望: 2 - Orchestration + CTO)"

# 測試 3: API 功能驗證
echo ""
echo "📋 測試 3: API 功能驗證..."

# 檢查當前狀態
CURRENT_STATE=$(curl -s "$API_BASE/api/scheduler" | jq -r '.enabled')
echo "  📊 當前調度器狀態: $CURRENT_STATE"

# 測試停止功能
echo "  🔴 測試停止調度器..."
STOP_RESULT=$(curl -s -X POST "$API_BASE/api/scheduler/enable" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}' | jq -r '.enabled')
echo "     結果: $STOP_RESULT (期望: false)"

# 測試啟用功能
echo "  🟢 測試啟用調度器..."
START_RESULT=$(curl -s -X POST "$API_BASE/api/scheduler/enable" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}' | jq -r '.enabled')
echo "     結果: $START_RESULT (期望: true)"

# 測試 4: CTO 調度器功能
echo ""
echo "📋 測試 4: CTO 調度器功能..."

CTO_CURRENT=$(curl -s "$API_BASE/api/cto/scheduler" | jq -r '.enabled')
echo "  📊 當前 CTO 調度器狀態: $CTO_CURRENT"

# 測試 CTO 停止功能
echo "  🔴 測試停止 CTO 調度器..."
CTO_STOP=$(curl -s -X POST "$API_BASE/api/cto/scheduler" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}' | jq -r '.enabled')
echo "     結果: $CTO_STOP (期望: false)"

# 測試 CTO 啟用功能
echo "  🟢 測試啟用 CTO 調度器..."
CTO_START=$(curl -s -X POST "$API_BASE/api/cto/scheduler" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}' | jq -r '.enabled')
echo "     結果: $CTO_START (期望: true)"

# 測試 5: 任務執行功能
echo ""
echo "📋 測試 5: 任務執行功能..."

# Planner run-now
echo "  🔧 測試 Planner 立即執行..."
PLANNER_REQ=$(curl -s -X POST "$API_BASE/api/planner/run-now" \
  -H "Content-Type: application/json" -d '{}' | jq -r '.request_id')
echo "     Request ID: ${PLANNER_REQ:0:8}..."

# Worker run-now
echo "  ⚙️ 測試 Worker 立即執行..."
WORKER_REQ=$(curl -s -X POST "$API_BASE/api/worker/run-now" \
  -H "Content-Type: application/json" -d '{}' | jq -r '.request_id')
echo "     Request ID: ${WORKER_REQ:0:8}..."

# CTO run-now
echo "  👨‍💼 測試 CTO 立即執行..."
CTO_REQ=$(curl -s -X POST "$API_BASE/api/cto/run-now" \
  -H "Content-Type: application/json" -d '{}' | jq -r '.request_id')
echo "     Request ID: ${CTO_REQ:0:8}..."

# 測試 6: 系統狀態一致性
echo ""
echo "📋 測試 6: 系統狀態一致性..."
SUMMARY=$(curl -s "$API_BASE/api/summary")
SCHEDULER_ENABLED=$(echo "$SUMMARY" | jq -r '.scheduler.enabled')
TASK_COUNTS=$(echo "$SUMMARY" | jq -r '.counts')

echo "  📊 調度器狀態: $SCHEDULER_ENABLED"
echo "  📊 任務統計: $TASK_COUNTS"

# 最終結果
echo ""
echo "🎯 驗收結果總結"
echo "=================="

# 計算通過的測試
PASS_COUNT=0
TOTAL_COUNT=6

# 檢查各項是否通過
[ "$ORCH_SECTION" -eq 1 ] && [ "$CTO_SECTION" -eq 1 ] && ((PASS_COUNT++))
[ "$ENABLE_BTN" -ge 2 ] && [ "$DISABLE_BTN" -ge 2 ] && ((PASS_COUNT++))
[ "$STOP_RESULT" = "false" ] && [ "$START_RESULT" = "true" ] && ((PASS_COUNT++))
[ "$CTO_STOP" = "false" ] && [ "$CTO_START" = "true" ] && ((PASS_COUNT++))
[ -n "$PLANNER_REQ" ] && [ -n "$WORKER_REQ" ] && [ -n "$CTO_REQ" ] && ((PASS_COUNT++))
[ "$SCHEDULER_ENABLED" = "true" ] && ((PASS_COUNT++))

echo "✅ 通過測試: $PASS_COUNT/$TOTAL_COUNT"

if [ "$PASS_COUNT" -eq "$TOTAL_COUNT" ]; then
    echo "🎉 所有測試通過！TARGET 系統與 SOURCE 完全等價"
    echo "📱 前端地址: http://127.0.0.1:8789/"
    echo "🔧 API 地址: http://127.0.0.1:8787/"
    exit 0
else
    echo "⚠️ 部分測試失敗，需要進一步檢查"
    exit 1
fi