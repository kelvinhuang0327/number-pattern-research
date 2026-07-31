#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${PROJECT_ROOT}/scripts/launchd/common.sh"
ensure_runtime_dirs

WORKER_STDOUT="${LAUNCHD_LOG_ROOT}/worker_tick.out.log"
WORKER_STDERR="${LAUNCHD_LOG_ROOT}/worker_tick.err.log"

{
    echo "[$(timestamp)] worker tick start"
    "${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/scripts/agent_orchestrator.py" worker-tick
    echo "[$(timestamp)] worker tick end"
} >> "${WORKER_STDOUT}" 2>> "${WORKER_STDERR}"
