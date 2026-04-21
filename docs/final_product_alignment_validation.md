# Final Product Alignment Validation Report
Generated: 2026-03-26

---

## 一、修改檔案清單

| 檔案 | 修改內容 |
|------|---------|
| `lottery_api/routes/prediction.py` | 1) `import os as _os` 修正（策略載入根本原因）2) 移除 coordinator fallback，改為 N/A + `prediction_error` 欄位 |
| `lottery_api/routes/prediction_tracking.py` | 移除 coordinator fallback，改為空結果 + ERROR log |
| `src/core/handlers/NextDrawHandler.js` | 1) `_renderBetRow` 改為 `pt-block` 格式（與預測追蹤一致）2) 加入空 numbers / `prediction_error` 的 N/A 顯示邏輯 |

---

## 二、修正的 Bugs

### BUG-1（高危）：`os` 未 import 導致所有 inline 策略靜默失敗
- **位置**：`prediction.py` 的 `next_draw_summary()` 內部 try block
- **症狀**：`name 'os' is not defined` → `_predict_fns = {}` → 全部 fallback 到 coordinator
- **效果**：1注/2注/3注/5注 全部使用 coordinator 疊加，號碼前綴相同（stacking）
- **修正**：`import sys as _sys, os as _os`

### BUG-2（高危）：Silent coordinator fallback
- **位置**：`prediction.py` L2239 + `prediction_tracking.py` L148
- **症狀**：`predict_fn` 為 None 時靜默呼叫 coordinator，前端看不到錯誤
- **修正**：移除 coordinator fallback，改為 `numbers=[]` + `prediction_error` 欄位 + ERROR log

### BUG-3（UI）：策略回測頁未顯示 N/A
- **位置**：`NextDrawHandler.js` `_renderBetRow()`
- **症狀**：`numbers = []` 時顯示空白，使用者不知道策略失敗
- **修正**：加入 `prediction_error` 判斷，顯示紅色 "N/A" + 錯誤原因

---

## 三、移除的 Fallback

| 位置 | 原行為 | 新行為 |
|------|--------|--------|
| `prediction.py` next_draw_summary | predict_fn 為 None → coordinator_predict() | `numbers=[]`, `prediction_error="..."`, ERROR log |
| `prediction_tracking.py` snapshot | predict_fn 為 None → coordinator_predict() | `bets_for_strategy=[]`, ERROR log |

---

## 四、各頁面行為對齊說明

### A. 策略回測頁（Next Draw）

**現在會看到**：
- 三個彩種各自顯示卡片（今彩539 / 大樂透 / 威力彩）
- 每個彩種依序顯示各注數的最佳策略區塊（pt-block 格式）
- 每個區塊包含：「N 注策略」標題 + 策略名稱 + PRODUCTION/WATCH/MAINTENANCE 徽章 + Edge%
- 每注號碼以 `01 02 03...` 格式顯示
- 若策略載入失敗：顯示紅色 **N/A** + 錯誤說明

**今彩 539 第 115000076 期**：
- 1注 ACB：`[03 04 16 26 35]`
- 2注 MidFreq+ACB：`注1: [01 02 18 27 28]` / `注2: [03 04 16 26 35]`
- 3注 ACB+Markov+MidFreq：三注各自獨立算法
- 5注 F4Cold：五注完全獨立（無與其他策略共享）

**大樂透 第 115000039 期**：
- 無 1注策略（RSM L90/L91：信號空間窮盡）
- 2注 Regime：兩注獨立
- 3注 TS3+Regime：三注獨立
- 5注 P1+Dev+Sum：五注獨立

**威力彩 第 115000025 期**：
- 3注 Fourier Rhythm：三注獨立
- 4注 PP3+FreqOrt：四注（前3注含威力彩最佳組合，第4注正交新增）
- 5注 正交：五注（前4注=PP3+FreqOrt，第5注新增）

### B. 預測追蹤頁（Prediction Tracking）

**現在會看到**：
1. **排程狀態卡**（頂部，3張）：
   - 三個彩種下期預測狀態 = SNAPSHOT_CREATED
   - 顯示最新已知期數和下期預期期數

2. **績效統計表**：
   - 預設 `valid_only=true` → 目前顯示空表格（尚無 VALID 已解析快照）
   - 切換到「含重建快照」→ 顯示 POWER_LOTTO 8期已解析資料

3. **歷史列表**（57筆）：
   - 最新：run#57（今彩539 / 115000076 / MULTI_STRATEGY / RECONSTRUCTED / PENDING）
   - 點擊展開：顯示 4 個策略分組（1+2+3+5 注），策略名稱清楚標示
   - RESOLVED 記錄：命中號碼綠色高亮，未中灰色

4. **排程歷史**：可查看各期快照建立記錄與狀態

### C. 資料完整性頁（嵌入在預測追蹤頁底部）

**現在會看到**：
- 排程狀態卡顯示 SCHEDULED/SNAPSHOT_CREATED/MISSED_WINDOW/RECONSTRUCTED
- 排程歷史記錄列表
- 重建快照按鈕（僅在 MISSED_WINDOW 狀態時啟用）

---

## 五、仍存在的 Blockers

### BLOCKER-1：VALID 績效統計為空
**原因**：系統剛開始使用新 MULTI_STRATEGY 格式。舊 VALID 快照為 coordinator 格式且 PENDING。
**解決**：非 bug，需時間累積。工作流程：
1. 每期開獎前 → 點擊「產生預測快照」（建 VALID MULTI_STRATEGY 快照）
2. 開獎後 → 點擊「比對待解析預測」
3. 累積 10+ 期後，`valid_only=true` 績效統計才有數據

### BLOCKER-2：同一期可重複建立 VALID 快照
**原因**：`prediction_runs` 無 UNIQUE(lottery_type, latest_known_draw, snapshot_source) 約束
**現狀**：DB 中 run#9 和 run#11 皆為 DAILY_539 / 115000075 / VALID（重複）
**影響**：不影響當前功能，但若兩筆都解析，績效計算會重複
**修正計劃**：下一版本在 create_snapshot endpoint 加入重複檢查

### BLOCKER-3：預測追蹤績效頁無策略/注數篩選器
**原因**：前端 `_renderPerformance()` 未實作 filter UI
**影響**：所有策略一次顯示，無法單獨查看某策略趨勢
**修正計劃**：待績效有足夠資料後再加

---

## 六、驗收矩陣

### A. 策略回測頁

| 驗收項目 | 結果 |
|---------|------|
| 今彩539 1注顯示 ACB 策略與號碼 | ✅ |
| 今彩539 2注顯示 MidFreq+ACB 獨立號碼 | ✅ |
| 今彩539 3注顯示 ACB+Markov+MidFreq 獨立號碼 | ✅ |
| 今彩539 5注顯示 F4Cold 完全獨立號碼 | ✅ |
| 大樂透 2注 Regime 獨立 | ✅ |
| 大樂透 3注 TS3+Regime 獨立 | ✅ |
| 大樂透 5注 P1+Dev+Sum 獨立 | ✅ |
| 威力彩 3/4/5注 各自顯示獨立策略 | ✅ |
| 策略名稱明確顯示 | ✅ |
| 狀態徽章（PRODUCTION/WATCH等）顯示 | ✅ |
| Edge 資訊顯示 | ✅ |
| 策略載入失敗顯示 N/A（非 silent fallback） | ✅ |
| 不同注數號碼不再相同（stacking 修正） | ✅ |

### B. 預測追蹤頁

| 驗收項目 | 結果 |
|---------|------|
| 可查每一期預測（歷史列表） | ✅ |
| 可看每一注命中情況（展開詳情） | ✅ |
| 命中號碼綠色高亮 | ✅ |
| 策略成功率統計（有數據時） | ✅（待累積 VALID 解析）|
| 依遊戲篩選 | ✅ |
| 依策略/注數篩選 | ⚠️（待實作 filter UI）|
| RECONSTRUCTED 預設排除 | ✅ |
| 多注策略逐注展開 | ✅ |

### C. 資料完整性頁

| 驗收項目 | 結果 |
|---------|------|
| 可抓最新獎號 | ✅ |
| 可掃描缺漏 | ✅ |
| 可回補（RECONSTRUCTED） | ✅ |
| 可查 schedule/missed/reconstructed 狀態 | ✅ |
| 不干擾正式績效統計 | ✅ |

---

## 七、三頁面功能清楚分離確認

| 功能 | 頁面 | 混淆？ |
|------|------|--------|
| 下一期最佳策略預測顯示 | 策略回測（Next Draw）| ❌ 無 |
| 歷史預測追蹤與成功率統計 | 預測追蹤（Tracking）| ❌ 無 |
| 資料完整性/排程/回補管理 | 嵌入預測追蹤底部 | ❌ 不干擾主功能 |

三者資料完全獨立，API 端點不共用，前端 handler 不交叉。
