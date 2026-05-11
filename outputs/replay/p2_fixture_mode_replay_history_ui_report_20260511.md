# P2 Fixture-Mode Replay History UI Report - 2026-05-11

## 1. Goal

Implement the smallest viable endpoint-level `fixture_mode` bridge so replay history can read the synthetic non-ONLINE fixture artifact and the dashboard can visibly indicate fixture mode without touching production DB write paths, registry state, backfill, promotion, or scheduler logic.

## 2. Implementation Summary

Implemented a read-only fixture branch in `GET /api/replay/history`:

- `fixture_mode=false` keeps the existing DB-backed behavior unchanged.
- `fixture_mode=true` reads `outputs/replay/non_online_replay_fixture_20260511.json` and returns synthetic replay rows.
- Returned fixture rows include the advisory flags required by the bridge spec.
- The dashboard now reads and persists `rp_fixture_mode=true` in the query string and renders a visible fixture banner when synthetic mode is active.

## 3. Modified Files

- `lottery_api/routes/replay.py`
- `index.html`
- `tests/test_replay_api_contract.py`
- `tests/test_replay_browser_smoke.py`

## 4. API Behavior

### `fixture_mode=false`

- Existing DB-backed `/api/replay/history` behavior remains in place.
- No synthetic fixture source is used.
- No `synthetic_fixture` marker is injected.
- No advisory-only flags are injected.

### `fixture_mode=true`

- Reads `outputs/replay/non_online_replay_fixture_20260511.json`.
- Returns synthetic records filtered by lifecycle status.
- Returns the required safety markers:
  - `source = synthetic_fixture`
  - `advisory_only = true`
  - `production_db_write = false`
  - `fixture_mode = true`
- Counts validated:
  - `REJECTED` -> 4 records
  - `RETIRED` -> 5 records
  - `OBSERVATION` -> 1 record

## 5. UI Behavior

- The replay page now persists `rp_fixture_mode=true` in the query string.
- When fixture mode is active, the dashboard displays:
  - `⚠ FIXTURE MODE — 合成資料、僅供驗收，不代表真實預測`
- Lifecycle filtering still works for `REJECTED`, `RETIRED`, and `OBSERVATION` while fixture mode is enabled.
- The UI does not present synthetic fixture rows as production replay truth.

## 6. Test Results

### PASS

- `python -m pytest tests/test_replay_api_contract.py::TestHistoryFixtureModeContract -q`
  - `7 passed`
- `python -m pytest tests/test_replay_browser_smoke.py -q`
  - `34 passed`
- `git diff --check`
  - passed

### FAIL

- None in the final validation set.

## 7. Production DB Safety

- Whether DB was written: `NO`
- `data/lottery_v2.db` dirty at final state: `NO`
- Registry changed: `NO`
- Backfill executed: `NO`
- Promotion / retire action executed: `NO`
- Scheduler / cron added: `NO`

Note: the broader replay contract suite can transiently dirty the local SQLite file during execution in this workspace, but the database was restored to `HEAD` before final handoff.

## 8. Unfinished Items

- No functional blocker remains for the P2 bridge scope.
- Summary endpoint fixture-mode support was not added; this was intentionally kept out of scope for the minimal bridge.

## 9. Next Step

Proceed to P22 fixture-mode browser smoke using a page URL that includes `rp_fixture_mode=true` and the lifecycle filters for `REJECTED`, `RETIRED`, and `OBSERVATION`.

## 10. Final Markers

- `P2_FIXTURE_MODE_API_BRIDGE_READY`
- `P2_FIXTURE_MODE_UI_BANNER_READY`
- `P2_FIXTURE_MODE_TESTS_PASS`
