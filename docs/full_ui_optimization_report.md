# Full UI Optimization Report
## 三頁面功能優化詳細報告

Generated: 2026-04-17

---

## 修正檔案清單

| 檔案 | 修正項目 | 類型 |
|------|---------|------|
| `src/ui/PredictionTracker.js` | `_renderStrategySlot()` 主 return block 重寫 | P0 Bug Fix |
| `src/ui/PredictionTracker.js` | `_renderStrategySlot()` 無歷史快照分支移除重複 warning | P0 Bug Fix |
| `src/ui/PredictionTracker.js` | `_renderPerformance()` 績效摘要卡加入 `summaryValidatedBadge` | P1 Enhancement |
| `src/ui/PredictionTracker.js` | `_renderPerformance()` 績效表格加入 `validated_status` + `data_complete` badge | P1 Enhancement |
| `lottery_api/engine/prediction_tracker.py` | `get_performance()` 輸出加入 `validated_status`, `data_complete` 欄位 | P1 Backend |
| `lottery_api/routes/prediction_tracking.py` | 移除 `_rsm_best_strategy_label()` dead function (edge_300p 排名) | P0/P1 Cleanup |
| `lottery_api/routes/prediction_tracking.py` | 移除 `_TRACKING_STRATEGIES` 含錯誤 POWER_LOTTO key 的舊常數 | P1 Cleanup |
| `src/core/handlers/NextDrawHandler.js` | `_renderBetRow()` 移除 "300期 Edge" 舊標籤 | P2 Cleanup |
| `src/core/handlers/NextDrawHandler.js` | `composite_score` fallback 加 `cp_score != null` guard | P2 Safety |
| `index.html` | Footer 版權年份 2025 → 2026 | P2 Text |

---

## 每個修正點的詳細說明

### [P0-1] PredictionTracker.js — `_renderStrategySlot()` 主 return block HTML 損毀

**問題根因：** 前次 Phase V.5 多替換操作時，`multi_replace_string_in_file` 工具的字串替換出現偏移，造成以下 HTML 片段損毀：
- `<span class="pt-r${validatedBadge}` — `sm-name"...>strategyName` 部分消失
- `${missingDataWarningck-body"...` — `missingDataWarning` 的 `}` 後面殘留了後面元素的開頭文字

**影響：** 所有已有歷史快照的策略 slot（預測追蹤頁展開詳情中的每個注數卡片）都顯示損毀的 HTML 而非正常界面。用戶無法看到預測號碼、命中資訊、策略名稱等。

**修正：** 完整重寫 return block 為正確 HTML：
```javascript
return `<div class="pt-block">
    <div class="pt-block-header">
        <span class="pt-block-title">${numBets} 注</span>
        <span class="pt-rsm-name" style="...">${strategyName}</span>
        ${strategyStatus}${validatedBadge}
        <span style="margin-left:6px">${snapshotState}</span>
        <span style="margin-left:auto;font-size:12px">${hitLabel}</span>
    </div>
    <div class="pt-block-body" style="padding:6px 14px">
        ${availability}
        ${missingDataWarning}
        ${perBetRows}
    </div>
</div>`;
```

---

### [P0-2] PredictionTracker.js — 雙重 `${missingDataWarning}` 

**問題根因：** 同上，上次編輯時 `無歷史快照` 分支插入了兩個 `${missingDataWarning}`。

**影響：** 若 `data_complete === false`，資料不足警告會顯示兩次。

**修正：** 移除重複插入，保留一個。

---

### [P0-3] prediction_tracking.py — 移除 `_rsm_best_strategy_label()` dead function

**問題：** 該函式使用 `edge_300p` 作為排名依據，是 Phase V 前的舊邏輯。雖然目前未被呼叫，但屬於 Phase V 違規程式碼，且帶有誤導性。

**修正：** 連同 `_TRACKING_STRATEGIES`（只被此函式使用）一起移除，改為說明性註解。

---

### [P1-1] prediction_tracking.py — 移除 `_TRACKING_STRATEGIES` 含錯誤 key

**問題：** POWER_LOTTO 的策略 key (`fourier_rhythm_2bet`, `fourier_rhythm_3bet`) 已不對應現有策略（現為 `midfreq_fourier_2bet`, `midfreq_fourier_mk_3bet`）。若未來有人重新啟用 `_rsm_best_strategy_label()`，會取得錯誤的策略名稱。

**修正：** 整體移除。策略排名由 `prediction_tracker.py` 中的 `_get_current_best_strategy_refs()` 統一管理。

---

### [P1-2] prediction_tracker.py + PredictionTracker.js — 績效表加入 validated_status

**問題：** 策略命中率統計表（`#pt-perf-body`）只顯示 `strategy_status`（PRODUCTION/WATCH 等舊系統狀態），沒有 Phase V 的 `validated_status`（VALIDATED/WATCH/REJECTED）badge。用戶無法從績效表直接判斷策略驗證等級。

**後端修正：** `get_performance()` 在每個績效項目加入 `validated_status` 和 `data_complete` 欄位（來自 `_get_current_best_strategy_refs()`）。

**前端修正：**
- 績效摘要卡 `summaryValidatedBadge` — 加在 `summaryStatus` 旁
- 績效表格 status 欄 — 加入 `this._renderValidatedBadge(p.validated_status, p.data_complete)`

---

### [P2-1] NextDrawHandler.js — 移除 "300期 Edge" 舊標籤

**問題：** RSM 預測注數卡片的 meta bottom 顯示 "Edge X.XX% 趨勢符號"，使用 `edge_300p` 舊指標。而卡片頂部已改用 Phase V composite_score / Edge 150/500/1500p，形成不一致。"300期 Edge" 文字對用戶有誤導作用。

**修正：** 移除 `edge_300p` 讀取和 "Edge X%" 文字。若策略有趨勢變化（IMPROVING/DECLINING）或警示，仍顯示方向符號（↑/↓/⚠️），無變化則不顯示。

---

### [P2-2] NextDrawHandler.js — `cp_score.toFixed(3)` null guard

**問題：** `s.composite_score != null ? s.composite_score.toFixed(4) : s.cp_score.toFixed(3)` — 若 `composite_score` 為 null 且 `cp_score` 也為 null（或 undefined），會拋 `TypeError: Cannot read properties of undefined`，導致整個策略卡片無法渲染。

**修正：** 改為 `s.cp_score != null ? s.cp_score.toFixed(3) : 'N/A'`。

---

### [P2-3] index.html — Footer 版權年份

**問題：** "© 2025 大數據智能分析系統"

**修正：** "© 2026 大數據智能分析系統"

---

## 不修正項目說明

| 項目 | 原因 |
|------|------|
| AutoLearning `generateDualBetPrediction` local computation | 已在 Phase V.5 加入 disclaimer，屬於研究實驗室功能，與主策略系統分離 |
| POWER_LOTTO 無 VALIDATED 策略 | 屬資料問題（樣本不足），非 UI 問題。系統已顯示 ⚠️ WATCH + validation_warning |
| ReviewManager 不含新增 session 入口 | Observer Mode 設計意圖，正確 |
| 績效表不顯示 edge_150p/500p/1500p | 績效表追蹤的是「快照命中率」（樣本量級不同），Phase V edge 指標顯示在策略總覽卡，兩者職責分開 |

---

## 架構一致性驗證

| 驗證項目 | 結果 |
|---------|------|
| Frontend 不自決策略排名 | ✅ 所有排名由 backend 提供 |
| Backend truth 唯一來源 | ✅ `strategy_states_*.json` via `_get_current_best_strategy_refs()` |
| 無 edge_300p 排名殘留（除文件中的說明） | ✅ |
| validated_status 在所有 3 頁面均顯示 | ✅ |
| Observer Mode (研究檢討) | ✅ |
| Review linkage 以 `prediction_review_status` 為主 | ✅ |
