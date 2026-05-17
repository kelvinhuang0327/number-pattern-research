# P4B1 Quick Predict Dry-run Interface Report - 20260516

## 1. 本輪目標

為 `tools/quick_predict.py` 新增正式 dry-run / no-write 介面，並提供 JSON output，讓 quick_predict 能安全進入可驗證、可自動化的預覽模式。

## 2. Why quick_predict was previously blocked

此前 `quick_predict.py` 雖然看起來是 print-only/read-only，但沒有正式的 `--dry-run` / `--json-out` 合約，因此安全 gate 只能把它視為「未證明可無寫入」。

## 3. CLI changes

新增：

- `--dry-run`
- `--json-out <path>`
- `--lottery <BIG_LOTTO|POWER_LOTTO|DAILY_539|ALL>`
- `--bets <n>`

保留原本的 positional 用法，維持 backward compatibility。

## 4. Dry-run contract

Dry-run JSON 內容包含：

- `generated_at`
- `final_classification = P4B_QUICK_PREDICT_DRYRUN_READY`
- `dry_run = true`
- `db_written = false`
- `prediction_items_inserted = false`
- `prediction_runs_inserted = false`
- `replay_rows_inserted = false`
- `predictions`
- `warnings`

Dry-run path uses read-only SQLite access for historical draw loading.

## 5. Dry-run result summary

Executed command:

- `tools/quick_predict.py --dry-run --json-out outputs/replay/p4b_quick_predict_dryrun_20260516.json --lottery BIG_LOTTO --bets 2`

Result:

- classification: `P4B_QUICK_PREDICT_DRYRUN_READY`
- output written: `outputs/replay/p4b_quick_predict_dryrun_20260516.json`
- preview generated successfully for `BIG_LOTTO` 2 bets

## 6. DB no-write verification

Read-only verification after dry-run:

- `prediction_items = 1095`
- `prediction_runs = 175`
- `replay_rows = 975`

The DB counts remained stable during the dry-run run, and the DB file hash stayed unchanged in the contract test.

## 7. Tests / validation

Passed:

- `python -m py_compile tools/quick_predict.py tests/test_quick_predict_dryrun_contract.py`
- `pytest tests/test_quick_predict_dryrun_contract.py -q --tb=short`
- `pytest tests/test_replay_strategy_lifecycle_registry.py tests/test_replay_lifecycle_drift_guard.py tests/test_replay_truth_level_contract.py tests/test_replay_api_contract.py -q --tb=short`
- `scripts/replay_lifecycle_drift_guard.py --strict --json-out outputs/replay/p4b1_pre_quick_predict_guard_20260516.json`

## 8. Safety confirmation

- No DB writes
- No `prediction_items` inserts
- No `prediction_runs` inserts
- No replay inserts
- No strategy logic changes
- No API/UI/backend changes

## 9. Remaining risks

- `DAILY_539` dry-run behavior was not the focus of this smoke run, although the CLI now supports it.
- The script still has a legacy print-first shape; future refactors should preserve the dry-run contract explicitly.

## 10. Next step recommendation

`P4B-2 merge gate + post-merge quick_predict dry-run`

