# Next Draw Prediction Page — Phase 3: Backend Wiring
**Date**: 2026-03-19
**Phase**: 3 — Backend Wiring

---

## 1. Change Made

**File**: `lottery_api/routes/prediction.py`
**Lines added**: ~130 (appended at end of file)

A single new GET endpoint `GET /api/next-draw-summary` was added.

---

## 2. New Endpoint Summary

```
GET /api/next-draw-summary
```

**Query Parameters**:
| Param | Default | Notes |
|-------|---------|-------|
| `mode` | `"direct"` | Coordinator mode: `direct` or `hybrid` |
| `recent_count` | `500` | History window |

**Design Principles**:
- Zero new prediction logic
- Calls existing `coordinator_predict()` unchanged
- Reads `strategy_states_*.json` from disk (already maintained by RSM)
- Partial failure safe: one game failure does not block others
- Latest period captured BEFORE slice (history is newest-first)

---

## 3. Supporting Functions Added

| Function | Purpose |
|----------|---------|
| `_NEXT_DRAW_CONFIG` | Hardcoded bet configs per game (which strategies to show) |
| `_GAME_STATUS_INFO` | Game-level status + note (editorial, from research record) |
| `_derive_strategy_status(state)` | Derives PRODUCTION/WATCH/ADVISORY_ONLY from RSM fields |
| `_load_strategy_states(lottery_type)` | Reads `lottery_api/data/strategy_states_*.json` |
| `_get_latest_period(history)` | Returns draw id from `history[0]` (newest-first) |
| `_increment_period(period_str)` | Integer +1 on period string |

---

## 4. Status Derivation Logic

```python
def _derive_strategy_status(state):
    edge = state.get("edge_300p", 0) or 0
    trend = state.get("trend", "STABLE")
    alert = state.get("alert", False)
    if alert:                                    → "WATCH"
    if edge >= 0.03 and trend in (STABLE, IMPROVING):  → "PRODUCTION"
    if edge > 0:                                 → "WATCH"
    else:                                        → "ADVISORY_ONLY"
```

---

## 5. Validation Results

```
DAILY_539:    latest=115000068, next=115000069  ✅
BIG_LOTTO:    latest=115000036, next=115000037  ✅
POWER_LOTTO:  latest=115000021, next=115000022  ✅

DAILY_539:
  1注 acb_1bet           PRODUCTION edge=3.27%  ✅
  2注 midfreq_acb_2bet   PRODUCTION edge=8.46%  ✅
  3注 acb_markov_midfreq PRODUCTION edge=8.50%  ✅
  5注 f4cold_5bet        PRODUCTION edge=6.61%  ✅

BIG_LOTTO:
  2注 regime_2bet      PRODUCTION edge=3.64%  ✅
  3注 ts3_regime_3bet  PRODUCTION edge=3.51%  ✅
  5注 p1_dev_sum5bet   PRODUCTION edge=4.04%  ✅

POWER_LOTTO:
  3注 fourier_rhythm_3bet  PRODUCTION edge=3.16%  special=3  ✅
  4注 pp3_freqort_4bet     PRODUCTION edge=3.40%  special=3  ✅
  5注 orthogonal_5bet      WATCH      edge=2.76%  special=3  ✅
```

Note: `orthogonal_5bet` shows WATCH (edge_300p=0.0276 < 0.03 threshold). This is correct.

---

## 6. No Changes To

- `lottery_api/engine/strategy_coordinator.py` — untouched
- `lottery_api/models/special_predictor.py` — untouched
- `lottery_api/data/strategy_states_*.json` — read-only
- All existing prediction endpoints — untouched

---

## Status: ✅ COMPLETE
