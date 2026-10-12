#!/usr/bin/env bash
# =============================================================================
# scheduler_start.sh — 手動啟動 Betting-pool 排程服務
#
# 用法：bash scripts/launchd/scheduler_start.sh
# =============================================================================

set -euo pipefail

PLIST_DIR="${HOME}/Library/LaunchAgents"

LABELS=(
  "com.bettingpool.main"
  "com.bettingpool.orchestrator.worker-daemon"
  "com.bettingpool.orchestrator.copilot-daemon"
  "com.bettingpool.orchestrator.planner"
  "com.bettingpool.orchestrator.worker"
)

echo "▶ 啟動 Betting-pool 排程服務..."
for label in "${LABELS[@]}"; do
  plist="${PLIST_DIR}/${label}.plist"
  if [[ ! -f "${plist}" ]]; then
    echo "  ✗ plist 不存在，跳過：${label}"
    continue
  fi
  # 若已載入則先 unload，確保使用最新 plist
  launchctl unload "${plist}" 2>/dev/null || true
  # load -w 忽略 RunAtLoad=false，強制啟動
  launchctl load -w "${plist}" 2>/dev/null && echo "  ✓ 已啟動：${label}" || echo "  ✗ 啟動失敗：${label}"
done

echo ""
echo "=== 目前狀態 ==="
for label in "${LABELS[@]}"; do
  pid=$(launchctl list 2>/dev/null | grep "$label" | awk '{print $1}')
  if [[ "${pid}" != "-" && -n "${pid}" ]]; then
    echo "  ● RUNNING  pid=${pid}  ${label}"
  else
    echo "  ○ STOPPED             ${label}"
  fi
done
