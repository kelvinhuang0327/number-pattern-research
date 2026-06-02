# P194 — Remove DB Binaries from Local Commit Plan

**Task:** P194_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_PLAN_ONLY  
**Date:** 2026-06-01  
**Authorization Phrase:** `YES start P194 remove DB binaries from local commit plan only`  
**Final Classification:** `P194_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_PLAN_READY`

---

## Phase 0 — Actual State Verification: PASS

| Check | Result |
|-------|--------|
| Repo / branch / git-dir | ✅ PASS |
| HEAD = P191 commit (012d4a3) | ✅ PASS |
| origin/main is ancestor of HEAD | ✅ PASS (ahead by 6 commits) |
| DB rows = 94924, bet_index PRESENT | ✅ PASS |
| integrity_check = ok | ✅ PASS |
| P188 backup + sha256 exist | ✅ PASS |
| Tests (P178A-P193) = 865 PASS | ✅ PASS |
| Drift guard = PASS | ✅ PASS |
| Staged files = 0 | ✅ PASS |
| P193 classification confirmed | ✅ P193_PUSH_REJECTION_REMEDIATION_PLAN_READY |

**No STOP conditions triggered.**

---

## Part A — Current State Summary

| Item | Value |
|------|-------|
| P191 local commit | `012d4a3` (INTACT, unpushed) |
| P192 push result | **REJECTED** — GH006 + large binary |
| P193 plan | **READY** — Option B: remove DB binaries |
| Production DB | 94924 rows, 96MB, bet_index PRESENT |
| Backup DB | 54462 rows, 51MB, bet_index ABSENT |
| origin/main | UNCHANGED — 684bffce |
| P194 file modifications | **0** |

---

## Part B — Large Binary Inventory

| File | Size | SHA256 | Remove from git | Preserve locally |
|------|------|--------|-----------------|-----------------|
| `lottery_api/data/lottery_v2.db` | 96MB (99,368,960 B) | `a5ac27a6...` | ✅ YES | **MUST KEEP** |
| `backups/p188_lottery_v2_backup_20260601_153821.db` | 51MB (53,374,976 B) | `5eea5313...` | ✅ YES | **MUST KEEP** |
| `backups/p188_lottery_v2_backup_20260601_153821.db.sha256` | <1KB | N/A | ❌ KEEP | ✅ KEEP |

**Total binary bytes to remove from git: 152,743,936 bytes (~146MB)**

### Replacement Evidence (manifest to create in P195)

A text file `docs/db_migration_manifest_p188_p191.json` should be committed in place of the binaries, containing:
- `production_db_sha256`: `a5ac27a6887d8c1d8da97349dbc97c36e9429270dd45f81b3b67a8d5793c4f87`
- `production_db_rows`: 94924
- `production_db_size_bytes`: 99368960
- `backup_sha256`: `5eea53135fb65369a3dd90512e7f8bfc4411b756abadf00a03b2b9b7d4e24da9`
- `backup_rows`: 54462
- `migration_summary`: "54462 → 94924 rows, bet_index added, 160 null-provenance rows deduped"

---

## Part C — Candidate Execution Approaches

### Approach 1 — Soft Reset and Recommit ⭐ RECOMMENDED

```bash
# Safety check first
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"
# → Must print 94924

# Undo P191 commit (staged files preserved; local DB files untouched)
git reset --soft HEAD~1

# Unstage DB binaries (local files NOT deleted)
git restore --staged lottery_api/data/lottery_v2.db
git restore --staged backups/p188_lottery_v2_backup_20260601_153821.db

# Create manifest + update .gitignore
# [create docs/db_migration_manifest_p188_p191.json]
# [append db paths to .gitignore]
git add .gitignore docs/db_migration_manifest_p188_p191.json

# Recommit without binaries
git commit -m "P182-P191: reconcile replay governance (no DB binaries)"

# Post-reset safety check
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"
# → Must still print 94924
```

| Property | Value |
|----------|-------|
| Rewrites commits | P191 only (new hash) |
| Local DB preserved | ✅ YES |
| Risk | MEDIUM |
| Recommendation | **⭐ PRIMARY** |

### Approach 2 — git rm --cached and Amend

```bash
git rm --cached lottery_api/data/lottery_v2.db   # removes from index, NOT disk
git rm --cached backups/p188_lottery_v2_backup_20260601_153821.db
# [update .gitignore and create manifest]
git add .gitignore docs/db_migration_manifest_p188_p191.json
git commit --amend  # rewrites P191 in place
```

| Property | Value |
|----------|-------|
| Rewrites commits | P191 (amend) |
| Local DB preserved | ✅ YES |
| Risk | MEDIUM |
| Recommendation | Acceptable alternative |

### Approach 3 — Feature Branch + Cherry-pick (for PR workflow)

After Approach 1, use this for the PR:
```bash
git checkout -b feature/p182-p191-governance origin/main
# [cherry-pick or re-stage content without binaries]
git push origin feature/p182-p191-governance
# Open PR → CI runs replay-default-validation → merge
```

| Property | Value |
|----------|-------|
| Rewrites commits | No (new branch) |
| Branch protection | ✅ Satisfied via PR + CI |
| Risk | LOW-MEDIUM |
| Recommendation | PREFERRED for PR path after Approach 1 |

### Approach 4 — Keep Unpushed (hold)

No action. P191 stays local. Remote stays at P124 state.

| Property | Value |
|----------|-------|
| Risk | LOWEST |
| Recommendation | Short-term hold only |

---

## Part D — CTO Recommendation

**Execute Approach 1, then Approach 3.**

1. **P195**: Run Approach 1 (soft reset + recommit without binaries)  
2. **P196**: Run Approach 3 (create feature branch, push, open PR, satisfy CI)

### Critical Safety Rules

> ⚠️ **NEVER** run `git rm lottery_api/data/lottery_v2.db` — only `git rm --cached` or `git restore --staged`  
> ⚠️ **NEVER** run `git reset --hard` — only `git reset --soft`  
> ✅ **ALWAYS** verify DB rows = 94924 **before AND after** the reset  
> ✅ **Do NOT** push current P191 commit as-is (96MB DB in blob)  
> ✅ **Do NOT** disable branch protection  
> ✅ **Do NOT** force push  

### .gitignore Entries Required

```
lottery_api/data/lottery_v2.db
lottery_api/data/lottery_v2.db-wal
lottery_api/data/lottery_v2.db-shm
lottery_api/data/*.bak_*
backups/*.db
backups/*.db-shm
backups/*.db-wal
```

---

## Part E — P195 Authorization Options

| Option | Authorization Phrase |
|--------|---------------------|
| **A ⭐** | `YES start P195 remove DB binaries from local commit execution plan only` |
| B | `YES start P195 amend local commit to remove DB binaries no push` |
| C | `YES start P195 create non-binary PR branch plan only` |
| D | `YES start P195 keep local commit unpushed and document state` |
| E | `YES start P195 rollback decision gate only` |

**P195 BLOCKED pending CEO authorization.**

---

## Governance Confirmations

| Confirmation | Value |
|---|---|
| no_db_write | ✅ true |
| no_db_delete | ✅ true |
| no_backup_delete | ✅ true |
| no_commit_rewrite | ✅ true |
| no_amend | ✅ true |
| no_reset | ✅ true |
| no_branch_creation | ✅ true |
| no_stage | ✅ true |
| no_commit | ✅ true |
| no_push | ✅ true |
| no_force_push | ✅ true |
| branch_protection_not_bypassed | ✅ true |
| power_lotto_research_closed | ✅ true |
| migrated_db_local_state_preserved | ✅ true |
| production_db_rows = 94924 | ✅ true |
| p191_local_commit_intact | ✅ true |

**next_task_blocked_by_user_authorization: true**

---

## Final Classification

**`P194_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_PLAN_READY`**

P195 BLOCKED pending CEO authorization phrase.
