#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${PROJECT_ROOT}/scripts/launchd/common.sh"
ensure_runtime_dirs

DAEMON_STDOUT="${LAUNCHD_LOG_ROOT}/worker_daemon.out.log"
DAEMON_STDERR="${LAUNCHD_LOG_ROOT}/worker_daemon.err.log"

PYTHON="${PROJECT_ROOT}/.venv/bin/python"

exec "${PYTHON}" "${PROJECT_ROOT}/scripts/agent_orchestrator.py" daemon >> "${DAEMON_STDOUT}" 2>> "${DAEMON_STDERR}"
