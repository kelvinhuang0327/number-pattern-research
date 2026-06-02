# P163 Reconcile Readiness Audit

**Task**: P163_RECONCILE_READINESS_AUDIT
**Date**: 2026-05-31
**Branch**: claude/zen-gates-ff6802
**Final Classification**: `P163_RECONCILE_READINESS_AUDIT_READY`

---

> **GOVERNANCE NOTICE**: This audit does NOT authorize any merge, DB write, registry change, or champion promotion. All findings are read-only observations. No reconcile action may be taken without explicit user authorization in P164.

---

## Executive Summary

A full state audit of the `zen-gates-ff6802` worktree against the `main` branch reveals a significant and non-trivial divergence that requires a deliberate reconcile decision before any action is taken.

**Key findings**:

1. **DB row count split**: zen-gates has 94,924 rows; main has 54,462 rows — a delta of 40,462 rows from P129B-P141 controlled_apply operations that were executed in zen-gates but never applied to main.
2. **Schema incompatibility**: zen-gates DB has a `bet_index` column (column 27, added in P129B); main DB does not. This is an irreversible schema divergence.
3. **Research artifacts exclusive to zen-gates**: P161/P162 POWER_LOTTO effectiveness baseline outputs, 36 test files (P140-P162), and 30+ scripts (P126a-P159B series) exist only in zen-gates.
4. **All Phase 0 verification checks passed**: DB=94924, drift guard=PASS, P161 23/23 PASS, P162 14/14 PASS, P162 artifacts confirmed.

---

## zen-gates vs main State Comparison

| Dimension | zen-gates (ff6802) | main |
|---|---|---|
| Branch | claude/zen-gates-ff6802 | main |
| HEAD commit | c8b423d | d1a6817 |
| DB total rows | **94,924** | **54,462** |
| POWER_LOTTO rows | 36,104 | 15,142 |
| `bet_index` column | **PRESENT** (col 27) | **ABSENT** (26 cols) |
| UNIQUE constraint | (type, draw, strategy, bet_index) | (type, draw, strategy) |
| outputs/research/power_lotto/ | 4 artifacts (P161-P162) | **NOT FOUND** |
| Tests p140-p162 | 36 test files | 0 test files |
| Scripts p126a-p159b | 30+ scripts | ~5 scripts |
| Roadmap last updated | 2026-05-30 (P159B) | 2026-05-28 (P128) |
| Drift guard | PASS | Not checked (main DB not run) |

---

## Diff Summary

### DB Row Count Difference

| Source | zen-gates | main | Delta |
|---|---:|---:|---:|
| Total replay rows | 94,924 | 54,462 | +40,462 |
| POWER_LOTTO rows | 36,104 | 15,142 | +20,962 |

The 40,462 row delta comes from P129B schema migration + P130-P141 Wave2 multi-bet controlled_apply operations executed exclusively in zen-gates. Each apply step was authorized via explicit phrase by the user.

### Schema Difference

The `bet_index` column was added to zen-gates in P129B via an 18-step SQLite migration (with ROW_NUMBER() COPY for 120 duplicate groups). Main DB lacks this column. The UNIQUE constraint also differs. **Applying zen-gates API code against main DB without migration would fail.**

### Artifact Differences

- **zen-gates only**: P161/P162 research outputs, analysis/ directory, 36 test files P140-P162, 30+ scripts P126a-P159B
- **main only**: roadmap up to P128 (design stage), DB at 54462 rows (pre-migration state)
- **Roadmap divergence**: zen-gates roadmap documents complete governance chain through P159B; main roadmap only reflects P128 design

---

## Risk Classification Table

| Category | Items | Risk Level |
|---|---|---|
| Docs/tests/report artifacts (P161-P162 JSON/MD, test files) | Read-only, no DB impact | LOW |
| Roadmap, active_task.md, CTO-Analysis.md updates | Documentation only | LOW |
| Research output scripts (analysis/, p126a-p159b read-only scripts) | Read-only | LOW |
| Strategy registry source code (lifecycle labels, new strategies) | Code reconcile needed | MEDIUM |
| API endpoint additions (/api/replay/all-strategy-catalog) | Code reconcile | MEDIUM |
| UI changes (multi-bet badges, provenance, lifecycle in index.html) | Code reconcile | MEDIUM |
| DB schema migration (bet_index column, UNIQUE constraint) | Irreversible schema change | HIGH |
| DB row insertion (40,462 multi-bet rows) | Irreversible data change | HIGH |
| Merge without explicit authorization | Unauthorized governance action | BLOCKED |
| Registry mutation without per-strategy auth | Unauthorized | BLOCKED |
| Champion promotion | BLOCKED (P147 evidence absent) | BLOCKED |

---

## Options A/B/C

### Option A: Merge code/docs/tests only — leave main DB untouched

Merge zen-gates code, tests, scripts, and documentation to main branch. Accept that main DB (54,462 rows, no bet_index) will be incompatible with multi-bet features until separately migrated.

**Pros**: No DB risk; preserves main DB integrity; research artifacts reach main history; lower authorization burden.

**Cons**: Code-DB split — API/UI bet_index features will fail against main DB; technical debt; large test surface becomes broken against main until DB migrated.

**Required Authorization**: Explicit user instruction to merge code/docs/tests only.

**Stop Guard**: Verify main DB row count remains 54,462 before and after merge.

---

### Option B: Designate zen-gates as canonical dataset

Accept zen-gates as the authoritative production DB and research dataset. Archive main's 54,462-row DB as legacy.

**Pros**: Eliminates split immediately; all zen-gates tests valid; no migration risk; P161/P162 baseline against full dataset is the canonical record.

**Cons**: Violates current "no worktree canonical" repo policy; worktree directories are ephemeral; requires policy update; CI/CD may target main branch.

**Required Authorization**: Explicit user instruction to designate zen-gates DB as canonical.

**Stop Guard**: Verify worktree at /Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802 before any work; copy DB to permanent location if designating as canonical.

---

### Option C: Controlled DB/data migration plan

Formally migrate main DB to match zen-gates state: (1) backup main DB, (2) P129B bet_index migration on main, (3) re-run P130-P141 controlled_apply in order, (4) drift guard at 94,924 rows, (5) merge code/tests.

**Pros**: Full consistency between main branch and zen-gates; all tests valid against main; single canonical branch; fully auditable.

**Cons**: Highest complexity; requires ~12 sequential authorization phrases; risk of partial failure; each controlled_apply is irreversible without backup; time-consuming.

**Required Authorization**: (1) P129B schema migration phrase on main DB; (2) per-strategy authorization for each of P126B, P126C, P126D, P126E, P126F, P131, P132, P133, P134, P136-P141 applies — documented in scripts/p126a_controlled_apply_authorization_gate.py.

**Stop Guard**: Drift guard PASS at expected intermediate row count before each apply step. STOP on any deviation.

---

## CTO Recommendation

**Choose Option A or C. Do not proceed with either until P164 decision gate.**

The CTO recommends a conservative approach:

1. **Immediate**: No autonomous action. Take this audit to P164 as a decision gate where the user explicitly chooses one option.

2. **If time-constrained**: Option A (code/docs/tests merge) is the lowest-risk first step. It gets 36 tests and 30+ scripts into main history without touching the DB. The DB migration can be authorized separately later.

3. **If full consistency is required**: Option C is correct but requires sequential authorization. The scripts are already written and rehearsed (P129B rehearsed on temp DB with all 54,462 rows preserved; P126A gate documents exact authorization phrases). The execution risk is manageable if done step-by-step.

4. **Option B** (designate zen-gates as canonical) is viable but requires a repo policy decision that only the user can make.

**Explicitly forbidden without authorization**:
- Any merge, rebase, or cherry-pick from zen-gates to main
- Any DB write to main DB (schema migration or row insertion)
- Any registry mutation on main branch
- Any champion promotion (P147 evidence still absent)

---

## Next Steps

**P164_RECONCILE_PLAN_DECISION_GATE** is the only authorized next task. It must:
- Present this audit to the user
- Require explicit choice of Option A, B, or C
- Require authorization phrases for any DB write
- Not autonomously execute any reconcile action

No further reconcile work may proceed without the user's explicit choice and authorization in P164.

---

## Artifact Provenance

| Artifact | Path |
|---|---|
| P163 JSON | outputs/research/power_lotto/p163_reconcile_readiness_audit_20260531.json |
| P163 MD | outputs/research/power_lotto/p163_reconcile_readiness_audit_20260531.md |
| P161 baseline JSON | outputs/research/power_lotto/p161_effectiveness_baseline_20260531.json |
| P162 closure JSON | outputs/research/power_lotto/p162_p161_result_closure_20260531.json |
| Drift guard script | scripts/replay_lifecycle_drift_guard.py |
| DB (zen-gates) | lottery_api/data/lottery_v2.db (94924 rows) |
| DB (main) | /Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db (54462 rows) |

---

*Generated by P163 audit-only task. No DB writes, no merge, no commit, no push, no registry mutation, no champion promotion.*
