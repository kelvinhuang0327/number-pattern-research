# Shared Task Templates

These templates are project-neutral. Project-specific details must come from `CURRENT_STATE.md`, `CEO-Decision.md`, `active_task.md`, and the task-specific prompt.

## Template 1 — Plan-Only Task

Use for:

- Discussion
- Roadmap planning
- Decision gates
- Protocol design
- Risk review
- Task planning

Allowed actions:

- Read files and artifacts
- Run read-only verification
- Run read-only guards when requested
- Produce a final report
- Update allowed roadmap / decision / analysis files only when explicitly listed

Forbidden actions:

- Code implementation
- DB write
- Production write
- Registry mutation
- Controlled apply
- Deployment
- Branch creation or checkout
- Git commit
- Git push
- Destructive cleanup

Required Phase 0:

- Verify repo
- Verify branch
- Verify git dir
- Verify HEAD / origin baseline when required
- Verify no staged files
- Verify project state from `CURRENT_STATE.md` or task-specific prompt
- Assess unrelated dirty files

Allowed file whitelist pattern:

- None by default
- Only roadmap, decision, analysis, active-task, report, or bootstrap files explicitly listed by the task

Required output:

1. Problem statement
2. Findings
3. Risks
4. Recommendation
5. Next task scope, if authorized
6. Required Completion Check

Completion check:

- Written files exist, if any were authorized
- Read-only guard status reported as PASS / FAIL / NOT RUN
- No staged / commit / push unless explicitly authorized

Final classification examples:

- `PLAN_ONLY_TASK_READY`
- `PLAN_ONLY_TASK_WITH_RISKS`
- `PLAN_ONLY_TASK_BLOCKED`

---

## Template 2 — Read-Only Execution Task

Use for:

- Diagnostic script execution
- Read-only SQL
- Audit
- Metrics extraction
- Artifact inspection
- CI / PR monitoring

Allowed actions:

- Run read-only commands
- Run tests
- Inspect DB in read-only mode
- Inspect git / PR / CI state
- Produce a report
- Write report artifacts only when explicitly allowed

Forbidden actions:

- DB write
- Source modification
- Production write
- Registry mutation
- Controlled apply
- Deployment
- Git add
- Git commit
- Git push
- Branch changes
- Destructive action

Required Phase 0:

- Verify repo
- Verify branch
- Verify git dir
- Verify no staged files
- Verify data / artifact baseline
- Verify required read-only guards
- Assess unrelated dirty files

Allowed file whitelist pattern:

- None by default
- Report artifacts only when the task explicitly lists paths or path patterns

Required output:

1. Commands run
2. Observations
3. Test status: PASS / FAIL / NOT RUN
4. Risk notes
5. Next recommended action
6. Required Completion Check

Completion check:

- No source / DB / production / registry files modified
- Report path exists if writing was allowed
- Guard/test status reported honestly
- No staged / commit / push

Final classification examples:

- `READ_ONLY_EXECUTION_READY`
- `READ_ONLY_EXECUTION_FOUND_ISSUES`
- `READ_ONLY_EXECUTION_BLOCKED`

---

## Template 3 — Implementation Task

Use for:

- Code changes
- Test changes
- Documentation changes
- Artifact creation
- Migration script creation
- Local commit / PR workflow only when explicitly authorized

Allowed actions:

- Modify files listed in allowed write files
- Run tests
- Stage whitelisted files only when explicitly authorized
- Commit / push only when explicitly authorized

Forbidden actions:

- Modify files outside whitelist
- DB write unless explicitly authorized
- Production write unless explicitly authorized
- Registry mutation unless explicitly authorized
- Controlled apply unless explicitly authorized
- Deployment unless explicitly authorized
- Broad git add
- Force push
- Branch / merge operations unless explicitly authorized
- Destructive cleanup unless explicitly authorized

Required Phase 0:

- Verify repo
- Verify branch
- Verify git dir
- Verify HEAD / origin baseline when required
- Verify no unrelated dirty files unless task explicitly allows working around them
- Verify no staged files
- Verify current baseline
- Verify allowed write list
- Verify expected tests

Allowed file whitelist pattern:

- Exact file paths preferred
- Narrow directory patterns allowed only for generated reports or scoped docs
- Never include DB, binary, runtime, logs, archive, production, or registry paths unless explicitly authorized

Implementation rules:

- Make minimal changes
- Do not expand scope
- After each failure, fix only the directly related issue
- If scope must expand, STOP
- Before staging, list changed files
- Stage only whitelisted files
- Never stage DB / binary / runtime / logs unless explicitly authorized

Required output:

1. Implementation summary
2. Files modified
3. Tests run
4. Staged / commit / push status
5. Remaining blocker
6. Required Completion Check

Completion check:

- Targeted tests or guards PASS / FAIL / NOT RUN
- Diff includes only whitelisted files
- No forbidden files modified or staged
- Staged / commit / push status is explicit

Final classification examples:

- `IMPLEMENTATION_READY`
- `IMPLEMENTATION_READY_LOCAL_ONLY`
- `IMPLEMENTATION_BLOCKED`
- `IMPLEMENTATION_TESTS_FAILED`
- `IMPLEMENTATION_SCOPE_REVISION_REQUIRED`
