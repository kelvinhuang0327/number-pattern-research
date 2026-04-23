# CTO Review — Force Rerun

> 文件版本：2026-04-23  
> 對應實作：`orchestrator/cto_review_tick.py`、`orchestrator/db.py`、`orchestrator/api.py`、`src/ui/OrchestrationManager.js`

---

## 功能說明

**Force Rerun** 允許使用者在 duplicate guard 阻擋的情況下，手動強制執行一次 CTO 審核。

**適用情境：**
- 上次 run 剛完成（30 分鐘內），但已有新的重要 commit 需立即審核
- 有 in-flight run 卡住，需要強制開啟新的審核流程
- 緊急情況下需繞過防重複機制

---

## 架構設計

### Guard 執行順序

```
1. Scheduler disabled?     → CTO_REVIEW_SKIP_DISABLED      (force run 仍遵守)
2. Frequency gate?         → CTO_REVIEW_SKIP_FREQUENCY      (scheduled only; manual 跳過)
3. In-flight duplicate?    → CTO_REVIEW_SKIP_DUPLICATE_RUNNING  (force run 跳過 ✓)
4. Recent duplicate?       → CTO_REVIEW_SKIP_DUPLICATE_RECENT   (force run 跳過 ✓)
5. 正常執行
```

Force run **不能**繞過的 guard：
- Scheduler disabled（`CTO_REVIEW_SKIP_DISABLED`）— 此為系統級停用，強制重跑亦不例外

---

## API

### `POST /api/orchestrator/cto/run-now`

**Request body（新增）：**

```json
{
  "force": false
}
```

| 欄位 | 型別 | 預設 | 說明 |
|------|------|------|------|
| `force` | bool | `false` | 是否略過 duplicate guards |

**Response（新增欄位）：**

```json
{
  "ok": true,
  "pid": 12345,
  "triggered_at": "2026-04-23T10:00:00Z",
  "request_id": "abc123...",
  "force": true
}
```

---

## 環境變數

| 變數 | 值 | 說明 |
|------|-----|------|
| `ORCHESTRATOR_FORCE_RUN` | `"1"` | 標記為 manual run（原有） |
| `ORCHESTRATOR_FORCE_RERUN` | `"1"` | 略過 duplicate guards（新增） |

兩者均由 `api.py` 注入至 subprocess 環境，`cto_review_tick.py` 讀取。

---

## DB 欄位

`cto_review_runs` 表新增欄位：

| 欄位 | 型別 | 預設 | 說明 |
|------|------|------|------|
| `is_force_run` | `INTEGER` | `0` | 此 run 是否為強制重跑（0/1） |

Migration 於 `db.init_db()` 中自動執行，支援現有 DB 升級。

---

## Outcome 事件

| Outcome | 類型 | 說明 |
|---------|------|------|
| `CTO_REVIEW_FORCE_RUN` | 非 terminal 日誌事件 | 記錄 force run 觸發並繞過哪個 guard |

`CTO_REVIEW_FORCE_RUN` 透過 `db.log_tick()` 寫入，**不是** terminal outcome，不影響前端 polling 的完成判斷。實際的 terminal outcome 仍為 `CTO_REVIEW_COMPLETED`、`CTO_REVIEW_ERROR` 等。

---

## UI

### 強制重跑觸發

CTO 頁面控制列新增：

```
[CTO 立即執行]  ☐ 強制重跑 (略過 duplicate guard)
```

- Checkbox 預設為 **未勾選**（正常行為不變）
- 觸發後 checkbox 自動 reset 為未勾選

### Badge 顯示

**Run 列表（Frequency 欄）：**
- 藍色 `手動` badge — `is_manual = true`
- 紅色 `強制` badge — `is_force_run = true`（兩者可同時出現）

**Run Detail Panel（header 區域）：**
- 紅色 `⚡ 強制重跑` 標籤 — `is_force_run = true`

---

## 驗收方式

### 場景 1：正常 run 仍被 duplicate 阻擋
1. 觸發一次 CTO run（不勾選強制重跑）
2. 30 分鐘內再次觸發（相同 scope）
3. 預期結果：outcome = `CTO_REVIEW_SKIP_DUPLICATE_RECENT`，無 force badge

### 場景 2：force run 突破 recent duplicate guard
1. 完成一次 CTO run
2. 勾選「強制重跑」後觸發
3. 預期結果：run 正常執行，`is_force_run = 1`，顯示紅色 `強制` badge
4. tick log 中有 `CTO_REVIEW_FORCE_RUN` 事件

### 場景 3：force run 突破 in-flight guard
1. 觸發一次長跑 CTO run（仍在執行中）
2. 勾選「強制重跑」後觸發
3. 預期結果：新 run 正常開始，不被 `SKIP_DUPLICATE_RUNNING` 阻擋

### 場景 4：scheduler disabled 時 force run 仍被阻擋
1. 在 UI 暫停 CTO 排程
2. 勾選「強制重跑」後觸發
3. 預期結果：outcome = `CTO_REVIEW_SKIP_DISABLED`（force 不能繞過 disabled）

### 場景 5：Scheduler 正常 run 行為不變
1. 不勾選任何選項，直接點「CTO 立即執行」
2. 預期結果：行為與原有完全相同，duplicate guard 正常運作

---

## 修改檔案摘要

| 檔案 | 變更 |
|------|------|
| `orchestrator/db.py` | 新增 `is_force_run` 欄位（migration + INSERT） |
| `orchestrator/cto_review_tick.py` | 讀取 `ORCHESTRATOR_FORCE_RERUN`；`_quick_skip_run()` 接受 `is_force_run`；duplicate guards 加 `and not is_force_run`；日誌 `CTO_REVIEW_FORCE_RUN` 事件；`run_record` 含 `is_force_run` |
| `orchestrator/api.py` | 新增 `CtoRunNowRequest(force: bool = False)`；注入 `ORCHESTRATOR_FORCE_RERUN=1` 至 subprocess env；response 含 `force` 欄位 |
| `index.html` | CTO 控制列新增 force rerun checkbox |
| `src/ui/OrchestrationManager.js` | `_triggerCtoRunNow()` 讀取 checkbox 並傳 `force`；run 列表紅色 `強制` badge；detail panel `⚡ 強制重跑` 標籤 |
