#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=8002
FRONTEND_PORT=8081
BACKEND_PID_FILE="$ROOT_DIR/backend.pid"
FRONTEND_PID_FILE="$ROOT_DIR/frontend.pid"
ORCH_LAUNCHD_DOMAIN="gui/$(id -u)"

join_lines() {
    tr '\n' ' ' | sed 's/[[:space:]]\+$//'
}

stop_launchd_job() {
    local label="$1"
    if ! command -v launchctl >/dev/null 2>&1; then
        return
    fi
    launchctl bootout "$ORCH_LAUNCHD_DOMAIN/$label" >/dev/null 2>&1 || true
}

cd "$ROOT_DIR"

echo "======================================"
echo "🛑 停止 Lottery 服務..."
echo "======================================"

# 停止後台
if [ -f "$BACKEND_PID_FILE" ]; then
    PID="$(cat "$BACKEND_PID_FILE")"
    echo "停止後台服務 (PID: $PID)..."
    kill $PID 2>/dev/null || true
    rm -f "$BACKEND_PID_FILE"
fi

# 端口清理 (8002)
BACKEND_PID="$(lsof -ti:"$BACKEND_PORT" 2>/dev/null | join_lines || true)"
if [ -n "$BACKEND_PID" ]; then
    echo "清理端口 $BACKEND_PORT (PID: $BACKEND_PID)..."
    # shellcheck disable=SC2086
    kill -9 $BACKEND_PID 2>/dev/null || true
fi

# 停止前台
if [ -f "$FRONTEND_PID_FILE" ]; then
    PID="$(cat "$FRONTEND_PID_FILE")"
    echo "停止前台服務 (PID: $PID)..."
    kill $PID 2>/dev/null || true
    rm -f "$FRONTEND_PID_FILE"
fi

# 端口清理 (8081)
FRONTEND_PID="$(lsof -ti:"$FRONTEND_PORT" 2>/dev/null | join_lines || true)"
if [ -n "$FRONTEND_PID" ]; then
    echo "清理端口 $FRONTEND_PORT (PID: $FRONTEND_PID)..."
    # shellcheck disable=SC2086
    kill -9 $FRONTEND_PID 2>/dev/null || true
fi

echo "停止 Orchestrator 服務..."
stop_launchd_job "com.kelvin.lottery.copilot-daemon"
stop_launchd_job "com.kelvin.lottery.agent-planner"
stop_launchd_job "com.kelvin.lottery.agent-worker"
stop_launchd_job "com.kelvin.lottery.agent-light-worker"

echo "✅ 服務已停止。"
echo "======================================"
