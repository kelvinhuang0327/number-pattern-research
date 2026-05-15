# Full UI Functionality Audit
## 三頁面全面功能合理性驗證報告

Generated: 2026-04-17

---

## 稽核範圍

| 頁面 | Section ID | 主要元件 |
|------|-----------|---------|
| A. 策略回測展示 | `#next-draw-section` | `NextDrawHandler.js`, `/api/decision/best-strategy-summary`, `/api/next-draw-summary` |
| B. 預測追蹤 | `#tracking-section` | `PredictionTracker.js`, `/api/tracking/*` |
| C. 研究檢討 | `#reviews-section` | `ReviewManager.js`, `/api/reviews/*` |

---

## Phase 1 — 問題盤點

### A. 策略回測展示

| # | 問題 | 優先 | 狀態 |
|---|------|------|------|
| A-1 | `NextDrawHandler.js` `_renderBetRow()` — bet row meta bottom 顯示 "Edge ${pct}% 趨勢" 使用 `edge_300p` 舊指標，與首部 Phase V composite_score 卡片不一致，且標籤錯誤引導 | P2 | ✅ 已修正 |
| A-2 | `NextDrawHandler.js` line 157 — `cp_score.toFixed(3)` 未用 optional chain，若 `composite_score` 和 `cp_score` 同時為 null 會拋 TypeError | P2 | ✅ 已修正 |
| A-3 | 策略總覽卡片 Phase V badge 正確 ✓ | — | OK |
| A-4 | 展開明細表格依 composite_score 排序 ✓ | — | OK |
| A-5 | validation_warning 在 WATCH 策略時正確顯示 ✓ | — | OK |

### B. 預測追蹤

| # | 問題 | 優先 | 狀態 |
|---|------|------|------|
| B-1 | `_renderStrategySlot()` 主 return block — HTML 嚴重損毀（前次 Phase V.5 edit 造成）：`<span class="pt-r${validatedBadge}` 語法錯誤，`${missingDataWarningck-body"...` 殘留文字，導致 ALL 策略 slot 顯示破碎 HTML | P0 | ✅ 已修正 |
| B-2 | `_renderStrategySlot()` `無歷史快照` 分支 — 雙重 `${missingDataWarning}` 插入（重複顯示警告） | P0 | ✅ 已修正 |
| B-3 | 策略績效表 (`pt-perf-body`) — 只顯示 `strategy_status`，不顯示 Phase V `validated_status` badge | P1 | ✅ 已修正 |
| B-4 | 績效摘要卡 — 同上，只有 PRODUCTION/WATCH 舊 badge | P1 | ✅ 已修正 |
| B-5 | 歷史清單 review 狀態以 `review_status` 為主，`analyzed` 為 fallback ✓ | — | OK |
| B-6 | 歷史清單 `run_id` 點擊展開詳情 ✓ | — | OK |
| B-7 | 分頁邏輯 ✓ | — | OK |
| B-8 | 只顯示 RESOLVED 紀錄（pending 不展示） ✓ | — | OK |
| B-9 | 各注數 slot 正確對應 actual_numbers + hit_count ✓ | — | OK |

### C. 研究檢討

| # | 問題 | 優先 | 狀態 |
|---|------|------|------|
| C-1 | 儀表板 "最近檢討結果" 正確來自 `/api/reviews/dashboard` ✓ | — | OK |
| C-2 | "尚未檢討期數" 來自 `/api/tracking/history?analyzed=UNREVIEWED`，後端正確排除 `prediction_review_status.review_status IN ('REVIEWED','RESOLVED')` ✓ | — | OK |
| C-3 | 會議列表 "查看" 按鈕 ✓ | — | OK |
| C-4 | 行動總覽 tab 正確載入 `/api/reviews/actions` ✓ | — | OK |
| C-5 | 詳情頁 "匯出 JSON / Markdown" 按鈕 — delegation 綁定在 `#rv-detail-view` ✓ | — | OK |
| C-6 | Observer Mode 成立：無新增/修改 session 按鈕，只有查看/匯出 ✓ | — | OK |
| C-7 | 從 PredictionTracker 點 "查看檢討 →" 跳轉 ReviewManager.init() ✓ | — | OK |

---

## Phase 2 — 資料來源盤點

### A. 策略回測展示

| UI 欄位 | 來源 API | Backend 欄位 | Fallback | 可信度 |
|---------|---------|-------------|---------|-------|
| 彩種名稱 | `/api/decision/best-strategy-summary` | `game` | — | ✅ |
| 最佳策略名稱 | 同上 | `best_strategy.strategy_name` | — | ✅ |
| 最佳注數 | 同上 | `best_strategy.bet_count` | — | ✅ |
| 驗證狀態 badge (VALIDATED/WATCH/REJECTED) | 同上 | `best_strategy.validated_status` | WATCH | ✅ |
| 綜合評分 | 同上 | `best_strategy.composite_score` | `cp_score` (修正後 null-safe) | ✅ |
| Edge 150/500/1500p | 同上 | `best_strategy.edge_{150,500,1500}p` | N/A | ✅ |
| Perm p / McNemar p / Sharpe | 同上 | `best_strategy.{perm_p,mcnemar_p,sharpe}` | N/A | ✅ |
| validation_warning | 同上 | `best_strategy.validation_warning` | 無 | ✅ |
| 全量明細表 | 同上 | `all_strategies[]` | — | ✅ |
| RSM 預測號碼 | `/api/next-draw-summary` | `games[lt].bets[].numbers` | — | ✅ |
| 策略狀態 (bet row) | 同上 | `bets[].strategy_status` | ADVISORY_ONLY | ✅ |
| ~~Edge 300p (bet row)~~ | ~~同上~~ | ~~`bets[].edge_300p`~~ | — | ❌ 已移除 |

### B. 預測追蹤

| UI 欄位 | 來源 API | Backend 欄位 | Fallback | 可信度 |
|---------|---------|-------------|---------|-------|
| 排程狀態卡片 | `/api/tracking/schedule/status` | `schedules[]` | — | ✅ |
| 績效統計表 — 策略名 | `/api/tracking/performance` | `strategy_name` | N/A | ✅ |
| 績效統計表 — strategy_status | 同上 | `strategy_status` (Phase V derived) | N/A | ✅ |
| 績效統計表 — validated_status | 同上 | `validated_status` (新增) | null | ✅ |
| 績效統計表 — data_complete | 同上 | `data_complete` (新增) | true | ✅ |
| 歷史清單 — 策略名 | `/api/tracking/history` | `single_bet_summary.strategy_name` | N/A | ✅ |
| 歷史清單 — 命中數 | 同上 | `single_bet_summary.best_hit` | — | ✅ |
| 歷史清單 — 已檢討 | 同上 | `review_status` (Phase V linkage 優先) | `analyzed` | ✅ |
| 詳情 — 各注數 slot | `/api/tracking/run/{run_id}` | `current_best_strategies[]` (Phase V ranked) | — | ✅ |
| 詳情 — validated_status badge | 同上 | `current_best_strategies[].validated_status` | — | ✅ |
| 詳情 — data_complete | 同上 | `current_best_strategies[].data_complete` | — | ✅ |
| 詳情 — LLM 報告 | 同上 | `review_json` | — | ✅ |
| 排程歷史 | `/api/tracking/schedule/history` | `schedules[]` | — | ✅ |

### C. 研究檢討

| UI 欄位 | 來源 API | Backend 欄位 | Fallback | 可信度 |
|---------|---------|-------------|---------|-------|
| 儀表板統計 | `/api/reviews/dashboard` | `session_status_counts` | {} | ✅ |
| 最近檢討結果 | 同上 | `recent_sessions[]` | [] | ✅ |
| 尚未檢討期數 | `/api/tracking/history?analyzed=UNREVIEWED` | `runs[]` | [] | ✅ |
| 會議列表 | `/api/reviews/history` | `sessions[]` | [] | ✅ |
| 決策/信心 | 同上 | `final_decision`, `confidence_level` | — | ✅ |
| 詳情 — 發現/假說/行動 | `/api/reviews/{id}` | `findings[]`,`hypotheses[]`,`actions[]` | [] | ✅ |
| 行動總覽 | `/api/reviews/actions` | `actions[]` | [] | ✅ |
| review → prediction 跳轉 | `/api/reviews/prediction-status` | `items[].review_session_id` | — | ✅ |

---

## Phase 3 — 功能合理性盤點

### 問題類型分類

| 類型 | 說明 | 數量 |
|------|------|------|
| 1. 功能正確但體驗差 | — | 0 |
| 2. 體驗正常但資料錯 | B-3/B-4：績效表不顯示 Phase V badge | 2 |
| 3. 死功能 / 假功能 | A-1 bet row `edge_300p` label（無意義顯示） | 1 |
| 4. 舊架構殘留 | `_rsm_best_strategy_label()` + `_TRACKING_STRATEGIES` dead code | 1 |
| 5. 文案誤導 | A-1 "300期 Edge" label 與 Phase V 不一致 | 1 |
| 6. 狀態不一致 | B-1 HTML 損毀導致 slot 狀態無法顯示 | 1 |
| 7. 可刪除 / 可簡化 | 同 A-1, A-2, dead code | 3 |

---

## 問題總表（依 P0/P1/P2）

| 優先 | 問題 | 影響 | 狀態 |
|------|------|------|------|
| P0 | PredictionTracker.js `_renderStrategySlot()` 主 return block HTML 損毀 | 所有策略 slot 顯示破碎 HTML，用戶看不到預測數字/命中資訊 | ✅ 已修正 |
| P0 | `_renderStrategySlot()` 無歷史快照分支 — 雙重 `${missingDataWarning}` | 資料不足警告重複顯示 | ✅ 已修正 |
| P0 | `prediction_tracking.py` 含 `_rsm_best_strategy_label()` 使用 `edge_300p` 排名的 dead function | Phase V 違規（雖未呼叫，但存在即風險） | ✅ 已移除 |
| P1 | `_TRACKING_STRATEGIES` 含 POWER_LOTTO 錯誤策略 key（`fourier_rhythm_2bet` 等） | 若未來被誤用，會造成策略名稱錯誤 | ✅ 已移除 |
| P1 | 績效統計表/摘要卡不顯示 Phase V `validated_status` badge | 用戶看不到策略驗證級別，無法區分 VALIDATED 與 WATCH | ✅ 已修正 |
| P2 | NextDrawHandler bet row 顯示 "300期 Edge" 舊指標 | 文案誤導，與 Phase V 不一致 | ✅ 已移正 |
| P2 | NextDrawHandler `cp_score.toFixed(3)` 無 null guard | 若資料缺損會拋 TypeError 導致整頁空白 | ✅ 已修正 |
| P2 | Footer 版權年份 "2025" | 過時顯示 | ✅ 已修正 |

---

## 已刪除 / 已隱藏 / 已保留的功能清單

### 已刪除（Dead Code）
- `prediction_tracking.py` 的 `_rsm_best_strategy_label()` 函式（`edge_300p` 排名，從未被呼叫）
- `prediction_tracking.py` 的 `_TRACKING_STRATEGIES` 常數（含 POWER_LOTTO 錯誤策略 key，從未被呼叫）

### 已修正（非刪除）
- `_renderStrategySlot()` 主 return block — 還原正確 HTML
- `_renderStrategySlot()` 無歷史快照分支 — 移除重複 missingDataWarning
- `_renderBetRow()` — 移除 "300期 Edge" 舊標籤，改為只顯示趨勢/警示符號
- `cp_score` fallback 加 null guard
- 績效表/摘要卡加入 `validated_status` + `data_complete` badge

### 已保留（功能合理）
- 排程狀態卡片 (SCHEDULED/SNAPSHOT_CREATED/MISSED_WINDOW/RECONSTRUCTED)
- 重建按鈕（MISSED_WINDOW 狀態下可重建，標記 RECONSTRUCTED，不計正式績效）
- 啟動補全按鈕
- 正式/重建績效篩選 toggle
- 分頁機制
- 研究檢討 Observer Mode（無修改入口，只讀）
- LLM Research Board 報告區塊（展開/折疊）
- 決策解釋 (Phase P Explainability) 區塊

---

## Phase 5 — 驗收結果

### A. 策略回測展示

| 項目 | 結果 |
|------|------|
| 最佳策略來源 `/api/decision/best-strategy-summary` | ✅ |
| validated_status badge 正確 | ✅ |
| 綜合評分 null-safe | ✅ |
| bet row 不再顯示 legacy "300期 Edge" | ✅ |
| 全量明細依 composite_score 排序 | ✅ |

### B. 預測追蹤

| 項目 | 結果 |
|------|------|
| 策略 slot HTML 正確（不再破碎） | ✅ |
| validated_status badge 顯示在 slot header | ✅ |
| missingDataWarning 不重複 | ✅ |
| 績效表顯示 validated_status badge | ✅ |
| 歷史清單 review 狀態正確（Phase V linkage 優先） | ✅ |
| 展開詳情可運作 | ✅ |
| 分頁可運作 | ✅ |

### C. 研究檢討

| 項目 | 結果 |
|------|------|
| 最近檢討結果正確 | ✅ |
| 尚未檢討期數正確（Phase V reviewed 排除） | ✅ |
| 查看詳情可用 | ✅ |
| 行動總覽可用 | ✅ |
| 匯出 JSON/MD 可用 | ✅ |
| Observer Mode 成立（無編輯入口） | ✅ |
