# P195 — Remove DB Binaries from Local Commit Execution Plan

**Task:** P195_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_EXECUTION_PLAN_ONLY  
**Date:** 2026-06-01  
**Authorization Phrase:** `YES start P195 remove DB binaries from local commit execution plan only`  
**Final Classification:** `P195_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_EXECUTION_PLAN_READY`

---

## Phase 0 — Actual State Verification: PASS

| Check | Result |
|-------|--------|
| Repo / branch / git-dir | ✅ PASS |
| HEAD = P191 binary-heavy commit (012d4a3) | ✅ PASS |
| origin/main is ancestor (ahead 6) | ✅ PASS |
| DB rows = 94924, bet_index PRESENT | ✅ PASS |
| DB integrity = ok | ✅ PASS |
| Backup + sha256 exist | ✅ PASS |
| Tests (P178A-P194) = 933 PASS | ✅ PASS |
| Drift guard = PASS | ✅ PASS |
| Staged files = 0 | ✅ PASS |
| P194 classification confirmed | ✅ P194_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_PLAN_READY |

**No STOP conditions triggered.**

---

## Part A — Current State Summary

| Item | Value |
|------|-------|
| P191 local commit | `012d4a3` — binary-heavy (96MB DB + 51MB backup) |
| P192 push | **REJECTED** — GH006 + large binary |
| P193 plan | READY |
| P194 plan | READY |
| Production DB | 94924 rows, 99,368,960 bytes |
| Production DB SHA256 | `a5ac27a6887d8c1d8da97349dbc97c36e9429270dd45f81b3b67a8d5793c4f87` |
| Backup DB | 54462 rows, 53,374,976 bytes |
| Backup SHA256 | `5eea53135fb65369a3dd90512e7f8bfc4411b756abadf00a03b2b9b7d4e24da9` |
| P195 file modifications | **0** |

---

## Part B — P196 Execution Plan

### Authorization phrase required for P196 execution:
```
YES execute P196 remove DB binaries from local commit using soft reset and recommit non-binary files, no push
```

### Pre-Execution Checklist (run before any git operation)

| # | Check | Expected |
|---|-------|----------|
| C-01 | `git diff --cached --name-only` | empty |
| C-02 | `git log -1 --oneline` | `012d4a3 P188-P191: reconcile...` |
| C-03 | `git show --name-only HEAD > /tmp/p191_committed_files.txt` | 109 files exported |
| C-04 | `shasum -a 256 lottery_api/data/lottery_v2.db` | `a5ac27a6...` |
| C-05 | `shasum -a 256 backups/p188_*.db` | `5eea5313...` |
| C-06 | DB rows | 94924 |
| C-07 | Backup rows | 54462 |
| C-08 | Full test suite | 933+ PASS, 0 FAIL |
| C-09 | Drift guard | PASS |
| C-10 | Repo / branch | LotteryNew / main |

---

### Step 1 — Create DB Migration Manifest (BEFORE reset)

```bash
mkdir -p docs
cat > docs/db_migration_manifest_p188_p191.json << 'MANIFEST'
{
  "schema_version": "1.0",
  "created_at": "2026-06-01",
  "migration_task": "P188_PRODUCTION_DB_MIGRATION_EXECUTED_RECONCILED_94924",
  "production_db": {
    "path": "lottery_api/data/lottery_v2.db",
    "note": "NOT tracked in git — local only",
    "rows": 94924,
    "bet_index_present": true,
    "integrity_check": "ok",
    "sha256": "a5ac27a6887d8c1d8da97349dbc97c36e9429270dd45f81b3b67a8d5793c4f87",
    "size_bytes": 99368960,
    "migration_from_rows": 54462,
    "dedup_dropped_rows": 160,
    "imported_multi_bet_rows": 40622
  },
  "backup_db": {
    "path": "backups/p188_lottery_v2_backup_20260601_153821.db",
    "note": "NOT tracked in git — local only",
    "sha256": "5eea53135fb65369a3dd90512e7f8bfc4411b756abadf00a03b2b9b7d4e24da9",
    "sha256_file_in_git": "backups/p188_lottery_v2_backup_20260601_153821.db.sha256",
    "size_bytes": 53374976,
    "rows": 54462,
    "bet_index_present": false
  },
  "p188_sql_log": "outputs/research/power_lotto/p188_production_db_migration_sql_log_20260601.sql",
  "external_storage_required": true,
  "no_controlled_apply": true,
  "power_lotto_research_closed": true
}
MANIFEST
```

---

### Step 2 — git reset --soft HEAD~1

```bash
git reset --soft HEAD~1
```

**What this does:**
- Moves HEAD back to `d1a6817` (P128)
- All 109 files from P191 remain **staged** (in the index)
- **Local disk files are NOT touched** — DB stays at 94924 rows
- Backup stays at `backups/p188_*.db`

> ⚠️ **NEVER use `--hard`** — that would destroy unstaged changes

---

### Step 3 — Unstage DB Binary Paths

```bash
git restore --staged lottery_api/data/lottery_v2.db
git restore --staged backups/p188_lottery_v2_backup_20260601_153821.db
```

**Verify after:**
```bash
# Must be EMPTY:
git diff --cached --name-only | grep "lottery_v2\.db"
git diff --cached --name-only | grep "p188_lottery_v2_backup.*\.db$"

# Local files must still exist:
ls -lh lottery_api/data/lottery_v2.db        # → ~96MB
ls -lh backups/p188_lottery_v2_backup_20260601_153821.db  # → ~51MB

# DB must still open:
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"  # → 94924
```

---

### Step 4 — Update .gitignore

```bash
cat >> .gitignore << 'IGNORE'

# SQLite production DB — managed locally, not tracked in git
lottery_api/data/lottery_v2.db
lottery_api/data/lottery_v2.db-wal
lottery_api/data/lottery_v2.db-shm
lottery_api/data/*.bak_*

# DB backups — stored locally, not tracked in git
backups/*.db
backups/*.db-shm
backups/*.db-wal

# Rehearsal temp DBs
outputs/research/power_lotto/p184_rehearsal/*.db
outputs/research/power_lotto/p185_rehearsal/*.db
IGNORE

git add .gitignore
```

---

### Step 5 — Stage Manifest

```bash
git add docs/db_migration_manifest_p188_p191.json
```

---

### Step 6 — Verify Staged Set (no DB binaries)

```bash
git diff --cached --name-only | sort > /tmp/p196_staged_list.txt

# Must be EMPTY:
grep "\.db$" /tmp/p196_staged_list.txt

# Count should be ~108 (original 109 - 2 DB binaries + .gitignore + manifest ≈ 109):
wc -l /tmp/p196_staged_list.txt
```

---

### Step 7 — Recommit (no binaries)

```bash
git commit -m "$(cat <<'EOF'
P182-P191: reconcile replay governance (no DB binaries)

Backport P161-P181 code/docs/tests parity, reconcile replay DB migration
evidence (manifest + sha256 only; DB binaries excluded from git history),
update drift guard and stale tests, add P189-P195 governance artifacts.
No controlled_apply. POWER_LOTTO research remains closed.

DB migration evidence: docs/db_migration_manifest_p188_p191.json
Production DB: 94924 rows, bet_index PRESENT (local only, not in git)
Backup DB: 54462 rows, sha256 in backups/p188_*.db.sha256 (local only)
EOF
)"
```

---

### Step 8 — Post-Commit Verification (all must PASS)

```bash
# New commit exists:
git log -1 --oneline

# NO DB binary in new commit (must be EMPTY):
git show HEAD --name-only | grep "\.db$"

# Nothing staged:
git diff --cached --name-only

# Production DB still intact:
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"  # → 94924

# Backup still intact:
sqlite3 backups/p188_lottery_v2_backup_20260601_153821.db "SELECT COUNT(*) FROM strategy_prediction_replays;"  # → 54462

# Full test suite:
python3 -m pytest [P178A-P195 suite] -v  # → all PASS

# Drift guard:
uv run python scripts/replay_lifecycle_drift_guard.py  # → PASS

# Branch:
git branch --show-current  # → main
```

---

### Step 9 — STOP (no push in P196)

P196 ends here. No push. No branch creation. Push requires P197.

---

## Part C — Safety Checks Summary

| Phase | Check | Must Satisfy |
|-------|-------|-------------|
| Before reset | Staged files | = 0 |
| Before reset | HEAD | = 012d4a3 |
| Before reset | DB SHA256 | `a5ac27a6...` |
| Before reset | DB rows | 94924 |
| After unstage | DB path in staged set | ABSENT |
| After unstage | Local DB file | EXISTS ~96MB |
| After unstage | DB rows from disk | 94924 |
| After commit | DB binary in new commit | ABSENT |
| After commit | Staged files | = 0 |
| After commit | DB rows | 94924 |
| After commit | Backup rows | 54462 |
| After commit | Tests | PASS |
| After commit | Drift guard | PASS |
| After commit | Push | NOT done |

---

## Part D — Manifest Evidence Design

**Path:** `docs/db_migration_manifest_p188_p191.json`

Replaces binary blobs in git history with:
- `production_db.sha256`: `a5ac27a6887d8c1d8da97349dbc97c36e9429270dd45f81b3b67a8d5793c4f87`
- `production_db.rows`: 94924
- `production_db.size_bytes`: 99368960
- `backup_db.sha256`: `5eea53135fb65369a3dd90512e7f8bfc4411b756abadf00a03b2b9b7d4e24da9`
- `backup_db.rows`: 54462
- `backup_db.size_bytes`: 53374976
- `migration_from_rows`: 54462 → 94924
- `dedup_dropped_rows`: 160

Auditors can verify by running `shasum -a 256 lottery_api/data/lottery_v2.db` and comparing to the manifest.

---

## Part E — P196 Authorization Options

| Option | Authorization Phrase |
|--------|---------------------|
| **A ⭐** | `YES execute P196 remove DB binaries from local commit using soft reset and recommit non-binary files, no push` |
| B | `YES start P196 binary removal dry-run checklist only` |
| C | `YES start P196 create external DB manifest only` |
| D | `YES start P196 keep local binary commit unpushed and pause` |
| E | `YES start P196 rollback decision gate only` |

**P196 BLOCKED pending CEO authorization.**

---

## Part F — CTO Recommendation

**Execute P196 Option A — soft reset + recommit, no push.**

> ⚠️ **NEVER** `git reset --hard` — only `git reset --soft HEAD~1`  
> ⚠️ **NEVER** `git rm lottery_api/data/lottery_v2.db` — only `git restore --staged`  
> ✅ **VERIFY** DB rows = 94924 before AND after reset  
> ✅ **DO NOT** push until P197 creates a feature branch + PR  
> ✅ **DO NOT** disable branch protection  
> ✅ **DO NOT** force push  

---

## Governance Confirmations

| Confirmation | Value |
|---|---|
| no_db_write | ✅ true |
| no_db_delete | ✅ true |
| no_backup_delete | ✅ true |
| no_commit_rewrite (in P195) | ✅ true |
| no_stage | ✅ true |
| no_commit | ✅ true |
| no_push | ✅ true |
| no_force_push | ✅ true |
| branch_protection_not_bypassed | ✅ true |
| power_lotto_research_closed | ✅ true |
| migrated_db_preserved | ✅ true |
| production_db_rows = 94924 | ✅ true |

**next_task_blocked_by_user_authorization: true**

---

## Final Classification

**`P195_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_EXECUTION_PLAN_READY`**
