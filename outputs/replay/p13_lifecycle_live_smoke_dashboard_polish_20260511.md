# P13 Lifecycle Live Smoke + Dashboard Polish

## 1. Goal

Harden the replay lifecycle surface in read-only mode by deciding whether live HTTP smoke should be enabled, then polish the lifecycle dashboard with client-side filter and sort controls.

## 2. Live Smoke Decision

Live HTTP smoke for `GET /api/replay/strategy-lifecycle` is deferred.

Reason:
- The shared venv does not have `httpx` installed.
- `lottery_api/requirements.txt` does not declare `httpx`.
- The repo already has deterministic read-only coverage that avoids a live server.

## 3. Dashboard Polish Summary

Added read-only client-side controls to the lifecycle registry card:
- lifecycle status filter
- lottery type filter
- strategy_id text search
- sort by strategy_id / lottery_type / lifecycle_status
- sort direction toggle
- row count display

The registry loader now renders through a reusable client-side function so the table can re-filter and re-sort without any POST/PUT/DELETE path.

## 4. Test Results

- Targeted lifecycle suite: 143 PASS
- Registry CLI JSON output: PASS
- No browser or live HTTP smoke was added

## 5. No DB Write Evidence

- The lifecycle registry report script does not import or call sqlite3.
- The lifecycle endpoint and registry tests remain read-only.
- No production DB write path was introduced.

## 6. No Backfill Evidence

- No replay backfill code was added.
- No backfill trigger button was introduced.
- No replay generation path was changed.

## 7. No Promotion / Executable Action Evidence

- No promote button was added.
- No retire button was added.
- No run replay button was added.
- No scheduler trigger was added.
- Non-ONLINE strategies remain non-executable.

## 8. Diff Scope

- `index.html`
- `tests/test_replay_strategy_lifecycle_dashboard_static.py`
- `docs/replay/strategy_lifecycle_live_smoke_decision.md`
- `outputs/replay/p13_lifecycle_live_smoke_dashboard_polish_20260511.md`

## 9. Risks and Limitations

- The new sort/filter controls operate on the client-side registry payload only.
- Live HTTP smoke remains deferred until `httpx` is added under a documented dependency policy.

## 10. P14 Recommendation

If the next round wants live HTTP smoke, first standardize `httpx` as a dev dependency and then add a dedicated TestClient smoke test for the lifecycle endpoint.

## 11. Final Markers

- `P13_LIFECYCLE_LIVE_SMOKE_DECISION_RECORDED`
- `P13_LIFECYCLE_LIVE_SMOKE_DEFERRED`
- `P13_DASHBOARD_READONLY_POLISH_READY`
- `P13_NO_DB_WRITE_NO_BACKFILL_CONFIRMED`
- `P13_NO_PROMOTION_ACTION_CONFIRMED`
- `P13_TARGETED_LIFECYCLE_TESTS_PASS`
