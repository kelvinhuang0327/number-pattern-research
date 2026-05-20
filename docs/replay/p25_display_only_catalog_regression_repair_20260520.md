# P25 Display-Only Catalog Regression Repair
**Date**: 2026-05-20  
**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519

---

## Root Cause

Two separate issues caused 8 test failures in `tests/test_p25_display_only_catalog.py`:

### Issue 1 — FastAPI `Query` object coercion (6 failures)

**Symptom**: `TestStrategiesApiContract` tests returned wrong results — REJECTED filter
returned ONLINE strategies; no-filter returned only 9 strategies (not all 18).

**Root cause**: `a89a7ca` added `public_only: bool = Query(False, ...)` to the
`list_replay_strategies` FastAPI route. When tests call this async route function
**directly** (not via HTTP), FastAPI's `Query(False, ...)` object is used as the
default value. The `Query` object is truthy (it's a Python object, not `False`),
so `if public_only:` evaluated to `True`, causing:
- `lifecycle_status` to be reset to `None` (overriding any filter)
- Results to be filtered to ONLINE + OBSERVATION only (9 strategies)

**Fix**: Extracted business logic into `get_strategies_response(lottery_type, lifecycle_status, public_only)` — a plain sync function with proper Python bool defaults. The HTTP endpoint now calls this with `bool(public_only)` for safety. Tests import and call `get_strategies_response` directly instead of the FastAPI handler.

### Issue 2 — Hardcoded ONLINE strategy set (2 failures)

**Symptom**: `TestOnlineStrategiesNonRegression` expected 6 ONLINE strategies but
registry now has 8.

**Root cause**: Commit `8b4ffc8` (P0+P1, 2026-05-19) registered `fourier_rhythm_3bet`
and `ts3_regime_3bet` as ONLINE (P1.3 strategy expansion). The P25 test file was
not updated.

**Fix**: Updated `TestRegistryCompleteness.ONLINE_IDS`, `test_online_strategy_count_unchanged`
(6 → 8), and `test_online_strategy_ids_unchanged` expected set to include the two
new ONLINE strategies. Annotated each with the source commit.

---

## Files Changed

| File | Change |
|------|--------|
| `lottery_api/routes/replay.py` | Extracted `get_strategies_response()` sync helper |
| `tests/test_p25_display_only_catalog.py` | Fixed import, `_strategies()` helper, ONLINE count/IDs |

---

## Test Result

| Before | After |
|--------|-------|
| 27 PASS / 8 FAIL | **35 PASS / 0 FAIL** |

---

## Non-regression Confirmation

The `get_strategies_response()` helper is called by the HTTP route with `bool(public_only)`,
so the HTTP behavior is unchanged. The `public_only=true` API path continues to return
only ONLINE + OBSERVATION strategies. The `filter_public_only` field in the response
envelope is preserved.
