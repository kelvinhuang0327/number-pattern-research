#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${PROJECT_ROOT}/scripts/launchd/common.sh"

ensure_runtime_dirs

SMOKE_LOG="${LAUNCHD_LOG_ROOT}/smoke_check.log"

{
    echo "[$(timestamp)] smoke_check begin"
    /usr/bin/env python3 "${PROJECT_ROOT}/scripts/agent_orchestrator.py" init
    summary_json="$(/usr/bin/env python3 "${PROJECT_ROOT}/scripts/agent_orchestrator.py" summary)"
    python3 - <<'PY' "${summary_json}"
import json
import sys
payload = json.loads(sys.argv[1])
assert "scheduler" in payload, "missing scheduler in summary output"
assert "counts" in payload, "missing counts in summary output"
print("summary_schema_ok")
PY
    echo "[$(timestamp)] smoke_check pass"
} >> "${SMOKE_LOG}" 2>&1

log_info "Smoke checks passed."
