# P1 Replay Lifecycle Aligned Fixture + Browser E2E Enablement

## 1. 本輪目標

建立 registry-aligned synthetic fixture，讓 replay lifecycle drift guard 在 aligned fixture 上回報 `PASS`，同時保留 mismatch fixture 的 `BLOCKED` 覆蓋，並補強 browser E2E 的 Playwright / browser tooling 檢查與 skip policy。此輪只處理 fixture / tests / skip policy / validation report，不碰 production DB、不做 strategy mining、不做 replay generation、不做 edge discovery。

## 2. 已完成事項

- 新增 deterministic registry-aligned synthetic fixture 產生模式，仍維持 `synthetic_only=1`。
- 保留 mismatch fixture 以覆蓋 drift guard 的 `BLOCKED` 負向路徑。
- drift guard positive path 已驗證：aligned fixture 會回報 `PASS`，且 payload 含 `traceable_strategy_ids` 與 `replay_rows_by_lifecycle`。
- browser E2E 已補強 skip policy：當 Playwright 或 browser tooling 無法使用時，會明確 skip，不會假稱 `PASS`。
- 保持 read-only drift guard，不改 registry semantics、不改 active strategy state。

## 3. 修改或產出的檔案

本輪修改：

- `scripts/build_replay_test_fixture.py`
- `tests/test_replay_lifecycle_browser_e2e.py`
- `tests/test_replay_lifecycle_aligned_fixture.py`

本輪產出：

- `outputs/replay/p1_replay_lifecycle_aligned_fixture_browser_e2e_20260509.md`

保留既有驗證依據：

- `scripts/check_replay_lifecycle_drift.py`
- `scripts/validate_replay_test_fixture.py`
- `tests/test_replay_lifecycle_drift_guard.py`

## 4. 驗證結果 / 測試結果

已執行的命令與結果如下：

- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/build_replay_test_fixture.py --output /tmp/lottery_replay_test_fixture.db`
  - `mode=mismatch`
  - `synthetic_only=1`
  - `strategy_replay_runs=4`
  - `strategy_prediction_replays=3`
- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/validate_replay_test_fixture.py --db /tmp/lottery_replay_test_fixture.db`
  - `integrity=PASS`
- `LOTTERY_TEST_DB_PATH=/tmp/lottery_replay_test_fixture.db /Library/Developer/CommandLineTools/usr/bin/python3 scripts/check_replay_lifecycle_drift.py`
  - `status=BLOCKED`
  - unknown strategy IDs: `synthetic_big_A`, `synthetic_power_A`, `synthetic_539_A`
- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/build_replay_test_fixture.py --fixture-mode aligned --output /tmp/lottery_replay_lifecycle_aligned_fixture.db`
  - `mode=aligned`
  - `synthetic_only=1`
  - `strategy_replay_runs=4`
  - `strategy_prediction_replays=3`
- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/validate_replay_test_fixture.py --db /tmp/lottery_replay_lifecycle_aligned_fixture.db`
  - `integrity=PASS`
- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/check_replay_lifecycle_drift.py --db-path /tmp/lottery_replay_lifecycle_aligned_fixture.db`
  - `status=PASS`
  - `traceable_strategy_ids=["biglotto_triple_strike", "daily539_f4cold", "power_precision_3bet"]`
  - `replay_rows_by_lifecycle={"ONLINE": 3}`
- ` /Library/Developer/CommandLineTools/usr/bin/python3 -m pytest tests/test_replay_lifecycle_aligned_fixture.py tests/test_replay_lifecycle_drift_guard.py tests/test_replay_lifecycle_browser_e2e.py -q`
  - `2 passed, 4 skipped`
  - browser E2E skipped because Playwright/browser tooling is unavailable in this workspace
- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_default_validation.py`
  - `57 passed, 32 skipped`

## 5. 目前結論

Aligned fixture 與 mismatch fixture 兩條路徑都已證實：aligned fixture 會讓 drift guard 正常 `PASS`，mismatch fixture 仍然會正確 `BLOCKED`。這表示 drift guard 的正向 / 負向行為都有覆蓋，且 browser E2E 的 skip policy 在工具鏈不可用時有正確收斂。

## 6. 尚未完成事項

- live browser E2E with actual Playwright/browser tooling。
- 更完整的 lifecycle DB migration / audit trail。
- richer / larger aligned fixture 的後續擴充。
- branch cleanup after audit 的最終收尾。

## 7. 風險與不確定點

- browser E2E 在此 workspace 仍是 `SKIPPED`，因為 Playwright/browser tooling 不可用。
- mismatch fixture 仍故意保留 registry mismatch，因此 drift guard 報 `BLOCKED` 是預期結果。
- aligned fixture 目前仍是 synthetic data，沒有寫入 production DB，也不代表 production catalog 已完整。
- 若未來要做更廣泛的 browser E2E，仍需要可用的 Playwright browser binary。

## 8. 建議今天/下一輪優先處理的方向

1. 若需要 live browser E2E，先補齊 Playwright/browser tooling，讓 scaffold 真跑 lifecycle filter path。
2. 若要擴大覆蓋，新增更多 registry-aligned synthetic rows，但仍保持 synthetic_only。
3. 維持 mismatch fixture 作為負向回歸測試，不放寬 unknown strategy guard。

## 9. 下一輪可直接執行的 task prompt

```text
# ROLE
你是 LotteryNew 的 P1 Replay Lifecycle Browser Tooling Enablement Agent，向 CTO agent 回報。

# MISSION
在不寫 production DB、不做 strategy mining、不做 replay generation、不做 edge discovery、不改 active strategy state 的前提下，補齊 browser tooling 檢查與執行環境，使 Replay Lifecycle browser E2E 能在可用環境中實跑。

# CONTEXT

aligned fixture 已經完成：
- registry-aligned synthetic fixture 在 drift guard 上可 PASS
- mismatch fixture 仍會 BLOCKED
- browser E2E scaffold 已存在並在 tooling 不可用時 skip

# PRIMARY GOAL

1. 檢查 Playwright / browser tooling 是否可用。
2. 若可用，讓 lifecycle filter browser E2E 真正執行。
3. 若不可用，維持明確 skip policy 並記錄原因。
4. 不修改 replay UI/API/lifecycle registry semantics。

# HARD SCOPE

Do not:
- modify replay UI code unless strictly necessary for selector stability
- modify replay API code
- modify lifecycle registry code
- write production DB
- run strategy mining
- run edge discovery
- run replay generation
- change branch protection
- claim browser E2E PASS if it only skipped

# FINAL MARKER

P1_REPLAY_LIFECYCLE_BROWSER_TOOLING_NEXT
```

## 10. CTO Agent 10 行內摘要

- 已建立 registry-aligned synthetic fixture，drift guard 在 aligned fixture 上可 PASS。
- mismatch fixture 仍保留且會 BLOCKED，負向覆蓋沒有被放寬。
- browser E2E skip policy 已補強，tooling 不可用時會明確 skip。
- aligned / mismatch 兩條 fixture 路徑都只用 synthetic data，synthetic_only=1。
- 沒有寫 production DB、沒有做 strategy mining、沒有做 replay generation。
- 沒有改 replay UI/API/lifecycle registry semantics。
- pytest 與 default validation 均已如實記錄 PASS / SKIPPED 結果。
- browser E2E 在此 workspace 仍因 tooling 不可用而 skipped。
- 目前適合繼續往 Playwright/browser tooling enablement 方向推進。
- 今日產出可作為 aligned fixture 與 browser E2E 的完整交接依據。