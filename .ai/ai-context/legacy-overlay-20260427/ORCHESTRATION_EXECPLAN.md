---
source_path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/ai-context/ORCHESTRATION_EXECPLAN.md
source_mtime: 2026-04-27T18:25:37+0800
source_sha256: 840375467fe2fbf7fb200c9ed00c6a481407c60a2b35dc716126cd67d5d7a811
legacy_warning: "COPY-IN from legacy workspace-AI overlay; may be stale. Source retained in place; do not treat as canonical without re-analysis."
---

# Orchestration ExecPlan

> [過時 2026-07-07] Historical overlay-only plan. It is retained for traceability but is not an approved current implementation plan. `orchestrator/` was not present in the `ac8ff5a` static scan; any orchestration disposition belongs in a separate E8 task.

Date: 2026-04-27
Project: LotteryNew
Mode: overlay-only

## Scope

This plan addresses three structural problems in the orchestration system without changing source code directly:

1. Queue stall is not observable enough.
2. Execution / review / strategy states are split across layers.
3. Worker gate mixes format failures and research failures, which weakens learning.

## Layered Diagnosis

### Execution Layer

- `agent_tasks` is the execution queue.
- Runtime evidence already shows `QUEUED` items can remain unclaimed.
- Current system can detect process liveness, but does not persist a canonical queue-stall reason snapshot.

### Review Layer

- `task_git_commits`, `strategy_reviews`, and `cto_review_runs` hold post-execution decisions.
- CTO decisions influence planner behavior through `planner_directives` and `active_strategy_state`.
- Those decisions are not reflected as a single external task state.

### Strategy Layer

- Strategy review decisions are richer than task statuses.
- The system can approve, shadow, reject, or request more research.
- This richness is lost at API/task summary level.

### Learning Layer

- Planner prompts require Handoff Notes and wiki / memory updates.
- There is no dedicated post-task learning hook that reliably transforms task outcomes into reusable negative learning.
- `FAILED_ACCEPTANCE` is too coarse to teach the planner whether the failure was formatting or research quality.

## Minimal Invasive Change Plan

### A. Observability

Goal:
- Add a queue-health snapshot layer that explains why a task is still `QUEUED`.

Add overlay reference logic for:
- queue age
- worker lock present / absent
- daemon running / not running
- scheduler enabled / disabled
- provider blocked / rate limited
- confidence of diagnosis

Target integration points in source system later:
- `orchestrator/worker_tick.py`
- `orchestrator/copilot_daemon.py`
- `orchestrator/api.py`

Expected output fields:
- `queue_health.reason_code`
- `queue_health.reason_detail`
- `queue_health.confidence`
- `queue_health.unverified_signals`

### B. Canonical State Layer

Goal:
- Preserve existing schema, but compute a single external status from multi-layer state.

Canonical sub-statuses:
- `execution_status`
- `review_status`
- `strategy_status`
- `knowledge_status`

Derived external status:
- `QUEUED`
- `IN_PROGRESS`
- `DONE`
- `FAILED`
- `REJECTED`

Mapping principle:
- execution answers whether work ran
- review answers whether output passed governance
- strategy answers whether research outcome is promotable
- knowledge answers whether learning was persisted or gated

### C. Learning-aware Worker Gate

Goal:
- Split `FAILED_ACCEPTANCE` into machine-learnable causes.

New overlay taxonomy:
- `FAILED_FORMAT_CONTRACT`
- `FAILED_RESEARCH_CONTRACT`

Rule:
- missing output sections, malformed tables, blank required columns → format contract
- weak edge, no positive signal, invalid promotion logic, missing research evidence → research contract

Planner learning benefit:
- format failures should trigger repair prompts
- research failures should update negative-space memory and redirect exploration

### D. Feedback Loop

Goal:
- Make CTO rejection visible to task summaries and planner memory.

Add overlay reference logic for:
- mapping CTO decision to task-level review summary
- building negative-space learning records
- exposing planner-readable rejection reasons

Target integration points later:
- `orchestrator/cto_review_tick.py`
- `orchestrator/planner_tick.py`
- `runtime/agent_orchestrator/research_registry/negative_space.json`

## Proposed Rollout Order

1. Add queue-health snapshot and canonical state mapper.
2. Add worker-gate failure taxonomy split.
3. Add feedback-loop projection from CTO decision to task summary.
4. Add learning hook only after runtime evidence stabilizes.

## Non-Goals

- No schema-breaking migration.
- No replacement of current orchestrator architecture.
- No source repo modification in this overlay phase.

## Evidence Base

- Source code: `orchestrator/planner_tick.py`, `orchestrator/worker_tick.py`, `orchestrator/cto_review_tick.py`, `orchestrator/db.py`, `orchestrator/copilot_daemon.py`, `orchestrator/api.py`
- Runtime evidence: `runtime/agent_orchestrator/orchestrator.db`, `runtime/agent_orchestrator/cto_reviews/...`
- Overlay knowledge: `ai-wiki/modules/orchestration-runtime.md`, `ai-wiki/flows/llm-execution-control.md`
