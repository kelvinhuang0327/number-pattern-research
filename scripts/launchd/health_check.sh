#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${PROJECT_ROOT}/scripts/launchd/common.sh"

ensure_runtime_dirs

BACKEND_URL="http://${SERVICE_HOST}:${BACKEND_PORT}/api/summary"
FRONTEND_URL="http://${SERVICE_HOST}:${FRONTEND_PORT}/"

if ! wait_http_ready "${BACKEND_URL}" 30; then
    log_error "Backend health check timeout: ${BACKEND_URL}"
    exit 1
fi

if ! wait_http_ready "${FRONTEND_URL}" 30; then
    log_error "Frontend health check timeout: ${FRONTEND_URL}"
    exit 1
fi

if ! curl -fsS "${BACKEND_URL}" | grep -q "\"scheduler\""; then
    log_error "Backend health response missing expected key: scheduler"
    exit 1
fi

log_info "Health checks passed."
