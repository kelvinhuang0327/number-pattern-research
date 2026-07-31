# P246H — Advanced Learning Scheduler Trace

**Task ID:** P246H · **Date:** 2026-06-05 · **Type:** Scheduler trace + targeted code update.
**No DB write performed.**
**Final Classification:** `P246H_ADVANCED_LEARNING_SCHEDULER_TRACE_COMPLETE`

---

## 1. Executive Summary

`advanced_learning.py` calls `scheduler.get_data(lottery_type)`. The scheduler is `LotteryOptimizationScheduler` in `lottery_api/utils/scheduler.py`. Its in-memory cache (`data_by_type`) was populated with raw unfiltered BIG_LOTTO rows (22,238) via `optimization.py:90 → db_manager.get_all_draws()`.

**Fix:** `scheduler.get_data('BIG_LOTTO')` now applies canonical filter at return time — ADD_ON_PRIZE_EXCLUDED, DATE_FORMAT_ALIEN, SMALL_POOL_ALIEN excluded. Non-destructive: raw cache preserved.

---

## 2. P246G Baseline

Already canonicalized:
- `quick_predict.py` (P246E), `rsm_bootstrap.py` (P246F), `core_satellite.py` (P246F)
- `drift_detector._load_draws()` (P246G), `backtest_framework.BacktestEngine.backtest()` (P246G)

---

## 3. Scheduler Call Chain

```
advanced_learning.py:21
  → scheduler.get_data('BIG_LOTTO')

utils/scheduler.py LotteryOptimizationScheduler.get_data()
  → self.data_by_type.get('BIG_LOTTO', [])
  [data populated via update_data()]

scheduler.update_data() called by:
  → optimization.py:90  db_manager.get_all_draws()  ← ALL 22,238 BIG_LOTTO rows
  → optimization.py:176 user-submitted sync-data
  → data.py:65          user-submitted upload
  → load_data_from_disk() JSON persistence
```

**Root cause:** `optimization.py:90` calls `db_manager.get_all_draws()` without lottery_type filter, pulling all 22,238 BIG_LOTTO rows into the scheduler cache.

---

## 4. Fix Applied: `scheduler.get_data()`

```python
def get_data(self, lottery_type: str) -> list:
    data = self.data_by_type.get(lottery_type, [])
    if lottery_type == 'BIG_LOTTO':
        canonical = []
        for d in data:
            draw_id = str(d.get('draw', ''))
            if '-' in draw_id:          # ADD_ON_PRIZE_EXCLUDED
                continue
            if len(draw_id) == 8 and draw_id.startswith('20'):  # DATE_FORMAT_ALIEN
                continue
            numbers = d.get('numbers', [])
            if numbers and max(numbers) <= 25:  # SMALL_POOL_ALIEN
                continue
            canonical.append(d)
        return canonical
    return data
```

- **Non-destructive:** `data_by_type['BIG_LOTTO']` raw cache is unchanged
- **All callers benefit:** `advanced_learning.py`, `optimization.py`, and any future caller of `scheduler.get_data('BIG_LOTTO')` now receives canonical draws
- **Non-BIG_LOTTO:** unchanged

---

## 5. Remaining Risks

| Issue | Risk | Action |
|---|---|---|
| `optimization.py:90` still calls `get_all_draws()` unfiltered | Low — mitigated by `get_data()` filter | Lower-priority cleanup |
| 60+ archived scripts | Non-production | Deferred |
| Phase 2/3 Type D DB operations | Pending | Separate authorization required |

---

## 6. Governance

| Rule | Status |
|---|---|
| No DB write | ✅ confirmed |
| No row deletion | ✅ confirmed |
| Raw add-on rows preserved in cache | ✅ data_by_type unchanged |
| Raw get_all_draws() unchanged | ✅ confirmed |
| No registry mutation | ✅ confirmed |
| BIG_LOTTO gate | ✅ GATE_RED_PENDING_CANONICAL_SEPARATION |

**ADD_ON_PRIZE_EXCLUDED records are valid lottery-related records. They are preserved in the raw DB and raw scheduler cache. Research/learning callers now receive only canonical draws via `scheduler.get_data('BIG_LOTTO')`.**

**Final Classification:** `P246H_ADVANCED_LEARNING_SCHEDULER_TRACE_COMPLETE`
