# Replay Fixture-Mode SOP + User Guide

**Version**: 1.0  
**Date**: 2026-05-11  
**Scope**: `outputs/replay/` fixture artifact + `/api/replay/history?fixture_mode=true`  
**Status**: ACTIVE — applies from main commit `ce87159` onwards  

---

## 1. 文件目的

Fixture Mode 是一種 **synthetic read-only** 操作模式，用於驗收 non-ONLINE lifecycle rows
（REJECTED / RETIRED / OBSERVATION）在 dashboard replay section 的可視化狀態。

**核心定義**：

| 屬性 | 說明 |
|------|------|
| 資料來源 | `outputs/replay/non_online_replay_fixture_20260511.json`（合成資料）|
| 資料性質 | Synthetic — 非真實 production replay 結果 |
| 用途 | 驗收 UI 狀態可視化、lifecycle filter 功能、banner 顯示 |
| 不可用於 | 評估 strategy 實際表現、production 決策、backfill 依據 |

> **重要**：Fixture records 帶有 `advisory_only=true`，永遠不代表 production replay outcome。
> 使用者看到 fixture records 時，不得解讀為真實預測結果。

---

## 2. 啟用方式

### 2.1 API 直接呼叫

```bash
# REJECTED lifecycle（預期 4 筆）
GET /api/replay/history?lifecycle_status=REJECTED&fixture_mode=true

# RETIRED lifecycle（預期 5 筆）
GET /api/replay/history?lifecycle_status=RETIRED&fixture_mode=true

# OBSERVATION lifecycle（預期 1 筆）
GET /api/replay/history?lifecycle_status=OBSERVATION&fixture_mode=true
```

**預設行為**（不帶 fixture_mode 或 fixture_mode=false）：
```bash
# 維持 production DB read path，不讀 fixture
GET /api/replay/history?lifecycle_status=REJECTED
```

### 2.2 UI 啟用方式

在 dashboard URL 加入 query param：

```
https://<host>/#replay?rp_fixture_mode=true
```

或在 replay section URL state 中設定：

```
rp_fixture_mode=true
```

UI 會自動：
1. 在所有 API 請求附加 `&fixture_mode=true`
2. 顯示 FIXTURE MODE banner（見 Section 4）

**UI 預設**：`rpFixtureMode = false`（fixture mode 關閉）

### 2.3 程式碼層級（route helper 直呼，僅用於測試）

```python
from lottery_api.routes.replay import _fixture_history_response

resp = _fixture_history_response(
    lifecycle_status="REJECTED",
    strategy_id=None,
    replay_status=None,
    date_from=None,
    date_to=None,
    page=1,
    page_size=50,
)
```

---

## 3. 預期結果

### 3.1 Lifecycle Counts

| lifecycle_status | 預期筆數 |
|-----------------|---------|
| REJECTED | **4** |
| RETIRED | **5** |
| OBSERVATION | **1** |
| 合計 | **10** |

### 3.2 Response 必含欄位與值

每筆 fixture record 必須包含：

| 欄位 | 預期值 |
|------|-------|
| `source` | `"synthetic_fixture"` |
| `advisory_only` | `true` |
| `production_db_write` | `false` |
| `fixture_mode` | `true` |

若以上任一欄位缺失或值不符，視為 fixture mode 實作異常，應停止並回報。

### 3.3 Fixture Mode=false 的預期

| 欄位 | 預期行為 |
|------|---------|
| `source` | 不含 `"synthetic_fixture"` |
| `advisory_only` | 不含此欄（或為 `false`）|
| `production_db_write` | 不含此欄（或為 `false`）|
| `fixture_mode` | 不含此欄（或為 `false`）|

---

## 4. UI 解讀規則

### 4.1 Fixture Banner

當 fixture mode 啟用時，dashboard 必須顯示：

```
⚠ FIXTURE MODE — 合成資料、僅供驗收，不代表真實預測
```

Banner 元素：`id="rp-fixture-banner"`  
顯示邏輯：`banner.style.display = active ? '' : 'none'`

**若 banner 未顯示但 fixture records 出現，視為 UI 安全防護失效，應立即停止操作。**

### 4.2 解讀禁止事項

| 禁止行為 | 原因 |
|---------|------|
| 把 fixture records 當作真實 replay outcome | 資料為 synthetic |
| 用 fixture records 評估 strategy 表現 | `advisory_only=true` |
| 根據 fixture records 做 promotion 決策 | 不代表 production 結果 |
| 把 fixture counts（4/5/1）視為實際 replay 次數 | 為驗收用 artifact 固定值 |

### 4.3 Lifecycle Filter 用途

Lifecycle filter（REJECTED / RETIRED / OBSERVATION）在 fixture mode 下，
**僅用於驗收 UI 狀態可視化是否正常**，不代表實際 lifecycle 切換或分類決策。

---

## 5. 安全邊界（強制）

以下限制在任何情況下均不可違反：

| 禁止事項 | 說明 |
|---------|------|
| **不寫 production DB** | `data/lottery_v2.db` 為 read-only，fixture mode 完全不觸及 DB write path |
| **不做 backfill** | production DB backfill 繼續 defer，直到 OFFLINE classification decision |
| **不改 registry** | strategy registry 不得因 fixture validation 產生任何變更 |
| **不改 active strategy state** | strategy 的 lifecycle state 不得因 fixture mode 操作改變 |
| **不做 promotion / retire action** | fixture records 不可觸發任何 lifecycle transition |
| **不新增 scheduler / cron** | 不為 fixture mode 建立任何定期執行機制 |
| **不做 strategy mining / edge discovery** | fixture validation 與 edge discovery 完全分離 |
| **Fixture artifact 不可升格為預設 runtime source** | `non_online_replay_fixture_20260511.json` 僅為驗收用，不可替換 production DB read path |

---

## 6. DB Dirty SOP

### 6.1 問題說明

`pytest` 執行 `lottery_api` routes 或 Python 直接 `import` route 模組時，
SQLite 會更新 `data/lottery_v2.db` 的 mtime，導致 `git status` 顯示 `M data/lottery_v2.db`。

**這是 mtime dirty，不等於 production write**，但仍不可 commit DB。

### 6.2 Restore 步驟

```bash
# Step 1: 確認 dirty 狀態
git status --short data/lottery_v2.db
# 若顯示「 M data/lottery_v2.db」則需 restore

# Step 2: Restore to HEAD
git checkout HEAD -- data/lottery_v2.db

# Step 3: 確認已 clean
git status --short data/lottery_v2.db
# 若無輸出 → CLEAN ✅
```

### 6.3 何時必須 Restore

| 情境 | 是否需要 restore |
|------|---------------|
| `pytest tests/test_replay_api_contract.py` 執行後 | 是 |
| `pytest tests/test_replay_browser_smoke.py` 執行後 | 視情況，通常是 |
| `python` 直接 import `lottery_api.routes.replay` 後 | 是 |
| 僅讀 HTML / JSON 檔案 | 否 |

### 6.4 Restore 必須在以下時機前完成

- `git commit` 之前
- `git push` 之前
- 切換 branch 之前（若 branch 間有 DB 差異）

---

## 7. 驗證 SOP

### 7.1 最小驗證指令集

```bash
# 環境：使用 LotteryNew venv
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean
export PYTHON=/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.venv/bin/python

# Step 1: API fixture-mode contract tests（7 tests）
$PYTHON -m pytest tests/test_replay_api_contract.py -v -k "FixtureMode"
# 預期：7 passed

# Step 2: 全套 contract tests（含 DB path 回歸，44 tests）
$PYTHON -m pytest tests/test_replay_api_contract.py -v
# 預期：44 passed

# Step 3: Browser smoke tests（34 tests）
$PYTHON -m pytest tests/test_replay_browser_smoke.py -v
# 預期：34 passed

# Step 4: Whitespace check
git diff --check
# 預期：無輸出（PASS）

# Step 5: DB restore（每次 pytest 後執行）
git checkout HEAD -- data/lottery_v2.db

# Step 6: Final DB clean check
git status --short data/lottery_v2.db
# 預期：無輸出（CLEAN）
```

### 7.2 通過標準

| 驗證項目 | 通過條件 |
|---------|---------|
| Fixture mode contract tests | 7 passed, 0 failed |
| Full contract suite | 44 passed, 0 failed |
| Browser smoke tests | 34 passed, 0 failed |
| `git diff --check` | 無輸出 |
| DB final state | `git status --short data/lottery_v2.db` 無輸出 |

---

## 8. Agent 操作規則

後續任何 agent 在操作 fixture mode 時，必須遵守以下規則：

### 8.1 允許的操作

| 允許 | 範圍 |
|------|------|
| 呼叫 `GET /api/replay/history?fixture_mode=true` | 讀取，不寫入 |
| 執行 fixture mode contract tests | 測試後必須 restore DB |
| 讀取 `non_online_replay_fixture_20260511.json` | 驗收用途 |
| 驗證 fixture banner 是否顯示 | UI smoke |

### 8.2 禁止的操作

| 禁止 | 原因 |
|------|------|
| 把 synthetic records 寫入 `data/lottery_v2.db` | 污染 production DB |
| 以 fixture validation 當作 strategy performance evidence | 資料為合成，不可信 |
| 擴充 fixture mode 為 production backfill 依據 | 超出 advisory-only 範圍 |
| 修改 `non_online_replay_fixture_20260511.json` 以填入真實資料 | 未經授權的 backfill |
| 在未收到 explicit YES 前 merge 任何 fixture-related PR | 必須遵守 YES gate |
| 更新 `_FIXTURE_HISTORY_PATH` 指向不同 artifact | 需要單獨的 code review |

### 8.3 Scope 邊界

Fixture mode 的 scope 嚴格限制在：

```
讀取 outputs/replay/non_online_replay_fixture_20260511.json
         ↓
回傳帶有 advisory_only=true 的 synthetic records
         ↓
UI 顯示 FIXTURE MODE banner
```

任何超出此 scope 的操作均需要獨立的 task prompt 和 YES gate。

---

## 9. Troubleshooting

### 9.1 Fixture File Missing

**症狀**：`fixture_mode=true` 回傳 HTTP 500

**原因**：`outputs/replay/non_online_replay_fixture_20260511.json` 不存在

**處理**：
```bash
ls outputs/replay/non_online_replay_fixture_20260511.json
# 若不存在，需重新執行 PR #51 的 fixture generator
# 參見 PR #51 commit 7762118
```

---

### 9.2 Lifecycle Filter 空畫面

**症狀**：`fixture_mode=true` + lifecycle filter 後，UI 顯示 0 records

**可能原因與處理**：

| 原因 | 處理 |
|------|------|
| lifecycle_status 大小寫錯誤 | 使用 `REJECTED` / `RETIRED` / `OBSERVATION`（全大寫）|
| fixture JSON 中該 lifecycle 無記錄 | 確認 counts：REJECTED=4, RETIRED=5, OBSERVATION=1 |
| API 未正確接收 `fixture_mode=true` | 確認 URL param 有正確附加 |

---

### 9.3 Banner 未出現

**症狀**：fixture_mode=true 啟用後，`⚠ FIXTURE MODE` banner 未顯示

**處理**：
1. 確認 `id="rp-fixture-banner"` 元素存在於 HTML
2. 確認 `rpFixtureMode` 狀態變數已設為 `true`
3. 確認 `rpSetFixtureModeBanner(true)` 有被呼叫
4. 執行 smoke test 驗證：
   ```bash
   pytest tests/test_replay_browser_smoke.py -v -k "fixture_mode_banner"
   ```

---

### 9.4 DB Dirty（`M data/lottery_v2.db`）

**症狀**：`git status --short data/lottery_v2.db` 顯示 `M data/lottery_v2.db`

**處理**：立即執行 restore（見 Section 6），**不可 commit**。

---

### 9.5 Fixture_mode=false 卻看到 `synthetic_fixture`

**症狀**：未帶 `fixture_mode=true` 但 response 包含 `source=synthetic_fixture`

**原因**：嚴重的路由邏輯錯誤，fixture_mode 條件判斷失效

**處理**：
1. 立即停止操作
2. 執行全套 contract tests 確認範圍
3. 回報 CTO
4. 不在修復前繼續任何 PR merge

---

## 10. 下一步建議

### 優先順序建議

| 優先度 | 項目 | 說明 |
|--------|------|------|
| **高** | OFFLINE Classification Decision Memo | 決定 OFFLINE vs REJECTED/RETIRED/OBSERVATION 邊界，是 production backfill 的前置條件 |
| **中** | UI Toggle Button（P23）| 在 replay section 加入 FIXTURE MODE toggle，取代 URL param 手動啟用；**必須在此 SOP merge 後才可啟動** |
| **低** | DB mtime SOP 自動化 | 在 `pytest conftest.py` 加入自動 restore fixture，消除人工漏 restore 風險 |
| **Defer** | Production replay backfill | 在 OFFLINE classification decision 確定前，繼續 defer |

### 下一輪可執行 Prompt 選項

**選項 A — OFFLINE Classification Decision Memo（建議優先）**：
```
產出 OFFLINE vs REJECTED/RETIRED/OBSERVATION 分類學決策備忘錄，
定義 OFFLINE 的語意邊界，提供 CTO 決策所需選項與取捨分析。
```

**選項 B — P23 UI Toggle Button**：
```
在 replay section 新增 FIXTURE MODE toggle button，
使使用者可在 UI 中直接切換，不依賴 URL param。
前置條件：此 SOP（PR #56）已 merge。
```

---

## Artifact Reference

| 檔案 | 用途 |
|------|------|
| `outputs/replay/non_online_replay_fixture_20260511.json` | Fixture artifact（10 records）|
| `lottery_api/routes/replay.py` | Fixture mode API 實作 |
| `index.html` | Fixture mode UI 實作（banner + URL param）|
| `tests/test_replay_api_contract.py` | Contract tests（含 7 fixture mode tests）|
| `tests/test_replay_browser_smoke.py` | Browser smoke tests（34 tests）|
| `outputs/replay/p22_fixture_mode_browser_e2e_validation_20260511.md` | P22 validation report |
| `outputs/replay/replay_fixture_mode_epic_closure_20260511.md` | Epic closure report |

---

*本文件由 Replay Fixture-Mode SOP/User Guide Agent 產出，基於 main commit `9f35999`。*  
*任何修改需透過獨立 PR 並經 explicit YES gate 審核。*
