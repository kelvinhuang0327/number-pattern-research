# P6B Scheduled Monitor Design

## 1. 本輪目標
建立支援彩種的 next-draw watcher 排程設計，並以只讀方式重新跑一次 watcher，確認目前仍處於等待官方開獎的狀態。

## 2. Current Post-P6A Baseline
P6A compatibility hotfix 已 merge，watcher 在目前 task venv 可穩定執行。

基線狀態：
- `prediction_runs = 177`
- `prediction_items = 1101`
- `replay_rows = 975`
- `BIG_LOTTO` run `176`, items `1096–1098`
- `POWER_LOTTO` run `177`, items `1099–1101`
- `DAILY_539` 仍排除在 supported production scope 外

## 3. Watched Targets
本輪只監控兩個目標：
- `BIG_LOTTO 115000053`
- `POWER_LOTTO 115000036`

對應支援 prediction lifecycle：
- `BIG_LOTTO` run `176`, pending items `1096–1098`
- `POWER_LOTTO` run `177`, pending items `1099–1101`

## 4. Watcher Rerun Result
只讀 rerun 結果：
- `P6_NEXT_DRAW_WATCHER_WAITING_FOR_OFFICIAL_DRAWS`
- `db_written = false`
- `BIG_LOTTO 115000053 exists = false`
- `POWER_LOTTO 115000036 exists = false`

## 5. Proposed Schedule Cadence
建議以固定 cadence 定期重跑 watcher：
- 優先：每 6 小時一次
- 較保守：每 12 小時一次

這個 cadence 只做 read-only check，不執行任何 import 或 replay。

## 6. Trigger Conditions
以下任一條件成立時，watcher 可視為需要更新狀態：
- `draws` 仍缺少 `BIG_LOTTO 115000053`
- `draws` 仍缺少 `POWER_LOTTO 115000036`
- target draw 資料被新匯入後，readiness 狀態需重新評估

## 7. Stop Conditions
watcher 應停止自動等待，改為手動介入流程：
- 兩個 target draw 都已存在於 `draws`
- 其中任一 target draw 已存在，分類改為 `IMPORT_READY`

## 8. Import Gate Policy
`IMPORT_READY` 只代表可以進入下一步人工 gate，不能自動寫入：
- 不自動 import draw
- 不自動 replay backfill
- 不自動 update `prediction_items`
- 不自動 update `prediction_runs`

下一步只能是 controlled draw import dry-run。

## 9. Safety Constraints
- read-only DB access only
- no draw imports
- no replay rows
- no prediction item/run mutation
- no strategy logic changes
- no API/UI/backend changes
- no scheduler or workflow changes in this PR

## 10. Next Step Recommendation
目前 watcher 仍然等待官方開獎發布，因此下一步是持續 scheduled monitor rerun。
等 `115000053` 與 `115000036` 出現在 `draws` 後，再切換到 controlled draw import dry-run gate。
