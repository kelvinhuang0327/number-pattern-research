# P254A — Fetcher Backfill Repair

**Date:** 2026-06-08  
**Branch:** `p254a-fetcher-backfill-repair`  
**Classification:** FETCHER_BACKFILL_REPAIR_COMPLETE  
**Prerequisite:** PR #360 (ACCEPT_BACKFILL_DB_DRIFT_2026_0608) merged before this task

---

## Problem

`lottery_api/fetcher/*` was accidentally deleted in commit `7306264`. This caused:

1. **CORS-blocked 500 errors** on `/api/ingest/log` and `/api/ingest/backfill` — `ModuleNotFoundError` propagated outside FastAPI's exception handler before CORS headers could be added. Browser showed `Origin http://localhost:8081 is not allowed by Access-Control-Allow-Origin`.
2. **`ValueError: invalid literal for int() with base 10: '009-01'`** in `missing_issue_detector.py` when scanning ADD_ON draw IDs like `103000009-01`. `_detect_internal_gaps()` called `int(draw[-6:])` on hyphenated draw IDs.

---

## Fix

### 1. Restored five deleted fetcher modules (from commit `997e07a`)

| File | Lines | Role |
|------|-------|------|
| `lottery_api/fetcher/__init__.py` | 4 | Package init |
| `lottery_api/fetcher/backfill_engine.py` | 368 | Orchestrates fetch → conflict-check → insert |
| `lottery_api/fetcher/ingest_logger.py` | 105 | Logs backfill operations to JSONL |
| `lottery_api/fetcher/taiwan_lottery_fetcher.py` | 237 | Fetches from api.taiwanlottery.com |
| `lottery_api/fetcher/missing_issue_detector.py` | 238 | Detects missing draws (with ADD_ON fix) |

### 2. Hardened `missing_issue_detector.py` for ADD_ON draw IDs

`_split()` helper in `_detect_internal_gaps()` now returns `None` for non-standard formats:

```python
def _split(draw: str):
    if len(draw) < 7 or not draw.isdigit():
        return None   # skip ADD_ON draws like '103000009-01'
    try:
        seq  = int(draw[-6:])
        year = int(draw[:-6])
        return year, seq
    except (ValueError, TypeError):
        return None
```

Loop skips `None` pairs (`if prev is None or curr is None: continue`). Sort key also hardened with `try/except`.

---

## Endpoint Verification

| Test | Status |
|------|--------|
| `GET /api/ingest/log?limit=5` → 200, `entries` key present | ✅ PASS |
| `GET /api/ingest/log` CORS header present | ✅ PASS |
| `POST /api/ingest/backfill` `dry_run=true` → 200, `success=true` | ✅ PASS |
| `POST /api/ingest/backfill` CORS header present | ✅ PASS |
| `OPTIONS /api/ingest/backfill` preflight → 200 with Allow-Origin | ✅ PASS |
| `_detect_internal_gaps(['103000008','103000009-01','103000010'])` → no crash | ✅ PASS |

---

## DB Baseline (after PR #360, read-only)

| Metric | Value |
|--------|-------|
| BIG_LOTTO raw rows | 22,239 |
| BIG_LOTTO canonical (`draws_big_lotto_canonical_main`) | 2,114 |
| BIG_LOTTO ADD_ON rows | 19,100 |
| POWER_LOTTO raw rows | 1,917 |
| DAILY_539 raw rows | 5,882 |
| `strategy_prediction_replays` | 94,924 |
| DB integrity | ok |

---

## Regression Tests

| Suite | Result |
|-------|--------|
| `test_p247g_big_lotto_canonical_isolation_final_guard.py` (67 tests) | ✅ PASS |
| `test_p253d_historical_draw_parser_inventory.py` | ✅ PASS |
| `test_p253e_historical_draw_parser_ssot.py` | ✅ PASS |
| `test_p253f_historical_draw_parser_adoption_audit.py` | ✅ PASS |
| `test_p251d_evidence_dashboard_readonly_api_route.py` | ✅ PASS |
| **Total** | **221 passed** |

---

## Compliance

- No DB write performed in P254A.
- No rows inserted, updated, or deleted.
- P247G constants unchanged (PR #360 already updated them).
- No strategy, registry, replay, or frontend files modified.
- Runtime dirty files (`backend.pid`, `frontend.pid`, `data/lottery_v2.db`) not staged.

---

*P254A — fetcher backfill repair — 2026-06-08*
