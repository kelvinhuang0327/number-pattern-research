# P34: Replay UI Usability Gap Closure

**Date:** 2026-05-23  
**Branch:** `p34-replay-ui-usability-gap-closure`  
**Base:** main @ `1528b4c`  
**Classification:** `P34_REPLAY_UI_USABILITY_GAP_CLOSURE_MERGED_TO_MAIN`

---

## Summary

P34 closes two UX gaps in the replay page (`index.html`):

1. **Date-range default** — `rp-date-from` and `rp-date-to` were blank on first load, requiring the user to manually type dates. P34 defaults them to the last 6 months (today − 6 months → today). URL params still override.

2. **RETIRED replay-backed labeling** — P31B backfilled 7500 rows for 5 DAILY_539 RETIRED strategies. The UI previously showed `[RETIRED]` with no indicator that rich historical replay data existed. P34 adds three visual cues:
   - Strategy dropdown: `[已退役 · 有回放資料]` when `rpStrategyRowCountMap[strategy_id] > 0`
   - History table: small `回放` badge next to `strategy_id` for RETIRED rows
   - Lifecycle registry: `有回放資料` badge next to the lifecycle status for RETIRED strategies with rows

---

## Changes

### `index.html`

| Location | Change |
|---|---|
| `DOMContentLoaded` | Added `rpSetDefaultDates()` IIFE before `rpRestoreFromURL()` |
| `rpLoadStrategies()` | RETIRED label now shows `[已退役 · 有回放資料]` or `[已退役]` based on row count |
| `rpBuildHistoryRows()` | Adds `回放` badge for RETIRED lifecycle rows |
| `rpRenderLifecycleRegistryRows()` | Adds `有回放資料` badge for RETIRED strategies with rows > 0 |

### `tests/test_p34_replay_ui_usability_gap_closure.py`

22 tests covering:
- Date range IIFE presence and ordering
- RETIRED dropdown label and row-count check
- History row badge presence
- Lifecycle registry badge + row-count gate
- Preset buttons (100/500/1000/1500)
- Production rows unchanged (19960)
- P31B strategies queryable (5 × 1500 rows)
- No lifecycle promotion

---

## Guard Results

| Guard | Result |
|---|---|
| `replay_lifecycle_drift_guard --strict` | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` |
| `replay_branch_governance_guard` | `BRANCH_GOVERNANCE_PASS` |

---

## Production Data Integrity

- **Total rows:** 19960 (unchanged)
- **P31B RETIRED strategies:** 5 × 1500 = 7500 rows
- **No DB writes in this phase**
- **No strategy lifecycle changes**

---

## Governance

- Only `index.html` + 3 new files staged
- No `*.db`, `*.pid`, `CEO-Decision.md`, or registry changes
- No production data modified
