# P2 Non-ONLINE Strategy Registry Completion Report
**Date:** 2026-05-11  
**Author:** Governance Agent  
**Branch:** `feature/p2-non-online-strategy-lifecycle-registry-20260511`  
**Markers:** `P2_NON_ONLINE_LIFECYCLE_CLASSIFIED` `P2_REGISTRY_ONLY_NO_DB_WRITE_CONFIRMED` `P2_ONLINE_STRATEGIES_BEHAVIOR_UNCHANGED` `P2_REPLAY_STRATEGY_LIFECYCLE_TESTS_PASS`

---

## Objective

Add registry-only lifecycle metadata for non-ONLINE strategies to `replay_strategy_registry.py`. No DB writes, no replay backfill, no production state changes.

---

## Before State

| Scope | Count |
|---|---|
| `_ALL_ADAPTERS` | 6 (all ONLINE) |
| `_REGISTRY` | 6 (all ONLINE) |
| `get_strategy_lifecycle_status(non_online_id)` | `None` (unknown) |
| `list_strategies()` total | 6 |

---

## After State

| Scope | Count |
|---|---|
| `_ALL_ADAPTERS` | 16 (6 ONLINE + 10 stubs) |
| `_REGISTRY` | 6 (ONLINE only — unchanged) |
| `get_strategy_lifecycle_status(non_online_id)` | Correct status returned |
| `list_strategies()` total | 16 |
| `list_strategies(lifecycle_status="REJECTED")` | 4 |
| `list_strategies(lifecycle_status="RETIRED")` | 5 |
| `list_strategies(lifecycle_status="OBSERVATION")` | 1 |

---

## Files Changed

| File | Change |
|---|---|
| `lottery_api/models/replay_strategy_registry.py` | Added `LifecycleNotExecutable` exception, `_LifecycleStub` class, `_NON_EXECUTABLE_STUBS` list (10 entries), extended `_ALL_ADAPTERS` |
| `tests/test_replay_strategy_lifecycle_registry.py` | New — 22 deterministic tests covering ONLINE unchanged, non-ONLINE metadata, non-executable guard, data integrity, no-DB-write |
| `pytest.ini` | Added `pythonpath = .` for test discovery |
| `outputs/replay/p2_non_online_lifecycle_classification_20260511.md` | New — classification decisions for UNKNOWN 14 |

---

## Test Results

```
22 passed in 0.04s
```

All 4 test classes pass:
- `TestOnlineStrategiesUnchanged` (5 tests) — ONLINE 6 behaviour preserved
- `TestNonOnlineMetadataVisible` (8 tests) — stubs queryable via list/lookup
- `TestNonOnlineNotExecutable` (3 tests) — stubs raise `LifecycleNotExecutable`
- `TestDataIntegrity` (6 tests) — uniqueness, valid statuses, no DB write

---

## No DB Write — Evidence

The `test_no_db_write_on_import` test patches `sqlite3.connect` and verifies zero calls during module import/reload. Registry is purely in-memory. **Confirmed: no DB write.**

---

## ONLINE Behaviour Unchanged — Evidence

`test_registry_contains_exactly_online_ids` asserts `_REGISTRY.keys() == ONLINE_IDS` (exact set equality). `test_get_adapter_succeeds_for_all_online` retrieves all 6 adapters via `get_adapter()`. **Confirmed: ONLINE behaviour unchanged.**

---

## P3 Scope (Out of This PR)

The following are explicitly excluded from this PR:
- Registry metadata UI exposure
- Replay lifecycle dashboard
- Observation-only replay scheduling
- Controlled backfill proposal for RETIRED strategies
- DB migration (adding `lifecycle_status` column)
- `replay_history` write path changes
