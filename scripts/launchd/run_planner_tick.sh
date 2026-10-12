#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${PROJECT_ROOT}/scripts/launchd/common.sh"
ensure_runtime_dirs

PLANNER_STDOUT="${LAUNCHD_LOG_ROOT}/planner_tick.out.log"
PLANNER_STDERR="${LAUNCHD_LOG_ROOT}/planner_tick.err.log"

{
    echo "[$(timestamp)] planner tick start"
    "${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/scripts/agent_orchestrator.py" planner-tick
    echo "[$(timestamp)] planner tick end"
} >> "${PLANNER_STDOUT}" 2>> "${PLANNER_STDERR}"
