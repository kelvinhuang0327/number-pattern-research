# P49 — POWER_LOTTO Post-Apply API/UI Verification

**Date:** 2026-05-24  
**Phase:** P49  
**Classification:** `P49_POWERLOTTO_POST_APPLY_API_UI_VERIFICATION_PASS`  
**Preceding phase:** P48 (4500 POWER_LOTTO rows inserted, PR #184 squash-merged to main)

---

## Objective

Read-only verification that the 4500 P48 POWER_LOTTO production rows are:
1. Correctly stored in the production DB (total = 42 460, 3 × 1500 by strategy)
2. Queryable through the replay API (`/api/replay/history`, `/api/replay/summary`)
3. Semantically correct (lottery type, number ranges, special-zone, hit_count, dry_run)

**No DB writes. No lifecycle promotion. No registry mutation.**

---

## Pre-flight Results

| Check | Result |
|---|---|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` ✅ |
| Branch | `main` ✅ |
| `git pull --ff-only` | Already up to date ✅ |
| DB total rows | 42 460 ✅ |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✅ |
| Governance guard | `BRANCH_GOVERNANCE_PASS — branch='main' rows=42460` ✅ |
| Cross-project contamination | `NO_CROSS_PROJECT_CONTEXT_FOUND` ✅ |

---

## DB Checks

| Check | Value | Status |
|---|---|---|
| Total production rows | 42 460 | ✅ |
| P48 `controlled_apply_id` rows | 4 500 | ✅ |
| `pp3_freqort_4bet` rows | 1 500 | ✅ |
| `midfreq_fourier_mk_3bet` rows | 1 500 | ✅ |
| `midfreq_fourier_2bet` rows | 1 500 | ✅ |
| `lottery_type` = `POWER_LOTTO` only | 0 violations | ✅ |
| NULL `actual_special` | 0 | ✅ |
| `dry_run` = 0 | 0 violations | ✅ |
| `truth_level` = `POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED` | 0 violations | ✅ |
| `replay_run_id` = `p48_wave4_prod_20260524` | 0 violations | ✅ |

### Semantic Checks

| Check | Result |
|---|---|
| `actual_numbers` all in [1, 38] | 0 out-of-range ✅ |
| `predicted_numbers` all in [1, 38] | 0 out-of-range ✅ |
| `predicted_numbers` length = 6 | 0 wrong-length ✅ |
| `actual_special` in [1, 8] | 0 out-of-range ✅ |
| `hit_count` ≤ 6 (first-zone only) | 0 violations ✅ |
| `hit_count` ≥ 0 | 0 negative ✅ |
| `special_hit` correct (1 iff `predicted_special == actual_special`) | 0 mismatches ✅ |
| `special_hit` ∈ {0, 1} | 0 violations ✅ |

---

## API Checks (backend port 8002)

### `/api/replay/history`

| Check | Result |
|---|---|
| `pp3_freqort_4bet` total | 1 500 ✅ |
| `midfreq_fourier_mk_3bet` total | 1 500 ✅ |
| `midfreq_fourier_2bet` total | 1 500 ✅ |
| POWER_LOTTO total ≥ 4 500 | ✅ |
| Required fields present in records | ✅ |
| `lottery_type` = `POWER_LOTTO` in all records | ✅ |
| `predicted_numbers` is list | ✅ |
| `actual_numbers` is list | ✅ |
| `hit_count` is non-negative int | ✅ |
| `hit_count` ≤ 6 | ✅ |
| `special_hit` ∈ {0, 1} | ✅ |
| `actual_special` not null | ✅ |
| Pagination: page size respected | ✅ |
| Pagination: page 2 distinct from page 1 | ✅ |
| No cross-lottery contamination | ✅ |

### `/api/replay/summary`

| Check | Result |
|---|---|
| Returns dict | ✅ |
| Contains `summaries` list | ✅ |
| All 3 P48 strategies present | ✅ |
| `pp3_freqort_4bet` total_rows = 1 500 | ✅ |
| `midfreq_fourier_mk_3bet` total_rows = 1 500 | ✅ |
| `midfreq_fourier_2bet` total_rows = 1 500 | ✅ |
| error_count = 0 for all P48 strategies | ✅ |

---

## No DB Writes Guard

| Check | Result |
|---|---|
| Row count unchanged after history calls | ✅ |
| Row count unchanged after summary calls | ✅ |
| Total rows still 42 460 after all tests | ✅ |

---

## Test Results

**Test file:** `tests/test_p49_powerlotto_post_apply_api_verification.py`

| Suite | Tests | Passed | Failed |
|---|---|---|---|
| P49 file only | 61 | 61 | 0 |
| Full P48+P49 suite | 170 | 170 | 0 |

```
============================== 170 passed in 1.68s ==============================
```

### Test classes

| Class | Coverage |
|---|---|
| `TestP49DBCounts` | Total rows, per-apply_id, per-strategy, lottery_type, null special, dry_run, truth_level, replay_run_id |
| `TestP49DBSemantics` | Number ranges, predicted length, special range, hit_count bounds, special_hit correctness |
| `TestP49APIHistory` | Per-strategy totals, record fields, lottery_type filter, number types, hit_count/special_hit semantics, pagination, cross-lottery |
| `TestP49APISummary` | Summary dict shape, all P48 strategies present, per-strategy total_rows, error_count |
| `TestP49NoDBWrites` | Row count unchanged after all API calls, final total=42460 |

---

## Post-verification Guards

```
REPLAY_LIFECYCLE_DRIFT_GUARD_PASS
BRANCH_GOVERNANCE_PASS — branch='main' rows=42460
```

---

## Classification

```
P49_POWERLOTTO_POST_APPLY_API_UI_VERIFICATION_PASS
```

**Recommended next phase:** P50 — POWER_LOTTO Wave 4 Performance / Promotion Analysis
