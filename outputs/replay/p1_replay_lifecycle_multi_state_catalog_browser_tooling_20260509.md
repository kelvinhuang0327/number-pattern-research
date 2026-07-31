# P1 Replay Lifecycle Multi-State Catalog + Browser Tooling Plan

## 1. 本輪目標

建立 multi-state synthetic catalog fixture，覆蓋 `ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED`，並整理 browser tooling installation / check path。此輪只做 fixture / tests / tooling plan / validation report，不寫 production DB、不做 strategy mining、不做 replay generation、不做 edge discovery、不改 active strategy state。

## 2. 已完成事項

- 新增 deterministic multi-state synthetic catalog fixture 支援。
- multi-state fixture 維持 `synthetic_only=1`，沒有 production DB data。
- drift guard 對 multi-state fixture 已驗證為 `PASS`。
- multi-state payload 的 `replay_rows_by_lifecycle` 已覆蓋所有 lifecycle statuses。
- mismatch fixture 的 `unknown_strategy_ids` 仍維持 `BLOCKED`，沒有被放寬。
- browser E2E 的 skip policy 已保持誠實：tooling 不可用時會跳過，不會假稱 `PASS`。
- main protection 與現有 replay lifecycle workflow 沒有被修改。

## 3. 修改或產出的檔案

本輪修改：

- `scripts/build_replay_test_fixture.py`
- `scripts/check_replay_lifecycle_drift.py`
- `tests/test_replay_lifecycle_browser_e2e.py`
- `tests/test_replay_lifecycle_multistate_fixture.py`

本輪產出：

- `outputs/replay/p1_replay_lifecycle_multi_state_catalog_browser_tooling_20260509.md`

保留既有驗證依據：

- `tests/test_replay_lifecycle_aligned_fixture.py`
- `tests/test_replay_lifecycle_drift_guard.py`
- `scripts/validate_replay_test_fixture.py`

## 4. 驗證結果 / 測試結果

已執行的命令與結果如下：

- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/build_replay_test_fixture.py --fixture-mode aligned --output /tmp/lottery_replay_lifecycle_aligned_fixture.db`
  - `mode=aligned`
  - `synthetic_only=1`
  - `strategy_replay_runs=4`
  - `strategy_prediction_replays=3`
- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/validate_replay_test_fixture.py --db /tmp/lottery_replay_lifecycle_aligned_fixture.db`
  - `integrity=PASS`
- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/check_replay_lifecycle_drift.py --db-path /tmp/lottery_replay_lifecycle_aligned_fixture.db`
  - `status=PASS`
  - `replay_rows_by_lifecycle={"ONLINE": 3}`
  - traceable strategy IDs: `biglotto_triple_strike`, `daily539_f4cold`, `power_precision_3bet`
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
- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/build_replay_test_fixture.py --fixture-mode multistate --output /tmp/lottery_replay_lifecycle_multistate_fixture.db`
  - `mode=multistate`
  - `synthetic_only=1`
  - `strategy_replay_runs=4`
  - `strategy_prediction_replays=5`
- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/validate_replay_test_fixture.py --db /tmp/lottery_replay_lifecycle_multistate_fixture.db`
  - `integrity=PASS`
- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/check_replay_lifecycle_drift.py --db-path /tmp/lottery_replay_lifecycle_multistate_fixture.db`
  - `status=PASS`
  - `replay_rows_by_lifecycle` covered all statuses:
    - `ONLINE`
    - `OFFLINE`
    - `REJECTED`
    - `OBSERVATION`
    - `RETIRED`
- ` /Library/Developer/CommandLineTools/usr/bin/python3 -m pytest tests/test_replay_lifecycle_multistate_fixture.py tests/test_replay_lifecycle_aligned_fixture.py tests/test_replay_lifecycle_browser_e2e.py -q`
  - `4 passed, 1 skipped`
  - browser E2E skipped because Playwright/browser tooling is unavailable in this workspace
- ` /Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_default_validation.py`
  - `57 passed, 32 skipped`

## 5. 目前結論

multi-state synthetic catalog fixture 已完成且 drift guard 可 PASS；aligned fixture 仍保留為 registry-known positive path；mismatch fixture 仍保留為 BLOCKED 負向控制。browser E2E 的 skip policy 仍是誠實的，tooling 不可用時不會被誤判為 PASS。

## 6. 尚未完成事項

- live browser E2E with actual Playwright/browser tooling。
- lifecycle DB migration / audit trail 的更完整落地。
- 更廣的 browser tooling 安裝 / 偵測計畫。
- optional cleanup of report branches / backup branches after audit。

## 7. 風險與不確定點

- multi-state fixture 仍是 synthetic-only，不代表 production catalog 已完整。
- mismatch fixture BLOCKED remains intentional negative control。
- browser E2E 在 browser tooling 不可用時仍會 skip。
- non-ONLINE tabs 在沒有對應 catalog data 時可能顯示 0。
- audit trail 仍分散在 PR #3 / #5 / #6 / #7 與多個 report branches。

## 8. 建議下一輪優先處理的方向

1. 規劃 browser tooling installation / check path，讓 browser E2E 在可用環境中真跑。
2. 若需要更完整的稽核面，擴充 multi-state synthetic catalog rows 的覆蓋與說明。
3. 維持 synthetic-only、read-only 原則，不寫 production DB、不做 strategy mining、不做 replay generation、不改 active strategy state。
4. 不把 browser skip 誤判為 PASS。

## 9. 下一輪可直接執行的 task prompt

```text
# ROLE
你是 LotteryNew 的 P1 Replay Lifecycle Browser Tooling Installation + Check Plan Agent，向 CTO agent 回報。

# MISSION
規劃並執行 browser tooling installation / check path，讓 Replay Lifecycle browser E2E 在可用環境中真跑。
本輪只做 tooling plan / check / validation report，不寫 production DB，不做 strategy mining，不做 replay generation，不做 edge discovery，不改 active strategy state。

# CONTEXT

multi-state synthetic catalog fixture 已完成：
- 覆蓋 ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED
- multi-state drift guard PASS
- mismatch fixture 仍 BLOCKED
- browser E2E 在 tooling 不可用時誠實 skip

# PRIMARY GOAL

1. 檢查 Playwright / browser tooling 是否可用。
2. 若可用，讓 browser lifecycle path 真跑。
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

P1_REPLAY_LIFECYCLE_BROWSER_TOOLING_INSTALLATION_NEXT
```

## 10. CTO Agent 10 行內摘要

- 已建立 multi-state synthetic catalog fixture，覆蓋五種 lifecycle status。
- multi-state fixture 為 synthetic-only，不含 production DB data。
- multi-state drift guard 已 PASS，且 `replay_rows_by_lifecycle` 覆蓋所有狀態。
- mismatch fixture 仍 BLOCKED，負向控制仍有效。
- aligned fixture 仍保留為 registry-known positive path。
- browser E2E 在工具鏈不可用時誠實 skip，沒有假稱 full PASS。
- pytest 與 default validation 結果一致，可追溯。
- 沒有寫 production DB、沒有做 strategy mining、沒有做 replay generation。
- 沒有改 replay UI/API/lifecycle registry semantics。
- 下一步建議先補 browser tooling 安裝 / check plan。