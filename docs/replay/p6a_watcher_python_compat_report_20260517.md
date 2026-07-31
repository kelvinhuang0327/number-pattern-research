# P6A Watcher Python Compatibility Report

## 1. 本輪目標
將 P6 next-draw watcher 的時間戳實作修正為目前 task venv 可穩定執行的版本，避免 `datetime.UTC` 相容性問題。

## 2. Why compatibility fix was needed
P6 watcher 在 post-merge 重新執行時，當前 venv 的 Python 版本不支援 `datetime.UTC`，會在產生 JSON artifact 前拋出屬性錯誤。

## 3. Exact code change
僅調整一行：
- `datetime.UTC` → `datetime.timezone.utc`

其餘 watcher semantics 保持不變。

## 4. Watcher rerun result
Watcher 以 read-only 模式重新執行成功，並輸出：
- `outputs/replay/p6a_watcher_compat_verify_20260517.json`

分類結果：
- `P6_NEXT_DRAW_WATCHER_WAITING_FOR_OFFICIAL_DRAWS`

## 5. Draw readiness
兩個目標開獎仍未出現在 `draws`：
- `BIG_LOTTO 115000053`: `exists=false`
- `POWER_LOTTO 115000036`: `exists=false`

## 6. Drift guard / tests
PASS。
- `scripts/replay_lifecycle_drift_guard.py --strict`: PASS
- `tests/test_p4c3_supported_prediction_apply_contract.py`: 6 passed
- `tests/test_quick_predict_dryrun_contract.py`: 2 passed
- replay governance suite: 109 passed

## 7. Safety confirmation
- No DB writes
- No draw imports
- No replay rows inserted
- No `prediction_items` updates
- No `prediction_runs` updates
- No strategy logic changes
- No API/UI/backend changes

## 8. Next step recommendation
繼續等待官方開獎發布；等 `115000053` 和 `115000036` 出現在 `draws` 後，再進 controlled draw import dry-run。
