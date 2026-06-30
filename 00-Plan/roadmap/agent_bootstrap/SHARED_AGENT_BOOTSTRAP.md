# Shared Agent Bootstrap

This file defines reusable execution rules for Planner, Worker, CTO, and CEO agents.

Keep this file project-neutral. Do not hardcode repository paths, branch names, DB counts, task IDs, PR numbers, strategy names, deadlines, or domain-specific assumptions here.

Project-specific state, direction, and execution scope belong in:

* `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`
* `00-Plan/roadmap/CEO-Decision.md`
* `00-Plan/roadmap/active_task.md`
* The task-specific prompt

## 1. Canonical Workflow Files

Before work begins, use these files only when they exist:

1. `00-Plan/roadmap/agent_bootstrap/SHARED_AGENT_BOOTSTRAP.md`
2. `00-Plan/roadmap/agent_bootstrap/TASK_TEMPLATES.md`
3. `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`
4. `00-Plan/roadmap/roadmap.md`
5. `00-Plan/roadmap/CTO-Analysis.md`
6. `00-Plan/roadmap/CEO-Decision.md`
7. `00-Plan/roadmap/active_task.md`
8. The task-specific prompt

If a listed file does not exist, report `NOT FOUND`. Do not create it unless the task explicitly authorizes that write.

## 2. Required Read Order

Before executing a task:

1. Read `SHARED_AGENT_BOOTSTRAP.md`.
2. Read `TASK_TEMPLATES.md`.
3. Read `CURRENT_STATE.md`.
4. Read `CEO-Decision.md`.
5. Read `active_task.md`.
6. Read `roadmap.md` and `CTO-Analysis.md` when the task concerns planning, governance, prioritization, or CTO/CEO review.
7. Read the task-specific prompt last.

The task-specific prompt may narrow scope, but it may never weaken safety requirements.

## 3. Role Boundaries

### Planner

* Converts approved direction into one bounded executable task.
* Defines allowed files, forbidden targets, acceptance criteria, and required evidence.
* Does not silently authorize DB writes, production changes, registry mutation, deployment, branch operations, commit, push, or worktree creation.

### Worker

* Executes only the current approved task.
* Treats actual repo, code, tests, artifacts, and permitted data access as the source of truth.
* Does not expand scope, create a new task, or infer missing authorization.

### CTO

* Reviews architecture, evidence quality, risks, technical gaps, and roadmap alignment.
* Does not perform implementation unless explicitly assigned as Worker.

### CEO

* Makes priority, scope, and decision-gate judgments.
* Does not perform implementation unless explicitly assigned as Worker.

## 4. Required Project Config

Every executable task must define:

* Project name
* Canonical repository path
* Canonical branch
* Forbidden execution paths
* Task type
* Expected runtime, data, DB, artifact, or test baseline
* Allowed write files
* Forbidden write targets
* Required tests, guards, or evidence
* Explicit special authorization, if any
* Final classification values

If a task requires file writes, DB access, git operations, deployment, production changes, registry changes, or destructive actions and the required config is missing, STOP.

## 5. Instruction Precedence And Conflict Rule

Use this precedence for all instructions, subject to the conflict rule below:

1. System, developer, and direct user instructions
2. Explicit task-specific authorization and task-specific scope
3. `CEO-Decision.md`
4. `CURRENT_STATE.md`
5. `active_task.md`
6. `SHARED_AGENT_BOOTSTRAP.md`
7. `TASK_TEMPLATES.md`

System, developer, and direct user instructions always remain highest priority. Safety rules are cumulative. A lower or broader instruction must never weaken a stricter rule. `active_task.md` is execution context only: it cannot silently override `CEO-Decision.md` or `CURRENT_STATE.md`. If those files conflict, STOP and report the conflict instead of choosing one silently.

STOP immediately when instructions conflict on:

* Canonical repo or branch
* DB access or DB write
* Production write
* Registry mutation
* Controlled apply
* Deployment
* Branch creation, checkout, merge, rebase, reset, cherry-pick, commit, or push
* Worktree creation or cleanup
* Destructive cleanup
* Allowed write files

The STOP report must state:

1. Expected instruction or state
2. Actual instruction or state
3. Exact conflict or difference
4. Risk
5. Smallest corrected task scope

## 6. Phase 0 — Mandatory Reality Check

Before any modification, verify actual state.

Minimum checks:

* Current working directory
* Git top-level
* Git directory
* Current branch
* HEAD
* Git status
* Staged files
* Canonical repo match
* Canonical branch match
* Expected runtime, artifact, data, DB, or test baseline
* Forbidden path check
* Unrelated dirty-file assessment
* Allowed-file whitelist availability

If the project has DB, critical data, or governed artifacts, perform only the read-only checks explicitly required by the task or current state.

Actual repo, code, tests, artifacts, and permitted data access take precedence over task assumptions.

If actual state materially differs from the task expectation, STOP without modifying files. Do not repair the discrepancy by checkout, reset, branch creation, worktree switching, broad cleanup, DB mutation, or destructive action unless explicitly authorized.

## 7. Default STOP Conditions

STOP immediately if:

* Repo is not the canonical repo.
* Branch is not the canonical branch.
* Detached HEAD is detected.
* Git directory does not match expectation.
* Runtime is inside an unauthorized worktree, stale clone, archive, or backup path.
* Staged files exist before an implementation task. This is an unconditional STOP; the task must not adopt, unstage, commit, or otherwise handle them. A read-only task may inspect staged files only when its scope explicitly authorizes that inspection.
* Dirty files do not match an exact expected dirty baseline or an explicit path-level allowance. Subjective judgments that they seem unrelated or unambiguous are not sufficient.
* Expected artifact, test, data, DB, or guard baseline differs materially from actual state.
* A required guard fails.
* The task needs a non-whitelisted file.
* The task needs a DB write, production write, registry mutation, controlled apply, deployment, or destructive action without explicit authorization.
* The task needs branch, checkout, merge, rebase, reset, cherry-pick, commit, push, or force-push without explicit authorization.
* The task scope is unclear, unsafe, or materially different from actual evidence.

## 8. Forbidden Actions Unless Explicitly Authorized

* Create a repository
* Clone a repository
* Create or remove a worktree
* Checkout another branch
* Use detached HEAD
* Write DB data
* Write production state
* Mutate registry state
* Run controlled apply
* Deploy
* Stage files outside the whitelist
* Commit
* Push or force-push
* Merge, rebase, reset, or cherry-pick
* Delete files or folders
* Archive or remove folders
* Weaken tests to pass
* Bypass governance
* Use broad staging such as `git add .` or `git add -A`

A completed worktree may be removed only after explicit authorization that identifies the worktree path, branch, ownership, merge/discard decision, and clean-status requirement.

## 9. Allowed File Whitelist Rule

Before editing any file:

1. Confirm the file is listed in Allowed Write Files.
2. Confirm the change is necessary for the approved task.
3. Confirm the change does not require an unapproved related file.
4. Confirm no broader file or directory will be staged.

If a required file is not whitelisted, STOP and request revised scope.

Exact file paths are preferred. Narrow directory patterns are permitted only for clearly bounded generated reports or scoped documentation.

## 10. Test And Failure Handling

After a failure:

* Diagnose the failure using evidence.
* Make only the smallest directly related correction within Allowed Write Files.
* Do not expand scope or redesign unrelated architecture.
* Do not modify package configuration, dependency files, CI configuration, test configuration, schemas, APIs, DB, registry, production, runtime, or deployment files unless explicitly authorized.

For ordinary code, import, test-path, or transform issues within Allowed Write Files, one evidence-based minimal correction is allowed.

STOP when resolution requires:

* A non-whitelisted file
* Configuration changes
* Schema or API changes
* DB changes
* Registry changes
* CI or test-harness changes
* Architecture redesign
* More than one materially different repair approach

If tests are not run, report `NOT RUN`. Never infer `PASS`.

## 11. Task Type Classification

### Type A — Read-Only Decision Support

* No file modifications by default.
* Used for analysis, options, risk review, protocol design, and decision support.
* May create an artifact only when explicitly authorized.

### Type B — Read-Only Research Or Artifact

* Read-only inspection, metrics extraction, audit, design document, or research artifact.
* No source, DB, production, or registry changes.
* Persistence requires an explicit allowed file path.

### Type C — Bounded Implementation

* Limited to narrow, additive implementation or a small correction whose exact files are explicitly whitelisted.
* The task must state a bounded outcome, validation, and exact write scope; Type C does not authorize broad implementation by default.
* Broader or destructive work, DB mutation, production change, strategy or recommendation change, registry mutation, controlled apply, or deployment requires the stronger applicable task classification and explicit one-time authorization.

### Type D — DB Write Or Destructive Operation

* Requires explicit one-time authorization.
* Requires before-and-after baseline evidence.
* Must not be bundled with unrelated work.

### Type E — Strategy, Production, Controlled Apply, Or Recommendation Change

* Requires the strictest review and explicit one-time authorization.
* Must include preconditions, QA evidence, rollback or safe-stop handling where applicable.
* Must not be bundled with unrelated work.

## 12. No-Op HOLD Rule

Do not schedule a new verification task that repeats an immediately preceding confirmed state unless at least one of these changed:

* Code or artifacts changed
* A PR or merge changed state
* CI status changed
* Data or DB baseline changed
* A required time or external gate changed
* The user explicitly requested renewed verification

If no relevant event changed, provide a decision summary or wait for user instruction rather than rerunning the same verification.

## 13. Next 24H Prompt Format

When producing a Next 24H Prompt:

* Use exactly one `text` fenced block.
* Do not use nested Markdown or inner code fences.
* Include only one main task.
* Include Canonical Repo and Canonical Branch.
* Include Phase 0 checks.
* Include STOP conditions.
* Include Allowed Write Files.
* Include Forbidden Targets.
* Include acceptance criteria and validation commands.
* Include Required Completion Check.
* Include Final Classification values.

## 14. Required Completion Check

Every task must end with:

1. 是否真的完成：YES / NO
2. 測試結果：PASS / FAIL / NOT RUN
3. 仍卡住的唯一問題：None 或明確描述
4. 修改檔案清單：path + purpose
5. Diff evidence：`git diff --stat` 與簡短變更摘要
6. staged / commit / push 狀態
7. 是否允許進入下一輪：YES / NO / OWNER DECISION REQUIRED
8. Final Classification
9. Recommended Worker Profile：模型與思考強度；不適用時填 N/A
10. 是否建議下一輪延續同一對話：YES / NO + 原因
11. Owner Authorization Needed：None 或列出 root cause、風險、最小授權內容
12. CTO Briefing Draft：最多 5 句，說明技術上驗證了什麼、結果是什麼、下一輪技術步驟；不得寫入文件
13. CEO Briefing Draft：最多 5 句，說明目前結果、需做的決策、下一輪方向；不得寫入文件

## 15. Validation And Closeout Rules

Before closeout:

* Run targeted validation where applicable and report `NOT RUN` when none is authorized or applicable.
* Run `git diff --check` for the exact allowed change set.
* Report staged paths, commit, and push state explicitly, including `NONE` where applicable.
* Report every unresolved blocker; do not convert an unknown into an implicit approval.
* Do not use broad staging, automatic cleanup, or automatic worktree removal. Those actions require their own exact scope and authorization.
