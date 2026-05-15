# Prediction Tracker Alignment Gap Report
Generated: 2026-03-26

This report audits the current 「預測追蹤」 page before any implementation changes. It focuses on the live code path, the stored tracking data, and where the current UI or backend behavior diverges from the product requirements.

## 1. Current Main Table Behavior

### 1.1 What the page currently shows

The main table on the tracking page is rendered from [`src/ui/PredictionTracker.js`](../src/ui/PredictionTracker.js) and currently shows:

- 開獎時間
- 基於期號
- 比對期號
- 最佳命中
- 狀態
- 研究狀態

It is populated by `loadHistory()` and `_renderHistory()` in the frontend.

Relevant code:

- [`src/ui/PredictionTracker.js#L274`](../src/ui/PredictionTracker.js#L274)
- [`src/ui/PredictionTracker.js#L290`](../src/ui/PredictionTracker.js#L290)
- [`index.html#L1560`](../index.html#L1560)

### 1.2 What the main table is actually based on

The main table is not a historical per-strategy tracker. It is a run-level summary built from:

- `GET /api/tracking/history`
- `engine/prediction_tracker.py:get_history()`

Backend behavior:

- groups by `prediction_runs.id`
- counts `prediction_items`
- computes `resolved_bets`
- computes `best_hit` as `MAX(hit_count)`
- returns `status` as only `RESOLVED` or `PENDING`

Relevant code:

- [`lottery_api/routes/prediction_tracking.py#L222`](../lottery_api/routes/prediction_tracking.py#L222)
- [`lottery_api/engine/prediction_tracker.py#L282`](../lottery_api/engine/prediction_tracker.py#L282)

### 1.3 Concrete current data sample

From the current SQLite database:

- `prediction_runs` total: 57
- `DAILY_539`: 30 runs
- `BIG_LOTTO`: 17 runs
- `POWER_LOTTO`: 10 runs

Snapshot source distribution:

- `DAILY_539`: 26 `RECONSTRUCTED`, 4 `VALID`
- `BIG_LOTTO`: 13 `RECONSTRUCTED`, 4 `VALID`
- `POWER_LOTTO`: 7 `RECONSTRUCTED`, 3 `VALID`

Latest run sample:

- run `#57`
- `DAILY_539`
- `latest_known_draw = 115000075`
- `strategy_name = MULTI_STRATEGY`
- `snapshot_source = RECONSTRUCTED`
- `analyzed = 未研究`
- `prediction_items = 11`
- all items are still `PENDING`

Observed via:

- `sqlite3 lottery_api/data/lottery_v2.db ...`

### 1.4 Mismatch vs requirement

The requirement says the main table should show:

- 彩種
- 期數
- 實際開獎號碼
- 目前各注數最佳策略中的「單注最佳策略」摘要
- 命中數
- 解析狀態

Current behavior diverges because:

- the table does not explicitly show `彩種`
- it does not show the predicted numbers
- it does not show the strategy name for the best single-bet summary
- it uses run-level aggregation rather than a single-bet historical summary
- it only surfaces `RESOLVED` / `PENDING`, not `MISSED` / `RECONSTRUCTED`

---

## 2. Current Detail Panel Behavior

### 2.1 What the detail currently shows

Clicking a history row fetches `GET /api/tracking/run/{run_id}` and renders:

- source badge: `VALID` / `RECONSTRUCTED` / `MANUAL`
- created time
- current draw info
- actual draw numbers
- one block per strategy group
- predicted numbers with hit highlighting
- per-bet hit counts

Relevant code:

- [`src/ui/PredictionTracker.js#L341`](../src/ui/PredictionTracker.js#L341)
- [`src/ui/PredictionTracker.js#L364`](../src/ui/PredictionTracker.js#L364)

### 2.2 Current backend shape for detail

`get_run_detail()` currently returns:

- `bets`: flat item list
- `bets_by_strategy`: grouped by `prediction_items.strategy_name` when available
- `rsm_strategies`: per-bet-count strategy reference loaded from `strategy_states_{lottery}.json`

Relevant code:

- [`lottery_api/engine/prediction_tracker.py#L379`](../lottery_api/engine/prediction_tracker.py#L379)
- [`lottery_api/engine/prediction_tracker.py#L443`](../lottery_api/engine/prediction_tracker.py#L443)
- [`lottery_api/engine/prediction_tracker.py#L463`](../lottery_api/engine/prediction_tracker.py#L463)

### 2.3 Current detail rendering path and fallback

The frontend detail renderer has two paths:

1. If `bets_by_strategy` exists, it renders those grouped items directly.
2. If `bets_by_strategy` is missing, it falls back to a synthetic grouping built from:
   - `detail.bets`
   - `rsm_strategies[num_bets]`
   - `detail.strategy_name`

Relevant code:

- [`src/ui/PredictionTracker.js#L422`](../src/ui/PredictionTracker.js#L422)

This fallback is important because it can make old runs look like they are already mapped to the current best strategy reference, even when the stored run is actually an older coordinator-style snapshot.

### 2.4 Mismatch vs requirement

The requirement says the expanded detail should show the current best strategy for each bet count:

- 1 注最佳策略
- 2 注最佳策略
- 3 注最佳策略
- 4 注 / 5 注 if formally present

Current detail diverges because:

- it renders stored run items, not a normalized per-bet-count historical comparison layer
- old runs can fall back to the live `strategy_states_*.json` labels
- the panel does not explicitly show a status badge per bet-count block as a first-class field
- it does not show `N/A` / `無歷史快照` when a bet-count has no formal strategy or no matching snapshot

---

## 3. Current Statistics Behavior

### 3.1 What the stats section currently does

The stats block on the page calls:

- `GET /api/tracking/performance?valid_only=true|false`

Frontend:

- [`src/ui/PredictionTracker.js#L225`](../src/ui/PredictionTracker.js#L225)
- [`src/ui/PredictionTracker.js#L246`](../src/ui/PredictionTracker.js#L246)

Backend:

- [`lottery_api/engine/prediction_tracker.py#L523`](../lottery_api/engine/prediction_tracker.py#L523)

Current behavior:

- groups by `prediction_runs.strategy_name`
- treats the whole run as one strategy bucket
- computes success if `best_hit >= 3`
- excludes `RECONSTRUCTED` by default when `valid_only=true`

### 3.2 Mismatch vs requirement

The requirement says the tracking page statistics should:

- use best single-bet summary as the primary statistic
- allow viewing each bet-count best strategy
- use only formal valid snapshots
- exclude `RECONSTRUCTED` by default

Current behavior diverges because:

- `MULTI_STRATEGY` runs collapse into a single bucket
- old coordinator-style runs also collapse into a legacy bucket
- the stats do not split by bet count
- the stats do not show the current best single-bet strategy as the primary summary item

The `valid_only=true` exclusion of `RECONSTRUCTED` is already aligned, but the grouping axis is not.

---

## 4. Current Source of "Current Best Strategy per Bet Count"

There are two different strategy-source mechanisms in the codebase.

### 4.1 Tracking detail reference source

`engine/prediction_tracker.py:_get_rsm_strategies()` reads:

- [`lottery_api/data/strategy_states_{LOTTERY}.json`](../lottery_api/data/strategy_states_DAILY_539.json)
- [`lottery_api/data/strategy_states_{LOTTERY}.json`](../lottery_api/data/strategy_states_BIG_LOTTO.json)
- [`lottery_api/data/strategy_states_{LOTTERY}.json`](../lottery_api/data/strategy_states_POWER_LOTTO.json)

It then:

- groups records by `num_bets`
- selects the record with the highest `edge_300p` per bet count
- returns `strategy_name`, `rate_*`, `edge_*`, `trend`, `alert`, `sharpe_300p`, etc.

Relevant code:

- [`lottery_api/engine/prediction_tracker.py#L336`](../lottery_api/engine/prediction_tracker.py#L336)

This is the current source of the per-bet-count strategy reference used by tracking detail.

### 4.2 Next-draw / decision source

The next-draw page and decision summary use a different notion:

- `routes/prediction.py` has `_NEXT_DRAW_CONFIG`
- `routes/decision.py` has `/best-strategy-summary`

Those paths read the same `strategy_states_*.json` files, but the next-draw page is about current recommendation, not history.

Relevant code:

- [`lottery_api/routes/prediction.py#L2085`](../lottery_api/routes/prediction.py#L2085)
- [`lottery_api/routes/decision.py#L55`](../lottery_api/routes/decision.py#L55)

### 4.3 Important distinction

The current tracking page is not deriving its history from the next-draw page. It only reuses the same `strategy_states_*.json` files as a reference overlay.

That means:

- the page does not compute history from current best strategy state
- it overlays current best strategy metadata onto stored run data
- it can therefore mix historical snapshot identity with current strategy reference labels

---

## 5. Historical Snapshot To Current Strategy Mapping

### 5.1 Current mapping rules

Current mapping depends on snapshot format:

- New format:
  - `create_snapshot(... strategy_bets=[...])`
  - stores `prediction_items.strategy_name`
  - `get_run_detail()` groups by item strategy name

- Old format:
  - flat `bets` only
  - `bets_by_strategy = None`
  - frontend falls back to `rsm_strategies` to invent a per-bet-count grouping

Relevant code:

- [`lottery_api/engine/prediction_tracker.py#L443`](../lottery_api/engine/prediction_tracker.py#L443)
- [`src/ui/PredictionTracker.js#L426`](../src/ui/PredictionTracker.js#L426)

### 5.2 Where current historical mapping can drift

Potential drift points:

- old runs use fallback grouping even when there was no formal per-bet strategy snapshot
- detail headers derive from `rsm_strategies` rather than historical snapshot metadata when the snapshot is legacy format
- the tracking page uses `prediction_runs.strategy_name` for performance grouping, which is not the same as per-bet-count best strategy
- the history list does not surface the underlying per-bet strategy mapping at all

### 5.3 Current database evidence of mixed formats

The latest runs show both formats:

- `run #57`: `MULTI_STRATEGY`, `prediction_items` all carry strategy names
- `run #56` and earlier in the latest set: `Coordinator-Direct (7 agents)`, item strategy fields are empty

That confirms the current tracker contains both modern and legacy history, and the UI already has a fallback path to paper over the legacy rows.

---

## 6. Fallback / Mixing / Contamination Risks

### 6.1 Frontend legacy fallback

Risk:

- when `detail.bets_by_strategy` is missing, the frontend synthesizes groups using `rsm_strategies`

Impact:

- historical rows can appear as if they belong to the current best strategy reference
- missing snapshot information can be silently masked

Relevant code:

- [`src/ui/PredictionTracker.js#L426`](../src/ui/PredictionTracker.js#L426)

### 6.2 Run-level strategy aggregation

Risk:

- `get_performance()` groups by `prediction_runs.strategy_name`

Impact:

- all multi-strategy rows are bucketed under `MULTI_STRATEGY`
- old coordinator-style rows are bucketed under their legacy run label
- bet-count-specific success rates are not visible

Relevant code:

- [`lottery_api/engine/prediction_tracker.py#L563`](../lottery_api/engine/prediction_tracker.py#L563)

### 6.3 Current detail does not enforce "no snapshot" behavior

Risk:

- if a bet count is missing in the current strategy states, the existing fallback can still show something

Impact:

- this violates the requirement to show `N/A` and to avoid silent replacement

### 6.4 Unused helper indicates half-wired intent

`_rsm_best_strategy_label()` exists in [`lottery_api/routes/prediction_tracking.py`](../lottery_api/routes/prediction_tracking.py#L30) but is not wired into the page flow.

This is a signal that the per-bet strategy reference logic exists conceptually, but the actual tracking UI is still relying on older render behavior.

---

## 7. Alignment Summary

### Main table

Current:

- run-level history summary
- RESOLVED / PENDING only
- no explicit per-row strategy name or predicted numbers

Required:

- historical per-period tracking view
- single-bet best strategy summary in the main row
- explicit resolved status family including `PENDING / RESOLVED / MISSED / RECONSTRUCTED`

### Detail panel

Current:

- legacy-compatible grouped bet rendering
- uses current `strategy_states_*.json` as overlay
- can fallback into synthetic grouping

Required:

- current best 1 / 2 / 3 / 4 / 5 bet strategy comparison
- explicit `N/A` when a bet-count has no formal strategy
- explicit `無歷史快照` when no matching snapshot exists

### Statistics

Current:

- grouped by run.strategy_name
- `VALID` filter already default

Required:

- primary summary by best single-bet strategy
- expandable bet-count comparison
- formal snapshots only, with `RECONSTRUCTED` excluded by default

---

## 8. Conclusion

The tracking page is currently built around a run-level historical summary with a legacy-compatible detail renderer. It partially reuses the live RSM strategy-state files, but it does so as an overlay rather than as the primary historical comparison model.

That is the core gap:

- the page is mixing historical run storage with current strategy-state references
- the main table is too coarse
- the detail view still has fallback pollution
- the statistics axis is run label, not current best strategy by bet count

This is why the page does not yet satisfy the requested two-layer model:

1. Main table = best single-bet historical summary
2. Detail = per-bet-count current best strategy historical comparison

