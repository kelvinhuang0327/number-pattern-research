# P196 — DB Binary External Storage Manifest

**Created:** 2026-06-01  
**Task:** P196_REMOVE_DB_BINARIES_SOFT_RESET_RECOMMIT_NON_BINARY_NO_PUSH  
**Purpose:** Text-based evidence replacing DB binary blobs in git history.

---

## Production DB Evidence

| Field | Value |
|-------|-------|
| Path | `lottery_api/data/lottery_v2.db` |
| Git tracked | **NO — local only** |
| SHA256 | `a5ac27a6887d8c1d8da97349dbc97c36e9429270dd45f81b3b67a8d5793c4f87` |
| Size | 99,368,960 bytes (96M) |
| Rows | **94924** |
| bet_index | **PRESENT** (NOT NULL DEFAULT 1) |
| bet_index NULL count | 0 |
| integrity_check | ok |
| Migrated from | 54462 rows |
| Dedup dropped | 160 rows (NULL provenance) |
| Multi-bet imported | 40622 rows |

**Verify:** `shasum -a 256 lottery_api/data/lottery_v2.db`  
**Verify rows:** `sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"`

---

## Backup DB Evidence

| Field | Value |
|-------|-------|
| Path | `backups/p188_lottery_v2_backup_20260601_153821.db` |
| Git tracked | **NO — local only** |
| SHA256 | `5eea53135fb65369a3dd90512e7f8bfc4411b756abadf00a03b2b9b7d4e24da9` |
| SHA256 file in git | `backups/p188_lottery_v2_backup_20260601_153821.db.sha256` |
| Size | 53,374,976 bytes (51M) |
| Rows | 54462 (pre-migration state) |
| bet_index | ABSENT |

---

## P188 SQL Evidence in Git

- SQL log: `outputs/research/power_lotto/p188_production_db_migration_sql_log_20260601.sql`
- Execution report: `outputs/research/power_lotto/p188_production_db_migration_execution_20260601.json`

---

## P191 Binary-Heavy Commit Reference

The binary-heavy commit `012d4a3f` (P188-P191) contained these DB binaries. P196 replaces it with a non-binary recommit.

---

## External Storage Policy

> ⚠️ DB binaries are **intentionally excluded** from pushable git history.  
> Store `lottery_api/data/lottery_v2.db` and `backups/p188_*.db` on local disk, secure offsite backup, or a data management system outside git.  
> **Do NOT delete local copies** until external backup is confirmed.
