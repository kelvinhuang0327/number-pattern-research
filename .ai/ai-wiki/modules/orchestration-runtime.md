---
source_path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/ai-wiki/modules/orchestration-runtime.md
source_mtime: 2026-04-27T17:57:35+0800
source_sha256: 14a0dbc578595b4309088e7ba66c0d790e1d7182df5d580902295865f218c18e
legacy_warning: "COPY-IN from legacy workspace-AI overlay; may be stale. Source retained in place; do not treat as canonical without re-analysis."
---

# Orchestration Runtime

> [過時 2026-07-07] `orchestrator/` was not present in the `ac8ff5a` worktree static scan, and `runtime/agent_orchestrator/**` is a do-not-touch runtime path. This page is retained as legacy overlay context, not as current canonical architecture.

Scope: local orchestrator control, execution policy, and launchd-managed agent jobs.

Primary paths:
- `orchestrator/`
- `runtime/agent_orchestrator/`
- `start_all.sh`
- `stop_all.sh`

Responsibilities:
- Control LLM execution policy for orchestrator and backend paths.
- Run planner / worker / daemon jobs through launchd.
- Expose control and status surfaces for operators.

Observed entry points:
- `python3 tools/orchestrator_status.py`
- `GET/POST /api/orchestrator/llm-control`
- `start_all.sh` orchestrator launchd reload sequence

Key integrations:
- launchctl / launchd
- `runtime/agent_orchestrator/logs/llm_control.jsonl`
- `runtime/agent_orchestrator/orchestrator.db`

Notes:
- README states orchestrator and backend share `orchestrator/execution_policy.py` as one control source.
