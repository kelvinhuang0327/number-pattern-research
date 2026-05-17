# P4C6 Post-Apply Monitoring Report

## 1. 本輪目標
整理 P4C5 supported production prediction apply 的結果，確認 DB 變更範圍，並做 post-apply monitoring。

## 2. P4C5 apply summary
P4C5 已成功寫入支援彩種的正式 prediction rows：
- `BIG_LOTTO`
- `POWER_LOTTO`

排除項目：
- `DAILY_539`

## 3. Inserted prediction_runs
本次新增 2 筆 `prediction_runs`：
- `id=176` → `BIG_LOTTO`
- `id=177` → `POWER_LOTTO`

## 4. Inserted prediction_items
本次新增 6 筆 `prediction_items`：
- `1096, 1097, 1098` → `BIG_LOTTO`
- `1099, 1100, 1101` → `POWER_LOTTO`

## 5. DB count changes
apply 前後差異：
- `prediction_runs`: `175 -> 177`
- `prediction_items`: `1095 -> 1101`
- `replay_rows`: `975 -> 975`

## 6. Idempotency check
重新執行 controlled apply preview 時：
- `db_written = false`
- `planned_prediction_runs_count = 2`
- `planned_prediction_items_count = 6`
- `duplicate_rows_count = 4`

這表示 preview 已能找到既有的 apply footprint，且不會再產生新的 DB 寫入。

## 7. Drift guard / tests
全部通過：
- pre-apply drift guard: PASS
- post-apply drift guard: PASS
- post-monitoring drift guard: PASS
- `tests/test_p4c3_supported_prediction_apply_contract.py`: PASS
- `tests/test_quick_predict_dryrun_contract.py`: PASS
- replay governance suite: PASS

## 8. DAILY_539 exclusion
`DAILY_539` 未參與本次 apply，也沒有新增任何 production row。

## 9. Safety confirmation
- No replay rows inserted
- No existing `prediction_items` updated
- No existing `prediction_runs` updated
- No strategy logic changes
- No API/UI/backend changes

## 10. Remaining risks
- apply fingerprint 仍依賴 `notes` / `review_json` 內的資訊做 idempotency 檢查
- `DAILY_539` 仍在支援彩種 production scope 之外

## 11. Next step recommendation
進入 P4C6 merge gate，將 apply 結果與監控 summary 封存後，轉入後續針對新批次的日常追蹤。
