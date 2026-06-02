# P183 — Controlled DB Migration Rehearsal Plan (Plan Only)

**Task**: `P183_CONTROLLED_DB_MIGRATION_REHEARSAL_PLAN_ONLY`
**Final Classification**: `P183_CONTROLLED_DB_MIGRATION_REHEARSAL_PLAN_READY`
**Date**: 2026-06-01
**Branch**: `main`
**Authorization Phrase**: `YES start P183 controlled DB migration rehearsal plan only`

---

## Phase 0 Verification — PASS

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | same | PASS |
| branch | `main` | `main` | PASS |
| main DB rows | `54462` | `54462` | PASS |
| main bet_index | ABSENT | ABSENT | PASS |
| zen-gates DB rows | `94924` | `94924` | PASS |
| zen-gates bet_index | PRESENT | PRESENT | PASS |
| P182 classification | `P182_CODE_DOCS_TESTS_PARITY_BACKPORT_READY` | same | PASS |
| P178A–P182 tests | 309 PASS / 4 SKIP | 309 passed, 4 skipped | PASS |
| drift guard | PASS | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` | PASS |

---

## Part A — Current DB Split Summary

| Item | main | zen-gates |
|------|------|-----------|
| DB rows | **54,462** | **94,924** |
| Row delta | — | **40,462** |
| bet_index | **ABSENT** | **PRESENT** (NOT NULL DEFAULT 1) |
| UNIQUE constraint | `(lottery_type, target_draw, strategy_id, replay_run_id)` | `(lottery_type, target_draw, strategy_id, bet_index)` |
| idx_spr_bet_index | ABSENT | PRESENT |
| P182 backport | code/docs/tests only | source |
| split status | **UNRESOLVED** | — |

### ⚠️ Critical Schema Finding

The UNIQUE constraint **changed between the two DB states**:

- **main**: `UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)`
- **zen-gates**: `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`

SQLite does not support `DROP CONSTRAINT`. A simple `ALTER TABLE ADD COLUMN bet_index` is **insufficient** — full table recreation is required. This is the primary risk driver for the migration.

---

## Part B — Controlled Migration Rehearsal Plan (11 Steps for P184)

> **P183 is plan-only.** None of these steps execute in P183. Execution requires:
> `YES start P184 controlled DB migration rehearsal on temp copy only`

### Step 1 — Pre-flight Checks

- Confirm repo = main, branch = main, git-dir = .git
- `SELECT COUNT(*) → expect 54462`
- Confirm `bet_index ABSENT` via `PRAGMA table_info`
- Confirm UNIQUE constraint = `(lottery_type, target_draw, strategy_id, replay_run_id)`
- Drift guard PASS at 54462
- `git status --short` — no DB files staged
- **STOP if any check fails**

### Step 2 — Immutable Backup

```bash
cp lottery_api/data/lottery_v2.db \
   lottery_api/data/lottery_v2.db.bak_p184_pre_migration_$(date +%Y%m%d_%H%M%S)
chmod 444 <backup_path>
sqlite3 <backup_path> "SELECT COUNT(*) FROM strategy_prediction_replays;"  # expect 54462
```

**STOP if backup size doesn't match or backup is unreadable. No migration proceeds without confirmed backup.**

### Step 3 — Temp Rehearsal DB

```bash
TEMP_DB=lottery_api/data/lottery_v2_migration_rehearsal_p184.db
cp lottery_api/data/lottery_v2.db $TEMP_DB
```

All migration steps target `$TEMP_DB` only. Production DB opened with `PRAGMA query_only=ON` throughout.

### Step 4 — Schema Migration (Table Recreation)

```sql
-- Against TEMP_DB only
BEGIN;

CREATE TABLE strategy_prediction_replays_new (
  id                       INTEGER PRIMARY KEY AUTOINCREMENT,
  lottery_type             TEXT NOT NULL,
  target_draw              TEXT NOT NULL,
  target_date              TEXT,
  strategy_id              TEXT NOT NULL,
  strategy_name            TEXT,
  strategy_version         TEXT,
  history_cutoff_draw      TEXT,
  replay_status            TEXT NOT NULL,
  reject_reason            TEXT,
  predicted_numbers        TEXT,
  predicted_special        INTEGER,
  actual_numbers           TEXT,
  actual_special           INTEGER,
  hit_numbers              TEXT,
  hit_count                INTEGER DEFAULT 0,
  special_hit              INTEGER DEFAULT 0,
  replay_run_id            INTEGER,
  generated_at             TEXT DEFAULT (datetime('now')),
  truth_level              TEXT DEFAULT NULL,
  controlled_apply_id      TEXT DEFAULT NULL,
  source                   TEXT DEFAULT NULL,
  provenance_hash          TEXT DEFAULT NULL,
  provenance_source        TEXT DEFAULT NULL,
  dry_run                  INTEGER DEFAULT 0,
  prediction_cutoff_date   TEXT,
  prediction_generated_at  TEXT,
  bet_index                INTEGER NOT NULL DEFAULT 1,
  UNIQUE(lottery_type, target_draw, strategy_id, bet_index),
  FOREIGN KEY (replay_run_id) REFERENCES strategy_replay_runs(id)
);

INSERT INTO strategy_prediction_replays_new
  SELECT id, lottery_type, target_draw, target_date, strategy_id,
         strategy_name, strategy_version, history_cutoff_draw,
         replay_status, reject_reason, predicted_numbers, predicted_special,
         actual_numbers, actual_special, hit_numbers, hit_count, special_hit,
         replay_run_id, generated_at, truth_level, controlled_apply_id,
         source, provenance_hash, provenance_source, dry_run,
         prediction_cutoff_date, prediction_generated_at,
         1 as bet_index  -- all existing rows are single-bet
  FROM strategy_prediction_replays;

-- Verify count before commit
SELECT COUNT(*) FROM strategy_prediction_replays_new;  -- expect 54462

DROP TABLE strategy_prediction_replays;
ALTER TABLE strategy_prediction_replays_new RENAME TO strategy_prediction_replays;

CREATE INDEX idx_spr_bet_index ON strategy_prediction_replays(bet_index);

COMMIT;
PRAGMA integrity_check;
VACUUM;
```

⚠️ **Pre-check required**: `SELECT lottery_type, target_draw, strategy_id, COUNT(*) FROM strategy_prediction_replays GROUP BY lottery_type, target_draw, strategy_id HAVING COUNT(*) > 1;` — must return 0 rows before recreation.

### Step 5 — Row Delta Reconciliation (Insert 40,462 Multi-bet Rows)

```sql
-- Against TEMP_DB only
ATTACH 'file:/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db?mode=ro' AS zg;

-- Insert multi-bet rows (bet_index > 1) from zen-gates
INSERT OR IGNORE INTO strategy_prediction_replays
  SELECT lottery_type, target_draw, target_date, strategy_id,
         strategy_name, strategy_version, history_cutoff_draw,
         replay_status, reject_reason, predicted_numbers, predicted_special,
         actual_numbers, actual_special, hit_numbers, hit_count, special_hit,
         replay_run_id, generated_at, truth_level, controlled_apply_id,
         source, provenance_hash, provenance_source, dry_run,
         prediction_cutoff_date, prediction_generated_at, bet_index
  FROM zg.strategy_prediction_replays
  WHERE bet_index > 1;

SELECT COUNT(*) FROM strategy_prediction_replays;  -- expect 94924

DETACH zg;
```

### Step 6 — Duplicate / Uniqueness Guard

```sql
SELECT lottery_type, target_draw, strategy_id, bet_index, COUNT(*)
FROM strategy_prediction_replays
GROUP BY lottery_type, target_draw, strategy_id, bet_index
HAVING COUNT(*) > 1;
-- Expected: 0 rows
```

**STOP and rollback if any duplicates found.**

### Step 7 — Provenance Preservation Check

Compare before-migration counts vs. after:

```sql
SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id IS NOT NULL;
SELECT COUNT(*) FROM strategy_prediction_replays WHERE provenance_hash IS NOT NULL;
SELECT COUNT(*) FROM strategy_prediction_replays WHERE source IS NOT NULL;
SELECT COUNT(*) FROM strategy_prediction_replays WHERE truth_level IS NOT NULL;
```

All counts must match pre-migration values for rows with bet_index=1 (existing rows unchanged).

### Step 8 — Drift Guard Adaptation Plan

`scripts/replay_lifecycle_drift_guard.py` currently expects 54462 rows. After migration:
- Guard must be updated to expect 94924 rows
- This update requires separate authorization and must happen AFTER migration is verified
- During rehearsal: run guard against temp DB and expect "DRIFT DETECTED" at 94924 (confirms guard still functions)
- Production update of guard = separate authorization step

### Step 9 — Rollback Plan

**Trigger conditions:** row count ≠ 94924 | duplicates found | provenance mismatch | integrity_check fails | any previously-PASS test now FAILS

```bash
# Immediate rollback
rm $TEMP_DB  # discard temp rehearsal
# Production DB untouched (read-only throughout rehearsal)
# Restore from backup if production DB was accidentally written:
cp lottery_api/data/lottery_v2.db.bak_p184_pre_migration_<timestamp> \
   lottery_api/data/lottery_v2.db
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*);"  # expect 54462
```

### Step 10 — Post-rehearsal Acceptance Criteria

| Criterion | Target |
|-----------|--------|
| temp DB row count | `94924` |
| PRAGMA integrity_check | `ok` |
| Duplicate check | `0 rows` |
| bet_index column | NOT NULL DEFAULT 1 |
| UNIQUE constraint | `(lottery_type, target_draw, strategy_id, bet_index)` |
| Provenance counts | unchanged for bet_index=1 rows |
| idx_spr_bet_index | created |
| P161 analysis script | runs successfully against temp DB |
| Contract tests (DB-dependent) | PASS against temp DB (not SKIP) |

### Step 11 — Production Migration Authorization Chain

Before any production migration:

1. P184 rehearsal report reviewed (all 10 acceptance criteria PASS)
2. CEO reviews rehearsal results
3. Immutable backup confirmed readable
4. Drift guard update reviewed
5. Exact CEO authorization phrase provided:
   `YES start P185 production DB migration execution authorized — backup confirmed — rehearsal passed`
6. All DB-dependent contract tests verified against rehearsal DB

**Production migration is P185 or later. P184 is rehearsal only.**

---

## Part C — Schema Migration Design

| | main | zen-gates target |
|-|------|-----------------|
| UNIQUE | `(lottery_type, target_draw, strategy_id, replay_run_id)` | `(lottery_type, target_draw, strategy_id, bet_index)` |
| bet_index | ABSENT | `INTEGER NOT NULL DEFAULT 1` |
| bet_index index | ABSENT | `idx_spr_bet_index` |

**Migration approach: TABLE RECREATION** — `ALTER TABLE ADD COLUMN` alone is insufficient because:
1. The UNIQUE constraint must change (SQLite has no `DROP CONSTRAINT`)
2. A new index (`idx_spr_bet_index`) must be created
3. The DDL for the old constraint references `replay_run_id` which must be dropped

**No production schema migration is authorized in P183.**

---

## Part D — Row Delta Reconciliation Design

| Source | Rows | Attribution |
|--------|------|-------------|
| P128 schema design | — | Defined bet_index column + UNIQUE constraint change |
| P126 Tier-B multi-bet | ~? | Controlled_apply of 5 Tier-B candidates generating bet_index 2-5 rows |
| P130–P135 replay expansion | ~? | Additional multi-bet controlled_apply rows |
| P149–P159B replay product chain | ~? | Provenance, lifecycle, truth_level assignments; may also include replay row expansion |
| P161–P181 research artifacts | 0 | Code/docs/tests only — no DB rows added |
| **Total delta** | **40,462** | **UNKNOWN precise breakdown — REQUIRES_P184_REHEARSAL_AUDIT** |

Exact per-task attribution requires `controlled_apply_id` and `source` field analysis in P184 rehearsal. Do not assume precise numbers without audit.

---

## Part E — Risk Assessment

| Risk | Level | Mitigation |
|------|-------|-----------|
| Schema mismatch (UNIQUE constraint change) | **HIGH** | Table recreation in transaction; verify row count before commit |
| Row-count drift after insert | **HIGH** | Step 5 count check; drift guard adaptation |
| Duplicate key on bet_index=1 for existing rows | **MEDIUM** | Pre-check (step 4) before table recreation |
| Old constraint vs new constraint code breakage | **HIGH** | Audit all code referencing replay_run_id uniqueness before production migration |
| Stale tests vs migrated DB | **MEDIUM** | requires_zen_gates_db tests will PASS after migration; verify in rehearsal |
| Backup/rollback failure | **LOW** | Immutable backup (step 2) required; production DB read-only during rehearsal |
| Accidental production DB write | **HIGH** | PRAGMA query_only=ON on production DB; all writes target temp DB only |

---

## Part F — P184 Authorization Options

| Option | Authorization Phrase | Recommended |
|--------|---------------------|-------------|
| **A** | `YES start P184 controlled DB migration rehearsal on temp copy only` | **YES** |
| B | `YES start P184 DB migration preflight audit only` | No |
| C | `YES start P184 replay product UI backlog implementation plan only` | No |
| D | `YES start P184 maintain documented divergence and pause DB migration` | No |
| E | `YES start P184 production DB migration authorization gate only` | No |

**P184 BLOCKED until CEO provides one of the above authorization phrases.**

---

## Part G — CTO Recommendation

**Primary**: `YES start P184 controlled DB migration rehearsal on temp copy only`

The schema change (UNIQUE constraint + bet_index column) requires full table recreation. This is a
non-trivial migration with HIGH risk of data corruption if executed without rehearsal. A verified
temp-copy rehearsal is mandatory before any production migration.

**Do NOT:**
- Perform production DB migration in P184
- Copy zen-gates DB file over main DB (destroys P149-P159B production chain governance)
- Run controlled_apply
- Reopen POWER_LOTTO research (P178A closure active)
- Weaken P182 code/docs/tests parity

**Production migration** only after: rehearsal PASS + backup confirmed + `P185` exact CEO authorization phrase.

---

## Explicit Forbidden Actions (P183 Confirmed)

| Action | Status |
|--------|--------|
| DB write | **0 — CONFIRMED** |
| DB migration | **NOT PERFORMED** |
| DB copy | **NOT PERFORMED** |
| Rehearsal execution | **NOT PERFORMED** (plan only) |
| Row insertion | **0** |
| Schema change | **NOT PERFORMED** |
| controlled_apply | **NOT PERFORMED** |
| Registry mutation | **NOT PERFORMED** |
| merge/rebase/cherry-pick | **NONE** |
| checkout | **NONE** |
| stage/commit/push | **NONE** |
| deployment | **NONE** |
| POWER_LOTTO research rerun | **NONE** (P178A active) |
| wagering recommendation | **NONE** |
| win guarantee | **NONE** |

---

## Governance Confirmations

| Item | Status |
|------|--------|
| main DB rows before/after | 54,462 / 54,462 |
| DB write | 0 |
| DB migration performed | NO |
| DB copy performed | NO |
| Rehearsal execution | NO (plan only) |
| P178A closure policy | **ACTIVE** |
| main/zen-gates split | **STILL UNRESOLVED** |
| P184 | **BLOCKED** — CEO authorization required |

---

*P183 is a plan-only document. No DB writes, no migration, no rehearsal execution, no schema changes,
no row insertions were performed. The main/zen-gates split remains unresolved. POWER_LOTTO research
remains closed per P178A. No wagering recommendations. No win outcome guaranteed.*
