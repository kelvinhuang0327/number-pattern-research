# P4C3 Supported Prediction Apply Path Report

## 1. 本輪目標
建立一條受控、可審計的 production prediction apply path，讓 `quick_predict` 的 dry-run JSON 可以在 explicit approval 後，轉成 `prediction_runs` / `prediction_items`。

## 2. Why P4C2 was blocked
P4C2 已確認支援彩種的 preview 可用，但 repo 內沒有安全、明確、可審計的 production apply path，因此無法直接把 preview 轉為正式 prediction rows。

## 3. Supported Scope
本輪只支援：
- `BIG_LOTTO`
- `POWER_LOTTO`

## 4. DAILY_539 exclusion
`DAILY_539` 明確排除在 production apply scope 外。  
原因是它在 broader dry-run matrix 中已知會碰到現有 predictor stack 的 `torch` dependency blocker，且本輪 approval gate 只針對支援彩種。

## 5. Schema / write-path design
新增的 controlled apply path 放在：
- [`scripts/p4c3_supported_prediction_apply.py`](</Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/scripts/p4c3_supported_prediction_apply.py>)

設計重點：
- 預設是 dry-run / no-write
- `--apply` 才會寫入 DB
- 需要 `--controlled-apply-id P4C3_20260516`
- 只接受 `BIG_LOTTO` / `POWER_LOTTO`
- 以 quick_predict dry-run JSON artifact 為來源
- 來源驗證包含：
  - `dry_run=true`
  - `db_written=false`
  - `predictions` 非空
  - 只能有一個 preview summary / 檔案
  - lottery type 與請求 scope 一致
- apply path 會先插入 `prediction_runs`，再插入對應 `prediction_items`
- 沒有 replay row 寫入
- 沒有 strategy logic 變更
- 沒有 API/UI/backend 變更
- idempotency 依賴 `controlled_apply_id` + payload fingerprint，透過 `notes` / `review_json` 做可重建檢查

## 6. Dry-run apply path result
dry-run 使用支援彩種的 P4-C preview artifact 進行驗證：
- `outputs/replay/p4c_quick_predict_dryrun_big_lotto_20260516.json`
- `outputs/replay/p4c_quick_predict_dryrun_power_lotto_20260516.json`

結果：
- `final_classification = P4C3_SUPPORTED_PREDICTION_APPLY_PATH_READY`
- `db_written = false`
- `prediction_runs_inserted = false`
- `prediction_items_inserted = false`
- `replay_rows_inserted = false`
- `supported_lotteries = ["BIG_LOTTO", "POWER_LOTTO"]`
- `excluded_lotteries = ["DAILY_539"]`
- `planned_prediction_runs_count = 2`
- `planned_prediction_items_count = 6`

## 7. DB no-write verification
dry-run 前後 DB 狀態一致：
- `prediction_items = 1095`
- `prediction_runs = 175`
- `replay_rows = 975`
- DB SHA256 unchanged:
  - `27f8f060dfb2641f29e4ad4fa62deef413ab69131f1548dac83a2e721f536acf`

## 8. Tests / validation
通過的驗證：
- `scripts/p4c3_supported_prediction_apply.py` `py_compile`
- `tests/test_p4c3_supported_prediction_apply_contract.py` `pytest`
- `tests/test_quick_predict_dryrun_contract.py` `pytest`
- replay governance suite:
  - `tests/test_replay_strategy_lifecycle_registry.py`
  - `tests/test_replay_lifecycle_drift_guard.py`
  - `tests/test_replay_truth_level_contract.py`
  - `tests/test_replay_api_contract.py`
- pre-apply drift guard PASS

## 9. Safety confirmation
- No DB writes
- No replay row inserts
- No `prediction_items` mutation outside future controlled apply
- No `prediction_runs` mutation outside future controlled apply
- No strategy logic changes
- No API/UI/backend changes

## 10. Remaining risks
- 真正的 apply mode 尚未執行，仍需後續 explicit approval gate
- `DAILY_539` 仍不在支援彩種 production scope
- apply path idempotency 依賴 `notes` / `review_json` 裡的 fingerprint，未來若 schema 變動，需要同步維護查詢邏輯

## 11. Next step recommendation
進入 `P4C4` merge gate，確認此 controlled apply path 與測試一起進 main；之後再進 `P4C5` operator approval gate，才會執行真正的 production prediction apply。
