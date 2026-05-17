# P4C5 Supported Prediction Apply Report

## 1. 本輪目標
在 explicit approval 後，對支援彩種建立正式 production prediction rows：
- `BIG_LOTTO`
- `POWER_LOTTO`

## 2. Authorization text
已收到明確授權：
`YES apply supported predictions`

## 3. Source dry-run artifacts
本輪 apply 來源為兩個已驗證 dry-run artifact：
- [`outputs/replay/p4c_quick_predict_dryrun_big_lotto_20260516.json`](</Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/outputs/replay/p4c_quick_predict_dryrun_big_lotto_20260516.json>)
- [`outputs/replay/p4c_quick_predict_dryrun_power_lotto_20260516.json`](</Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/outputs/replay/p4c_quick_predict_dryrun_power_lotto_20260516.json>)

## 4. Applied prediction_runs
正式寫入 2 筆 `prediction_runs`：
- `BIG_LOTTO` → run `176`
- `POWER_LOTTO` → run `177`

兩筆都以 `controlled_apply_id=P4C3_20260516` 和來源 artifact fingerprint 做可審計標記。

## 5. Applied prediction_items
正式寫入 6 筆 `prediction_items`：
- `BIG_LOTTO` → item `1096` 到 `1098`
- `POWER_LOTTO` → item `1099` 到 `1101`

## 6. DAILY_539 exclusion confirmation
`DAILY_539` 完全不在本次 apply scope 內，沒有被寫入任何 production row。

## 7. DB count changes
apply 前：
- `prediction_items = 1095`
- `prediction_runs = 175`
- `replay_rows = 975`

apply 後：
- `prediction_items = 1101`
- `prediction_runs = 177`
- `replay_rows = 975`

因此本次淨變化為：
- `prediction_runs +2`
- `prediction_items +6`
- `replay_rows +0`

## 8. Drift guard / tests
結果全部通過：
- pre-apply drift guard: PASS
- post-apply drift guard: PASS
- `tests/test_p4c3_supported_prediction_apply_contract.py`: PASS
- `tests/test_quick_predict_dryrun_contract.py`: PASS
- replay governance suite: PASS

## 9. Safety confirmation
- No replay rows inserted
- No existing `prediction_items` updated
- No existing `prediction_runs` updated
- No strategy logic changes
- No API/UI/backend changes

## 10. Remaining risks
- 後續若要重跑 apply，需依賴 idempotency 鎖定與既有 fingerprint 查詢邏輯
- `DAILY_539` 仍排除在支援彩種 production scope 之外

## 11. Next step recommendation
進入 production prediction post-apply monitoring，觀察 `BIG_LOTTO` 與 `POWER_LOTTO` 的後續 lifecycle 與任何 downstream replay / review 工作流影響。
