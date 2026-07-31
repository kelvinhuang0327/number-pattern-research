# P6 Next-Draw Watcher Report

## 1. 本輪目標
建立支援彩種的只讀 next-draw watcher，持續監控下列待確認開獎：
- `BIG_LOTTO` 需要 `115000053`
- `POWER_LOTTO` 需要 `115000036`

本輪只做 watcher / report / artifact，不進行 draw import、replay backfill 或 prediction 更新。

## 2. P5 Post-Merge Baseline
P5 已完成並 merge，supported production predictions 已進入等待開獎狀態。

Baseline 狀態：
- `prediction_runs = 177`
- `prediction_items = 1101`
- `replay_rows = 975`
- `BIG_LOTTO` run `176`, items `1096–1098`
- `POWER_LOTTO` run `177`, items `1099–1101`
- `DAILY_539` 仍排除在 supported production scope 外

## 3. Watched Prediction Runs / Items
Watcher 針對下列 production prediction lifecycle 做讀取驗證：
- `BIG_LOTTO`
  - support run: `176`
  - item ids: `1096, 1097, 1098`
  - pending item count: `3`
- `POWER_LOTTO`
  - support run: `177`
  - item ids: `1099, 1100, 1101`
  - pending item count: `3`

## 4. Target Draw Readiness
Watcher 結果顯示兩個目標開獎仍未進入 `draws`：
- `BIG_LOTTO`
  - latest draw in DB: `115000052`
  - next needed: `115000053`
  - exists in draws: `false`
  - readiness: `WAITING_FOR_OFFICIAL_DRAW_PUBLICATION`
- `POWER_LOTTO`
  - latest draw in DB: `115000035`
  - next needed: `115000036`
  - exists in draws: `false`
  - readiness: `WAITING_FOR_OFFICIAL_DRAW_PUBLICATION`

## 5. Official Source Preview Result
This watcher does not import draws and does not attempt network ingestion.
No official draw preview was fetched.

## 6. Current Classification
`P6_NEXT_DRAW_WATCHER_WAITING_FOR_OFFICIAL_DRAWS`

## 7. Safety Confirmation
- No DB writes
- No draw imports
- No replay rows inserted
- No `prediction_items` updates
- No `prediction_runs` updates
- No strategy logic changes
- No API/UI/backend changes

## 8. Remaining Risks
The next official draws for both supported lotteries are still absent from `draws`, so lifecycle progression is blocked on external publication timing.

## 9. Next Step Recommendation
Continue scheduled monitoring until the official draws appear.
Once `115000053` and `115000036` are present, move to controlled draw import dry-run and then replay resolution dry-run.
