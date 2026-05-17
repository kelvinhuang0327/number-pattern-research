# P1 Replay Lifecycle Formalization Report

**Date:** 2026-05-17  
**Scope:** replay contract / validation / fixture / report only  
**Safety:** no DB write, no draw import, no replay row generation, no prediction update, no strategy execution

## 1. 本輪目標

本輪目標是把 Strategy Historical Replay 的 lifecycle contract 正式化，讓 replay history 的 contract 可以穩定表達所有正式生命周期狀態，並解除非 PRODUCTION 策略在展示與驗證層面的阻塞。

## 2. P0 inventory 輸入摘要

- Total strategies: 506
- Lifecycle breakdown: PRODUCTION 68, WATCHING 7, PROVISIONAL 6, REJECTED 90, OFFLINE 0, EXPERIMENTAL 307, UNKNOWN 28
- Coverage gap summary:
  - strategies with replay rows: 13
  - strategies without replay rows: 493
  - strategies with historical records but no replay: 86
  - strategies with no records anywhere: 407

P0 的 UNKNOWN = 28，低於停止門檻 50，因此可以進入 P1 contract formalization。

## 3. 原本 blockers

| Blocker | File path | Current behavior | Required change | Risk level | Code change required |
|---|---|---|---|---|---|
| Fixture path locked to old non-online artifact | `lottery_api/routes/replay.py` | `fixture_mode=true` 只讀舊 non-online fixture | 改用 P1 formalization fixture，並保留 legacy fallback | Medium | Yes |
| Fixture mode did not enforce `lottery_type` filter | `lottery_api/routes/replay.py` | 混合彩種時可能誤回傳不相干 rows | 在 fixture path 加上 lottery_type 過濾 | Medium | Yes |
| Lifecycle enum for replay formalization missing | `lottery_api/models/replay_lifecycle_contract.py` | 沒有 7-state formal contract SSOT | 新增 7-state contract + apply safety helpers | Low | Yes |
| Contract tests still frozen in 16-strategy snapshot | `tests/test_replay_strategy_lifecycle_endpoint.py` | 仍用舊 16 策略數字 | 跟著 registry 現況更新成 18 策略快照 | Low | Yes |
| API contract tests only covered old non-online states | `tests/test_replay_api_contract.py` | 只驗證 OFFLINE/REJECTED/OBSERVATION/RETIRED | 擴到 7-state formal lifecycle fixture | Low | Yes |

## 4. 正式化的 lifecycle states

允許的 formal display states:

- PRODUCTION
- WATCHING
- PROVISIONAL
- REJECTED
- OFFLINE
- EXPERIMENTAL
- UNKNOWN

### 可 display

上述 7 個狀態都可在 replay fixture / contract 中 display 與查詢。

### 禁止 production apply

下列狀態不可進入 production apply:

- WATCHING
- PROVISIONAL
- REJECTED
- OFFLINE
- EXPERIMENTAL
- UNKNOWN

### Unknown handling

UNKNOWN 只允許作為分類不確定的安全落點，不可被誤判為 active / production-safe apply state。

## 5. 最小 product acceptance fixture

新增 P1 formalization fixture:

- `outputs/replay/p1_lifecycle_formalization_fixture_20260517.json`

內容包含 7 筆合成紀錄，各 1 筆覆蓋:

- PRODUCTION
- WATCHING
- PROVISIONAL
- REJECTED
- OFFLINE
- EXPERIMENTAL
- UNKNOWN

並且全部保持 read-only synthetic fixture 性質，不依賴 DB，不生成 replay row。

## 6. 測試結果

- `python3 scripts/replay_lifecycle_drift_guard.py --strict --json-out /tmp/p1_post_lifecycle_drift_guard.json`
  - PASS
- `pytest -q tests/test_replay_api_contract.py tests/test_replay_lifecycle_formalization_contract.py tests/test_replay_strategy_lifecycle_endpoint.py`
  - PASS
  - 89 passed
- `python3 -m py_compile` on changed Python files
  - PASS

## 7. Safety confirmation

- No DB write
- No draw import
- No replay row generation
- No prediction update
- No strategy logic change

## 8. Modified / created files

- [lottery_api/models/replay_lifecycle_contract.py](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/lottery_api/models/replay_lifecycle_contract.py)
- [scripts/generate_p1_lifecycle_formalization_fixture.py](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/scripts/generate_p1_lifecycle_formalization_fixture.py)
- [lottery_api/routes/replay.py](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/lottery_api/routes/replay.py)
- [tests/test_replay_api_contract.py](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/tests/test_replay_api_contract.py)
- [tests/test_replay_lifecycle_formalization_contract.py](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/tests/test_replay_lifecycle_formalization_contract.py)
- [tests/test_replay_strategy_lifecycle_endpoint.py](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/tests/test_replay_strategy_lifecycle_endpoint.py)
- [outputs/replay/p1_lifecycle_formalization_fixture_20260517.json](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/outputs/replay/p1_lifecycle_formalization_fixture_20260517.json)

## 9. Current conclusion

P1 lifecycle formalization is complete at the contract / fixture / validation layer. The replay history fixture mode now has a formal 7-state sample, and the endpoint contract tests no longer depend on the old non-online-only framing.

## 10. Next action proposal

建議進入 **P3 Historical Reconstruction vs Future Waiting Split**。  
下一輪可把「歷史可重建」與「未來等待中」兩條線正式切開，讓 replay 覆蓋率與治理邊界更清楚。

## 11. CTO agent 10-line summary

1. P1 formalized the replay lifecycle contract without touching DB or strategy execution.
2. Added a 7-state formal lifecycle SSOT for replay-facing display and validation.
3. Built a minimal product fixture covering PRODUCTION, WATCHING, PROVISIONAL, REJECTED, OFFLINE, EXPERIMENTAL, UNKNOWN.
4. Redirected replay fixture_mode to the new P1 fixture with a legacy fallback.
5. Tightened fixture-mode filtering so lottery_type is respected.
6. Updated API contract tests to prove all 7 formal states are accepted in replay history.
7. Updated endpoint snapshot tests to match the current 18-strategy registry.
8. Drift guard remained PASS before and after the change.
9. Pytest on the replay lifecycle contract surface passed 89/89.
10. Safety boundaries held: no DB writes, no draw import, no replay-row generation, no prediction updates.
