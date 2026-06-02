# P186 — Production DB Migration Authorization Gate (Plan Only)

**Task**: `P186_PRODUCTION_DB_MIGRATION_AUTHORIZATION_GATE_ONLY`
**Final Classification**: `P186_PRODUCTION_DB_MIGRATION_AUTHORIZATION_GATE_READY`
**Date**: 2026-06-01
**Branch**: `main`
**Authorization**: `YES start P186 production DB migration authorization gate only`

---

## Phase 0 — PASS

Production DB: 54,462 rows, bet_index ABSENT. Zen-gates: 94,924 rows, bet_index PRESENT. P185 classification confirmed. P178A–P185 tests: 459 passed, 5 skipped.

---

## Part A — P185 Rehearsal Evidence Summary

| Metric | Value |
|--------|-------|
| Production DB (before/after P185) | 54,462 (UNCHANGED) |
| Temp base rows after dedup | 54,302 |
| Dedup dropped rows | 160 (ALL NULL provenance) |
| Duplicate groups | 120 |
| Imported rows (bet_index 2–5) | 40,622 |
| Temp final rows | **94,924** |
| Per-lottery match vs zen-gates | **EXACT** ✅ |
| bet_index distribution match | **EXACT** ✅ |
| Duplicate check | **0** ✅ |
| Integrity check | **ok** ✅ |
| Provenance coverage (imported) | 99.7% (40,502/40,622) |
| P185 classification | `P185_ROW_DELTA_IMPORT_REHEARSAL_TEMP_COPY_READY` |

---

## Part B — Production Migration Authorization Gate (12 Conditions)

**ALL 12 conditions must be explicitly met before P187 may execute.**

| Gate | Condition | Impact |
|------|-----------|--------|
| **G1** | Approve MAX(id) dedup policy | 160 rows permanently removed |
| **G2** | Approve dropping exactly 160 NULL-provenance rows | Irreversible without backup |
| **G3** | Approve full table recreation (UNIQUE constraint change) | SQLite has no DROP CONSTRAINT |
| **G4** | Approve adding bet_index INTEGER NOT NULL DEFAULT 1 | Schema change |
| **G5** | Approve importing 40,622 multi-bet rows from zen-gates lineage | 11 controlled_apply waves |
| **G6** | Approve timestamped immutable backup before migration | `chmod 444` — must verify row count 54,462 |
| **G7** | Approve production lock / no concurrent writes | Stop frontend + backend before migration |
| **G8** | Approve exact SQL from P185 rehearsal log | `p185_row_delta_import_sql_log_20260601.sql` reviewed |
| **G9** | Approve post-migration validation commands | COUNT=94924, bet_index PRESENT, 0 dups, integrity_check=ok |
| **G10** | Approve rollback plan | Trigger: count≠94924 / dups>0 / integrity fails → cp backup |
| **G11** | Acknowledge no controlled_apply during migration | Rows come only from rehearsed SQL |
| **G12** | Acknowledge P178A closure: no POWER_LOTTO research restart | P178A remains ACTIVE |

---

## Part C — P187 Execution Boundary

### Allowed in P187

- Create timestamped immutable backup
- Stop API writers (verify stopped)
- Run reviewed migration SQL (dedup + table recreation + bet_index + row import)
- Verify: COUNT = 94,924 | bet_index PRESENT | 0 duplicates | integrity_check = ok
- Update drift guard expected count: 54,462 → 94,924
- Run contract tests — DB-dependent tests should now PASS (not SKIP)
- Restart API writers after validation passes
- Produce P187 result artifact

### Forbidden in P187

- Strategy research of any kind
- controlled_apply beyond rehearsed 40,622 rows
- Registry mutation
- UI/API new feature implementation
- Importing rows beyond the 40,622 validated in P185
- stage / commit / push of DB file

---

## Part D — Exact Authorization Phrase for P187

> **`YES execute P187 production DB migration from main 54462 to reconciled 94924 using P185 rehearsal SQL, approve MAX(id) dedup dropping 160 null-provenance duplicate rows, create timestamped backup, no controlled_apply`**

**This exact phrase is required verbatim in the P187 prompt.** No paraphrase, partial quote, or synonym is accepted. If absent, P187 must `STOP` and report `P187_STOPPED_MISSING_EXACT_AUTHORIZATION_PHRASE`.

---

## Part E — Risk Review

| Risk | Level | Mitigation |
|------|-------|-----------|
| Destructive migration (DROP + recreate) | **HIGH** | Single transaction; immediate rollback on any error |
| Dedup drops 160 rows permanently | **MEDIUM** | All NULL-provenance confirmed; CEO explicit approval required |
| Row import lineage (40,622 rows) | **LOW** | Wave attribution verified; 99.7% provenance coverage |
| Backup/restore failure | **MEDIUM** | Verify backup row count + file size + chmod 444 before migration |
| Production lock (concurrent writes) | **HIGH** | Stop and verify all API writers before first SQL statement |
| Test compatibility post-migration | **MEDIUM** | requires_zen_gates_db markers become obsolete; drift guard needs update |
| Rollback after partial migration | **LOW** | Transaction wraps all DDL/DML; rollback = cp backup |
| Accidental DB stage/commit/push | **LOW** | DB file must be in .gitignore; verify with git status before and after |
| main/zen-gates split resolution | **MEDIUM** | After P187, main DB = zen-gates DB count. Verify all contract tests pass. |

---

## Part F — P187 Preflight Checklist

All 15 steps must pass. Stop on first failure.

| Step | Command | Expected |
|------|---------|---------|
| PF-1 | `pwd && git rev-parse --show-toplevel` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` |
| PF-2 | `git branch --show-current` | `main` |
| PF-3 | `git rev-parse --git-dir` | `.git` |
| PF-4 | `sqlite3 ... "SELECT COUNT(*)"` | `54462` |
| PF-5 | `PRAGMA table_info` — bet_index check | `bet_index ABSENT` |
| PF-6 | zen-gates worktree accessible | `SOURCE_EXISTS` |
| PF-7 | P185 artifact classification | `P185_ROW_DELTA_IMPORT_REHEARSAL_TEMP_COPY_READY` |
| PF-8 | Exact authorization phrase in P187 prompt | Verbatim match |
| PF-9 | `git status --short` — no forbidden staged paths | Clean |
| PF-10 | Drift guard PASS at 54462 | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` |
| PF-11 | Stop all API writers | `backend.pid / frontend.pid` processes killed |
| PF-12 | Create backup: `cp lottery_api/data/lottery_v2.db lottery_api/data/lottery_v2.db.bak_p187_pre_migration_<timestamp>` | File created |
| PF-13 | Verify backup row count | `54462` |
| PF-14 | Make backup immutable: `chmod 444 <backup_path>` | `ls -la` confirms r--r--r-- |
| PF-15 | **ONLY THEN**: run migration SQL | Proceed |

---

## Part G — P187 Next Options

| Option | Phrase | Recommended |
|--------|--------|-------------|
| **A** | `YES execute P187 production DB migration from main 54462 to reconciled 94924 using P185 rehearsal SQL, approve MAX(id) dedup dropping 160 null-provenance duplicate rows, create timestamped backup, no controlled_apply` | **YES** ⚠️ DESTRUCTIVE |
| B | `YES start P187 production DB migration dry-run checklist only` | No |
| C | `YES start P187 DB migration risk review only` | No |
| D | `YES start P187 maintain documented divergence and pause DB migration` | No |
| E | `YES start P187 replay product UI backlog implementation plan only` | No |

**P187 BLOCKED until CEO provides one of the above phrases.**

---

## Governance Confirmations

| Item | Status |
|------|--------|
| Production DB rows before/after | 54,462 / 54,462 |
| Production DB write | **0** |
| DB migration executed | **NO** |
| DB copy to production | **NONE** |
| controlled_apply | **NONE** |
| stage/commit/push | **NONE** |
| POWER_LOTTO research | **CLOSED** (P178A active) |
| main/zen-gates split | **STILL UNRESOLVED** |
| P187 | **BLOCKED** — CEO auth required |

---

*P186 is a plan-only authorization gate. No DB writes, no migration, no schema changes performed. Production DB unchanged. No wagering recommendations. No win outcome guaranteed.*
