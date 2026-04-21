# Research Review System — 研究檢討系統

## 概述

Research Review System 是一套結構化的研究治理子系統，讓每期開獎後的檢討變成組織化知識。所有發現、假說、行動項目、影子實驗都被持久化到 SQLite 資料庫，並可在前端管理介面 (研究檢討 tab) 中瀏覽與操作。

---

## 架構

```
index.html  (nav + reviews-section HTML + CSS)
   │
   └─► src/ui/ReviewManager.js   — 前端 UI 管理
          │
          └─► /api/reviews/*      — FastAPI 路由 (lottery_api/routes/reviews.py)
                 │
                 ├─► engine/review_service.py  — 會議 CRUD + 儀表板 + 匯出
                 └─► engine/shadow_service.py  — 影子實驗 CRUD + 比較
                        │
                        └─► database.py         — 6 張資料表
```

---

## 資料表

| 資料表 | 用途 |
|--------|------|
| `review_sessions` | 檢討會議(每期/策略) |
| `review_findings` | 會議中的發現 (section_type, evidence) |
| `review_hypotheses` | 假說 (待驗證/已確認/已拒絕) |
| `review_actions` | 行動項目 (P0/P1/P2 + OPEN/IN_PROGRESS/DONE/WONT_DO) |
| `shadow_experiments` | 影子實驗 (base vs experiment 策略) |
| `prediction_review_status` | 預測 run_id → 檢討狀態對應 |

所有表都在 `database.py:_init_database()` 自動建立。

---

## API 端點

| Method | Path | 說明 |
|--------|------|------|
| POST | `/api/reviews/create` | 建立檢討會議 |
| GET | `/api/reviews/history` | 查詢會議清單 (支援 game/draw/status/session_type 篩選) |
| GET | `/api/reviews/{id}` | 取得完整會議詳情 (含 findings, hypotheses, actions) |
| PUT | `/api/reviews/{id}` | 更新會議 (summary, decision, status) |
| POST | `/api/reviews/{id}/mark-resolved` | 標記會議已解決 |
| POST | `/api/reviews/{id}/reopen` | 重新開啟會議 |
| GET | `/api/reviews/actions` | 查詢行動項目 (支援 status/priority/game) |
| PUT | `/api/reviews/actions/{id}/status` | 更新行動狀態 |
| PUT | `/api/reviews/hypotheses/{id}/status` | 更新假說狀態 |
| GET | `/api/reviews/prediction-status` | 查詢預測的檢討狀態 |
| GET | `/api/reviews/dashboard` | 檢討儀表板摘要 |
| GET | `/api/reviews/{id}/export/json` | 匯出 JSON |
| GET | `/api/reviews/{id}/export/markdown` | 匯出 Markdown |
| POST | `/api/reviews/{id}/create-shadow` | 從假說建立影子實驗 |
| GET | `/api/reviews/shadow-experiments` | 查詢影子實驗列表 |
| GET | `/api/reviews/shadow-experiments/{id}` | 取得影子實驗詳情 |
| PUT | `/api/reviews/shadow-experiments/{id}` | 更新影子實驗 |
| GET | `/api/reviews/shadow-experiments/{id}/comparison` | 影子 vs production 比較 |

---

## 前端介面

### 入口
導航列 → **研究檢討** 按鈕 → `reviews-section`

### 面板

1. **儀表板** (`rv-dashboard`) — 關鍵數字卡片 + 優先行動
2. **會議列表** (`rv-session-tbody`) — 可篩選狀態/類型，分頁
3. **會議詳情** (`rv-detail`) — 發現、假說、行動、操作按鈕
4. **行動總覽** (`rv-actions-panel`) — 跨會議行動項目

### 操作

- 查看會議詳情 → 修改假說/行動狀態 (下拉選單即時更新)
- 標記已解決 / 重新開啟
- 匯出 JSON / Markdown
- 從假說建立影子實驗

---

## 預測追蹤整合

`PredictionTracker.js` 的歷史表新增「檢討」欄位，顯示每筆預測是否已完成研究檢討：
- **已檢討**: 綠色 badge
- **未檢討**: 灰色 badge

`_renderReviewBlock()` 依然在展開詳情中渲染 LLM Research Board 面板。

---

## 檔案清單

| 檔案 | 角色 |
|------|------|
| `lottery_api/database.py` | DB schema (6 表) |
| `lottery_api/engine/review_service.py` | 會議 CRUD + dashboard + export |
| `lottery_api/engine/shadow_service.py` | 影子實驗 CRUD + 比較 |
| `lottery_api/routes/reviews.py` | API 路由 (18 端點) |
| `lottery_api/app.py` | Router 註冊 |
| `src/ui/ReviewManager.js` | 前端 UI 管理 |
| `src/core/App.js` | ReviewManager 初始化 + section switching |
| `src/ui/PredictionTracker.js` | 檢討狀態欄位 + Review Block |
| `index.html` | Nav button + section HTML + CSS |
