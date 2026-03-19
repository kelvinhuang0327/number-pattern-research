# 策略快速參考矩陣（2026-03-19）

本文件提供三遊戲現役策略的標準化參考。
所有 Edge 數值來自 RSM 滾動回測，非保證報酬。

---

## 今彩 539（5812期資料，維護模式）

信號空間窮盡（L82）。現有策略持續 RSM 監控，無新假設測試。

| 注數 | 策略鍵 | 策略描述 | 300p Edge | Sharpe | 狀態 |
|------|-------|---------|----------|--------|------|
| 1 | `acb_1bet` | ACB 邊界加成 | +3.27% | 0.092 | PRODUCTION |
| 2 | `midfreq_acb_2bet` | 中頻段 × ACB | +8.46% | 0.185 | PRODUCTION |
| 3 | `acb_markov_midfreq_3bet` | ACB × Markov × MidFreq | +8.50% | 0.174 | PRODUCTION |
| 5 | `f4cold_5bet` | 四冷號融合 | +6.61% | 0.132 | PRODUCTION |

**設計原則**：ACB = fd×0.4 + gs×0.6, boundary=1.2（n≤8, n≥35）。
**負面紀錄**：f4cold_3bet 30p=-0.50% ⚠️，但 300p=+0.17% STABLE，不降權。

---

## 大樂透（2117期資料，維護模式）

L91：49C6 與公平隨機過程無法區分。零信號達 p<0.05。
策略為歷史觀測所產生，無法保證未來效果。

| 注數 | 策略鍵 | 策略描述 | 300p Edge | Sharpe | 狀態 |
|------|-------|---------|----------|--------|------|
| 2 | `regime_2bet` | 機制切換 2注 | +3.64% | 0.140 | PRODUCTION |
| 3 | `ts3_regime_3bet` | TS3 × 機制切換 | +3.51% | 0.123 | PRODUCTION |
| 5 | `p1_dev_sum5bet` | P1偏差 × Sum約束 | +3.71% | 0.112 | PRODUCTION |

**監控警告**：DriftDetector PSI=0.1018（輕微偏移，持續監控）。
**邊際效率急降**：1注 eff=0.83, 2注=0.64, 3注=0.49。

---

## 威力彩（1893期資料，RSM 監控中）

部分策略持正邊際。MidFreq 和 Fourier 信號可從 539 轉移（L83）。

| 注數 | 策略鍵 | 策略描述 | 300p Edge | Sharpe | 狀態 |
|------|-------|---------|----------|--------|------|
| 3 | `fourier_rhythm_3bet` | 傅立葉韻律 3注 | +3.16% | 0.090 | PRODUCTION |
| 4 | `pp3_freqort_4bet` | PP3 × 頻率正交 | +3.40% | 0.088 | PRODUCTION |
| 5 | `orthogonal_5bet` | 正交 5注 | +2.76% | 0.068 | WATCH |

**RSM 監控中（待升格評估）**：
- `midfreq_fourier_2bet`：300p=+0.08%
- `midfreq_fourier_mk_3bet`：300p=+1.83%

---

## 狀態定義

| 狀態 | 條件 | 說明 |
|------|------|------|
| PRODUCTION | edge_300p ≥ 3% + STABLE/IMPROVING | 已驗證，RSM 監控中 |
| WATCH | 0 < edge_300p < 3% 或有警告 | 信號正向但較弱，持續觀察 |
| ADVISORY_ONLY | edge_300p ≤ 0% | 近期偏弱，僅供參考 |
| MAINTENANCE | 信號空間窮盡 | 維護模式，無新假設 |

---

## 注意事項

- 300p Edge 為歷史滾動估計，非保證報酬
- 三窗口（150/500/1500p）一致性比單窗口更可靠
- McNemar 測試確認替換優於現有策略（p<0.05）
- 所有遊戲 ruin_prob = 1.000，請勿據此進行實際投注
