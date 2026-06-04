# P240B Governance Simplification Design Proposal

**Date:** 2026-06-04
**Classification:** `P240B_GOVERNANCE_SIMPLIFICATION_DESIGN_PROPOSAL_COMPLETE`
**Status:** Proposal only — not adopted. Requires separate explicit user/CTO authorization to adopt.
**Artifact type:** Read-only design doc. No code changes. No DB write. No registry mutation.

---

## 1. Problem Statement

The Lottery project governance chain has grown to 240+ numbered tasks (P1–P240B). The overhead is real and measurable:

**Recurring multi-phase pattern per research unit:**

| Phase | Example (NIST audit chain) | Value |
|---|---|---|
| Decision support | P236A scouting | High |
| Design doc | P237C tripwire design | High |
| Build plan | P238A build plan | Medium |
| Artifact build | P238B NIST build | High |
| Governance closeout | P238D closeout | Low |
| Steady-state verify | P239A post-P238D | Near-zero |
| Decision matrix | P240A next-direction | Medium |

The NIST audit chain consumed 7 tasks (P236A → P240A) where 3 were substantive and 4 were administrative. Specific patterns that create overhead without safety value:

1. **No-op HOLD verification tasks** (e.g., P239A) that re-confirm a state already established in the previous round without any new external event.
2. **Separate closeout PRs** for small read-only tasks where the artifact PR already contains all safety-relevant content.
3. **Repeated boilerplate** governance file updates (Last Reviewed, State Marker, Active worker task) that duplicate information already in the commit message and PR.
4. **Over-fragmentation** of design-doc + build-plan + artifact-build into three separate PRs when scope is clearly bounded and read-only.
5. **Growing governance files**: CURRENT_STATE.md exceeds 200 lines and is partially truncated in MEMORY.md, reducing its practical usefulness.

**This proposal does not weaken any safety boundary.** All STOP conditions, Phase 0 gates, explicit authorization requirements, and forbidden-action rules remain unchanged.

---

## 2. Safety Principles That Must Not Be Weakened

The following rules are load-bearing and must be preserved in any simplified workflow:

| Principle | Rule |
|---|---|
| **Phase 0 actual-state verification** | Mandatory before any write action in any task type |
| **Canonical repo/branch enforcement** | STOP if repo != LotteryNew or branch unexpected |
| **STOP on any mismatch** | DB rows, drift guard, HEAD != origin/main, staged files, schema mismatch |
| **Allowed File Whitelist** | Every task must enumerate allowed files; no writes outside whitelist |
| **Explicit authorization: DB write** | No `INSERT`/`UPDATE`/`DELETE` without explicit destructive-write authorization phrase |
| **Explicit authorization: registry mutation** | No `replay_strategy_registry.py` changes without explicit phrase |
| **Explicit authorization: production/recommendation** | No changes to live recommendation logic without explicit phrase |
| **Explicit authorization: controlled_apply** | No `controlled_apply` without explicit phrase |
| **Explicit authorization: monitoring/scheduler** | No cron/monitoring job without explicit phrase |
| **Explicit authorization: strategy promotion** | No strategy status change without explicit phrase |
| **Explicit authorization: P211 restart** | P211 remains `HELD_BY_USER` unless user explicitly says "Start P211" |
| **Required Completion Check** | Mandatory 8–11 point checklist at task end |
| **No workaround/obfuscation** | Cannot weaken tests, bypass hooks, or obfuscate governance semantics |
| **P238B YELLOW boundary** | YELLOW is observation-only regardless of simplified governance; no strategy, production, registry, recommendation, monitoring, DB write, or betting advice |

---

## 3. Proposed Simplified Workflow

Tasks are classified into five types. Types A–C are candidates for simplification. Types D–E are unchanged.

### Type A — Read-only Decision Support

**Definition:** Task produces only a terminal/response analysis. No artifact files created. No PR needed.

**Examples:** Decision matrices, next-direction reviews, option comparisons, gate-proximity checks.

**Current overhead:** Each decision support task generates a separate phase number, governance file update, PR, and Required Completion Check.

**Proposed:** Type A tasks end with an in-response report only. No PR, no commit, no artifact file unless the user explicitly requests a persisted artifact. The response itself is the deliverable.

**Retained:**
- Phase 0 verification still required
- Required Completion Check still required in response
- No file writes of any kind

**Savings:** ~1–2 tasks and ~1 PR per research unit where a decision support step is the only output.

---

### Type B — Read-only Design Doc or Artifact

**Definition:** Task produces one or more read-only artifact files (Markdown, JSON). No code changes. No DB write.

**Examples:** Design docs, build plans, research artifacts, audit artifacts, feasibility reviews.

**Current overhead:** Artifact PR + separate governance closeout PR = 2 PRs per artifact unit.

**Proposed:** One PR includes both the artifact files and the governance closeout (active_task + CURRENT_STATE + roadmap updates). No separate closeout PR.

**Conditions for same-PR closeout:**
- All changes are read-only (no DB, no registry, no production code)
- Governance changes are minimal: ≤4 files modified, ≤120 new governance lines
- CI passes on the single PR
- No merge conflict with main

**Conditions requiring separate closeout PR (existing rule applies):**
- Artifact PR merged from external branch with potential conflicts
- CI status changed unexpectedly
- Governance files need substantial reconciliation (>4 files or >120 lines)
- Any DB write, registry mutation, or production change present

**Savings:** ~1 PR per Type B task. In the P237–P240 chain: P237C + P238A + P238B each could have saved one closeout PR (3 PRs total).

---

### Type C — Implementation (Low-Risk, Read-Only Code)

**Definition:** Task adds code (scripts, tests) and artifact files. No DB write. No registry mutation. All changes are additive and do not modify existing production code paths.

**Examples:** Dry-run scripts, research scripts, non-production artifact-build scripts, targeted test suites.

**Current overhead:** Implementation PR + separate governance closeout PR = 2 PRs.

**Proposed:** One PR includes code, tests, artifacts, and governance closeout if:
- All code is additive (new files only; no modifications to existing production paths)
- Targeted tests pass (≥1 test per allowed file)
- `git diff --check` passes
- Governance changes stay within Type B caps (≤4 files, ≤120 lines)

**Retained:** Explicit authorization for any DB write, registry mutation, or production code modification still requires a separate PR with its own Phase 0.

**Savings:** ~1 PR per Type C task. In P237–P240 chain: P238B (artifact build) + governance in one PR.

---

### Type D — DB Write / Ingestion / Destructive Operations

**No simplification.** Existing governance unchanged.

- Separate explicit authorization phrase required per operation
- Dedicated Phase 0 with DB baseline snapshot before and after
- Cannot be consolidated with read-only changes
- Required Completion Check must verify DB rows before/after

---

### Type E — Strategy / Production / Controlled Apply

**No simplification.** Strictest existing governance unchanged.

- Full Phase 0 + STOP guards + explicit authorization + QA verification
- No consolidation with any other task type
- Cannot be combined with read-only artifact or governance changes

---

## 4. No-op HOLD Rule

**Definition of a no-op HOLD task:** A task that:
1. Re-verifies state already confirmed in the immediately preceding round
2. Is triggered by no new external event (no PR merge, no DB change, no CI status change, no draw data addition, no user request)
3. Has no expected output beyond "state unchanged — same as last round"

**Rule:** Do not schedule no-op HOLD verification tasks. If the previous round already confirmed clean state and no external event has occurred, the system remains at `WAITING_FOR_USER_AUTHORIZATION` without a new task.

**Triggers that justify a new verification task:**
- A new PR was merged (verify post-merge state)
- DB row count changed (verify integrity)
- CI status changed on a pending PR
- New draw data was ingested
- A time-based gate opened (e.g., P224B ≥300 draws)
- User explicitly requests verification ("please verify the current state")
- An external service/dependency changed

**Non-triggers (do not schedule a task for these):**
- Previous round ended cleanly and no new event occurred
- System is already at `WAITING_FOR_USER_AUTHORIZATION`
- A decision matrix was just produced

**Example:** P239A (post-P238D steady-state verification) is a no-op HOLD: P238D already confirmed clean state, PR #289 and PR #290 were merged in P238D, and no new event occurred between P238D and P239A. Under this rule, P239A would not be scheduled.

**Exception:** If the user explicitly requests a verification, it is valid regardless of prior state.

---

## 5. Closeout Consolidation Rule

**Current pattern:** Every artifact PR followed by a separate governance-only closeout PR.

**Proposed:** Same-PR closeout is the default for Types B and C (read-only).

### Same-PR Closeout Allowed When

- Task type is B or C (read-only artifact or additive code)
- Governance changes: ≤4 files, ≤120 new lines across all governance files
- All CI checks pass on the single PR
- No merge conflict resolution required
- DB row count is unchanged before and after (drift guard passes)

### Governance Files Allowed in Same-PR Closeout (for read-only tasks)

- `00-Plan/roadmap/active_task.md`
- `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`
- `00-Plan/roadmap/roadmap.md`
- `00-Plan/roadmap/CEO-Decision.md`

### Separate Closeout PR Still Required When

- Artifact PR was merged from an external/forked branch
- CI failed on the artifact PR and had to be fixed
- Governance files need substantial updates (>4 files or >120 lines)
- Any DB write, registry mutation, or production change
- The artifact PR itself introduced conflicts that required manual resolution

---

## 6. Authorization Phrase Templates

Standard minimal phrases for each task type. Longer phrases may always be provided.

| Task Type | Minimal Authorization Phrase |
|---|---|
| **Type A: Decision support** | *(none required — response only)* |
| **Type B: Read-only design doc** | `"Authorize [P###] [description] (read-only design doc, no code changes)"` |
| **Type B: Read-only artifact build** | `"Authorize [P###] [description] (read-only artifact build, no DB write)"` |
| **Type C: Implementation** | `"Authorize [P###] [description] (additive code + tests, no DB write, governance closeout in same PR)"` |
| **Type D: DB write/ingestion** | `"Authorize [P###] [description] (DB write required, explicit destructive authorization)"` |
| **Type D: Registry mutation** | `"Authorize [P###] [description] (registry mutation required)"` |
| **Type D: Controlled apply** | `"Authorize [P###] [description] (controlled_apply required)"` |
| **Type E: Strategy/production** | `"Authorize [P###] [description] (strategy/production change, full governance)"` |
| **P211 restart** | `"Start P211"` or `"Authorize P211 short/mid-window read-only diagnostic"` |

---

## 7. Examples of Overhead to Reduce

| Actual chain | Simplified equivalent | PRs saved | Tasks saved |
|---|---|---|---|
| P237C design + P237D closeout | One PR: design doc + governance closeout | 1 | 1 |
| P238A build plan + P238C closeout | One PR: build plan + governance closeout | 1 | 1 |
| P238B artifact + P238D closeout + P239A verify | One PR: artifact + governance closeout; skip no-op verify | 2 | 2 |
| P240A decision matrix (response) | Response only, no PR | 1 | 0 |
| **Total savings in P237–P240 chain** | | **5 PRs** | **4 tasks** |

**Boundary note:** P238B YELLOW classification (`RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY`) remains observation-only regardless of how governance overhead is reduced. Simplified governance does not change what YELLOW means or authorize.

---

## 8. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Simplification weakens safety gates | Phase 0, STOP conditions, and explicit authorization phrases are unchanged for all types. Types D and E have no simplification. |
| Consolidated PRs make review harder | Cap: ≤4 governance files, ≤120 governance lines per same-PR closeout. Large changes still require separate PR. |
| No-op HOLD rule causes missed problems | The trigger list is conservative: any new event (PR, DB change, CI, draw data, user request) justifies a new verification task. |
| Governance files become stale | Same-PR closeout makes the governance sync happen sooner (same commit), not later. |
| Agent over-expands scope in consolidated PR | Whitelist and STOP rules remain strict. Any expansion beyond allowed files triggers STOP. |
| P238B YELLOW misinterpreted after simplification | Explicitly stated: YELLOW is observation-only. Simplified governance does not change interpretation. |
| Type C over-consolidation | Require that all Type C code changes are purely additive (new files only). Any modification to existing production paths remains Type D/E. |

---

## 9. Recommendation

**Adopt as proposal only.**

- This document is a design proposal. It does not automatically change any active governance rule.
- To adopt, the user or CTO must separately authorize with a phrase such as: `"Authorize P240C governance simplification rule adoption"`.
- Until adoption is authorized, the existing governance rules remain in effect.
- The current system state is `WAITING_FOR_USER_AUTHORIZATION`.
- P211 remains `HELD_BY_USER`.
- P238B YELLOW remains `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY` — observation-only, no strategy, no production, no betting advice.

---

## No-Claim Statements

- `adoption_authorized`: **false** — this is a proposal only; governance rules are not changed
- `db_write_performed`: **false**
- `registry_write_performed`: **false**
- `production_change_authorized`: **false**
- `monitoring_job_authorized`: **false**
- `p211_restart_authorized`: **false**
- `strategy_authorized`: **false**
- `betting_advice`: **false**
- `p238b_yellow_remains_observation_only`: **true**
- `p211_remains_held_by_user`: **true**
