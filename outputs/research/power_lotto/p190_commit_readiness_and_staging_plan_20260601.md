# P190 — Commit Readiness and Staging Plan

**Task:** P190_COMMIT_READINESS_AND_STAGING_PLAN_ONLY  
**Date:** 2026-06-01  
**Authorization Phrase:** `YES start P190 commit readiness and staging plan only`  
**Final Classification:** `P190_COMMIT_READINESS_AND_STAGING_PLAN_READY`

---

## Phase 0 — Actual State Verification: PASS

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| Repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew | /Users/kelvin/Kelvin-WorkSpace/LotteryNew | ✅ PASS |
| Branch | main | main | ✅ PASS |
| git-dir | .git | .git | ✅ PASS |
| In worktree | false | false | ✅ PASS |
| Production DB rows | 94924 | 94924 | ✅ PASS |
| bet_index PRESENT | true | true | ✅ PASS |
| bet_index NULL count | 0 | 0 | ✅ PASS |
| Duplicate count | 0 | 0 | ✅ PASS |
| integrity_check | ok | ok | ✅ PASS |
| P188 backup exists | true | true | ✅ PASS |
| Backup rows | 54462 | 54462 | ✅ PASS |
| Backup bet_index | ABSENT | ABSENT | ✅ PASS |
| P178A-P189 tests | 644 PASS | 644 passed, 0 failed | ✅ PASS |
| Drift guard | PASS | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS | ✅ PASS |
| Staged files | 0 | 0 | ✅ PASS |
| P189 classification | P189_POST_MIGRATION_VERIFICATION_COMMIT_READINESS_READY | MATCH | ✅ PASS |

**No STOP conditions triggered.**

---

## Part A — Commit Readiness Audit

### Overall Status: READY

The production DB has been successfully migrated, verified, and tested. All technical gates pass.

| Item | Status |
|------|--------|
| DB migration 54462→94924 | ✅ COMPLETE |
| bet_index column added | ✅ PRESENT |
| PRAGMA integrity_check | ✅ ok |
| Duplicate rows | ✅ 0 |
| NULL bet_index | ✅ 0 |
| P188 backup verified | ✅ 54462 rows, ABSENT bet_index |
| Drift guard | ✅ PASS (94924, legacy 420) |
| Full test suite | ✅ 644 passed, 0 failed, 0 skipped |
| Staged / committed / pushed | **0 / 0 / 0** |

### Git Dirty File Inventory

**17 modified tracked files:**

| File | Category | Action in P191 |
|------|----------|----------------|
| lottery_api/data/lottery_v2.db | DB migration payload | STAGE (Group A) |
| scripts/replay_lifecycle_drift_guard.py | Drift guard update | STAGE (Group E) |
| tests/conftest.py | Stale test repair | STAGE (Group E) |
| pytest.ini | Test config (P182 backport) | STAGE (Group E) |
| 00-Plan/roadmap/CTO-Analysis.md | Roadmap doc | STAGE (Group H) |
| 00-Plan/roadmap/roadmap.md | Roadmap doc | STAGE (Group H) |
| docs/replay/p126_*.md | Pre-existing dirty (P128) | STAGE (Group G, CEO confirm) |
| outputs/replay/p126_*.json | Pre-existing dirty (P128) | STAGE (Group G, CEO confirm) |
| outputs/replay/p12_1500_*.json | Pre-existing dirty | STAGE (Group G, CEO confirm) |
| outputs/replay/p2_lifecycle_*.json | Pre-existing dirty | STAGE (Group G, CEO confirm) |
| outputs/replay/p2_lifecycle_*.md | Pre-existing dirty | STAGE (Group G, CEO confirm) |
| data/rolling_monitor_BIG_LOTTO.json | Monitoring data | DO NOT STAGE without review |
| data/rolling_monitor_POWER_LOTTO.json | Monitoring data | DO NOT STAGE without review |
| lottery_api/data/lottery_history.json | Data file | DO NOT STAGE without review |
| backend.pid | **FORBIDDEN runtime** | **NEVER STAGE** |
| frontend.pid | **FORBIDDEN runtime** | **NEVER STAGE** |
| claude-code-showcase | **Unknown/suspicious** | **DO NOT STAGE without CEO review** |

**Key untracked new files (major groups):**
- `00-Plan/roadmap/active_task.md`, `CEO-Decision.md` → Stage (Group H)
- `backups/p188_*` → Stage .db + .sha256 (Group B); exclude .db-shm/.db-wal
- `outputs/research/power_lotto/p161-p190` (65+ files) → Stage (Group C)
- `tests/test_p161-p190, test_szc1, test_p2-p5` (40 files) → Stage (Group D)
- `analysis/power_lotto/*.py` (7 files) → Stage (Group F)
- `runtime/`, `.gstack/`, `.fuse_hidden*`, `*.db.bak_*` → **NEVER STAGE**

---

## Part B — Staging Whitelist Proposal for P191

### Group A — DB Migration Payload
**Files:** `lottery_api/data/lottery_v2.db`  
**Prerequisite:** `sqlite3 lottery_api/data/lottery_v2.db "PRAGMA wal_checkpoint(TRUNCATE);"` before staging  
**Risk:** MEDIUM — large binary (~15-25MB repo size increase)

### Group B — Backup Payload
**Include:** `backups/p188_lottery_v2_backup_20260601_153821.db`, `.db.sha256`  
**Exclude:** `.db-shm`, `.db-wal` (WAL sidecars — should be empty after checkpoint)  
**Exclude:** `backups/lottery_v2_pre_p0_*` through `pre_p7_*` (older backups — separate CEO decision)  
**Risk:** MEDIUM — backup DB binary ~5MB

### Group C — Research Artifacts P161-P190
**Pattern:** `outputs/research/power_lotto/p16[1-9]_*, p17[0-9]_*, p18[0-9]_*, p190_*, szc[12]_*, p184_rehearsal/, p185_rehearsal/, p188_*sql_log*`  
**Count:** 65+ files  
**Risk:** LOW — text/JSON/MD files

### Group D — Contract Tests
**Include:** `tests/test_p161_*` through `tests/test_p190_*`, `tests/test_szc1_*`, `tests/test_p2_catalog_apply_*.py`, `tests/test_p3_relay_*.py`, `tests/test_p4_*.py`, `tests/test_p5_*.py`  
**Count:** 40 test files  
**Risk:** LOW

### Group E — Drift Guard and Test Config
**Files:** `scripts/replay_lifecycle_drift_guard.py`, `tests/conftest.py`, `pytest.ini`  
**Risk:** LOW

### Group F — Analysis Scripts (Backported from zen-gates)
**Files:** `analysis/power_lotto/*.py` (7 files including `__init__.py`)  
**Risk:** LOW

### Group G — Other Code, Scripts, and Docs (CEO review required)
**Includes:** P0-P128 chain artifacts, `lottery_api/fetcher/`, migration SQL, server script, CSS, docs, replay outputs  
**Note:** These are pre-existing dirty from the P0-P128 chain. CEO should confirm whether they belong in the P182-P190 commit or a separate cleanup commit.  
**Risk:** LOW

### Group H — Roadmap Docs
**Files:** `00-Plan/roadmap/active_task.md`, `roadmap.md`, `CTO-Analysis.md`, `CEO-Decision.md`  
**Risk:** LOW

---

## Part C — Commit Message Proposal

```
P182-P190: reconcile replay DB and post-migration governance

P182: backport 42 research artifacts (P161-P181), 5 analysis scripts,
      21 contract tests, and conftest skip markers from zen-gates to main.
      No DB write; main was still 54462 rows, bet_index ABSENT.

P183-P185: controlled DB migration rehearsal (temp copy only).
  P183: 11-step plan; TABLE RECREATION required (ALTER TABLE insufficient).
  P184: schema rehearsal; MAX(id) dedup 54462->54302 base rows.
  P185: row-delta import; 40622 rows added; final 94924 exact match zen-gates.

P186-P187: production migration authorization gate + 13-item dry-run checklist.
      MAX(id) dedup policy and exact SQL approved before production write.

P188: production DB migration executed.
  DB rows: 54462 -> 94924
  bet_index: ABSENT -> PRESENT (NOT NULL DEFAULT 1)
  Dropped: 160 duplicate rows (all NULL provenance)
  Imported: 40622 multi-bet rows (bet_index 2-5)
  Backup: backups/p188_lottery_v2_backup_20260601_153821.db (54462 rows, verified)
  PRAGMA integrity_check: ok | No controlled_apply | No POWER_LOTTO research rerun

P189: post-migration verification + test repair.
  Drift guard updated: total=94924, legacy=420
  9 stale pre-migration assertions repaired (P183-P187 contract tests)
  Full test suite: 644 passed, 0 failed, 0 skipped

P190: commit readiness audit + staging whitelist plan.
  Staged: 0 (P190 plan-only; stage/commit/push deferred to P191)

Governance:
  POWER_LOTTO R2 research: CLOSED (P178A) — no promotion, no wagering guidance
  Second-zone SZC1/SZC2: display-only governance enforced
  main/zen-gates DB split: RECONCILED
  DB-level reconciliation: COMPLETE; not yet committed (awaiting P191 authorization)
```

---

## Part D — P191 Authorization Gate Options

| Option | Phrase | Risk |
|--------|--------|------|
| **A** | `YES start P191 stage commit push authorization gate only` | LOW — plan only |
| **B** | `YES start P191 stage reviewed files and create local commit only, no push` | MEDIUM — local, reversible |
| **C** | `YES start P191 stage reviewed files commit and push to origin main` | HIGH — irreversible after push |
| **D** | `YES start P191 rollback decision gate only` | LOW — plan only |
| **E** | `YES start P191 pause with migrated DB uncommitted` | LOW — no action |

> P191 BLOCKED pending CEO authorization phrase.  
> If P191 involves staging/committing/pushing, P191 MUST re-run full verification and forbidden staging scan before any git add.

---

## Part E — Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| R1: Committing DB binary (repo size ~15-25MB) | HIGH | WAL checkpoint before staging; consider git-lfs |
| R2: Backup DB inclusion (~5MB) | MEDIUM | Include for audit trail; CEO may decide otherwise |
| R3: Large diff (2 DBs + 65 artifacts + 40 tests) | MEDIUM | Stage in groups A-H; consider splitting commit |
| R4: Incomplete staging (DB without tests/drift guard) | MEDIUM | Stage ALL groups atomically; run 644-test suite before commit |
| R5: Accidental forbidden file staging | **HIGH** | ABSOLUTE: per-file git add only; run forbidden scan after each add |
| R6: Push without explicit authorization | **HIGH** | Default to Option B (local only); never push unless CEO selects Option C |
| R7: Rollback complexity after commit+push | MEDIUM | P188 backup verified; document procedure in Option D |
| R8: Branch protection / CI blocking push | LOW-MEDIUM | Check branch protection before attempting push in P191 |
| R9: WAL sidecar (.db-wal/.db-shm) | LOW | PRAGMA wal_checkpoint(TRUNCATE) before staging |

---

## Governance Confirmations

| Confirmation | Value |
|---|---|
| no_db_write_in_p190 | ✅ true |
| no_controlled_apply | ✅ true |
| no_registry_mutation | ✅ true |
| no_research_rerun | ✅ true |
| no_merge | ✅ true |
| no_rebase | ✅ true |
| no_cherry_pick | ✅ true |
| no_checkout_other_branch | ✅ true |
| no_stage | ✅ true |
| no_commit | ✅ true |
| no_push | ✅ true |
| production_db_rows = 94924 | ✅ true |
| bet_index_present | ✅ true |
| drift_guard_pass | ✅ true |
| tests_pass (644 passed) | ✅ true |
| power_lotto_research_closed | ✅ true |
| db_level_reconciliation_complete | ✅ true |
| commit_not_yet_created | ✅ true |

**next_task_blocked_by_user_authorization: true**

---

## Final Classification

**`P190_COMMIT_READINESS_AND_STAGING_PLAN_READY`**

P191 is BLOCKED pending explicit CEO authorization phrase.
