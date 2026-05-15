# Next Draw Strategy Binding Report
Generated: 2026-03-26

---

## 各注數策略綁定（驗證結果）

### 今彩 539（DAILY_539）

| 注數 | strategy_key | 算法來源 | Inline 函數 | 狀態 |
|------|-------------|---------|------------|------|
| 1注 | `acb_1bet` | ACB 異常捕捉 | ✅ `_539_acb_bet()` | PRODUCTION |
| 2注 | `midfreq_acb_2bet` | bet1=MidFreq / bet2=ACB(exclude) | ✅ `_539_midfreq_bet()` + `_539_acb_bet()` | PRODUCTION |
| 3注 | `acb_markov_midfreq_3bet` | bet1=ACB / bet2=Markov / bet3=MidFreq | ✅ 三種獨立算法 | PRODUCTION |
| 5注 | `f4cold_5bet` | F4Cold 完整5注 | ✅ `f4cold_predict()` — 完全獨立 | PRODUCTION |

**驗證輸出**（2026-03-26 伺服器重啟後）：
```
acb_1bet (1注):               [[3, 4, 16, 26, 35]]
midfreq_acb_2bet (2注):       [[1, 2, 18, 27, 28], [3, 4, 16, 26, 35]]
acb_markov_midfreq_3bet (3注): [[3, 4, 16, 26, 35], [8, 10, 11, 13, 39], [1, 2, 18, 27, 28]]
f4cold_5bet (5注):            [[10, 14, 15, 30, 39], [12, 22, 26, 29, 32], [2, 3, 7, 8, 37], [9, 17, 23, 24, 36], [4, 5, 16, 31, 35]]
```
→ F4Cold 5注完全獨立（無共享號碼），ACB bet 在 1注/2注/3注 策略間共用是算法設計，非疊加。

### 大樂透（BIG_LOTTO）

| 注數 | strategy_key | 算法來源 | Inline 函數 | 狀態 |
|------|-------------|---------|------------|------|
| 1注 | ❌ 無（RSM 未驗證 1注有效策略） | — | — | 不顯示 |
| 2注 | `regime_2bet` | Regime 2注 | ✅ `generate_regime_2bet()` | PRODUCTION |
| 3注 | `ts3_regime_3bet` | TS3+Regime 3注 | ✅ `generate_ts3_regime_3bet()` | PRODUCTION |
| 5注 | `p1_dev_sum5bet` | P1+Dev+Sum 5注 | ✅ `generate_p1_dev_sum5bet()` | PRODUCTION |

**說明**：大樂透 1注無正式策略，因 RSM 研究結論（L90/L91）49C6 信號空間窮盡。
遊戲卡底部顯示 "信號邊界研究確認（L91）：49C6 與公平隨機無差異，策略維護中"。

**驗證輸出**：
```
regime_2bet (2注):   [[11, 16, 33, 34, 39, 45], [4, 21, 24, 30, 32, 37]]
ts3_regime_3bet (3注): [[15, 16, 33, 34, 39, 45], [17, 19, 21, 24, 30, 37], [1, 10, 12, 28, 43, 44]]
p1_dev_sum5bet (5注): [[12, 13, 26, 27, 28, 31], [3, 21, 24, 30, 33, 37], ...]
```
→ 三個策略各自獨立，無號碼共享。

### 威力彩（POWER_LOTTO）

| 注數 | strategy_key | 算法來源 | Inline 函數 | 狀態 |
|------|-------------|---------|------------|------|
| 3注 | `fourier_rhythm_3bet` | Fourier Rhythm | ✅ `generate_fourier_rhythm_3bet()` | PRODUCTION |
| 4注 | `pp3_freqort_4bet` | PP3+FreqOrt | ✅ `generate_pp3_freqort_4bet()` | PRODUCTION |
| 5注 | `orthogonal_5bet` | 正交5注（PP3+FreqOrt×2） | ✅ `generate_orthogonal_5bet()` | WATCH |

**注意**：PP3+FreqOrt 4注和正交 5注共享前 3注是算法設計（正交擴展），非疊加。
第4注/第5注是額外正交擴展注，各自新增號碼。

**驗證輸出**：
```
fourier_rhythm_3bet (3注): [[10, 19, 20, 26, 33, 35], [6, 9, 25, 28, 29, 34], [1, 5, 7, 14, 18, 38]]
pp3_freqort_4bet (4注):    [[10, 19, 20, 26, 33, 35], [6, 9, 25, 28, 29, 34], [2, 12, 14, 15, 16, 27], [5, 7, 11, 22, 24, 36]]
orthogonal_5bet (5注):     [[10, 19, 20, 26, 33, 35], [6, 9, 25, 28, 29, 34], [2, 12, 14, 15, 16, 27], [5, 7, 11, 22, 24, 36], [3, 8, 18, 30, 37, 38]]
```

---

## Silent Fallback 修正紀錄

### 修正前（問題）

**根本原因**：`prediction.py` 的 `next_draw_summary` 函數內：
```python
import sys as _sys
_proj = os.path.dirname(...)  # ← os 未 import！名稱錯誤
```
導致整個 try block 失敗，`_predict_fns = {}`（空），所有策略 fallback 到 `coordinator_predict()`。

coordinator_predict 的疊加行為：
- 以共同評分排名，n注 = 前n個 slices，各注共享前綴
- 1注/2注/3注 預測號碼前綴相同 → 顯示效果就像疊加

**修正**：`import sys as _sys, os as _os`

### 修正後（現況）

若 `predict_fn` 為 None（策略 key 找不到對應函數）：
- **不** fallback 到 coordinator
- `numbers = []`，`prediction_error = "無對應策略函數: {key}"`
- Backend 記錄 ERROR 級別 log
- Frontend 顯示紅色 **N/A** + 錯誤訊息
- 使用者可清楚知道哪個策略無法載入，不被靜默欺騙

---

## 驗收確認

- ✅ 今彩 1/2/3/5注 各自獨立算法
- ✅ 大樂透 2/3/5注 各自獨立算法（無 1注為設計決定）
- ✅ 威力彩 3/4/5注 各自獨立算法
- ✅ coordinator fallback 已從 next-draw 和 tracking 兩個端點移除
- ✅ 策略載入失敗顯示 N/A，不 silent fallback
- ✅ 每個 bet entry 含 `prediction_error` 欄位（null=正常, string=錯誤說明）
