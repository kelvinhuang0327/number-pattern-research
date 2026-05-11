# P10 — Lifecycle Endpoint Contract + Read-only Smoke Report

**Date:** 2026-05-11  
**Phase:** P10 — Lifecycle Endpoint Contract Docs + Read-only E2E Smoke  
**Branch:** `feature/p10-lifecycle-contract-smoke-20260511`  
**Base:** main @ `219b9b2`

---

## 1. Objectives

| Goal | Status |
|---|---|
| API contract documentation | ✅ Done |
| Contract / snapshot tests | ✅ Done |
| Dashboard static smoke tests | ✅ Done |
| Endpoint live smoke via TestClient | ⏭ Deferred (see §6) |
| Governance report | ✅ This file |

---

## 2. API Contract Documentation

**File:** `docs/replay/strategy_lifecycle_endpoint_contract.md`

Content covers:
- Endpoint path and purpose
- Hard constraints (no DB write, no backfill, no promotion, no scheduler)
- Full response schema (top-level keys + strategy entry keys)
- Expected lifecycle counts (ONLINE=6, REJECTED=4, RETIRED=5, OBSERVATION=1, total=16)
- Response marker: `P7_STRATEGY_LIFECYCLE_ENDPOINT_READY`
- Example response (abbreviated)
- Frontend usage (badges, table, `_esc()` XSS protection)
- Explicitly prohibited UI actions (promote, retire, backfill, run replay, scheduler)
- Governance markers

---

## 3. Contract / Snapshot Test Results

**File:** `tests/test_replay_strategy_lifecycle_contract.py`

```
pytest tests/test_replay_strategy_lifecycle_contract.py -q
```

**Result: 27 passed** ✅

Test classes and coverage:

| Class | Tests | Assertion |
|---|---|---|
| `TestTopLevelKeys` | 2 | Response has exactly the expected 9 top-level keys |
| `TestLifecycleCountsSchema` | 4 | `lifecycle_counts` is dict with 4 status keys, values are int, sum == total |
| `TestTotal` | 2 | total=16, strategies list length matches total |
| `TestMarker` | 2 | marker = "P7_STRATEGY_LIFECYCLE_ENDPOINT_READY", is string |
| `TestNoDbWrite` | 2 | no_db_write=True, no_db_write_note is non-empty string |
| `TestStrategyEntryKeys` | 5 | Entries have only allowed keys, required keys present, types correct |
| `TestStrategyOrdering` | 1 | strategy ordering stable across two consecutive calls |
| `TestNoCallablesInResponse` | 2 | No callable / non-JSON-serializable objects in strategy entries |
| `TestIdSets` | 3 | exec/non_exec disjoint, union=total, only ONLINE strategies executable |
| `TestContractDocCompleteness` | 2 | Contract doc exists and mentions all top-level response fields |

---

## 4. Dashboard Static Smoke Results

**File:** `tests/test_replay_strategy_lifecycle_dashboard_static.py`

```
pytest tests/test_replay_strategy_lifecycle_dashboard_static.py -q
```

**Result: 21 passed** ✅

Test classes and coverage:

| Class | Tests | Assertion |
|---|---|---|
| `TestCardPresence` | 3 | `rp-lifecycle-registry-card`, `rp-lc-tbody`, `rp-lc-table` present |
| `TestJsFunction` | 2 | `rpLoadLifecycleRegistry` defined as function |
| `TestEndpointReference` | 2 | `/api/replay/strategy-lifecycle` in JS, used via `fetch()` |
| `TestBadgeElements` | 4 | All 4 badge elements present (ONLINE, REJECTED, RETIRED, OBS) |
| `TestNoPromoteButton` | 1 | No promote/升級/晉升 in lifecycle card block |
| `TestNoBackfillButton` | 2 | No backfill button tag in lifecycle card block |
| `TestNoRunReplayButton` | 2 | No run/replay button or triggerReplay in lifecycle card block |
| `TestNoSchedulerTrigger` | 1 | No scheduler-toggle in lifecycle card block |
| `TestXssProtection` | 3 | `_esc()` defined, used for `strategy_id` and `lifecycle_status` |
| `TestErrorStateDisplayOnly` | 3 | `rp-lc-error` exists, is not a button, has no onclick handler |

---

## 5. Full Targeted Lifecycle Test Results (P10 baseline)

```
pytest tests/test_replay_strategy_lifecycle_registry.py \
       tests/test_replay_strategy_lifecycle_exposure.py \
       tests/test_replay_strategy_lifecycle_endpoint.py \
       tests/test_replay_strategy_lifecycle_contract.py \
       tests/test_replay_strategy_lifecycle_dashboard_static.py -q
```

**Result: 135 passed in 0.29s** ✅

| File | Tests | Phase |
|---|---|---|
| `test_replay_strategy_lifecycle_registry.py` | 22 | P2 |
| `test_replay_strategy_lifecycle_exposure.py` | 39 | P3-P6 |
| `test_replay_strategy_lifecycle_endpoint.py` | 26 | P7 |
| `test_replay_strategy_lifecycle_contract.py` | 27 | P10 (new) |
| `test_replay_strategy_lifecycle_dashboard_static.py` | 21 | P10 (new) |
| **Total** | **135** | |

---

## 6. Endpoint Live Smoke — DEFERRED

**Reason:** `httpx` package not installed in the project venv (`/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.venv`). FastAPI `TestClient` requires `httpx` at import time and raises `RuntimeError` if absent.

**Risk:** Low. The contract tests (`TestTopLevelKeys`, `TestTotal`, `TestMarker`, `TestNoDbWrite`, `TestIdSets`) call the route function directly via `asyncio.new_event_loop()` — the same pattern used across all existing replay API contract tests (`test_replay_api_contract.py`). Response shape, field values, and no-DB-write guarantee are fully verified at the function level.

**P11 recommendation:** Install `httpx` as a dev dependency and add a `tests/test_replay_strategy_lifecycle_live_smoke.py` that uses `TestClient` to verify HTTP status 200, `Content-Type: application/json`, and response invariants over the full ASGI stack.

---

## 7. No DB Write Evidence

- `GET /api/replay/strategy-lifecycle` contains no `sqlite3.connect` call
- `test_replay_strategy_lifecycle_endpoint.py::TestNoDbWrite::test_no_sqlite3_connect_called` spy confirms no sqlite3 import is called during endpoint execution
- Contract test `TestNoDbWrite::test_no_db_write_is_true` confirms field = `True`
- All data sourced from `replay_strategy_registry.py` in-memory structures

---

## 8. No Backfill / No Strategy Promotion Evidence

- Dashboard static smoke: no backfill button in `rp-lifecycle-registry-card` block
- Dashboard static smoke: no promote button in `rp-lifecycle-registry-card` block
- Dashboard static smoke: no scheduler-toggle in card block
- Contract tests confirm OBSERVATION/REJECTED/RETIRED strategies remain `is_executable=False`
- `test_only_online_strategies_are_executable` verifies no non-ONLINE strategy appears in `executable_strategy_ids`

---

## 9. Diff Scope

```
docs/replay/strategy_lifecycle_endpoint_contract.md     (new — contract doc)
tests/test_replay_strategy_lifecycle_contract.py        (new — 27 tests)
tests/test_replay_strategy_lifecycle_dashboard_static.py (new — 21 tests)
outputs/replay/p10_lifecycle_contract_smoke_20260511.md (new — this report)
```

No runtime code modified. No `lottery_v2.db` touched.

---

## 10. Risks and Limitations

| Risk | Severity | Notes |
|---|---|---|
| Live HTTP smoke not done | Low | Direct async call tests cover contract fully |
| `_extract_js_function` 2000-char window | Resolved | Fixed test to search full HTML text |
| Browser E2E tests pre-existing failures | Pre-existing | `test_replay_lifecycle_browser_e2e.py` ×5 — unchanged |
| MAB ensemble failures | Pre-existing | `test_mab_ensemble.py` ×6 — unchanged |

---

## 11. P11 Recommendations

```text
1. Install httpx as dev dependency → enable TestClient live smoke
2. PR readiness review for P10 (this PR)
3. YES-gated merge of P10 PR
4. P10 post-merge verification
5. Dashboard filter/sort polish (lifecycle filter UX)
6. Consider API response versioning strategy
```

---

## 12. Final Markers

```
P10_LIFECYCLE_ENDPOINT_CONTRACT_DOC_READY
P10_LIFECYCLE_ENDPOINT_CONTRACT_TESTS_PASS
P10_LIFECYCLE_DASHBOARD_STATIC_SMOKE_PASS
P10_READONLY_NO_DB_WRITE_NO_BACKFILL_CONFIRMED
P10_LIFECYCLE_ENDPOINT_LIVE_SMOKE_DEFERRED
```
