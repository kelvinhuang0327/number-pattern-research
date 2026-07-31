#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME_ROOT="${PROJECT_ROOT}/runtime/agent_orchestrator"
RUN_ROOT="${RUNTIME_ROOT}/run"
LOG_ROOT="${RUNTIME_ROOT}/logs"
LAUNCHD_LOG_ROOT="${LOG_ROOT}/launchd"
SERVICE_LOG_ROOT="${LOG_ROOT}/service"
FRONTEND_ROOT="${RUNTIME_ROOT}/frontend"

SERVICE_HOST="${SERVICE_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8787}"
FRONTEND_PORT="${FRONTEND_PORT:-8788}"
PROXY_PORT="${PROXY_PORT:-8789}"

BACKEND_PID_FILE="${RUN_ROOT}/backend.pid"
FRONTEND_PID_FILE="${RUN_ROOT}/frontend.pid"
PROXY_PID_FILE="${RUN_ROOT}/proxy.pid"

BACKEND_OUT_LOG="${SERVICE_LOG_ROOT}/backend.out.log"
BACKEND_ERR_LOG="${SERVICE_LOG_ROOT}/backend.err.log"
FRONTEND_OUT_LOG="${SERVICE_LOG_ROOT}/frontend.out.log"
FRONTEND_ERR_LOG="${SERVICE_LOG_ROOT}/frontend.err.log"
PROXY_OUT_LOG="${SERVICE_LOG_ROOT}/proxy.out.log"
PROXY_ERR_LOG="${SERVICE_LOG_ROOT}/proxy.err.log"

ensure_runtime_dirs() {
    mkdir -p "${RUN_ROOT}" "${LAUNCHD_LOG_ROOT}" "${SERVICE_LOG_ROOT}" "${FRONTEND_ROOT}"
}

timestamp() {
    date +"%Y-%m-%d %H:%M:%S"
}

log_info() {
    printf "[%s] [INFO] %s\n" "$(timestamp)" "$*"
}

log_warn() {
    printf "[%s] [WARN] %s\n" "$(timestamp)" "$*" >&2
}

log_error() {
    printf "[%s] [ERROR] %s\n" "$(timestamp)" "$*" >&2
}

is_pid_running() {
    local pid="${1:-}"
    [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

read_pid_file() {
    local pid_file="${1}"
    if [[ -f "${pid_file}" ]]; then
        cat "${pid_file}"
    fi
}

port_pid() {
    local port="${1}"
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true
}

assert_port_available() {
    local port="${1}"
    local name="${2}"
    local owner_pid
    owner_pid="$(port_pid "${port}")"
    if [[ -n "${owner_pid}" ]]; then
        log_error "Port ${port} is already occupied by pid ${owner_pid} (${name})."
        return 1
    fi
}

stop_pid_file() {
    local pid_file="${1}"
    local name="${2}"
    local pid
    pid="$(read_pid_file "${pid_file}")"
    if [[ -z "${pid}" ]]; then
        rm -f "${pid_file}" 2>/dev/null || true
        return 0
    fi

    if is_pid_running "${pid}"; then
        log_info "Stopping ${name} (pid=${pid})"
        kill "${pid}" 2>/dev/null || true
        sleep 1
        if is_pid_running "${pid}"; then
            log_warn "${name} still running, sending SIGKILL (pid=${pid})"
            kill -9 "${pid}" 2>/dev/null || true
        fi
    fi
    rm -f "${pid_file}" 2>/dev/null || true
}

kill_port_owner() {
    local port="${1}"
    local pid
    pid="$(port_pid "${port}")"
    if [[ -n "${pid}" ]]; then
        log_warn "Killing process occupying port ${port} (pid=${pid})"
        kill "${pid}" 2>/dev/null || true
        sleep 1
        if is_pid_running "${pid}"; then
            kill -9 "${pid}" 2>/dev/null || true
        fi
    fi
}

start_service_process() {
    local name="${1}"
    local pid_file="${2}"
    local stdout_log="${3}"
    local stderr_log="${4}"
    shift 4
    local cmd=( "$@" )

    "${cmd[@]}" >>"${stdout_log}" 2>>"${stderr_log}" &
    local pid=$!
    echo "${pid}" > "${pid_file}"
    sleep 1
    if ! is_pid_running "${pid}"; then
        log_error "${name} failed to start; check ${stdout_log} and ${stderr_log}."
        return 1
    fi
    log_info "${name} started (pid=${pid})"
}

wait_http_ready() {
    local url="${1}"
    local timeout_seconds="${2:-30}"
    local started
    started="$(date +%s)"
    while true; do
        if curl -fsS "${url}" >/dev/null 2>&1; then
            return 0
        fi
        local now
        now="$(date +%s)"
        if (( now - started >= timeout_seconds )); then
            return 1
        fi
        sleep 1
    done
}
