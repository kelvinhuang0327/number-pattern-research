# Agent Orchestrator Backlog

## North Star

Describe the long-running goal of this project in one paragraph.

Example:

Build, validate, and ship production-safe improvements toward the project's main outcome while preserving stability, protected data, and existing operational guarantees.

## Success Criteria

List the conditions that define success for work in this project.

1. The delivered output must satisfy all acceptance checks.
2. Protected paths must never be modified.
3. Production behavior must not regress.
4. Every completed task must leave machine-readable and human-readable results.

## Priorities

Use these sections to guide planner behavior.

### Priority 1: Critical Validation

- Validate the highest-risk or highest-impact pending work item first.
- Re-check any task previously marked `REPLAN_REQUIRED`.

### Priority 2: Active Delivery

- Continue the most important in-progress initiative that still has measurable progress to make.

### Priority 3: Exploration

- Explore new candidate ideas only when critical validation and active delivery do not block progress.

### Priority 4: Maintenance

- Cleanup, tests, docs, UI polish, and internal tooling only when higher-priority work is clear.

## Planner Rules

Planner must follow these rules:

1. Read the latest `task_result.json` before producing the next task.
2. Do not repeat the same failed plan without changing scope, method, or acceptance logic.
3. If the latest task is `RUNNING`, skip planning.
4. If the latest task is `REPLAN_REQUIRED`, handle it before creating unrelated new work.
5. Each prompt must include:
   - `Objective`
   - `Scope`
   - `Constraints`
   - `Acceptance Criteria`
   - `Handoff Notes`

## Constraints

- Do not modify protected paths listed in the project profile.
- Do not claim success without evidence.
- Do not leave a task in `RUNNING` if execution is blocked by permission/runtime issues.
- Do not create tasks with ambiguous completion criteria.

## References

List the documents planner is allowed to use.

- `README.md`
- `docs/`
- `wiki/`
- `memory/`
- project profile JSON

## Auto Status Block

The orchestrator may maintain an auto-generated section below this line.
