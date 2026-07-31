# P39: Replay UI Smoke Closure After P38

**Date:** 2026-05-23
**Branch:** p39-replay-ui-smoke-closure-after-p38
**Classification:** P39_REPLAY_UI_SMOKE_CLOSURE_AFTER_P38_MERGED_TO_MAIN

---

## Scope and Goal

P38 (#174, merge commit 9e343f7) deferred the UI smoke test because the frontend
verification was not performed at the time of merge (only API layer was verified).
P39 closes that deferred item.

No production DB writes. No backfill. No new strategies. No lifecycle changes.

---

## Pre-flight Results

| Check | Result |
|-------|--------|
| Repo root | /Users/kelvin/Kelvin-WorkSpace/LotteryNew |
| Branch at start | main |
| P38 merge commit included (9e343f7) | YES |
| Production rows | 28960 |
| Drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |
| Branch governance guard | BRANCH_GOVERNANCE_PASS |

---

## API Cross-Check Results

Backend: http://localhost:8002
Endpoint: GET /api/replay/history?lottery_type=DAILY_539&strategy_id=...&page=1&page_size=1

| Strategy | Rows via API | Status |
|----------|-------------|--------|
| markov_1bet_539 | 1500 | PASS |
| acb_single_539 | 1500 | PASS |
| zone_gap_3bet_539 | 1500 | PASS |
| 539_3bet_orthogonal | 1500 | PASS |
| p0b_539_3bet_f_cold_fmid | 1500 | PASS |
| p0c_539_3bet_f_cold_x2 | 1500 | PASS |
| **Total Wave 2 rows** | **9000** | **PASS** |

Pagination check: page1=100 rows, page15=100 rows, total=1500 for markov_1bet_539 — PASS.

DAILY_539 overall total: 19680 rows (all strategies combined).

---

## UI Smoke Results

Frontend: http://localhost:8081 (Python HTTP server, PID from frontend.pid)
Backend: http://localhost:8002 (uvicorn app.py, PID from backend.pid)

### Page Load

- Frontend accessible: YES
- Replay tab (歷史回放) visible: YES
- Replay page loads without error: YES

### Filter Functionality

- 彩種 (lottery type) selector present: YES
- DAILY_539 option available: YES (shown as "今彩539")
- Date range filter present: YES
- DAILY_539 filter query returns rows: YES

### P37 Wave 2 Strategy Visibility

All 6 P37 Wave 2 strategies are visible in the replay table after selecting DAILY_539:

| Strategy | Visible in Table |
|----------|-----------------|
| markov_1bet_539 | YES |
| acb_single_539 | YES |
| zone_gap_3bet_539 | YES |
| 539_3bet_orthogonal | YES |
| p0b_539_3bet_f_cold_fmid | YES |
| p0c_539_3bet_f_cold_x2 | YES |

**Note on strategy dropdown:** The strategy selector dropdown only shows registry-registered
strategies (ONLINE/OFFLINE/RETIRED). P37 Wave 2 strategies have lifecycle_status=DRY_RUN
and are not in the ONLINE registry — so they do not appear in the dropdown. However, they
DO appear in the table rows when querying by lottery_type=DAILY_539, which is the correct
behavior.

### Preset Buttons

| Preset | Status |
|--------|--------|
| 100期 | Present |
| 500期 | Present |
| 1000期 | Present |
| 1500期 | Present (tested — shows ~3000 rows for DAILY_539 across all strategies) |

### Console Errors

None. `(no console errors)` confirmed via browser tooling.

### Network Errors

All API calls returned 200:

```
GET /api/replay/strategy-catalog          -> 200
GET /api/replay/strategies?lottery_type=DAILY_539 -> 200
GET /api/replay/freshness                 -> 200
GET /api/replay/strategy-lifecycle        -> 200
GET /api/replay/history?lottery_type=DAILY_539&... -> 200
GET /api/replay/summary?lottery_type=DAILY_539     -> 200
```

### Overall UI Smoke Status: PASS

---

## P38 Deferred UI Smoke Item

**Status: RESOLVED**

P38 deferred the UI smoke because the frontend was not verified at merge time.
P39 completes the UI smoke:
- Frontend accessible at localhost:8081
- Replay page loads
- DAILY_539 filter works
- All 6 P37 Wave 2 strategies are visible in the table
- No console errors
- All API calls succeed with 200

---

## Test Summary

Test file: `tests/test_p39_replay_ui_smoke_closure_after_p38.py`

| Test Class | Tests |
|-----------|-------|
| TestProductionRowCount | 2 tests — rows=28960 unchanged |
| TestP37StrategyRows | 5 tests — each strategy 1500 rows, all DAILY_539, none ONLINE |
| TestReplayAPIEndpoint | 4 integration tests (skip if server unavailable) |
| TestP39UISmokeDocumentation | 7 tests — output JSON structure and content |

---

## Post-Test Guards

| Guard | Result |
|-------|--------|
| Production rows | 28960 (unchanged) |
| Drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |
| Branch governance guard | BRANCH_GOVERNANCE_PASS (branch=p39-..., rows=28960) |

---

## Recommended Next Phase

P40 or higher: Consider promoting one or more P37 Wave 2 strategies from DRY_RUN
to OBSERVATION or ONLINE lifecycle after accumulating sufficient monitoring data.
Current status: all 6 strategies have 1500 historical replay rows available for
review via the UI and API.

---

## Final Classification

**P39_REPLAY_UI_SMOKE_CLOSURE_AFTER_P38_MERGED_TO_MAIN**
