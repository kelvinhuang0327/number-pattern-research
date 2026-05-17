# P5 Next Draw Monitoring Report

## 1. 本輪目標
針對 P4C 已完成的支援彩種 production prediction rows，建立下一期開獎監控與 prediction lifecycle readiness。

支援範圍：
- `BIG_LOTTO` run `176`, items `1096–1098`
- `POWER_LOTTO` run `177`, items `1099–1101`

## 2. P4C supported production apply closure
P4C supported production prediction apply 已完成並 merge，且本輪只做 read-only monitoring。

## 3. Current DB counts
目前 DB counts：
- `prediction_runs = 177`
- `prediction_items = 1101`
- `replay_rows = 975`

## 4. New prediction_runs
支援彩種的新 prediction runs：
- `176` → `BIG_LOTTO`
- `177` → `POWER_LOTTO`

兩筆皆維持 `PENDING` 對應 lifecycle，尚未進入 replay/backfill。

## 5. New prediction_items
支援彩種的新 prediction items：
- `1096, 1097, 1098` → `BIG_LOTTO`
- `1099, 1100, 1101` → `POWER_LOTTO`

所有新 items 目前皆為 `PENDING`。

## 6. Current draw readiness
DB 內最新 draw 與下一個需要的 draw：

### BIG_LOTTO
- DB 最新 draw: `115000052`
- prediction run latest known draw: `115000052`
- 下一個需要的 draw: `115000053`
- `draws` table 是否已存在: `false`

### POWER_LOTTO
- DB 最新 draw: `115000035`
- prediction run latest known draw: `115000035`
- 下一個需要的 draw: `115000036`
- `draws` table 是否已存在: `false`

## 7. Pending lifecycle state
兩個支援彩種目前都處於等待官方開獎發布的狀態：
- `BIG_LOTTO` → `WAITING_FOR_OFFICIAL_DRAW_PUBLICATION`
- `POWER_LOTTO` → `WAITING_FOR_OFFICIAL_DRAW_PUBLICATION`

Pending prediction counts：
- `BIG_LOTTO`: `3`
- `POWER_LOTTO`: `3`

## 8. DAILY_539 exclusion note
`DAILY_539` 仍然排除在支援 production scope 外，本輪不做任何 draw import 或 prediction lifecycle 動作。

## 9. Safety confirmation
- No DB writes
- No draw imports
- No replay backfill
- No `prediction_items` updates
- No `prediction_runs` updates
- No strategy logic changes
- No API/UI/backend changes

## 10. Next step recommendation
等待官方開獎資料發布，然後進入後續的 `post_draw_pipeline` / lifecycle follow-up。  
如果目標 draw 一旦出現在 `draws` table，再進行 read-only monitoring 或後續受控流程。
