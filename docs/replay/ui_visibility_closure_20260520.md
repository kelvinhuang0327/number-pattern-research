# UI Visibility Recovery — Closure Report
**Date**: 2026-05-20  
**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Commit**: `a89a7ca` — `fix(replay): hide internal catalog states from public replay UI`

---

## Root Cause

`catalog_visibility_state` model had no public vs admin visibility gate.  
`/api/replay/strategies` and the lifecycle registry card could expose all internal states
(`ARTIFACT_CANDIDATE`, `RECONSTRUCTIBLE`, `REGISTERED_NO_DATA`, `UNSUPPORTED`) to
public/unauthenticated consumers — these states carry no replay rows, predictions, or
user-actionable content and should never appear in the main replay UI.

---

## Fix Summary

Three files changed in `a89a7ca`:

| File | Change |
|------|--------|
| `lottery_api/models/replay_catalog_visibility_gate.py` | **New**: visibility gate model |
| `tests/test_p3_replay_catalog_ui_state_contract.py` | **Updated**: 18 new assertions |
| `lottery_api/routes/replay.py` | **Updated**: `?public_only=true` param |

### Visibility Rule

```
PUBLIC_VISIBLE_STATES  = { REGISTERED_WITH_REPLAY_ROWS }
INTERNAL_ONLY_STATES   = { ARTIFACT_CANDIDATE, RECONSTRUCTIBLE,
                            REGISTERED_NO_DATA, UNSUPPORTED }
```

- `REGISTERED_WITH_REPLAY_ROWS` — public: has real replay rows, verifiable data
- `ARTIFACT_CANDIDATE` — internal: strategy code exists but zero replay rows
- `RECONSTRUCTIBLE` — internal: historical rows reconstructible but not yet applied
- `REGISTERED_NO_DATA` — internal: registered with no data at all
- `UNSUPPORTED` — internal: format/schema not supported for replay

### API Change

`GET /api/replay/strategies?public_only=true`
- Restricts to **ONLINE / OBSERVATION** lifecycle states only
- Response envelope includes `"filter_public_only": true`
- Default (`public_only=false`) behavior unchanged — internal/admin usage unaffected

---

## Test Results

| Test Suite | Result | Count |
|------------|--------|-------|
| `test_p3_replay_catalog_ui_state_contract.py` | **PASS** | 35 |
| `test_replay_api_contract.py` | **PASS** | — |
| `test_p1_catalog_visibility_contract.py` | **PASS** | — |
| `test_p1_catalog_visibility_plan.py` | **PASS** | — |
| `test_p2_lifecycle_backfill_dry_run.py` | **PASS** | — |
| `test_p4c3_supported_prediction_apply_contract.py` | **PASS** | — |
| **Core baseline total** | **PASS** | **118** |
| Drift guard (`--strict`) | **PASS** | — |

### Pre-existing Failure (not caused by this commit)

`test_p25_display_only_catalog.py` — 8 tests FAIL with ONLINE set mismatch:
- Expected 6 ONLINE strategies; actual 8 (`fourier_rhythm_3bet` + `ts3_regime_3bet` added in `8b4ffc8`)
- Confirmed: `a89a7ca` did NOT touch `test_p25_display_only_catalog.py`
- This is a non-regression from P1.3 strategy registration (pre-existing since `8b4ffc8`)

---

## Safety Confirmation

- `strategy_prediction_replays` rows: **460** (unchanged, drift guard verified)
- No DB write, no prediction rows, no replay rows generated
- No pipeline side effects
- No backfill triggered
- No lifecycle state mutations

---

## Manual Browser Check Steps

1. Open the replay page (`/replay` or equivalent frontend route)
2. Confirm only strategies with `REGISTERED_WITH_REPLAY_ROWS` state appear in the public list
3. Confirm no entries labeled `ARTIFACT_CANDIDATE`, `RECONSTRUCTIBLE`, `REGISTERED_NO_DATA`, or `UNSUPPORTED` appear
4. Open DevTools → Network → filter `strategies`
5. Call `GET /api/replay/strategies?public_only=true` — confirm response `filter_public_only: true`
6. Confirm response entries are all `lifecycle_state: ONLINE` or `OBSERVATION`
7. Call `GET /api/replay/strategies` (no param) — confirm all states still visible (admin path unchanged)

---

## P6 Source Promotion Policy — Status Gap

The current session's context referenced P6 source promotion policy artifacts as "completed but untracked."  
**Actual finding**: All 7 P6 source promotion policy target files are absent from both working tree and git history.

Missing files:
- `lottery_api/models/replay_source_promotion_policy.py`
- `scripts/p6_source_promotion_policy.py`
- `tests/test_p6_source_promotion_policy_contract.py`
- `tests/test_p6_source_promotion_policy.py`
- `outputs/replay/p6_source_promotion_policy_20260520.json`
- `docs/replay/p6_source_promotion_policy_20260520.md`
- `docs/replay/p6_readiness_report_20260520.md`

**Classification**: P6 source promotion policy must be **created** before P7 dry-run can be authorized.

---

## Next Step: P6 Source Promotion Policy Required Before P7

P7 dry-run preparation is **blocked** until:
1. P6 source promotion policy is created and committed
2. P6 tests PASS
3. P6 candidate list is established (expected: 9 ARTIFACT_CANDIDATE strategies)

P7 dry-run will NOT be prepared in this session.
