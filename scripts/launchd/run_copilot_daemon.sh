#!/usr/bin/env bash
# Betting-pool Copilot Daemon launch script (for launchd LaunchAgent)
# 必須以 LaunchAgent 執行（非 LaunchDaemon），以存取 macOS keychain

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${PROJECT_ROOT}/scripts/launchd/common.sh"
ensure_runtime_dirs

mkdir -p "${RUNTIME_ROOT}/locks"

DAEMON_STDOUT="${LAUNCHD_LOG_ROOT}/copilot_daemon.out.log"
DAEMON_STDERR="${LAUNCHD_LOG_ROOT}/copilot_daemon.err.log"

PYTHON="${PROJECT_ROOT}/.venv/bin/python"

exec "${PYTHON}" "${PROJECT_ROOT}/orchestrator/copilot_daemon.py" \
    --poll-seconds 10 \
    >> "${DAEMON_STDOUT}" 2>> "${DAEMON_STDERR}"
