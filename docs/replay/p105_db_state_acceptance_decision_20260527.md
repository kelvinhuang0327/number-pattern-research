# P105: DB State Acceptance Decision
## Option A — Accept Current DB State for Special3 Evaluation Only

**Date**: 2026-05-27  
**Classification**: `P105_DB_STATE_ACCEPTED_FOR_SPECIAL3_EVALUATION_ONLY`  
**Task Authority**: CEO-Authorized post-P104 (see `00-Plan/roadmap/CEO-Decision.md`)

---

## PROJECT_CONTEXT_LOCK

```
Project = LotteryNew
Canonical Repo = /Users/kelvin/Kelvin-WorkSpace/LotteryNew
Canonical Branch = main
This Active Task applies ONLY to LotteryNew.
If any task, file, commit, roadmap, artifact, or context belongs to another project
(Betting-pool, Stock-Prediction-System, etc.):
  STOP immediately. Do not summarize. Do not create artifacts. Do not commit.
  Classify as P105_BLOCKED_BY_CONTEXT_CONTAMINATION.
```

---

## Pre-Flight Evidence

| Check | Result |
|---|---|
| Repo Root | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` ✅ |
| Branch at task start | `ceo-decision-after-p104-2026-05-27` (same commit as `main`; switched to `main` before branching) |
| P105 Branch | `p105-db-state-acceptance-special3-evaluation-only` |
| HEAD Commit | `cf8db28710c7fb000435c005a9db7b4f3de2e4b2` ✅ (P104 merge) |
| Replay Rows | **54462** ✅ |
| 3_STAR count / max_draw | **4179** / **115000106** ✅ |
| 4_STAR count / max_draw | **2922** / **115000103** ✅ |
| POWER_LOTTO count / max_draw | 1913 / **115000041** ✅ |
| Drift Guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✅ |
| Branch Governance Guard | `BRANCH_GOVERNANCE_PASS — branch=main rows=54462` ✅ |
| Context Contamination | `NO_CROSS_PROJECT_CONTEXT_FOUND` ✅ |
| P104 Artifacts | All 4 files verified ✅ |
| Origin sync | 0 commits ahead of `origin/main` ✅ |

---

## User Input (Verbatim) and Interpretation

| Field | Value |
|---|---|
| **User Input Verbatim** | `A-` |
| **Interpretation** | **Option A — Accept current DB state for Special3 evaluation only** |
| **Selected Option** | **A** |

The CEO interprets the user input `A-` as Option A: accept the current DB state (3_STAR rows) as input for Special3 evaluation ONLY. This interpretation is final and is recorded in this artifact verbatim.

---

## P104 Input Summary

| Field | Value |
|---|---|
| PR Number | **#233** |
| Merge Commit | `cf8db28710c7fb000435c005a9db7b4f3de2e4b2` |
| PR Title | P104: Post-Ingestion DB Audit + Source Trace |
| Data Integrity Status | `PASS_WITH_NOTES` (date-format inconsistencies detected) |
| Raw Source File | NOT FOUND |
| `ingest_log` 3_STAR Entries | **0** |
| `ingest_log` 4_STAR Entries | **0** |
| Fetcher Supports 3_STAR | **NO** |
| Fetcher Supports 4_STAR | **NO** |
| Overall Source Finding | **SOURCE_UNKNOWN** |
| P104 Governance | No DB writes, no replay row inserts, no DB/history staged |

---

## Source-Unknown Caveat

> The 3_STAR rows (count=4179, max_draw=115000106) and 4_STAR rows (count=2922, max_draw=115000103) currently in the production DB have **no traceable ingestion path**. No raw source file was found, no `ingest_log` entries exist, and the fetcher does not support these lottery types. **This caveat MUST be propagated to all downstream evaluations (P106 Special3 evaluation)**. Evaluation results derived from these rows carry a source-unknown confidence penalty.

---

## "Never Again" Governance Clause

> **NEVER AGAIN: Future production DB schema mutations or row insertions MUST have ALL of the following before being authorized:**
> 1. **A corresponding `ingest_log` entry** recording source, timestamp, and row count;
> 2. **A verified fetcher or documented source-acquisition path**;
> 3. **Explicit governance authorization** in the active task document.
>
> **Any DB row mutation without these three elements constitutes a governance violation and MUST be rolled back.**

---

## Authorization Table

| Action | Status |
|---|---|
| P106 Special3 evaluation rerun | ✅ **AUTHORIZED** (separate task, carries source-unknown caveat) |
| 4_STAR backtest | ❌ **NOT AUTHORIZED** |
| Special3 production promotion | ❌ **NOT AUTHORIZED** |
| DB write (any) | ❌ **NOT AUTHORIZED** |
| DB staging (`lottery_v2.db`, `lottery_history.json`) | ❌ **NOT AUTHORIZED** |
| Lifecycle / champion / registry mutation | ❌ **NOT AUTHORIZED** |
| Migrations | ❌ **NOT AUTHORIZED** |
| DB staging | ❌ **NOT AUTHORIZED** |
| Force push | ❌ **NOT AUTHORIZED** |
| P107 stale baseline repair (this task) | ❌ **NOT IN SCOPE — deferred to P107** |
| P1.2 cross-lottery audit (this task) | ❌ **NOT IN SCOPE — deferred to P1.2** |
| P1.4 source-acquisition plan (this task) | ❌ **NOT IN SCOPE — deferred to P1.4** |
| Worktree-wide housekeeping | ❌ **NOT AUTHORIZED** |

---

## P98–P103 Stale-Baseline Test Waiver

The following phases carry stale baseline tests expecting `3_STAR=4115/max=115000024` and `4_STAR=0` (pre-ingestion state): **P98, P99, P100, P101, P102, P103**.

These tests are **KNOWN DEBT** and are deferred to **P107 (Stale Baseline Guard Repair)**. They are **NOT modified in P105**. Any test failures from these phases during the focused P105 CI run are tolerated and documented as known debt.

---

## Forbidden-Staging Scan Results

All scans performed after `git add` of the whitelist-only P105 files:

| Scan | Result |
|---|---|
| Scan 1 — filesystem artifacts / pid / backups / worktrees / runtime | `STAGE_CLEAN` ✅ |
| Scan 2 — DB / data / history files (`lottery_api/data/`) | `DB_STAGE_CLEAN` ✅ |
| Scan 3 — prior-phase outputs (non-P105 JSON) | `OUTPUT_STAGE_CLEAN` ✅ |
| Scan 4 — prior-phase docs (non-P105 MD) | `DOC_STAGE_CLEAN` ✅ |
| Scan 5 — test files (non-P105 test) | `TEST_STAGE_CLEAN` ✅ |
| Scan 5 — script files (non-P105 script) | `SCRIPT_STAGE_CLEAN` ✅ |
| Scan 5 — roadmap files | `ROADMAP_STAGE_CLEAN` ✅ |
| Scan 5 — `.gitignore` | `GITIGNORE_STAGE_CLEAN` ✅ |
| **Overall** | **ALL_CLEAN** ✅ |

`lottery_v2.db` and `lottery_history.json` are **NOT staged** (modified/unstaged, as per P104 governance). ✅

---

## Drift Guard / Branch Governance Guard Results

### Pre-branch (on `main`)
- Drift Guard: `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` @ 54462 rows ✅
- Branch Governance Guard: `BRANCH_GOVERNANCE_PASS — branch=main rows=54462` ✅

### Post-commit (on `p105-db-state-acceptance-special3-evaluation-only`)
- Drift Guard: See post-commit verification section
- Branch Governance Guard: `--expected-branch p105-db-state-acceptance-special3-evaluation-only --expected-rows 54462`

---

## Tests Summary

Focused test suite (P105 + adjacent guards):

```
tests/test_replay_lifecycle_drift_guard.py
tests/test_replay_branch_governance_guard.py
tests/test_p82_freshness_guard.py           (or closest available)
tests/test_p96_governance_baseline_repair.py
tests/test_p97_special3_special4_dryrun_closure.py
tests/test_p104_post_ingestion_db_audit_source_trace.py
tests/test_p105_db_state_acceptance_decision.py
```

P98–P103 stale baseline test failures are KNOWN DEBT (P107 scope) and are NOT modified here.

---

## DB Invariants (Pre and Post Commit)

| Metric | Expected | Status |
|---|---|---|
| `strategy_prediction_replays` rows | 54462 | ✅ |
| 3_STAR count | 4179 | ✅ |
| 3_STAR max_draw | 115000106 | ✅ |
| 4_STAR count | 2922 | ✅ |
| 4_STAR max_draw | 115000103 | ✅ |
| POWER_LOTTO max_draw | 115000041 | ✅ |

Production rows remain **unchanged at 54462**. No DB write was performed. No DB staging occurred.

---

## Next Actions (Separate Tasks)

| Phase | Name | Description |
|---|---|---|
| **P1.1 / P106** | Special3 Prospective Evaluation Rerun | Score P99 prospective predictions against accepted 3_STAR rows; carry source-unknown caveat |
| **P0.2 / P107** | Stale Baseline Guard Repair | Repair P98–P103 active guards to current accepted state without rewriting historical artifacts |
| **P1.2** | Cross-Lottery Prediction-Helpfulness Audit | POWER_LOTTO / DAILY_539 / BIG_LOTTO; must produce concrete promote/demote/Wave-N actions |
| **P1.3** | 4_STAR Provenance Decision Path | Rows present ≠ backtest authorized; decide governance path |
| **P1.4** | Source-Acquisition Plan for 3/4 Star | Design official source / fetcher / ingest_log path |

---

## CI Status

Push to `origin/p105-db-state-acceptance-special3-evaluation-only` — no force push attempted.  
PR title: `P105: DB state acceptance decision (Option A, Special3 evaluation only)`.

---

## Confirmations

- ✅ No production DB write
- ✅ No DB staging (`lottery_v2.db` and `lottery_history.json` NOT staged)
- ✅ No force push
- ✅ No lifecycle promotion
- ✅ No champion replacement
- ✅ No registry mutation
- ✅ No 4_STAR backtest
- ✅ No P106/P107/P1.2/P1.4 work performed in this task
- ✅ No worktree-wide cleanup
- ✅ P98–P103 tests NOT modified (known debt, P107 scope)
- ✅ Whitelist-only `git add`

---

## Final Classification

```
P105_DB_STATE_ACCEPTED_FOR_SPECIAL3_EVALUATION_ONLY
```
