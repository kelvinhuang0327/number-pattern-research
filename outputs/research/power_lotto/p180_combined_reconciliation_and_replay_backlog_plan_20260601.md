# P180 — Combined Reconciliation and Replay Backlog Plan (Plan Only)

**Task**: `P180_COMBINED_MAIN_ZEN_GATES_RECONCILIATION_AND_REPLAY_BACKLOG_PLAN_ONLY`
**Final Classification**: `P180_COMBINED_RECONCILIATION_AND_REPLAY_BACKLOG_PLAN_READY`
**Date**: 2026-06-01
**Branch**: `claude/zen-gates-ff6802`
**Authorization Phrase**: `YES start P180 combined reconciliation and replay backlog plan only`

---

## Phase 0 Verification — PASS

| Check | Actual | Status |
|-------|--------|--------|
| Repo | `zen-gates-ff6802` | PASS |
| Branch | `claude/zen-gates-ff6802` | PASS |
| DB rows | `94924` | PASS |
| bet_index | PRESENT | PASS |
| Drift guard | PASS | PASS |
| P178A test | PASS | PASS |
| P179 test | PASS | PASS |

---

## Part A — main/zen-gates Reconciliation Plan (Plan Only)

### Current Split Summary

| Item | zen-gates | main |
|------|-----------|------|
| DB rows | **94,924** | 54,462 |
| bet_index column | **PRESENT** | ABSENT |
| Row delta | — | **40,462** |
| P161–P179 test contracts | **1,122 tests** | 0 tests |
| Research artifacts | **P161–P179 complete** | Not present |
| Status | canonical research state | stale production state |

**main/zen-gates split remains UNRESOLVED.**

---

### Reconciliation Options

#### A1 — Promote zen-gates to canonical mainline
Merge zen-gates worktree branch into main. Both code and DB follow zen-gates state.

| | |
|--|--|
| Risk | **HIGH** |
| Requires | Merge authorization + DB migration plan + backup rehearsal |
| Pros | Resolves all divergence in one step |
| Cons | Requires careful conflict resolution; DB migration separate step |

#### A2 — Backport code/docs/tests only to main (DB migration separate)
Copy analysis scripts, test contracts, roadmap docs, research artifacts from zen-gates to main. No DB changes.

| | |
|--|--|
| Risk | **MEDIUM** |
| Requires | Branch copy authorization + per-file review |
| Pros | Low risk, incremental, no DB changes |
| Cons | Contract tests fail against main DB until migration |

#### A3 — Controlled DB migration: main 54,462 → zen-gates-equivalent 94,924
Plan for migrating main DB: add bet_index column, insert 40,462 missing rows.

| | |
|--|--|
| Risk | **HIGH** |
| Requires | DB backup + rehearsal script + rollback plan + exact migration authorization phrase |
| Pros | Resolves DB divergence directly |
| Cons | Production DB mutation — irreversible without backup |

#### A4 — Maintain documented divergence temporarily
Accept current split, document it clearly, continue all work in zen-gates worktree.

| | |
|--|--|
| Risk | **LOW (now); grows over time** |
| Requires | No authorization |
| Pros | Zero risk, buys time to plan |
| Cons | Technical debt accumulates; main becomes increasingly stale |

---

### Required Future Authorization Chain

| Action | Requirement |
|--------|-------------|
| Any merge to main | Exact authorization phrase |
| DB migration | Backup confirmation + rehearsal run + exact migration phrase |
| Any controlled_apply | Per-step exact authorization |
| Schema change (e.g., add bet_index to main) | Explicit column-level authorization |

---

### Risk Assessment

| Risk | Level | Notes |
|------|-------|-------|
| Schema mismatch | HIGH | main missing bet_index; P161–P179 tests assume it present |
| Row count drift | HIGH | 40,462 delta; drift guard would flag in main |
| Artifact/test parity | MEDIUM | 1,122 tests exist only in zen-gates |
| Production governance | HIGH | main holds P149–P159B chain not fully present in zen-gates |

---

### Acceptance Criteria for Reconciled State

| Criterion | Target |
|-----------|--------|
| DB row count | 94,924 |
| bet_index schema | PRESENT in production DB |
| Drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |
| Tests | All P161–P179 contracts pass against production DB |
| Code parity | All analysis scripts and test contracts present in main |
| Roadmap docs | active_task.md, roadmap.md, CTO-Analysis.md current in main |

---

## Part B — Replay Product Backlog Audit (Plan Only)

### Current State

| Item | Status |
|------|--------|
| P149–P159B chain | COMPLETE |
| Strategies visible | 40/40 |
| Lifecycle as label | YES (not exclusion gate) |
| DB_ONLY_MISSING_LIFECYCLE | 0 |
| Multi-bet max | Bet 5 |
| Provenance fields displayed | YES |

---

### Backlog Categories

| Category | Priority | Key Items |
|----------|----------|-----------|
| Production governance / main sync | **P0** | Merge or backport P149–P179 code/docs; DB migration plan |
| UI polish | P1 | Multi-bet display (Bet 1–5), bet_index filter, lifecycle tooltips, provenance source labels |
| API contract hardening | P1 | bet_index in API response, pagination, structured errors |
| Operator guide / monitoring docs | P2 | Drift guard guide, incident playbook, DB anomaly runbook |
| Long-term trigger governance | P2 | P108 (37 draws remaining), P117 (0 new draws), P118 (phrase absent), POWER_LOTTO monitoring |
| Source/provenance caveats | P3 | 4_STAR (provenance absent), LEGACY_UNVERIFIED disposition, h6_gate_mk20_ew85 investigation |

---

### Prioritized Backlog

| ID | Title | Risk | Type | P181 Candidate |
|----|-------|------|------|----------------|
| B-P0-1 | main/zen-gates reconciliation plan execution | MEDIUM | Implementation — auth required | YES |
| B-P1-1 | Multi-bet display in replay UI | LOW | Implementation — auth required | YES |
| B-P1-2 | bet_index exposed in replay API | LOW | Implementation — auth required | No |
| B-P2-1 | Drift guard + DB migration operator guide | VERY LOW | Documentation | YES |
| B-P3-1 | 4_STAR provenance investigation | LOW (read-only) | Investigation | No |

---

### Exclusions

- No POWER_LOTTO research restart (P178A closure active)
- No wagering recommendations
- No new strategy prototype
- No DB write in P180
- No scheduler install

---

## Part C — P181 Decision Gate

Provide one of the following authorization phrases to proceed:

| Option | Authorization Phrase | Effect |
|--------|---------------------|--------|
| A2 plan | `YES start P181 main zen-gates reconciliation detailed plan only` | Detailed A2 backport plan. No execution. |
| Backlog exec | `YES start P181 replay product backlog audit execution only` | Execute B-P0-1, B-P1-1, B-P2-1. Per-item auth required. |
| Parity plan | `YES start P181 code-docs-tests parity plan only` | Plan for code/docs/tests parity. No implementation. |
| DB rehearsal | `YES start P181 controlled DB migration rehearsal plan only` | Rehearsal script + rollback plan design. No migration. |
| Monitoring | `YES start P181 long-term monitoring governance plan only` | P108/P117/P118/4_STAR trigger governance docs. No execution. |

**P181 BLOCKED until CEO provides one of the above authorization phrases.**

---

## Part D — CTO Recommendation

**Primary**: Code/docs/tests parity (A2 backport) before any production DB migration  
**Secondary**: Replay product backlog audit execution (B-P0-1 + B-P1-1 + B-P2-1)

**DB migration policy**: A3 only after detailed migration plan + dry-run rehearsal + DB backup + explicit per-step authorization. Never autonomous.

**Do not reopen POWER_LOTTO**: P178A closure policy remains active.

The highest near-term risk is the code divergence — 1,122 contract tests and research artifacts exist only in zen-gates. An A2 backport at MEDIUM risk resolves most documentation and test coverage gaps. DB migration follows only after full rehearsal planning. Multi-bet UI display (B-P1-1) and operator documentation (B-P2-1) are low-risk, high-value near-term wins.

---

## Explicit Forbidden Actions

| Action | Status |
|--------|--------|
| DB write | ENFORCED — FORBIDDEN |
| DB migration | ENFORCED — FORBIDDEN in P180 |
| Merge / rebase | ENFORCED — FORBIDDEN |
| Checkout other branch | ENFORCED — FORBIDDEN |
| controlled_apply | ENFORCED — FORBIDDEN |
| Registry mutation | ENFORCED — FORBIDDEN |
| Champion promotion | ENFORCED — FORBIDDEN |
| Deployment | ENFORCED — FORBIDDEN |
| POWER_LOTTO research rerun | ENFORCED — P178A closure active |
| New strategy | ENFORCED — FORBIDDEN |
| Scheduler install | ENFORCED — no separate authorization |
| 4_STAR backtest | ENFORCED — provenance absent |
| P108/P117/P118 execution | ENFORCED — wait-state conditions not met |
| Wagering recommendations | ENFORCED — FORBIDDEN |
| Win-guarantee claim | ENFORCED — FORBIDDEN |
| Stage/commit/push | ENFORCED — FORBIDDEN |

---

## Governance Confirmations

| Item | Status |
|------|--------|
| DB rows before/after | 94,924 / 94,924 |
| DB write | 0 |
| Registry mutation | 0 |
| Merge | None |
| controlled_apply | Not executed |
| Champion promotion | Not executed |
| Wagering recommendations | None |
| No win-guarantee claim | Confirmed |
| No stage/commit/push | Confirmed |
| P178A closure policy | ACTIVE — POWER_LOTTO research CLOSED |
| main/zen-gates split | Still unresolved |

---

*P180 is a plan-only document. No actions were executed. The main/zen-gates split remains unresolved. POWER_LOTTO research remains closed per P178A. Historical replay retains governance transparency value. No wagering recommendations are given. No win outcome is guaranteed.*
