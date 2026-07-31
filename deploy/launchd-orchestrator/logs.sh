#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "${PROJECT_ROOT}/scripts/launchd/manage_launch_agents.sh" logs
