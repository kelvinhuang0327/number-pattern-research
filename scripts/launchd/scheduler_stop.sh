#!/usr/bin/env bash
# =============================================================================
# scheduler_stop.sh — 手動停止 Betting-pool 排程服務
#
# 用法：bash scripts/launchd/scheduler_stop.sh
# =============================================================================

set -euo pipefail

PLIST_DIR="${HOME}/Library/LaunchAgents"

LABELS=(
  "com.bettingpool.orchestrator.planner"
  "com.bettingpool.orchestrator.worker"
  "com.bettingpool.orchestrator.worker-daemon"
  "com.bettingpool.orchestrator.copilot-daemon"
  "com.bettingpool.main"
)

echo "■ 停止 Betting-pool 排程服務..."
for label in "${LABELS[@]}"; do
  plist="${PLIST_DIR}/${label}.plist"
  if [[ ! -f "${plist}" ]]; then
    echo "  - plist 不存在，跳過：${label}"
    continue
  fi
  launchctl unload "${plist}" 2>/dev/null && echo "  ✓ 已停止：${label}" || echo "  - 已是停止狀態：${label}"
  # 重新 load（不啟動）確保 launchd 記錄 RunAtLoad=false 的設定
  launchctl load "${plist}" 2>/dev/null || true
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
