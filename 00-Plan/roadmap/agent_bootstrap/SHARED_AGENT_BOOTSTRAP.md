# Shared Agent Bootstrap

This file defines reusable execution rules for Planner, Worker, CTO, and CEO agents.

Keep this file project-neutral. Do not hardcode repo paths, DB rows, branch names, task IDs, strategy names, PR numbers, or domain-specific assumptions here. Project-specific state belongs in `CURRENT_STATE.md`, `CEO-Decision.md`, `active_task.md`, or the task-specific prompt.

## Required Read Order

Before executing any task, read these files if they exist:

1. `00-Plan/roadmap/agent_bootstrap/SHARED_AGENT_BOOTSTRAP.md`
2. `00-Plan/roadmap/agent_bootstrap/TASK_TEMPLATES.md`
3. `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`
4. `00-Plan/roadmap/CEO-Decision.md`
5. `00-Plan/roadmap/active_task.md`
6. The task-specific prompt

The task-specific prompt controls the task. `active_task.md` is authoritative only when the project workflow or user explicitly says it is.

## Project Config Required

Every executable task prompt must define:

- Project name
- Canonical repo
- Canonical branch
- Expected runtime, data, DB, artifact, or test baseline
- Forbidden execution paths
- Allowed write files
- Forbidden write targets
- Required tests or guards
- Final classification values

If Project Config is missing and the task requires file writes, DB access, git operations, deployment, production changes, or registry changes, STOP.

## Conflict Priority

If instructions conflict, use this order:

1. System / developer / direct user instructions
2. Explicit task-specific authorization phrase and task-specific scope
3. `CEO-Decision.md`
4. `CURRENT_STATE.md`
5. `SHARED_AGENT_BOOTSTRAP.md`
6. `TASK_TEMPLATES.md`
7. `active_task.md`, when present

Safety rules must never be weakened. If the conflict involves repo, branch, DB, production write, registry mutation, controlled apply, deployment, branch operations, commit, push, merge, destructive cleanup, archive deletion, or allowed write files, STOP and report the conflict.

## Phase 0 Verification

Before any modification, verify actual state.

Minimum checks:

- Current working directory
- Git top-level
- Current branch
- Git dir
- Git status
- Staged files
- HEAD
- Expected canonical repo
- Expected canonical branch
- Expected data / artifact / test baseline
- Forbidden path check
- Unrelated dirty file assessment

If the project has DB or critical data files, run read-only checks required by `CURRENT_STATE.md` or the task-specific prompt.

If actual state differs from the expected state, STOP. Do not repair by `cd`, checkout, reset, branch creation, worktree switching, or broad cleanup unless explicitly authorized.

## STOP Conditions

STOP immediately if:

- Repo is not the canonical repo
- Branch is not the canonical branch
- Git dir does not match expectation
- Runtime is inside an unauthorized worktree, stale clone, archive, or backup path
- Staged files exist before task
- Unrelated dirty files exist and the task does not explicitly allow working around them
- Expected data / artifact / guard baseline does not match actual state
- Required tests or guards fail
- Task needs files outside the allowed write list
- Task needs DB write without explicit authorization
- Task needs production write without explicit authorization
- Task needs registry mutation without explicit authorization
- Task needs controlled apply without explicit authorization
- Task needs deployment without explicit authorization
- Task needs branch creation, checkout, merge, rebase, reset, cherry-pick, commit, push, or force push without explicit authorization
- Task needs destructive action without explicit authorization
- Task scope is unclear or unsafe

STOP report must include:

1. Expected state
2. Actual observed state
3. Difference
4. Risk
5. Suggested corrected task scope

## General Forbidden Actions Unless Explicitly Authorized

- Create a new repo
- Clone a repo
- Create a worktree
- Checkout another branch
- Use detached HEAD
- Write DB data
- Write production state
- Mutate registry state
- Run controlled apply
- Deploy
- Stage outside a whitelist
- Commit
- Push
- Force push
- Merge
- Rebase
- Reset
- Cherry-pick
- Delete files or folders
- Archive folders
- Weaken tests to pass
- Bypass governance

## Allowed File Whitelist Rule

Before editing any file:

1. Verify it is listed in the task-specific allowed write files.
2. Verify the change is necessary for the task.
3. Verify no broader file or directory will be staged.

If a file is not whitelisted, STOP and request corrected scope.

Do not use `git add .` or `git add -A` unless explicitly authorized.

## Test And Failure Handling

After a test failure:

- Fix only the minimal directly related scope.
- Do not rewrite unrelated architecture.
- Do not change package, dependency, config, CI, DB, registry, production, or runtime files unless authorized.
- If the failure requires scope expansion, STOP.

If no tests are run, report `NOT RUN`. Do not claim `PASS`.

## Next Prompt Format

If producing the next task prompt:

- Use one single text block.
- Include canonical repo and branch.
- Include Phase 0 verification.
- Include STOP conditions.
- Include allowed write files.
- Include forbidden write targets.
- Include validation commands.
- Include required completion check.
- Include final classification.
- Include only one main task.

## Required Completion Check

Every task must end with:

1. 是否真的完成
2. 測試結果 PASS / FAIL / NOT RUN
3. 仍卡住的唯一問題
4. 修改檔案清單
5. staged / commit / push 狀態
6. 是否允許進入下一輪
7. Final Classification
