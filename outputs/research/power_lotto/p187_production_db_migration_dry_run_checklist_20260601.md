# P187 — Production DB Migration Dry-Run Checklist (Plan Only)

**Task**: `P187_PRODUCTION_DB_MIGRATION_DRY_RUN_CHECKLIST_ONLY`
**Final Classification**: `P187_PRODUCTION_DB_MIGRATION_DRY_RUN_CHECKLIST_READY`
**Date**: 2026-06-01
**Branch**: `main`
**Authorization**: `YES start P187 production DB migration dry-run checklist only`

---

## Phase 0 — PASS

Production DB: 54,462 rows, bet_index ABSENT. P178A–P186 tests: 502 passed, 5 skipped. Drift guard: PASS.

---

## Part A — P186 Gate Evidence Summary

| Item | Value |
|------|-------|
| P186 classification | `P186_PRODUCTION_DB_MIGRATION_AUTHORIZATION_GATE_READY` |
| Production DB rows (current) | 54,462 (UNCHANGED) |
| Production bet_index | ABSENT |
| P185 temp rehearsal final rows | 94,924 |
| P185 dedup dropped | 160 (ALL NULL provenance) |
| P185 imported rows | 40,622 |
| Destructive phrase | Listed as **next option only** — NOT authorized in P187 |

---

## Part B — Dry-Run Checklist (13 Items — All Must Pass)

> **STOP on any failure. Do not skip items. Order is mandatory.**

### DRC-01 — Dispatch Verification
```bash
pwd                          # /Users/kelvin/Kelvin-WorkSpace/LotteryNew
git rev-parse --show-toplevel  # /Users/kelvin/Kelvin-WorkSpace/LotteryNew
git branch --show-current    # main
git rev-parse --git-dir      # .git
```
**STOP if**: any mismatch → `P188_STOPPED_ACTUAL_STATE_MISMATCH`

### DRC-02 — Clean Working Tree
```bash
git status --short
git diff --cached --name-only   # must be empty
```
**STOP if**: anything staged

### DRC-03 — Production DB Row/Schema Precheck
```bash
sqlite3 lottery_api/data/lottery_v2.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays;"  # expect 54462
sqlite3 lottery_api/data/lottery_v2.db \
  "PRAGMA table_info(strategy_prediction_replays);" | grep bet_index  # expect: no output
```
**STOP if**: count ≠ 54462 OR bet_index unexpectedly present

### DRC-04 — Zen-Gates Source DB Verification
```bash
test -d /Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802
git -C /Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802 \
  branch --show-current   # claude/zen-gates-ff6802
sqlite3 <zen-gates-db> "SELECT COUNT(*) FROM strategy_prediction_replays;"  # 94924
```
**STOP if**: worktree absent, wrong branch, or count ≠ 94924

### DRC-05 — P185 Artifact Classification Check
```bash
python3 -c "import json; d=json.load(open('outputs/research/power_lotto/\
p185_row_delta_import_rehearsal_temp_copy_20260601.json')); \
assert d['final_classification']=='P185_ROW_DELTA_IMPORT_REHEARSAL_TEMP_COPY_READY'; print('PASS')"
```
**STOP if**: assertion fails

### DRC-06 — Exact Destructive Authorization Phrase Verification
Operator must confirm the following phrase appears **verbatim** in the P188 prompt:

> `YES execute P188 production DB migration from main 54462 to reconciled 94924 using P185 rehearsal SQL, approve MAX(id) dedup dropping 160 null-provenance duplicate rows, create timestamped backup, no controlled_apply`

**STOP if**: phrase absent or any character differs

### DRC-07 — SQL Script Human Review
Open and read: `outputs/research/power_lotto/p185_rehearsal/p185_row_delta_import_sql_log_20260601.sql`

| Item | What to verify |
|------|---------------|
| SRC-01 | CREATE TABLE has all required columns |
| SRC-02 | INSERT uses `MAX(id)` dedup per (lottery_type, target_draw, strategy_id) |
| SRC-03 | `bet_index INTEGER NOT NULL DEFAULT 1` present |
| SRC-04 | `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)` present |
| SRC-05 | Zen-gates INSERT uses `WHERE bet_index > 1` |
| SRC-06 | ATTACH uses `file:...?mode=ro` |
| SRC-07 | COUNT checks after each step (54302, then 94924) |
| SRC-08 | Duplicate check expected 0 |
| SRC-09 | DROP + RENAME present in correct order |
| SRC-10 | `CREATE INDEX idx_spr_bet_index` present |
| SRC-11 | `PRAGMA integrity_check` present |
| SRC-12 | Transaction boundaries wrap all DDL/DML |

**STOP if**: any item fails human inspection

### DRC-08 — MAX(id) Dedup Approval
Verify on production DB before migration:
```sql
SELECT COUNT(*) FROM strategy_prediction_replays
WHERE id NOT IN (
  SELECT MAX(id) FROM strategy_prediction_replays
  GROUP BY lottery_type, target_draw, strategy_id
);   -- expect 160
```
**Operator confirms**: 160 rows will be dropped permanently. All have NULL provenance. This is irreversible without backup.

**STOP if**: count ≠ 160

### DRC-09 — 40,622-Row Import Approval
Verify on zen-gates source DB:
```sql
SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index > 1;  -- expect 40622
```
**Operator confirms**: 40,622 rows will be inserted from zen-gates.

**STOP if**: count ≠ 40622

### DRC-10 — Stop All API Writers
```bash
cat backend.pid 2>/dev/null | xargs kill -0 2>/dev/null \
  && echo 'BACKEND_RUNNING—STOP_IT' || echo 'BACKEND_STOPPED'
cat frontend.pid 2>/dev/null | xargs kill -0 2>/dev/null \
  && echo 'FRONTEND_RUNNING—STOP_IT' || echo 'FRONTEND_STOPPED'
```
**STOP if**: any writer still running

### DRC-11 — Create Timestamped Immutable Backup
```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP="lottery_api/data/lottery_v2.db.bak_p188_pre_migration_${TIMESTAMP}"
cp lottery_api/data/lottery_v2.db "${BACKUP}"
sqlite3 "${BACKUP}" "SELECT COUNT(*) FROM strategy_prediction_replays;"  # expect 54462
chmod 444 "${BACKUP}"
ls -la "${BACKUP}"   # verify r--r--r--
```
**STOP if**: backup count ≠ 54462 OR file not read-only

### DRC-12 — Pre-Migration Drift Guard
```bash
uv run python scripts/replay_lifecycle_drift_guard.py
# expect: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS
```
**STOP if**: drift guard FAIL

### DRC-13 — Final Go/No-Go Gate
Operator confirms ALL of the following:
- [ ] DRC-01 through DRC-12 all PASS
- [ ] Backup verified at 54,462 rows and immutable
- [ ] API writers confirmed stopped
- [ ] SQL script reviewed line-by-line (SRC-01 through SRC-12)
- [ ] Exact authorization phrase confirmed verbatim
- [ ] Operator ready to monitor migration to completion without interruption

**GO**: if all items ticked → execute migration SQL  
**NO-GO**: if any item unticked → do not execute, investigate and restart checklist

---

## Part C — SQL Review Checklist

**Source**: `outputs/research/power_lotto/p185_rehearsal/p185_row_delta_import_sql_log_20260601.sql`

Do NOT run ad-hoc SQL in production. Use only the reviewed SQL log.

---

## Part D — Backup / Rollback Checklist

### Backup
- **Path**: `lottery_api/data/lottery_v2.db.bak_p188_pre_migration_<YYYYMMDD_HHMMSS>`
- **Row count** must equal `54462`
- **bet_index** must be ABSENT before migration
- **chmod 444** — immutable before any migration SQL

### Rollback Triggers
Any of these → STOP immediately and restore from backup:
- Post-migration count ≠ 94924
- bet_index column absent after migration
- `PRAGMA integrity_check` ≠ ok
- Duplicate check > 0
- Any exception during migration SQL
- Drift guard FAIL after migration

### Rollback Procedure
```bash
cp lottery_api/data/lottery_v2.db.bak_p188_pre_migration_<timestamp> \
   lottery_api/data/lottery_v2.db
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*);"          # verify 54462
sqlite3 lottery_api/data/lottery_v2.db "PRAGMA table_info(...);" | grep bet_index  # ABSENT
uv run python scripts/replay_lifecycle_drift_guard.py               # verify PASS
# Restart API writers
```

---

## Part E — P188 Next Options

| Option | Phrase | Recommended |
|--------|--------|-------------|
| **A ⚠️ DESTRUCTIVE** | `YES execute P188 production DB migration from main 54462 to reconciled 94924 using P185 rehearsal SQL, approve MAX(id) dedup dropping 160 null-provenance duplicate rows, create timestamped backup, no controlled_apply` | **YES — after DRC-13 GO** |
| B | `YES start P188 production DB migration risk review only` | No |
| C | `YES start P188 maintain documented divergence and pause DB migration` | No |
| D | `YES start P188 replay product UI backlog implementation plan only` | No |

**P188 BLOCKED until CEO provides one of the above phrases.**  
The destructive phrase in option A is listed as a **next option only** — it is **NOT** authorized in P187.

---

## Governance Confirmations

| Item | Status |
|------|--------|
| Production DB rows before/after | 54,462 / 54,462 |
| DB write | **0** |
| Migration executed | **NO** |
| Backup created | **NO** |
| Schema change | **NO** |
| Row insert | **NO** |
| stage/commit/push | **NONE** |
| POWER_LOTTO research | **CLOSED** (P178A active) |
| main/zen-gates split | **STILL UNRESOLVED** |
| P188 | **BLOCKED** — CEO auth required |

---

*P187 is a plan-only dry-run checklist. No DB operations performed. Production DB unchanged. No wagering recommendations. No win outcome guaranteed.*
