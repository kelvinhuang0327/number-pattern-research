# P1.4 — ts3_regime_3bet Adapter Binding Resolution Report

**Date:** 2026-05-15  
**Branch:** `chore/p14-ts3-regime-adapter-binding-20260515`  
**Depends on:** PR #106 (`chore/p13-registry-online-proposal-20260515`)  
**Final Classification:** `P14_TS3_REGIME_ADAPTER_BINDING_READY`  
**Decision:** `SAFE_RECONSTRUCTION`  
**Binding Status:** `BOUND`

---

## 1. 本輪目標

P1.3 (PR #106) 將 `ts3_regime_3bet` 加入 registry 作為 ONLINE 策略，但 adapter binding 標記為 `PENDING`，`get_one_bet()` 呼叫時仍 raise `AdapterBindingPending`。

P1.4 目標：
1. Verify PR #106 狀態（CI、mergeable、draft）
2. 搜尋 `ts3_regime_3bet` 對應的 callable
3. 決定 Case A（exact callable）/ Case B（safe reconstruction）/ Case C（blocked）
4. 若有證據支持，實作 thin wrapper adapter 並解除 PENDING 狀態
5. 新增專屬測試（`tests/test_ts3_regime_adapter_binding.py`）
6. 生成 JSON 報告與本報告
7. Commit、push、建立 draft PR

---

## 2. PR #106 Verify 結果

| 欄位 | 值 |
|------|----|
| PR 編號 | #106 |
| 標題 | feat(replay): add online strategies to registry proposal |
| 狀態 | OPEN (DRAFT) |
| Mergeable | MERGEABLE |
| Merge State | CLEAN |
| Head → Base | `chore/p13-registry-online-proposal-20260515` → `main` |
| CI 結果 | ✅ 2 passing, 1 skipped, 0 failing |

**結論：PR #106 PASS** — 可作為 P1.4 工作分支的上游基礎。

---

## 3. P1.3 遺留風險

P1.3 結束時遺留：

| 風險 | 嚴重程度 | 狀態 |
|------|----------|------|
| `ts3_regime_3bet` adapter binding PENDING | HIGH | ✅ P1.4 已解決 |
| `AdapterBindingPending` 在 `get_one_bet()` 被 raise | HIGH | ✅ P1.4 已修復 |
| `run_id=175 RECONSTRUCTED` snapshot 審計風險 | LOW | ⏳ 保留，待 P2 backfill 後清除 |
| 9 個 PENDING prediction_items（1069-1095） | LOW | ⏳ 待 P2 backfill |

---

## 4. Evidence Search Summary

### 搜尋範圍
- `grep -rn "ts3_regime_3bet"` → 找到 `lottery_api/models/replay_strategy_registry.py`、`memory/lessons.md`、`tests/`
- `grep -rn "generate_p1a_regime_adaptive"` → 找到 `tools/backtest_biglotto_enhancements.py:199`
- `grep -rn "fourier_rhythm_bet|cold_numbers_bet|tail_balance_bet"` → 同一檔案內存在三個 sub-callable
- `grep -rn "detect_regime"` → 同一檔案內存在，但只影響 bet4

### 關鍵發現

```
tools/backtest_biglotto_enhancements.py:199
def generate_p1a_regime_adaptive(history):
    """P1-A: Regime-aware TS3+Markov4"""
    regime, avg_hr = detect_regime(history)
    bet1 = fourier_rhythm_bet(history)               # TS3 Bet1
    bet2 = cold_numbers_bet(history, exclude=set(bet1))   # TS3 Bet2
    bet3 = tail_balance_bet(history, ...)              # TS3 Bet3
    ...
    bet4 = markov_orthogonal_bet(...) or gray-zone bet  # regime-adaptive
    return [bet1, bet2, bet3, bet4]
```

**ts3_regime_3bet = first 3 bets of `generate_p1a_regime_adaptive`**  
Bets 1-3 是 regime-invariant（不受 `detect_regime` 影響）。

---

## 5. Git History Findings

| Commit | Branch/Tag | Summary |
|--------|------------|---------|
| `3d11378` | `chore/p13-registry-online-proposal-20260515` | P1.3: add online strategies to registry (ts3_regime_3bet PENDING) |
| `eb4c768` | `docs/p12-operator-decision-resolution-20260515` | P1.2: resolve strategy denominator operator decisions |
| `d1a7096` | `docs/p11-strategy-denominator-cleanup-20260515` | P1.1: classify strategy universe denominator |
| `63a7d8d` | `docs/p1-strategy-universe-inventory-20260515` | P1: add strategy universe inventory (ts3_regime_3bet 首次記錄) |

`git log -S "generate_p1a_regime_adaptive"` → 首次出現於 `8da5d4c`（初始發布），確認 callable 存在已久。

---

## 6. Callable Decision

**Case B — SAFE_RECONSTRUCTION** 

理由：
- 未找到獨立的 `ts3_regime_3bet` callable（無獨立函式，非精確 callable）
- 找到 `generate_p1a_regime_adaptive` 包含 TS3 成分（bets 1-3）
- `memory/lessons.md:L843-L846` 明確記載 `ts3_regime_3bet` 為生產策略
- TS3 成分（bet1/bet2/bet3）與 regime detection 完全解耦
- 重建語義完整，無歧義

**Evidence chain：**

```
tools/backtest_biglotto_enhancements.py
  └── generate_p1a_regime_adaptive()  [line 199]
        ├── bet1 = fourier_rhythm_bet(history)
        ├── bet2 = cold_numbers_bet(history, exclude=set(bet1))
        ├── bet3 = tail_balance_bet(history, exclude=set(bet1)|set(bet2))
        └── bet4 = regime_adaptive (EXCLUDED from 3-bet variant)

ts3_regime_3bet = [bet1, bet2, bet3]  ← safe reconstruction
```

---

## 7. Adapter Implementation

### 新增 callable

```python
def _ts3_regime_3bet_predict(history):
    from tools.backtest_biglotto_enhancements import (
        fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet,
    )
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]
```

### Adapter class 更名

| Before (P1.3) | After (P1.4) |
|---------------|--------------|
| `_BigLottoTs3Regime3BetPendingAdapter` | `_BigLottoTs3Regime3BetAdapter` |
| `get_one_bet()` → raises `AdapterBindingPending` | `_call_strategy()` → calls `_ts3_regime_3bet_predict` |

### `AdapterBindingPending` 保留

類別保留，不刪除，確保 import 相容性。加入文件說明：`Retained for import compatibility; no longer raised by ts3_regime_3bet.`

---

## 8. Tests Added / Updated

| 檔案 | 動作 | 測試數 |
|------|------|--------|
| `tests/test_ts3_regime_adapter_binding.py` | **新增**（P1.4 專屬） | 22 |
| `tests/test_replay_strategy_registry_online_candidates.py` | **更新** — `TestTs3Regime3BetAdapter` class：PENDING 斷言翻轉為 BOUND 斷言 | 44（含既有） |

### 新增測試類別（`test_ts3_regime_adapter_binding.py`）

- `TestTs3Regime3BetRegistryEntry` — registry metadata assertions
- `TestTs3Regime3BetAdapterBinding` — no AdapterBindingPending, no LifecycleNotExecutable
- `TestTs3Regime3BetOutputValidity` — valid BIG_LOTTO output (6 numbers, range 1-49, distinct, sorted)
- `TestAdapterBindingPendingRetention` — import compatibility

---

## 9. Validation Results

```
python3 -m py_compile lottery_api/models/replay_strategy_registry.py
→ COMPILE OK

pytest tests/test_ts3_regime_adapter_binding.py -q --tb=short
→ 22 passed

pytest tests/test_replay_strategy_registry_online_candidates.py -q --tb=short
→ 44 passed

pytest tests/test_replay_strategy_lifecycle_registry.py \
       tests/test_replay_lifecycle_drift_guard.py \
       tests/test_replay_truth_level_contract.py \
       tests/test_replay_api_contract.py -q --tb=short
→ 109 passed

TOTAL GOVERNANCE SUITE: 175 passed, 0 failed
```

**JSON validity:**
```
python3 -m json.tool outputs/replay/p14_ts3_regime_adapter_binding_20260515.json
→ PASS (valid JSON)
```

**Forbidden artifact check:**
```
git diff --name-only | grep -E '\.db$|\.sqlite$|\.pid$'
→ PASS no forbidden artifact (data/lottery_v2.db is pre-existing untracked)
```

---

## 10. Safety Confirmation

| Safety Flag | Value |
|-------------|-------|
| `db_written` | `false` |
| `replay_rows_generated` | `false` |
| `backfill_run` | `false` |
| `strategy_logic_changed` | `false` |
| `api_ui_backend_changed` | `false` |
| `drift_guard_baseline_changed` | `false` |
| `prediction_items_changed` | `false` |
| `prediction_runs_changed` | `false` |

Note: `data/lottery_v2.db` appears in `git status` as a pre-existing modified file (not touched by this branch). It is **not staged** and will not be committed.

---

## 11. Next Step Recommendation

### 分類：READY → P2 Controlled Replay Backfill Dry-run

**前提條件：**
1. PR #106 (`chore/p13-registry-online-proposal-20260515`) merge 至 main
2. 此 PR (`chore/p14-ts3-regime-adapter-binding-20260515`) merge 至 main

**P2 作業範圍（dry-run 優先）：**
- 9 個 PENDING prediction_items：1069, 1070, 1071, 1090, 1091, 1092, 1093, 1094, 1095
- lottery_type: BIG_LOTTO
- strategy_id: `ts3_regime_3bet`
- 執行 dry-run → 驗證 replay_status 分佈 → 確認後才寫入 DB

**下一輪 prompt（P2 dry-run）：**
```
# P2 Controlled Replay Backfill Dry-run
# Strategy: ts3_regime_3bet (BIG_LOTTO)
# Pending items: 1069-1071, 1090-1095
# Mode: DRY_RUN first, DB write only after operator approval
```

**遺留風險：**
- `run_id=175 RECONSTRUCTED` — 待 P2 backfill 後以新鮮預測取代
- 重建 callable 與原始不保證 byte-identical（語義相符，無法驗證完全一致）
