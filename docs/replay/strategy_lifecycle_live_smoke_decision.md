# Strategy Lifecycle Live Smoke Decision

Date: 2026-05-11
Branch: `feature/p13-lifecycle-live-smoke-dashboard-polish-20260511`

## Decision

Live HTTP smoke for `GET /api/replay/strategy-lifecycle` is deferred.

## Why

- The shared venv does not have `httpx` installed, so FastAPI `TestClient` cannot run here.
- `lottery_api/requirements.txt` does not declare `httpx`, so enabling TestClient would widen the dependency surface without a repo-level dependency policy change.
- The current read-only coverage already validates the lifecycle surface deterministically without a live server.

## Current Coverage

- Direct async route tests for the replay API and lifecycle endpoints.
- Contract tests for the lifecycle registry response shape and invariants.
- Static dashboard smoke tests for the lifecycle registry card.
- CLI inventory/report checks for registry metadata.
- Full targeted lifecycle suite: 143 tests PASS.

## Future Condition For Live Smoke

Enable a live TestClient smoke only when the project adopts a documented dev dependency policy for `httpx` and the test harness can run it without broadening runtime risk.

## Governance Markers

- `P13_LIFECYCLE_LIVE_SMOKE_DECISION_RECORDED`
- `P13_LIFECYCLE_LIVE_SMOKE_DEFERRED`
- `P13_NO_DB_WRITE_NO_BACKFILL_CONFIRMED`
- `P13_NO_PROMOTION_ACTION_CONFIRMED`
