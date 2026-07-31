#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${PROJECT_ROOT}/scripts/launchd/common.sh"

FOREGROUND=false
QUIET=false
for arg in "$@"; do
    case "${arg}" in
        --foreground) FOREGROUND=true ;;
        --quiet) QUIET=true ;;
    esac
done

if [[ "${QUIET}" == "false" ]]; then
    log_info "Starting Betting-pool services..."
fi

ensure_runtime_dirs
mkdir -p "${FRONTEND_ROOT}"

assert_port_available "${BACKEND_PORT}" "backend"
assert_port_available "${FRONTEND_PORT}" "frontend"
assert_port_available "${PROXY_PORT}" "proxy"

BACKEND_CMD=(/usr/bin/env python3 "${PROJECT_ROOT}/scripts/agent_orchestrator.py" api --host "${SERVICE_HOST}" --port "${BACKEND_PORT}")
FRONTEND_CMD=(/usr/bin/env python3 -m http.server "${FRONTEND_PORT}" --bind "${SERVICE_HOST}" --directory "${FRONTEND_ROOT}")
PROXY_CMD=(/usr/bin/env python3 "${FRONTEND_ROOT}/proxy_server.py")

start_service_process "backend" "${BACKEND_PID_FILE}" "${BACKEND_OUT_LOG}" "${BACKEND_ERR_LOG}" "${BACKEND_CMD[@]}"
start_service_process "frontend" "${FRONTEND_PID_FILE}" "${FRONTEND_OUT_LOG}" "${FRONTEND_ERR_LOG}" "${FRONTEND_CMD[@]}"
start_service_process "proxy" "${PROXY_PID_FILE}" "${PROXY_OUT_LOG}" "${PROXY_ERR_LOG}" "${PROXY_CMD[@]}"

if ! "${PROJECT_ROOT}/scripts/launchd/health_check.sh"; then
    log_error "Health check failed during startup."
    "${PROJECT_ROOT}/stop_all.sh" --quiet || true
    exit 1
fi

if ! "${PROJECT_ROOT}/scripts/launchd/smoke_check.sh"; then
    log_error "Smoke check failed during startup."
    "${PROJECT_ROOT}/stop_all.sh" --quiet || true
    exit 1
fi

if [[ "${QUIET}" == "false" ]]; then
    log_info "Startup checks passed."
fi

if [[ "${FOREGROUND}" != "true" ]]; then
    if [[ "${QUIET}" == "false" ]]; then
        log_info "Services started in background mode."
    fi
    exit 0
fi

cleanup() {
    "${PROJECT_ROOT}/stop_all.sh" --quiet || true
}

trap cleanup INT TERM EXIT

if [[ "${QUIET}" == "false" ]]; then
    log_info "Foreground supervision active."
fi

while true; do
    backend_pid="$(read_pid_file "${BACKEND_PID_FILE}")"
    frontend_pid="$(read_pid_file "${FRONTEND_PID_FILE}")"
    proxy_pid="$(read_pid_file "${PROXY_PID_FILE}")"

    if ! is_pid_running "${backend_pid}"; then
        log_error "Backend process exited unexpectedly."
        exit 1
    fi
    if ! is_pid_running "${frontend_pid}"; then
        log_error "Frontend process exited unexpectedly."
        exit 1
    fi
    if ! is_pid_running "${proxy_pid}"; then
        log_error "Proxy process exited unexpectedly."
        exit 1
    fi
    sleep 5
done
