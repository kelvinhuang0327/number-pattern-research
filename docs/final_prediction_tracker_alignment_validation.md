# Final Prediction Tracker Alignment Validation
Generated: 2026-03-26

This document records the final alignment of the 「預測追蹤」 page after the Phase 1 audit and the page/data-shape update.

## 1. Changed Files

- [`/Users/kelvin/Kelvin-WorkSpace/LotteryNew/docs/prediction_tracker_alignment_gap_report.md`](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/docs/prediction_tracker_alignment_gap_report.md)
- [`/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/engine/prediction_tracker.py`](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/engine/prediction_tracker.py)
- [`/Users/kelvin/Kelvin-WorkSpace/LotteryNew/src/ui/PredictionTracker.js`](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/src/ui/PredictionTracker.js)
- [`/Users/kelvin/Kelvin-WorkSpace/LotteryNew/index.html`](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/index.html)

## 2. Main Table Data Source

The main history table now comes from:

- `GET /api/tracking/history?lottery_type=...`
- [`lottery_api/engine/prediction_tracker.py:get_history()`](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/engine/prediction_tracker.py)

Data rules:

- The table is still history-based, one row per run.
- The row summary is anchored on the **current best single-bet strategy** for that lottery type.
- The current best single-bet strategy is loaded from `lottery_api/data/strategy_states_{LOTTERY}.json`.
- If the lottery type has no formal single-bet strategy, the row shows `N/A`.
- If there is no matching historical snapshot for the current best single-bet strategy, the row shows `無歷史快照`.
- No silent fallback is used to replace missing snapshots.

Main table columns:

- 彩種
- 期數
- 單注最佳策略
- 預測號碼
- 實際開獎號碼
- 命中數
- 解析狀態

## 3. Detail Data Source

The expanded detail panel now comes from:

- `GET /api/tracking/run/{run_id}`
- [`lottery_api/engine/prediction_tracker.py:get_run_detail()`](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/engine/prediction_tracker.py)

Data rules:

- Detail is normalized into the current best strategy slots for `1注` through `5注`.
- The current best strategy per bet count is selected by the highest `edge_300p` within the current `strategy_states_{LOTTERY}.json`.
- Each slot is rendered in order `1 -> 5`.
- Missing formal strategy slots render as `N/A`.
- Formal strategy slots without a matching historical snapshot render as `無歷史快照`.
- Historical comparison uses stored prediction snapshot rows only.
- `RECONSTRUCTED` is preserved as a non-formal source state and is not mixed into formal performance.

Each slot shows:

- 注數
- 策略名稱
- 策略狀態 badge
- 解析狀態 badge
- 預測號碼
- 實際開獎號碼
- 命中數
- 命中號碼高亮

## 4. Statistic Source

The statistics block now comes from:

- `GET /api/tracking/performance?lottery_type=...&valid_only=...`
- [`lottery_api/engine/prediction_tracker.py:get_performance()`](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/engine/prediction_tracker.py)

Data rules:

- The aggregation axis is the **current best strategy per bet count**, not `prediction_runs.strategy_name`.
- `valid_only=true` remains the default and excludes `RECONSTRUCTED`.
- If a bet-count slot has no formal strategy, the row displays `N/A`.
- If a formal strategy has no historical matches, the row displays `無歷史快照`.

The summary card above the table uses the current best single-bet strategy as the primary summary item.

## 5. How "Current Best Strategy" Is Determined

Current best strategy is determined by:

1. Reading `lottery_api/data/strategy_states_{LOTTERY}.json`
2. Grouping strategies by `num_bets`
3. Selecting the record with the highest `edge_300p` in that bet-count group
4. Deriving the strategy status from the live RSM fields

This is a read-only reference step. It does not change the prediction engine or regenerate historical predictions.

## 6. UI Mock

### Main Table

| 彩種 | 期數 | 單注最佳策略 | 預測號碼 | 實際開獎號碼 | 命中數 | 解析狀態 |
|------|------|--------------|----------|--------------|--------|----------|
| 今彩539 | 115000076 | `acb_1bet` | 3,4,16,26,35 | 1,7,10,18,24 | 1 中 | `RESOLVED` |
| 大樂透 | 115000039 | `N/A` | `N/A` | `—` | `—` | `PENDING` |
| 威力彩 | 115000025 | `N/A` | `N/A` | `—` | `—` | `RECONSTRUCTED` |

### Detail Panel

| 1注 | 2注 | 3注 | 4注 | 5注 |
|-----|-----|-----|-----|-----|
| Strategy badge + snapshot state + predicted numbers + actual numbers + matched numbers | same | same | `N/A` if no formal strategy | same |

Rules:

- No fallback to coordinator-style mixed results.
- No mixing with Decision V3 confidence/exposure UI.
- No "all historical strategies" dump.

## 7. Validation Performed

Syntax validation completed successfully:

- `node --check src/ui/PredictionTracker.js`
- `PYTHONPYCACHEPREFIX=/tmp python3 -m py_compile lottery_api/engine/prediction_tracker.py lottery_api/routes/prediction_tracking.py lottery_api/routes/prediction.py lottery_api/routes/decision.py`

Notes:

- The repository contains other unrelated local modifications, but this alignment work is limited to the files listed above.
- The prediction engine itself was not changed.

