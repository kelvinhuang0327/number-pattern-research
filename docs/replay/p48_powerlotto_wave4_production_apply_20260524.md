# P48 — POWER_LOTTO Wave 4 Production Apply
**Date:** 2026-05-24  
**Phase:** P48  
**Branch:** `p48-powerlotto-wave4-production-apply`  
**Classification (final):** `P48_POWERLOTTO_WAVE4_PRODUCTION_APPLY_MERGED_TO_MAIN`

---

## Authorization

Both required authorization phrases were provided and confirmed in session before any write:

1. `YES create new branch for P48 powerlotto wave4 production apply` ✅  
2. `YES apply P48 production wave4 powerlotto` ✅

---

## Summary

| Field | Value |
|---|---|
| Production rows before | 37,960 |
| Production rows after | 42,460 |
| Rows inserted | 4,500 |
| Rows skipped (Policy A) | 0 |
| Strategies | 3 |
| Rows per strategy | 1,500 |
| Lottery type | POWER_LOTTO |
| Controlled apply ID | `P48_POWERLOTTO_WAVE4_4500_PROD_20260524` |
| Truth level | `POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED` |
| Run ID | `p48_wave4_prod_20260524` |
| Semantics valid | ✅ True |
| Duplicate check pass | ✅ True |
| Lifecycle | DRY_RUN (not ONLINE, no registry mutation) |

---

## Pre-flight (`--dry-run-check`)

All pre-flight checks PASS before any DB write:

- Production row count: **37,960** (expected ≥ 37,960) ✅  
- Skip count (actual_special = NULL): **0** ✅  
- Rows to insert: **4,500** ✅  
- Duplicate check: **PASS** (0 pre-existing rows with this apply ID) ✅

---

## Per-Strategy Production Row Counts

| Strategy ID | Rows Inserted |
|---|---|
| `midfreq_fourier_2bet` | 1,500 |
| `midfreq_fourier_mk_3bet` | 1,500 |
| `pp3_freqort_4bet` | 1,500 |
| **Total** | **4,500** |

All three strategies were verified in P47 dryrun rehearsal before promotion.

---

## POWER_LOTTO Two-Zone Semantics

| Field | Rule | Verified |
|---|---|---|
| `numbers` | List of 6 integers in [1, 38] | ✅ |
| `special` (actual) | Integer in [1, 8] | ✅ |
| `hit_count` | First-zone hits only (not counting special) | ✅ |
| `special_hit` | 0 or 1 (actual_special == predicted_special) | ✅ |
| `lottery_type` | `POWER_LOTTO` exclusively | ✅ |

---

## Policy A — NULL Special Handling

**Decision:** Policy A (skip row if `actual_special is None`).

**Rationale:** All 1,912 POWER_LOTTO draws in the production dataset have non-null specials, so Policy A results in zero skips. Skip rows with null special rather than insert with `special_hit=0` to avoid polluting hit statistics with semantically undefined outcomes.

**Result:** `skip_count = 0` — all 4,500 rows inserted.

---

## Lifecycle Confirmation

- Strategy adapter lifecycle: `DRY_RUN` (not `ONLINE`)
- Production rows use `dry_run = 0` (production write flag)
- No registry mutation performed — lifecycle column is adapter-internal only
- Production DB column `dry_run = 0` correctly distinguishes production rows from adapter-only dryrun rows

---

## Coverage Denominator

| Metric | Before P48 | After P48 |
|---|---|---|
| Strategies in production | 25/59 | 28/59 |
| Coverage gap | 34 remaining | 31 remaining |
| Estimated rows to full coverage | ~51,000 | ~46,500 |

P48 promotes 3 POWER_LOTTO Wave 4 strategies to production.

---

## Governance Guards

### Drift Guard
```
No violations found.
Final classification: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS
```
Baseline updated: `total_count` 37,960 → 42,460, `p48_count` 4,500 whitelisted, `POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED` added to allowed truth levels, `P48_POWERLOTTO_WAVE4_4500_PROD_20260524` added to known apply IDs.

### Branch Governance Guard
```
BRANCH_GOVERNANCE_PASS — branch='p48-powerlotto-wave4-production-apply' rows=42460
```

---

## Test Results

| Test File | Tests | Result |
|---|---|---|
| `test_p48_powerlotto_wave4_production_apply.py` | 44 | ✅ PASS |
| `test_p48_powerlotto_special_null_policy.py` | 7 | ✅ PASS |
| `test_replay_lifecycle_drift_guard.py` | (subset) | ✅ PASS |
| `test_replay_branch_governance_guard.py` | (subset) | ✅ PASS |
| `test_p47_powerlotto_wave4_dryrun_rehearsal.py` | (subset) | ✅ PASS |
| `test_replay_api_contract.py` | (subset) | ✅ PASS |
| **Full suite (6 files)** | **145** | **✅ 145 passed** |

---

## Apply Script

**File:** `scripts/p48_powerlotto_wave4_production_apply.py`  
**Manifest:** `outputs/replay/p48_powerlotto_wave4_production_apply_20260524.json`

Key constants:
- `PRE_APPLY_PROD_ROWS = 37960`
- `EXPECTED_APPLIED_ROWS = 4500`
- `CONTROLLED_APPLY_ID = "P48_POWERLOTTO_WAVE4_4500_PROD_20260524"`
- `TRUTH_LEVEL = "POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED"`
- `SPECIAL_NULL_POLICY = "A"` (skip)

---

## Wave 5 Readiness

Wave 5 candidates are POWER_LOTTO strategies verified in P47 dryrun but not yet promoted. The `_wave5_sketch()` function in the apply script is reserved for future enumeration once additional P47 adapter strategies are validated.

Current undeployed POWER_LOTTO strategies available for Wave 5 review include all adapter variants not in `{pp3_freqort_4bet, midfreq_fourier_mk_3bet, midfreq_fourier_2bet}`.

---

## Files Changed (Whitelist)

| File | Type |
|---|---|
| `scripts/p48_powerlotto_wave4_production_apply.py` | New — apply script |
| `tests/test_p48_powerlotto_wave4_production_apply.py` | New — 44 tests |
| `tests/test_p48_powerlotto_special_null_policy.py` | New — Policy A tests |
| `tests/test_replay_lifecycle_drift_guard.py` | Modified — P48 baseline |
| `tests/test_replay_branch_governance_guard.py` | Modified — 42460 |
| `tests/test_p47_powerlotto_wave4_dryrun_rehearsal.py` | Modified — `POST_P48_PRODUCTION_ROWS` |
| `scripts/replay_lifecycle_drift_guard.py` | Modified — P48 baseline |
| `outputs/replay/p48_powerlotto_wave4_production_apply_20260524.json` | New — manifest |
| `docs/replay/p48_powerlotto_wave4_production_apply_20260524.md` | New — this doc |
