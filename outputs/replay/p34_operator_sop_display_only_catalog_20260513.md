# Operator SOP — Replay Display-Only Catalog
**Version:** P34 / 2026-05-13  
**Feature:** P25 Display-Only Catalog for Non-ONLINE Strategies  
**Main SHA:** `2e4c1e7`  
**Audience:** Replay Operators, QA, Product Reviewers  
**Classification:** Internal Operations Document

> ⚠️ **重要聲明：** 本 SOP 所描述之 Replay 功能僅供歷史查詢與稽核使用。不代表提高中獎率，不構成任何投注建議，不保證任何回放結果。

---

## 1. 目標

讓 operator 能在 Replay 頁面：

1. 查看所有已登錄策略（包含 ONLINE / REJECTED / RETIRED / OBSERVATION / OFFLINE）
2. 正確理解各 lifecycle 的 UI 行為差異
3. 區分 production replay rows vs. display-only catalog rows vs. fixture 合成數據
4. 確認 OFFLINE 策略顯示 coming soon 狀態
5. 不誤把 display-only 結果當作 production truth

---

## 2. 操作流程

### 2-1 開啟 Replay 頁面

1. 在瀏覽器開啟系統前端（index.html 所在位置）
2. 找到 **「歷史預測回放」** 頁籤或區塊
3. 確認頁面頂端出現 Replay 區段標題

**預期畫面：** Replay 頁面，顯示 lifecycle filter 下拉選單、彩券種類選單、及查詢區。

---

### 2-2 確認 Fixture Mode 為 OFF（預設狀態）

1. 查看頁面頂端是否有 **fixture mode 提示 banner**
   - 若無 banner → Fixture mode OFF（正常）
   - 若有 banner → Fixture mode ON（見 2-9 說明）
2. Fixture mode OFF 時顯示的是 production 真實資料（或空值），非合成數據

> **規則：** 所有 operator 正式查核必須在 Fixture mode OFF 下進行。

---

### 2-3 選擇 ONLINE lifecycle — Production Replay Rows

1. 在 lifecycle filter 選擇 **ONLINE**
2. 選擇彩券種類（Big Lotto / Power Lotto / 539）
3. 點擊查詢

**預期行為：**
- 顯示 ONLINE 策略的歷史回放資料列
- 每列包含：策略名稱、策略 ID、彩券種類、回放期數、回放日期、結果
- 頁面說明文字包含：「不保證任何回放結果」、「不代表提高中獎率」

**判定：**
- ✅ PASS：出現 replay 資料列，顯示策略 ID 與回放日期
- ❌ FAIL：頁面空白或 error（需回報）

---

### 2-4 選擇 REJECTED lifecycle — Display-Only Catalog

1. 在 lifecycle filter 選擇 **REJECTED**
2. 選擇彩券種類
3. 點擊查詢

**預期行為：**
- 頁面顯示 catalog 表格（非 replay 資料列）
- 表格標題包含：「無歷史回放資料」
- 每列包含：策略名稱、策略 ID、lifecycle badge（🔴 已拒絕 REJECTED）
- 頁面 disclaimer 顯示

**判定：**
- ✅ PASS：catalog 表格 + 🔴 badge + 「無歷史回放資料」文字
- ❌ FAIL：顯示 production replay rows（不應發生）或 error

> **說明：** REJECTED 策略已通過開發評估但被拒絕上線。「無歷史回放資料」不是 bug，也不是策略失敗的直接證明，而是代表此策略從未進入 production replay。

---

### 2-5 選擇 RETIRED lifecycle — Display-Only Catalog

1. 在 lifecycle filter 選擇 **RETIRED**
2. 選擇彩券種類
3. 點擊查詢

**預期行為：**
- catalog 表格 + ⚪ 已退役 RETIRED badge
- 「無歷史回放資料」文字
- disclaimer 文字

**判定：**
- ✅ PASS：catalog 表格 + ⚪ badge
- ❌ FAIL：production replay rows 出現或 error

> **說明：** RETIRED 策略曾進入或考慮過 production，但已正式退役。Display-only 是正確的 UI 行為。

---

### 2-6 選擇 OBSERVATION lifecycle — Display-Only Catalog

1. 在 lifecycle filter 選擇 **OBSERVATION**
2. 選擇彩券種類
3. 點擊查詢

**預期行為：**
- catalog 表格 + 🟡 觀察中 OBSERVATION badge
- 「無歷史回放資料」文字
- disclaimer 文字

**判定：**
- ✅ PASS：catalog 表格 + 🟡 badge
- ❌ FAIL：production replay rows 出現或 error

> **說明：** OBSERVATION 策略正在觀察期，**不代表推薦或候選**。不可對外宣稱任何預測能力。

---

### 2-7 選擇 OFFLINE lifecycle — Coming Soon / Disabled

1. 在 lifecycle filter 選擇 **OFFLINE**
2. 點擊查詢

**預期行為：**
- 顯示 ⚫ OFFLINE 訊息
- 文字：「OFFLINE 策略目前無已登錄項目（coming soon）」
- 無 catalog 表格、無 replay 資料列

**判定：**
- ✅ PASS：coming soon 文字，無表格
- ❌ FAIL：任何資料列出現或 error

> **說明：** OFFLINE 策略目前登錄數量為 0。Coming soon 是預期行為，非 bug。

---

### 2-8 確認 Lifecycle Counts（Registry 對照）

目前已知 registry 數量（`lottery_api/models/replay_strategy_registry.py`）：

| Lifecycle | 數量 | Display Mode |
|-----------|------|-------------|
| ONLINE | 6 | Standard replay rows |
| REJECTED | 4 | Display-only catalog |
| RETIRED | 5 | Display-only catalog |
| OBSERVATION | 1 | Display-only catalog |
| OFFLINE | 0 | Coming soon |
| **Total** | **16** | |

若 catalog 顯示的策略數量與上表不符，需回報差異。

---

### 2-9 開啟 Fixture Mode（合成數據模式）

1. 在 Replay 頁面找到 fixture mode 開關（toggle 或 URL parameter `?fixture=true`）
2. 開啟 Fixture mode

**預期行為：**
- 頁面頂端出現 **fixture mode banner**
- Banner 文字應包含：「合成」、「synthetic」、「非 production」、「demo」等語意
- 所有顯示資料皆為 **合成/模擬數據**，非 production DB 真實數據

**判定：**
- ✅ PASS：banner 明確標示 fixture / synthetic / demo
- ❌ FAIL：無 banner，資料看起來像 production（重大問題，需立即回報）

---

### 2-10 關閉 Fixture Mode — 確認乾淨切回

1. 關閉 fixture mode 開關（或移除 URL parameter）
2. 重新查詢

**預期行為：**
- Fixture banner 消失
- 顯示 production 資料或正確的 display-only catalog（依 lifecycle 而定）
- 無任何 fixture / synthetic 資料殘留

**判定：**
- ✅ PASS：banner 消失，資料恢復 production 模式
- ❌ FAIL：banner 殘留或資料不一致（需回報）

---

## 3. Lifecycle 說明表

| Lifecycle | 意義 | UI 行為 | 是否有 production replay rows |
|-----------|------|---------|-------------------------------|
| ONLINE | 已上線，正常運作 | 標準 replay 資料列 | ✅ 有 |
| REJECTED | 已被評估但拒絕上線 | Display-only catalog + 🔴 | ❌ 無 |
| RETIRED | 曾運作，已退役 | Display-only catalog + ⚪ | ❌ 無（或歷史已封存）|
| OBSERVATION | 觀察期，未正式上線 | Display-only catalog + 🟡 | ❌ 無 |
| OFFLINE | 目前無登錄項目 | Coming soon ⚫ | ❌ 無 |

---

## 4. 判讀規則

### 4-1「無歷史回放資料」
- **意義：** 此 lifecycle 的策略沒有 production replay rows
- **不代表：** Bug / 系統錯誤 / 策略失敗的直接證明
- **正確處理：** 閱讀 catalog 表格，了解此 lifecycle 的策略登錄情況

### 4-2「🔴 已拒絕 (REJECTED)」badge
- **意義：** 策略曾被評估，已通過開發程序，但最終被拒絕上線
- **不代表：** 數據錯誤或系統問題

### 4-3「🟡 觀察中 (OBSERVATION)」badge
- **意義：** 策略仍在觀察期，尚未決定是否上線
- **重要：不代表推薦，不構成任何投注依據**

### 4-4 Fixture mode 合成數據
- **意義：** 模擬/展示用途，使用固定合成數據集，非 production DB 真實數據
- **不代表：** 實際歷史回放結果
- **規則：fixture 截圖不得用於對外展示或決策**

---

## 5. 禁止事項

| 禁止行為 | 說明 |
|----------|------|
| ❌ 把 fixture mode 截圖當 production truth | Fixture = 合成數據，非 production |
| ❌ 對外宣稱命中率 | 系統不提供任何命中率保證 |
| ❌ 說「推薦投注」 | 任何 lifecycle 的策略均不構成投注建議 |
| ❌ 說「保證中獎」 | 嚴禁 |
| ❌ 手動改 production DB | 不得直接操作 `data/lottery_v2.db` |
| ❌ 自行 backfill 歷史資料 | backfill 需要 CTO/CEO 書面授權 |
| ❌ 把 OBSERVATION 策略對外宣稱為「候選推薦」 | 觀察中不等於推薦 |
| ❌ 把 display-only 結果截圖當作回放勝率 | Display-only ≠ production replay |

---

## 6. Troubleshooting

### 6-1 看不到 non-ONLINE catalog rows
- 確認 lifecycle filter 已選擇正確（REJECTED / RETIRED / OBSERVATION / OFFLINE）
- 確認 fixture mode OFF（fixture ON 時行為不同）
- 若仍無資料，回報 CTO（可能是 API 連線問題）

### 6-2 Fixture banner 不見
- 確認 URL 或 toggle 已正確開啟 fixture mode
- 若開啟後仍無 banner → 回報工程團隊（重大 UI 問題）
- **不得在無 banner 情況下假設資料為 fixture**

### 6-3 Lifecycle filter 選擇後無反應
- 確認網路連線正常
- 確認後端服務有啟動（若 backend 無啟動，部分 API 可能失敗）
- 若 backend 啟動失敗，記錄錯誤訊息，回報工程團隊

### 6-4 DB dirty 警告（工程人員限定）
- 若看到 `git status --short data/lottery_v2.db` 顯示 `M`
- 執行：`git checkout -- data/lottery_v2.db`
- 記錄 restore 事件
- **不得 commit dirty DB**

### 6-5 Backend startup 失敗（工程人員限定）
- 已知 pre-existing 問題：`ModuleNotFoundError` 當從 `lottery_api/` 目錄啟動
- 此問題不影響 CI 與自動化測試
- 前端 fixture mode 可在 backend 未啟動時獨立運作（使用合成數據）
- 記錄錯誤，不阻止 SOP 操作，但標記為 open issue

### 6-6 Browser smoke test skipped（工程人員限定）
- `tests/test_replay_browser_smoke.py` 中 playwright 測試預期會 skip（1 skipped）
- 這是已知預期行為，非 failure
- 其餘 127 tests 必須全部 pass

---

## 7. 附錄 — 策略 ID 清單（Registry 快照）

請參考：`lottery_api/models/replay_strategy_registry.py`

完整策略清單由 registry 管理，SOP 不重複列出以避免版本不一致。  
如需查看完整策略 ID，請直接讀取 registry 檔案或透過 API：

```
GET /api/replay/strategies?lifecycle_status=ONLINE
GET /api/replay/strategies?lifecycle_status=REJECTED
GET /api/replay/strategies?lifecycle_status=RETIRED
GET /api/replay/strategies?lifecycle_status=OBSERVATION
GET /api/replay/strategies?lifecycle_status=OFFLINE
```

---

## 文件版本控制

| 版本 | 日期 | 說明 |
|------|------|------|
| P34 / v1.0 | 2026-05-13 | 初版，基於 main `2e4c1e7` |
