# P73 Local DB Recovery Guard + Apply Authorization Hardening

## PROJECT_CONTEXT_LOCK

```
Project = LotteryNew
Canonical Repo = /Users/kelvin/Kelvin-WorkSpace/LotteryNew
Canonical Branch = main
```

This document applies ONLY to LotteryNew.

---

## Identity

| Field | Value |
|---|---|
| Task | P73_LOCAL_DB_RECOVERY_GUARD_APPLY_AUTH_HARDENING |
| Date | 20260526 |
| Repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew |
| Branch | p73-local-db-recovery-guard-apply-auth-hardening |
| Base HEAD | 5e29c7b (P72 merge) |
| Authorization mode | READINESS_ONLY |
| Production rows before | **46960** |
| Production rows after | **46960** |
| DB write occurred | NO |
| Force push occurred | NO |
| `git reset --hard` used | NO |
| `git clean` used | NO |
| Lifecycle promotion | NO |
| Champion replacement | NO |
| Registry mutation | NO |

---

## Pre-flight Results

| Check | Result |
|---|---|
| Repo path | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` ✓ |
| Branch before create | `main` ✓ |
| Production rows | 46960 ✓ |
| P58 controlled apply ID | 1500 rows ✓ |
| P66 cold_complement_2bet ID | 1500 rows ✓ |
| P66 zonal_entropy_2bet ID | 1500 rows ✓ |
| Drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS ✓ |
| Branch governance (main) | BRANCH_GOVERNANCE_PASS ✓ |
| Cross-project contamination | CLEAN (`novel_hybrid_lotto` = LotteryNew-internal) ✓ |

---

## P72 Incident Summary

### What Happened

During P72 post-merge verification, the command `git reset --hard origin/main` was run to synchronize the local branch with origin/main after the squash merge.

This command **overwrote the local live DB** (`lottery_api/data/lottery_v2.db`), reverting it from the locally-authoritative 46960-row state back to the committed origin/main state of 37960 rows.

| Timeline | Rows |
|---|---|
| Before incident | 46960 |
| After `git reset --hard origin/main` | 37960 |
| After recovery | 46960 |

### Root Cause

`lottery_api/data/lottery_v2.db` is tracked by git. Rows applied by P59 (+1500), P65 (+1500), P66 (+1500+1500) after the last committed DB state accumulate as unstaged local modifications. `git reset --hard` discards all unstaged changes to tracked files — including the DB file — reverting it to the last committed snapshot.

**The committed DB on origin/main lagged the local live DB by 9000 rows.**

### Recovery Path

1. `cp lottery_api/data/lottery_v2.db.bak_p59_20260525_135638 lottery_api/data/lottery_v2.db`
   — restored to 42460-row P59 backup state
2. `python scripts/p59_powerlotto_wave5_controlled_apply.py`
   — re-applied fourier30_markov30_2bet 1500 POWER_LOTTO rows → 43960
3. `python scripts/p66_wave6_controlled_apply.py`
   — re-applied cold_complement_2bet + zonal_entropy_2bet 3000 rows → 46960
4. Verified: `sqlite3 … "SELECT COUNT(*) …"` → **46960**
5. Drift guard: **PASS**
6. Branch governance: **PASS**

No permanent data loss. Recovery time: ~10 minutes.

---

## New Safety Rules

### Rule 1: No `git reset --hard` When Local DB Is Authoritative

**Condition:** `lottery_api/data/lottery_v2.db` appears in `git status` as modified (unstaged).

**Rule:** `git reset --hard` is **FORBIDDEN** unless:
- Explicit authorization phrase present: `YES reset hard after verified DB backup`
- AND a verified DB backup exists with confirmed row count = 46960

### Rule 2: No Destructive Git Sync Without DB Backup Verification

The following commands are **PROHIBITED** when local DB has untracked/uncommitted live rows:

```
git reset --hard
git reset --hard origin/<branch>
git clean -fd
git checkout -- .
git checkout -- lottery_api/data/lottery_v2.db
```

### Rule 3: Post-Merge DB Integrity Check

After any git operation (fetch, merge, rebase, reset), immediately verify:

```bash
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"
```

Expected: `46960`. If unexpected, **STOP** and do not continue.

---

## Required Pre-Apply DB Backup Gate

Before any future `YES apply P71 controlled replay rows` authorization is acted upon, the following gate must pass in order:

| Step | Command | Expected |
|---|---|---|
| 1 | `sqlite3 … "SELECT COUNT(*) …"` | 46960 |
| 2 | `cp lottery_v2.db lottery_v2.db.bak_pre_p74_apply_<timestamp>` | file created |
| 3 | `sqlite3 <backup> "SELECT COUNT(*) …"` | 46960 |
| 4 | Record backup path in apply evidence JSON | ✓ |
| 5 | Verify 3 reference controlled_apply_ids → 1500 rows each | ✓ |
| 6 | Drift guard PASS | PASS |
| 7 | Branch governance PASS | PASS |
| 8 | Proceed with controlled apply | — |

**Abort conditions:**
- Source rows ≠ 46960
- Backup rows ≠ source rows
- Drift guard FAIL
- Branch governance FAIL
- Backup file not created

---

## Safe Post-Merge Verification Path

### Preferred Commands (Safe)

```bash
# Fetch without merging
git fetch origin main

# Inspect log remotely
git log --oneline origin/main | head -10

# Inspect individual files without checkout
git show origin/main:path/to/file

# Check file diff between local and remote
git diff HEAD origin/main --name-only

# Check if local DB is dirty
git status lottery_api/data/lottery_v2.db
```

### Forbidden Commands (When Local DB Is Authoritative)

| Command | Risk | Alternative |
|---|---|---|
| `git reset --hard origin/main` | Overwrites local live DB | `git fetch` + inspect |
| `git reset --hard` | Same risk | `git fetch` + inspect |
| `git clean -fd` | Removes untracked files | Manual inspection |
| `git checkout -- .` | Reverts all tracked files | Selective inspection |

### Safe Local Sync Procedure (If Needed)

1. Verify `git status lottery_api/data/lottery_v2.db` — check if modified
2. If modified: create backup `cp lottery_v2.db lottery_v2.db.bak_<timestamp>`
3. Verify backup rows
4. Obtain `YES reset hard after verified DB backup` authorization
5. Only then: `git reset --hard origin/main`
6. Immediately verify rows: `sqlite3 … "SELECT COUNT(*) …"`
7. If rows < 46960: recover using backup + apply scripts

---

## P71/P72 Apply Authorization Gate Reinforcement

Production apply requires the explicit phrase:

```
YES apply P71 controlled replay rows
```

This phrase authorizes production DB writes for P71 candidates. Its absence means **ZERO DB writes**.

Additional pre-apply requirements beyond the phrase:
1. Pre-apply DB backup gate (above) must pass fully
2. Duplicate check: no `controlled_apply_id` collision in DB
3. Rollback plan documented in apply evidence
4. Drift guard PASS immediately before apply
5. Branch governance PASS immediately before apply
6. Post-apply row count matches expected
7. API verification confirms rows served correctly

---

## Recommended Next Apply Scope (P74)

### Phase 1: Batch A Only (Lowest Risk)

Apply Batch A first, verify, then decide on B1.

| Strategy | Lottery Type | Lifecycle | Rows | Total After |
|---|---|---|---|---|
| fourier_rhythm_3bet | POWER_LOTTO | ONLINE | 1500 | 48460 |
| fourier30_markov30_2bet | POWER_LOTTO | ACTIVE | 1500 | 49960 |

Expected rows after Batch A: **49960**

### Phase 2: Batch B1 (After Batch A Verified)

| Strategy | Lottery Type | Lifecycle | Rows | Total After |
|---|---|---|---|---|
| 539_3bet_orthogonal | DAILY_539 | ACTIVE | 1500 | 51460 |
| acb_single_539 | DAILY_539 | ACTIVE | 1500 | 52960 |

Expected rows after Batch A + B1: **52960**

### Batch Risk Table

| Batch | Strategies | Lifecycle | Risk | Blocked | Reason |
|---|---|---|---|---|---|
| A | fourier_rhythm_3bet, fourier30_markov30_2bet | ONLINE/ACTIVE | LOW | No | Ready for P74 |
| B1 | 539_3bet_orthogonal, acb_single_539 | ACTIVE/ACTIVE | LOW | No | After Batch A verified |
| B2 | midfreq_acb_2bet, midfreq_fourier_2bet | RETIRED/RETIRED | MEDIUM | **YES** | Lifecycle promotion gate required |
| B3 | acb_1bet, acb_markov_midfreq_3bet | RETIRED/RETIRED | MEDIUM | **YES** | Lifecycle promotion gate required |

### B2/B3 Lifecycle Gate

Batches B2 and B3 are **BLOCKED** until:
- A separate lifecycle promotion gate task explicitly promotes RETIRED → ACTIVE/ONLINE for each strategy
- The promotion is committed to main
- Drift guard confirms no lifecycle drift

### midfreq_fourier_2bet Extra Gate

Before any apply of `midfreq_fourier_2bet`:
- Enforce `WHERE lottery_type = 'DAILY_539'` filter during insert
- Post-apply: verify POWER_LOTTO rows for this strategy still = 1500
- If POWER_LOTTO rows change from 1500, roll back immediately

---

## Future Branch Sync Guidance

| Concern | Rule |
|---|---|
| P6 remote sync debt | NOT resolved in P73; separate explicit authorization required |
| Force push | Requires `YES force push <branch> for <reason>` |
| `git reset --hard` | Requires `YES reset hard after verified DB backup` + backup verified |
| Branch cleanup/deletion | Requires `YES archive stale branches` |
| Worktree cleanup | Requires explicit authorization |

---

## Explicit Exclusions (Unchanged from P72)

| Strategy | Reason |
|---|---|
| BIG_LOTTO | Excluded from P71 scope |
| cold_complement_2bet | Sub-baseline ROI |
| zonal_entropy_2bet | Fallback-equivalent |
| midfreq_fourier_mk_3bet | OOS deferred |

---

## Governance Confirmations

- No DB write in P73: **CONFIRMED**
- No force push in P73: **CONFIRMED**
- No `git reset --hard` in P73: **CONFIRMED**
- No `git clean` in P73: **CONFIRMED**
- No lifecycle promotion in P73: **CONFIRMED**
- No champion replacement in P73: **CONFIRMED**
- No registry mutation in P73: **CONFIRMED**
- No production apply in P73: **CONFIRMED**
- Requires future explicit apply authorization: **CONFIRMED**
- P6 sync debt not resolved in P73: **CONFIRMED**

---

## Final Classification

```
P73_LOCAL_DB_RECOVERY_GUARD_APPLY_AUTH_HARDENING_MERGED_TO_MAIN
```
