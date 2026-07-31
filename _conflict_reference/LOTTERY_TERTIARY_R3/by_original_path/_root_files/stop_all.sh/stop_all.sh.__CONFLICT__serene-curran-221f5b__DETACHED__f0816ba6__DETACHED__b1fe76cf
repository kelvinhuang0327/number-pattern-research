#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${PROJECT_ROOT}/scripts/launchd/common.sh"

QUIET=false
for arg in "$@"; do
    case "${arg}" in
        --quiet) QUIET=true ;;
    esac
done

if [[ "${QUIET}" == "false" ]]; then
    log_info "Stopping Betting-pool services..."
fi

ensure_runtime_dirs
stop_pid_file "${BACKEND_PID_FILE}" "backend"
stop_pid_file "${FRONTEND_PID_FILE}" "frontend"
stop_pid_file "${PROXY_PID_FILE}" "proxy"
kill_port_owner "${BACKEND_PORT}"
kill_port_owner "${FRONTEND_PORT}"
kill_port_owner "${PROXY_PORT}"

if [[ "${QUIET}" == "false" ]]; then
    log_info "All services stopped."
fi
