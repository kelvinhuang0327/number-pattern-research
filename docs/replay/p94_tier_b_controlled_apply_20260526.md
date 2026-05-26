# P94 — Tier B Controlled Replay Apply

**Date:** 2026-05-26  
**Classification:** `P94_TIER_B_CONTROLLED_APPLY_SUCCESS`  
**Branch:** `p94-tierb-controlled-apply`  
**Based on:** P93 Tier B Dry-run (PR #218, commit 9e18185)  
**Authorization:** YES apply P94 tier B controlled replay rows

---

## Governance Assertions

| Assertion | Value |
|-----------|-------|
| dry_run flag on inserted rows | **false (dry_run=0 — PRODUCTION)** |
| truth_level | **TIERB_DRYRUN_VALIDATED** |
| controlled_apply_id | **P94_TIERB_CONTROLLED_APPLY_20260526** |
| Lifecycle/champion/registry mutation | **false** |
| Draw table mutation | **false** |
| Official API ingestion | **false** |
| New DB tables created | **false** |
| Causal isolation enforced | **true** |
| Duplicate guard enforced | **true** |

---

## DB Backup

| Item | Value |
|------|-------|
| Backup path | `lottery_api/data/lottery_v2.db.bak_p94_pre_apply_20260526_223934` |
| Created before | Any write to production DB |

---

## Production DB Counts

| Metric | Before | After |
|--------|--------|-------|
| `strategy_prediction_replays` row count | **46962** | **54462** |
| Delta | | **+7500** |
| POWER_LOTTO max draw | 115000041 | **115000041** (unchanged) |
| P79 row 46961 (`fourier_rhythm_3bet`) | intact | **intact** |
| P79 row 46962 (`fourier30_markov30_2bet`) | intact | **intact** |

---

## Per-Strategy Production Row Counts

| Strategy ID | Lottery | Bets | Rows Inserted | Status |
|-------------|---------|------|--------------|--------|
| `daily539_f4cold_3bet` | DAILY_539 | 3 | **1500** | OK |
| `daily539_f4cold_5bet` | DAILY_539 | 5 | **1500** | OK |
| `biglotto_echo_aware_3bet` | BIG_LOTTO | 3 | **1500** | OK |
| `power_fourier_rhythm_2bet` | POWER_LOTTO | 2 | **1500** | OK |
| `biglotto_ts3_markov_4bet_w30` | BIG_LOTTO | 4 | **1500** | OK |
| **TOTAL** | | | **7500** | **SUCCESS** |

---

## Controlled Apply Metadata

| Field | Value |
|-------|-------|
| `controlled_apply_id` | `P94_TIERB_CONTROLLED_APPLY_20260526` |
| `truth_level` | `TIERB_DRYRUN_VALIDATED` |
| `source` | `P94_TIERB_CONTROLLED_APPLY` |
| `dry_run` | `0` |
| `provenance_source` | `P94_CONTROLLED_APPLY` |

---

## Duplicate Guard

All 7500 rows passed the duplicate guard:
- `strategy_id + target_draw` key checked before each insert
- Zero duplicate rows detected or inserted
- Status: **PASS**

---

## P79 Sentinel Status

| Row ID | strategy_id | dry_run | truth_level | Status |
|--------|-------------|---------|-------------|--------|
| 46961 | `fourier_rhythm_3bet` | 0 | `POWERLOTTO_DRAW_EXT_VERIFIED` | **INTACT** |
| 46962 | `fourier30_markov30_2bet` | 0 | `POWERLOTTO_DRAW_EXT_VERIFIED` | **INTACT** |

---

## Rollback SQL

```sql
-- P94 rollback — removes all rows inserted by this controlled apply
-- DO NOT EXECUTE unless explicitly authorized
DELETE FROM strategy_prediction_replays
WHERE controlled_apply_id = 'P94_TIERB_CONTROLLED_APPLY_20260526';
-- Expected: 7500 rows deleted
-- After rollback: replay_rows = 46962
```

---

## No Lifecycle Mutation Statement

- `replay_strategy_registry._REGISTRY` was not modified.
- `replay_strategy_registry._ALL_ADAPTERS` was not modified.
- No strategy lifecycle status was changed (ONLINE/OFFLINE/REJECTED/RETIRED).
- No champion or registry metadata was written.

## No Draw Table Mutation Statement

- `draws` table was not modified.
- POWER_LOTTO max draw remains `115000041`.
- No new draws were ingested.

---

## Recommended P95 Verification Task

**Scope:** Replay UI/API verification — query newly applied rows via replay API and confirm they appear correctly in the frontend.

**Preconditions:**
1. `replay_rows = 54462` in production DB
2. POWER_LOTTO max draw = 115000041
3. P94 classification = `P94_TIER_B_CONTROLLED_APPLY_SUCCESS`

**Sample API queries:**
```
GET /api/replays?strategy_id=biglotto_echo_aware_3bet&limit=10
GET /api/replays?strategy_id=daily539_f4cold_3bet&limit=10
GET /api/replays?strategy_id=power_fourier_rhythm_2bet&limit=10
```

---

## Artifacts Produced

| File | Purpose |
|------|---------|
| `scripts/p94_tierb_controlled_apply.py` | Controlled apply script |
| `outputs/replay/p94_tier_b_controlled_apply_20260526.json` | Machine-readable report |
| `docs/replay/p94_tier_b_controlled_apply_20260526.md` | This document |
| `tests/test_p94_tier_b_controlled_apply.py` | Test suite |
