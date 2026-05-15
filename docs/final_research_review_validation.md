# Research Review System — 最終驗證清單

## 後端驗證

- [x] `database.py` — 6 張資料表存在 (`review_sessions`, `review_findings`, `review_hypotheses`, `review_actions`, `shadow_experiments`, `prediction_review_status`)
- [x] `review_service.py` — 685 行完整 CRUD (create/get/list/update/dashboard/export)
- [x] `shadow_service.py` — 影子實驗 create/get/list/update/compare
- [x] `routes/reviews.py` — 18 個 API 端點 (Pydantic 驗證 + error handling)
- [x] `app.py` — `reviews.router` 已註冊

## 前端驗證

- [x] `ReviewManager.js` — Dashboard + Session List + Session Detail + Actions 面板
- [x] `App.js` — import ReviewManager + constructor init + section switching
- [x] `index.html` nav — "研究檢討" 按鈕 (data-section="reviews")
- [x] `index.html` section — `reviews-section` 完整 HTML 結構
- [x] `index.html` CSS — `.rv-*` 系列樣式
- [x] `PredictionTracker.js` — 歷史表新增「檢討」欄位 (已檢討/未檢討 badge)
- [x] `index.html` 表頭 — 歷史表新增「檢討」th, colspan 更新為 9

## 功能矩陣

| 功能 | 後端 | 前端 | 狀態 |
|------|------|------|------|
| 建立會議 | `POST /api/reviews/create` | (API-driven) | ✅ |
| 會議列表 | `GET /api/reviews/history` | `loadSessions()` | ✅ |
| 會議詳情 | `GET /api/reviews/{id}` | `loadSession()` → `_renderDetail()` | ✅ |
| 更新會議 | `PUT /api/reviews/{id}` | (API-driven) | ✅ |
| 標記已解決 | `POST /api/reviews/{id}/mark-resolved` | `.rv-resolve-btn` | ✅ |
| 重新開啟 | `POST /api/reviews/{id}/reopen` | `.rv-reopen-btn` | ✅ |
| 行動項目 | `GET /api/reviews/actions` | `loadActions()` | ✅ |
| 更新行動狀態 | `PUT /api/reviews/actions/{id}/status` | `.rv-act-select` | ✅ |
| 更新假說狀態 | `PUT /api/reviews/hypotheses/{id}/status` | `.rv-hyp-select` | ✅ |
| 儀表板 | `GET /api/reviews/dashboard` | `loadDashboard()` | ✅ |
| 匯出 JSON | `GET /api/reviews/{id}/export/json` | `.rv-export-json` | ✅ |
| 匯出 Markdown | `GET /api/reviews/{id}/export/markdown` | `.rv-export-md` | ✅ |
| 建立影子實驗 | `POST /api/reviews/{id}/create-shadow` | (API-driven) | ✅ |
| 影子實驗列表 | `GET /api/reviews/shadow-experiments` | (API-driven) | ✅ |
| 影子實驗比較 | `GET /api/reviews/shadow-experiments/{id}/comparison` | (API-driven) | ✅ |
| 預測檢討狀態 | `GET /api/reviews/prediction-status` | PredictionTracker 欄位 | ✅ |

## 整合確認

- [x] 與現有預測追蹤系統整合 (PredictionTracker → 檢討 badge)
- [x] 與全局彩種切換同步 (lottery-type-filter → ReviewManager._currentGame)
- [x] 不影響現有功能 (所有修改均為 additive)
