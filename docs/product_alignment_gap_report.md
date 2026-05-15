# Product Alignment Gap Report
Generated: 2026-03-26

---

## 一、各頁面現狀說明

### A. 策略回測頁（Next Draw — `data-section="next-draw"`）

**實際行為**：
- 呼叫 `GET /api/next-draw-summary?mode=direct&recent_count=500`
- 顯示三個彩種各自注數的最佳策略與預測號碼
- 同時顯示 Decision V3 建議面板（風險等級、信心度、建議注數）
- Handler: `src/core/handlers/NextDrawHandler.js`

**策略配置**（`_NEXT_DRAW_CONFIG` in `routes/prediction.py`）：
```
今彩539:   1注 acb_1bet / 2注 midfreq_acb_2bet / 3注 acb_markov_midfreq_3bet / 5注 f4cold_5bet
大樂透:    2注 regime_2bet / 3注 ts3_regime_3bet / 5注 p1_dev_sum5bet
威力彩:    3注 fourier_rhythm_3bet / 4注 pp3_freqort_4bet / 5注 orthogonal_5bet
```

**本次 session 已修正**：
- 修正 `os as _os` import 問題（`name 'os' is not defined`），使 inline 策略函數可正確載入
- 重啟伺服器後驗證：各策略現在使用獨立算法，F4Cold 5注完全獨立

### B. 預測追蹤頁（Tracking — `data-section="tracking"`）

**實際行為**：
- 呼叫 4 個端點：`/api/tracking/history` / `/api/tracking/performance` / `/api/tracking/schedule/status` / `/api/tracking/schedule/history`
- 顯示：排程狀態 (3張卡) + 績效統計表 + 歷史紀錄列表 + 排程歷史
- 展開行：呼叫 `/api/tracking/run/{run_id}` 顯示逐注命中詳情
- Handler: `src/ui/PredictionTracker.js`

**正確性**：
- `valid_only=True` 為預設（engine/prediction_tracker.py L524），RECONSTRUCTED 預設排除 ✅
- 展開詳情使用 `bets_by_strategy` 分組，每注顯示命中號碼（綠色高亮）✅
- PENDING / RESOLVED 狀態正確標記 ✅

### C. 排程／回補頁

**現況**：嵌入在預測追蹤頁底部，非獨立頁面。包含：
- 排程狀態卡（SCHEDULED / SNAPSHOT_CREATED / MISSED_WINDOW / RECONSTRUCTED）
- 排程歷史記錄
- 重建快照按鈕（`/api/tracking/schedule/generate/{schedule_id}?source=RECONSTRUCTED`）

---

## 二、與需求不一致之處（Gaps）

### GAP-1：Silent Coordinator Fallback（高危）

**位置**：
- `lottery_api/routes/prediction.py` L2239-2242
- `lottery_api/routes/prediction_tracking.py` L151-154

**問題**：當 `predict_fn = _predict_fns.get(strategy_key)` 為 None 時，程式碼靜默 fallback 到 `coordinator_predict()`，使用 coordinator 疊加結果，且前端無法得知。

**需求要求**："不能因為策略載入失敗就 silently fallback 而讓不同注數顯示一樣的號碼"

**現狀**：目前 `_predict_fns` 已包含所有正式策略 key，fallback 不會被觸發；但程式碼邏輯仍在，若未來策略 key 不匹配仍會靜默 fallback。

**修正方向**：移除 coordinator fallback，改為設定 `numbers = []` + 在 response 中加入 `prediction_error: true`，前端顯示 "N/A（策略無法載入）"。

### GAP-2：大樂透缺 1注 策略

**需求**："大樂透：1注 / 2注 / 3注 / 5注（如有）各自正確獨立"

**現狀**：`_NEXT_DRAW_CONFIG["BIG_LOTTO"]` 無 1注策略配置，因為 RSM 從未驗證過大樂透 1注有效策略（L90 結論：信號空間窮盡）。

**判斷**：需求括號內說「如有」—— 因此大樂透沒有 1注是合理的，但需在 UI 明確說明「無有效 1注策略（信號窮盡）」，而非空白不顯示。

**修正方向**：在大樂透遊戲卡加入說明標注。

### GAP-3：威力彩缺 1注 / 2注 策略

**需求**："威力彩：1注 / 3注 / 4注 / 5注（依現有正式策略）各自正確獨立"

**現狀**：`_NEXT_DRAW_CONFIG["POWER_LOTTO"]` 只有 3/4/5注，符合需求（需求列出 1/3/4/5 但「依現有正式策略」——目前無 1注驗證策略）。

**判斷**：符合需求，無需修正。

### GAP-4：策略載入失敗後前端顯示

**現狀**：若 `numbers = []`（空列表），前端 `_renderBetRow` 的 `numbers.map()` 會產生空的 betRows，整個策略欄顯示空白，使用者不知道是策略失敗還是正常。

**修正方向**：前端加入空 numbers 時的 "N/A" 顯示。

### GAP-5：預測追蹤詳情頁「策略成功率」欄位

**需求**："可依遊戲 / 策略 / 注數篩選"

**現狀**：Performance 表有彩種篩選（透過 `_currentGame`），但無策略名稱篩選 input。現有 `_renderPerformance()` 列出所有策略，使用者無法按策略名稱或注數過濾。

**判斷**：功能欠缺，但非阻斷性問題（資料已顯示，只是無篩選器）。

---

## 三、已驗證正常的部分

| 功能 | 狀態 |
|------|------|
| 三頁面完全獨立，無混用 | ✅ |
| 策略回測用獨立算法（本 session 修正） | ✅ |
| RECONSTRUCTED 預設排除績效統計 | ✅ |
| 展開詳情逐注顯示命中號碼（綠色高亮） | ✅ |
| bets_by_strategy 分組（多注策略） | ✅ |
| PENDING / RESOLVED 狀態標記 | ✅ |
| 排程狀態（SCHEDULED / SNAPSHOT_CREATED 等）可查 | ✅ |
| 可抓最新獎號（DrawEntryManager） | ✅ |
| 可掃描缺漏期數（schedule/status） | ✅ |
| 可回補重建快照（schedule/generate） | ✅ |

---

## 四、待修正 Action Items

| 優先級 | 問題 | 檔案 | 修正 |
|--------|------|------|------|
| P1（必修） | Silent coordinator fallback | prediction.py L2239 | 移除 fallback，改為 `numbers=[], error=True` |
| P1（必修） | Tracking route 同樣問題 | prediction_tracking.py L151 | 同上 |
| P1（必修） | 前端空 numbers 顯示 N/A | NextDrawHandler.js | 加入空 numbers 判斷 |
| P2（建議） | 大樂透無 1注說明 | NextDrawHandler.js | 加入 "無 1注驗證策略" 標注 |
| P3（建議） | 預測追蹤績效篩選 | PredictionTracker.js | 加入策略/注數 filter input |
