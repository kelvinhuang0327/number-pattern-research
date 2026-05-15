# AI Setup Prompt

Use the prompt below with another AI agent when you want it to scaffold this orchestrator into a different project.

```text
Set up a reusable dual-agent orchestrator in this repository.

Context:
- I already have a project and want a generic planner/worker orchestration mechanism.
- The implementation must be project-agnostic in core logic.
- Domain-specific rules must live in a project profile and backlog.

Files to create:
- `orchestrator/common.py`
- `orchestrator/db.py`
- `orchestrator/planner_tick.py`
- `orchestrator/worker_tick.py`
- `orchestrator/api.py`
- optional daemon worker runtime if the worker provider needs a resident process
- `runtime/agent_orchestrator/backlog.md`
- `runtime/agent_orchestrator/logs/`
- `runtime/agent_orchestrator/tasks/YYYYMMDD/`
- `runtime/agent_orchestrator/orchestrator.db`

Workflow rules:
1. Planner runs every 10 minutes.
2. Worker runs every 10 minutes.
3. Planner must skip if the latest task is still `RUNNING`.
4. Planner must read the previous `task_result.json` before generating the next task.
5. Planner must write both a human-readable prompt file and a machine-readable contract file.
6. Worker must produce a human-readable completed summary.
7. Orchestrator must produce a machine-readable task result file.
8. Orchestrator must validate worker delivery mechanically and convert invalid delivery into `REPLAN_REQUIRED`.

Task statuses:
- `QUEUED`
- `RUNNING`
- `COMPLETED`
- `FAILED`
- `REPLAN_REQUIRED`
- `CANCELLED`

Task contract schema:
- `version`
- `objective`
- `scope`
- `constraints`
- `acceptance_tests`
- `required_outputs`
- `forbidden_changes`
- `handoff_questions`

Task result schema:
- `version`
- `task_id`
- `status`
- `gate_verdict`
- `gate_reason`
- `duration_seconds`
- `changed_files`
- `error_markers_hit`
- `missing_required_outputs`
- `forbidden_change_violations`
- `acceptance_results`
- `next_action`

Provider rules:
- Planner and worker runtimes must be configurable.
- Provider switching must not change task schemas or gate logic.
- Orchestrator must remain the source of truth for validation.

Minimum API:
- summary
- task list
- task detail
- recent runs
- scheduler enable/disable
- provider switch
- planner run-now
- worker run-now

Minimum UI:
- scheduler state
- next planner run time
- next worker run time
- provider combo
- paginated task list
- task detail
- task contract
- task result
- gate verdict
- last output time
- latest progress summary

Implementation constraints:
- Keep orchestrator core generic.
- Move project-specific rules into a profile/config file.
- Add progress tracking from worker stdout logs.
- Finalize blocked worker tasks instead of letting them stay in `RUNNING`.
- Add one manual smoke path for planner and one for worker.

Definition of done:
- one planner run creates a valid task prompt and contract
- one worker run creates completed/result artifacts
- one invalid worker delivery becomes `REPLAN_REQUIRED`
- task detail API returns contract/result/progress
- UI can render contract/result/progress correctly
```

## What To Provide Together With This Prompt

Always provide these values to the implementation agent:

- protected paths
- required checks
- allowed reference directories
- desired planner provider
- desired worker provider
- preferred schedule interval
