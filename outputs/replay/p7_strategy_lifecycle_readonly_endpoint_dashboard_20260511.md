# P7 Governance Report — Strategy Lifecycle Read-Only Endpoint + Dashboard

**Report ID:** p7_strategy_lifecycle_readonly_endpoint_dashboard_20260511  
**Date:** 2026-05-11  
**Base commit (pre-P7):** `ff11226`  
**Status:** IMPLEMENTATION COMPLETE — PENDING PR APPROVAL

---

## 1. Objective

Expose the strategy lifecycle registry (established in P2+P3) via a read-only REST endpoint and surface it in the frontend replay dashboard.

Constraints enforced throughout:
- No DB write, no backfill, no strategy promotion
- No OBSERVATION→ONLINE transition
- Non-ONLINE strategies must not become executable
- No scheduler / cron
- No write buttons in frontend
- `lottery_v2.db` must not be committed

---

## 2. Files Changed

| File | Change |
|---|---|
| `lottery_api/routes/replay.py` | Added `GET /api/replay/strategy-lifecycle` endpoint + expanded P3 imports |
| `tests/test_replay_strategy_lifecycle_endpoint.py` | NEW — 27 endpoint tests |
| `index.html` | Added lifecycle registry card + `rpLoadLifecycleRegistry()` JS fetch |

---

## 3. Endpoint Specification

```
GET /api/replay/strategy-lifecycle
```

**Response fields:**

| Field | Type | Value |
|---|---|---|
| `total` | int | 16 |
| `lifecycle_counts` | dict | `{ONLINE:6, REJECTED:4, RETIRED:5, OBSERVATION:1}` |
| `executable_strategy_ids` | list[str] | 6 ONLINE strategy IDs |
| `non_executable_strategy_ids` | list[str] | 10 non-ONLINE strategy IDs |
| `strategies` | list[dict] | 16 entries with per-strategy metadata |
| `no_db_write` | bool | `true` |
| `no_db_write_note` | str | audit note |
| `marker` | str | `P7_STRATEGY_LIFECYCLE_ENDPOINT_READY` |
| `disclaimer` | str | audit disclaimer |

**Per-strategy entry keys:** `strategy_id`, `strategy_name`, `strategy_version`, `supported_lottery_types`, `min_history`, `lifecycle_status`, `is_executable`

**`is_executable` rule:** `True` iff `lifecycle_status == "ONLINE"` (no exception, no promotion path).

---

## 4. Test Results

### Scoped lifecycle test run (P7 Phase D)
```
tests/test_replay_strategy_lifecycle_registry.py   — PASS
tests/test_replay_strategy_lifecycle_exposure.py   — PASS
tests/test_replay_strategy_lifecycle_endpoint.py   — PASS (27 new tests)

87 passed in 0.29s
```

### Full tests/ suite (Phase F)
```
204 passed, 11 failed in 15.41s
```

**Pre-existing failures (not caused by P7):**
- `tests/test_mab_ensemble.py` — 5 failures (pre-existing, unrelated)
- `tests/test_replay_lifecycle_browser_e2e.py` — 6 failures (require live server, pre-existing)

No regression introduced by P7 changes.

---

## 5. Frontend Changes

Added to `index.html` inside the `#replay-section`:

- **Strategy Lifecycle Registry card** (`#rp-lifecycle-registry-card`)  
  - Summary badges: ONLINE / REJECTED / RETIRED / OBS counts  
  - Lifecycle table: strategy_id, name, supported lottery types, lifecycle status (colour-coded), executable (✓ or —)  
  - All data is fetched from `GET /api/replay/strategy-lifecycle` — no direct registry import
  - HTML-escaped output via `_esc()` — no XSS risk
  - No write buttons, no promotion controls

- **Auto-load hook:** `rpLoadLifecycleRegistry()` called when user navigates to replay section.

---

## 6. P7 Markers

```
P7_STRATEGY_LIFECYCLE_ENDPOINT_READY
P7_STRATEGY_LIFECYCLE_ENDPOINT_NO_DB_WRITE_CONFIRMED
P7_READONLY_LIFECYCLE_EXPOSURE_CONFIRMED
P7_STRATEGY_LIFECYCLE_ENDPOINT_TESTS_PASS
P7_STRATEGY_LIFECYCLE_DASHBOARD_READY
```

---

## 7. Invariants Verified

| Invariant | Status |
|---|---|
| `no_db_write = True` in endpoint response | PASS |
| `sqlite3.connect` not called by endpoint (spy test) | PASS |
| ONLINE count = 6 | PASS |
| REJECTED count = 4 | PASS |
| RETIRED count = 5 | PASS |
| OBSERVATION count = 1 | PASS |
| Executable count = 6 (ONLINE only) | PASS |
| Non-executable count = 10 | PASS |
| Executable ∩ Non-executable = ∅ | PASS |
| Executable ∪ Non-executable = all 16 IDs | PASS |
| No callable leaked in strategy entries | PASS |
| No DB write, no strategy promotion in frontend | PASS |

---

## 8. Next Action

This report is complete. A PR should be opened on branch `feature/p7-strategy-lifecycle-readonly-dashboard-20260511`.  
**Do not merge without explicit user YES.**
