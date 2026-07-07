---
source_path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/ai-wiki/flows/llm-execution-control.md
source_mtime: 2026-04-27T17:57:35+0800
source_sha256: 8f0bc07d88920c0a8e03a9311449a1c4e82e92c10d23deae8cae50b1c0b10a13
legacy_warning: "COPY-IN from legacy workspace-AI overlay; may be stale. Source retained in place; do not treat as canonical without re-analysis."
---

# LLM Execution Control

> [過時 2026-07-07] This legacy overlay page references `orchestrator/`, runtime DB/log paths, and orchestrator API/CLI surfaces that were not confirmed by the `ac8ff5a` static scan. Runtime paths are do-not-touch for Bootstrap/Re-Analysis. Treat this page as historical context only until a separate orchestration audit verifies it.

Intent: govern whether orchestrator and backend LLM paths are allowed to execute.

Flow:
1. Operator checks or changes execution mode through UI, API, or CLI.
2. Shared policy in `orchestrator/execution_policy.py` determines whether execution is allowed.
3. Orchestrator and backend code consult the same control source.
4. Status and blocked execution telemetry are recorded in runtime files and databases.

Primary actors:
- Operator
- Orchestrator runtime
- Backend API
- Shared execution policy

Observed control surfaces:
- API: `GET/POST /api/orchestrator/llm-control`
- UI: orchestration screen control panel
- CLI: `python3 tools/orchestrator_status.py`

Observed state stores:
- `runtime/agent_orchestrator/logs/llm_control.jsonl`
- `runtime/agent_orchestrator/orchestrator.db`
