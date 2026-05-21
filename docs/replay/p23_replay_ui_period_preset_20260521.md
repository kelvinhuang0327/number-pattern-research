# P23a: Replay UI Period Preset Quick-Select Buttons

**Branch**: `p23-replay-ui-period-preset`  
**Date**: 2026-05-21  
**Status**: IMPLEMENTED — pending PR

---

## Summary

Added four period preset quick-select buttons (100期 / 500期 / 1000期 / 1500期) to the replay history card header. Clicking a preset button fetches the latest N periods using multi-fetch (page_size=200 per call, client-side accumulation) and displays all results in a single table with pagination disabled.

No backend changes. No DB writes. `rpQuery` (standard paginated mode) is unchanged in behavior.

---

## Changes

### `index.html`

**1. Card-header HTML** (line ~2047)  
- Added `flex-wrap:wrap` to card-header container  
- Inserted `#rp-preset-btns` div with four `rp-preset-btn` buttons  
- Each button: `data-preset="N"`, `data-testid="rp-preset-N"`, class `btn btn-sm btn-secondary rp-preset-btn`

**2. JS Variables**
- `const rpPageSize = 50` → `let rpPageSize = 50`  
- Added `let rpPresetPeriods = 0;` (0 = normal paginated, N = preset mode)

**3. `rpBuildHistoryRows(records)` — new shared helper**
- Extracted row rendering from `rpQuery` to avoid duplication  
- Preserves all P22 guards: `predicted_special != null`, truth-level badge, fixture_mode class, REPLAY_ERROR tooltip  
- Called by both `rpQuery` and `rpPresetFetch`

**4. `rpPresetFetch(n)` — new multi-fetch function**
- `FETCH_PS = 200` (backend ceiling `le=200`)  
- `while (allRecords.length < n)` loop; each call uses `page_size = min(200, remaining)`  
- Forwards all current filter values (lottery_type, strategy_id, dates, fixture_mode)  
- Disables prev/next pagination buttons  
- Shows `前 N 期 / X 筆` in `rp-total-label` and `rp-page-info`  
- Manual query button click resets `rpPresetPeriods = 0, rpPageSize = 50` to restore normal mode

**5. DOMContentLoaded event wiring**
- `querySelectorAll('.rp-preset-btn').forEach` → calls `rpPresetFetch(n)` on click  
- Query button listener updated to reset preset state before calling `rpQuery()`

---

## Multi-Fetch Architecture

| Preset | Backend calls | Record distribution |
|--------|--------------|---------------------|
| 100期  | 1            | page_size=100       |
| 500期  | 3            | 200+200+100         |
| 1000期 | 5            | 200×5               |
| 1500期 | 8            | 200×7+100           |

Early termination if batch is empty or total rows exhausted.

---

## Test Results

| Suite | Tests | PASS | FAIL |
|-------|-------|------|------|
| `test_p23_replay_ui_period_preset.py` (new) | 47 | 47 | 0 |
| Canonical governance + P22 + P23 (regression) | 186 | 186 | 0 |

### Test coverage (P23a)
- HTML structure: 9 tests (buttons present, data-testid, class, total-label, flex-wrap)  
- JS variables: 3 tests (let rpPageSize, rpPresetPeriods, comment)  
- `rpBuildHistoryRows`: 7 tests (declared, called by rpQuery, called by rpPresetFetch, no inline map in rpQuery, toggle button, detail row, null guard)  
- `rpPresetFetch`: 12 tests (FETCH_PS=200, while loop, concat, slice, rpPresetPeriods, prev/next disabled, filters, fixture_mode, labels)  
- DOM event wiring: 5 tests (preset buttons wired, rpPresetFetch called, query btn resets preset/pageSize/page)  
- Backend ceiling: 3 tests (le=200, default 50, FETCH_PS ≤ 200)  
- Production row count: 2 tests (12460, DAILY_539=3180)  
- DAILY_539 regression: 6 tests (null special unchanged, null guard in helper, rpQuery uses helper, selectors intact, fixture toggle intact, pagination intact)

---

## Guards

- **Drift guard**: `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`  
- **Governance guard**: `BRANCH_GOVERNANCE_PASS — branch='p23-replay-ui-period-preset' rows=12460`  
- **Production rows**: 12460 (unchanged)  
- **DAILY_539 predicted_special non-null**: 0 (P22 regression PASS)

---

## Forbidden file check

Staged files (4 only):
- `index.html`
- `tests/test_p23_replay_ui_period_preset.py`
- `outputs/replay/p23_replay_ui_period_preset_20260521.json`
- `docs/replay/p23_replay_ui_period_preset_20260521.md`

NOT staged: `*.db`, `*.bak_*`, `*.pid`, `runtime/`
