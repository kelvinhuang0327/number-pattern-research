# CTO Review → Backlog Integration

## 概覽

CTO Review 系統可以將 findings 直接寫入 orchestrator backlog，讓 worker 自動執行修復任務。
**不建立第二套任務系統**：CTO backlog 項目直接建立 `agent_tasks` (status=QUEUED)，由現有 `worker_tick.py` 正常領取執行。

---

## 架構流程

```
cto_review_tick.py
   └─ 生成 decisions + intelligence (JSON / Markdown)

UI: OrchestrationManager._loadCtoRunDetail()
   ├─ 載入 backlog 狀態 (GET /api/orchestrator/cto/backlog)
   ├─ 每個 finding 顯示「加入 backlog」按鈕（尚未入列）或狀態 badge（已入列）
   └─ 「加入全部高優先 backlog」批次按鈕（高優先 + 未入列的數量）

API: POST /api/orchestrator/cto/backlog
   └─ 建立 agent_tasks row (QUEUED) + cto_backlog_items row

API: POST /api/orchestrator/cto/backlog/batch
   └─ 批次處理，過濾 severity >= min_severity AND impact >= min_impact

worker_tick.py
   └─ 正常 list_tasks(status="QUEUED") 領取並執行
```

---

## DB Schema

### `cto_backlog_items` 表

| 欄位 | 說明 |
|------|------|
| `id` | 自增主鍵 |
| `finding_id` | 去重鍵（UNIQUE），批次格式：`{run_id}__t{task_id}_{SEVERITY}` |
| `cto_run_id` | 對應的 CTO review run |
| `source` | 預設 `cto_review` |
| `severity` | CRITICAL / HIGH / MEDIUM / LOW |
| `impact_score` | 0–100 |
| `urgency` | IMMEDIATE / HIGH / SHORT / MEDIUM / LOW |
| `category` | 問題類別（architecture / performance / quality 等） |
| `suggested_action` | 建議執行動作描述 |
| `task_id` | FK → `agent_tasks.id` |
| `task_slot_key` | 任務建立時的 slot key |
| `status` | `pending` / `queued`（由 `get_cto_backlog_item_task_status()` 從 agent_tasks 派生） |
| `created_at` / `updated_at` | ISO timestamp |

---

## API 端點

### `GET /api/orchestrator/cto/backlog`

查詢 CTO backlog 項目清單。

| 參數 | 說明 |
|------|------|
| `cto_run_id` | 過濾特定 run（可選） |
| `status` | 過濾狀態（可選） |
| `limit` | 最大筆數，預設 200 |

**回傳**
```json
{
  "items": [
    {
      "id": 1,
      "finding_id": "run_20241201120000__t42_HIGH",
      "task_id": 99,
      "live_status": "queued",
      ...
    }
  ],
  "count": 1
}
```

---

### `POST /api/orchestrator/cto/backlog`

加入單筆 CTO finding 到 backlog。

**Request Body**
```json
{
  "finding_id": "run_20241201120000__t42_HIGH",
  "cto_run_id": "run_20241201120000",
  "severity": "HIGH",
  "impact_score": 75,
  "urgency": "SHORT",
  "category": "architecture",
  "suggested_action": "重構 XYZ 模組以解決循環依賴"
}
```

**Success (200)**
```json
{
  "ok": true,
  "conflict": false,
  "item_id": 1,
  "task_id": 99,
  "slot_key": "202412011201",
  "title": "重構 XYZ 模組以解決循環依賴",
  "live_status": "queued",
  "message": "Finding xxx added to backlog as task #99"
}
```

**Duplicate (200 + conflict:true)**
```json
{
  "ok": false,
  "conflict": true,
  "message": "Finding xxx already in backlog (status: queued)",
  "existing": { ... }
}
```

---

### `POST /api/orchestrator/cto/backlog/batch`

批次加入高優先 findings（自動從 report JSON 讀取）。

**Request Body**
```json
{
  "cto_run_id": "run_20241201120000",
  "min_severity": "HIGH",
  "min_impact": 60
}
```

過濾條件：`SEVERITY_RANK >= min_severity OR impact_score >= min_impact`

**Response**
```json
{
  "ok": true,
  "added_count": 3,
  "skipped_count": 1,
  "added": [
    { "finding_id": "...", "item_id": 1, "task_id": 99, "slot_key": "...", "title": "..." }
  ],
  "skipped": [
    { "finding_id": "...", "reason": "duplicate", "live_status": "completed" }
  ]
}
```

---

## UI 行為

### 單筆加入
- 每個 finding card 右側顯示「＋ 加入 backlog」按鈕（尚未入列時）
- 點擊後：按鈕變為「加入中…」→ 成功後替換為「● 已排入 backlog (#task_id)」badge
- 重複加入：按鈕替換為「已存在」badge

### 批次加入
- Intelligence panel 右上角顯示「⚡ 加入全部高優先 backlog (N)」按鈕
  - N = 符合高優先條件（CRITICAL/HIGH 或 impact≥60）且尚未入列的數量
  - 若全部已入列，改顯示「✓ 高優先項目已全部入 backlog」
- 點擊後自動批次加入，1.2 秒後重新整理頁面更新 badge 狀態

### 狀態 Badge 顏色
| 狀態 | 顏色 | 說明 |
|------|------|------|
| queued | 藍 (#58a6ff) | 已排入 backlog，等待 worker |
| running | 橘 (#d29922) | 執行中 |
| completed | 綠 (#3fb950) | 已完成 |
| failed | 紅 (#f85149) | 執行失敗 |
| cancelled | 灰 (#8b949e) | 已取消 |

---

## 去重設計

- `cto_backlog_items.finding_id` 設有 UNIQUE 約束
- 批次模式 `finding_id` 格式：`{cto_run_id}__t{task_id}_{SEVERITY}`
- API 在建立前先查 `get_cto_backlog_item_by_finding(finding_id)`，重複則回傳 `conflict:true` 而非報錯

---

## Prompt 格式

每個 CTO backlog 任務會產生結構化 prompt，包含：
- CTO Run ID / Finding ID 追蹤資訊
- Severity / Impact / Urgency / Category
- 執行目標（suggested_action 展開）
- 約束條件（遵循 wiki/governance.md）
- Acceptance Criteria
- Handoff Notes

Prompt 存放路徑：`runtime/prompts/{date_folder}/{slot_key}_{slug}.md`

---

## backlog.md 可見性

每次加入 backlog 時，同步 append 一行到 `runtime/agent_orchestrator/backlog.md`：
```
- [ ] [CTO/HIGH] 重構 XYZ 模組以解決循環依賴 `(run=run_20241201120000, id=...)`
```
人工審閱 backlog.md 可見所有待處理 CTO findings。

---

## 相關檔案

| 檔案 | 說明 |
|------|------|
| `orchestrator/db.py` | `cto_backlog_items` table + 5 helper functions |
| `orchestrator/api.py` | GET / POST single / POST batch 端點 |
| `src/ui/OrchestrationManager.js` | `_loadCtoRunDetail()` — 按鈕渲染 + 事件綁定 |
| `orchestrator/cto_review_tick.py` | Intelligence scoring + `_write_reports()` |
