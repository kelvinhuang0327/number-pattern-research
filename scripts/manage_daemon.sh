#!/usr/bin/env bash
# =============================================================================
# manage_daemon.sh — MLB Odds Capture Daemon Control Script
#
# Usage:
#   scripts/manage_daemon.sh install    # Copy plist → LaunchAgents + load
#   scripts/manage_daemon.sh uninstall  # Unload + remove plist
#   scripts/manage_daemon.sh start      # launchctl start (if already installed)
#   scripts/manage_daemon.sh stop       # launchctl stop (keeps installed)
#   scripts/manage_daemon.sh restart    # stop then start
#   scripts/manage_daemon.sh status     # Show running state + last capture
#   scripts/manage_daemon.sh logs       # Tail live log
# =============================================================================

set -euo pipefail

LABEL="com.mlb.odds_capture"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_SRC="${PROJECT_ROOT}/scripts/com.mlb.odds_capture.plist"
PLIST_DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
PID_FILE="${PROJECT_ROOT}/build/runtime_artifacts/odds_capture.pid"
LOG_FILE="${PROJECT_ROOT}/logs/odds_capture.log"
ERR_LOG="${PROJECT_ROOT}/logs/odds_capture_error.log"

# ── helpers ──────────────────────────────────────────────────────────────────

_is_loaded() {
    launchctl list | grep -q "${LABEL}" 2>/dev/null
}

_pid() {
    [[ -f "${PID_FILE}" ]] && cat "${PID_FILE}" || echo ""
}

_is_running() {
    local pid
    pid="$(_pid)"
    [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

_print_status() {
    echo "Label:     ${LABEL}"
    echo "Plist:     ${PLIST_DST} $([ -f "${PLIST_DST}" ] && echo '(installed)' || echo '(not installed)')"
    echo "Loaded:    $(_is_loaded && echo 'YES' || echo 'NO')"
    if _is_running; then
        echo "Process:   RUNNING (pid=$(_pid))"
    else
        echo "Process:   NOT RUNNING"
    fi
    if [[ -f "${LOG_FILE}" ]]; then
        echo "Last log:  $(tail -1 "${LOG_FILE}" 2>/dev/null || echo '(empty)')"
    fi
    if [[ -f "${PROJECT_ROOT}/data/mlb_context/odds_capture_schedule.json" ]]; then
        local last_run
        last_run=$(python3 -c "
import json
d=json.load(open('${PROJECT_ROOT}/data/mlb_context/odds_capture_schedule.json'))
print(d.get('last_run','unknown'))
" 2>/dev/null || echo "unknown")
        echo "Last run:  ${last_run}"
    fi
}

# ── commands ──────────────────────────────────────────────────────────────────

cmd_install() {
    echo "→ Installing launchd agent..."
    mkdir -p "$(dirname "${PLIST_DST}")"
    cp "${PLIST_SRC}" "${PLIST_DST}"
    # Unload first in case there's a stale entry
    launchctl unload "${PLIST_DST}" 2>/dev/null || true
    launchctl load -w "${PLIST_DST}"
    echo "✓ Installed and loaded. Daemon will start now and on every reboot."
    sleep 2
    _print_status
}

cmd_uninstall() {
    echo "→ Uninstalling launchd agent..."
    if [[ -f "${PLIST_DST}" ]]; then
        launchctl unload -w "${PLIST_DST}" 2>/dev/null || true
        rm -f "${PLIST_DST}"
        echo "✓ Unloaded and removed."
    else
        echo "  (plist not found, nothing to remove)"
    fi
}

cmd_start() {
    if ! [[ -f "${PLIST_DST}" ]]; then
        echo "✗ Not installed. Run: scripts/manage_daemon.sh install"
        exit 1
    fi
    launchctl start "${LABEL}"
    echo "✓ Start signal sent."
    sleep 1
    _print_status
}

cmd_stop() {
    launchctl stop "${LABEL}" 2>/dev/null || true
    echo "✓ Stop signal sent. (launchd will restart it unless unloaded)"
}

cmd_restart() {
    cmd_stop
    sleep 2
    cmd_start
}

cmd_status() {
    _print_status
}

cmd_logs() {
    echo "=== stdout log (${LOG_FILE}) ==="
    tail -f "${LOG_FILE}"
}

# ── dispatch ──────────────────────────────────────────────────────────────────

case "${1:-status}" in
    install)    cmd_install ;;
    uninstall)  cmd_uninstall ;;
    start)      cmd_start ;;
    stop)       cmd_stop ;;
    restart)    cmd_restart ;;
    status)     cmd_status ;;
    logs)       cmd_logs ;;
    *)
        echo "Usage: $0 {install|uninstall|start|stop|restart|status|logs}"
        exit 1
        ;;
esac
