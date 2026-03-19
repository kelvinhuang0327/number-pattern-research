# 執行摘要：2026 彩券研究成果

**日期**：2026-03-19（持續更新）
**研究範圍**：今彩 539（5812期）/ 大樂透（2117期）/ 威力彩（1893期）

---

## 核心結論

**所有彩種長期負期望值，破產率 = 1.000。**
本系統研究目標為統計邊際測量，而非投注建議。

---

## 各遊戲研究結案狀態

### 今彩 539 — 維護模式（L82）

**研究結論**：信號空間窮盡。8 個假設（H001~H008）全部被拒絕。

| 假設 | 描述 | 結果 |
|------|------|------|
| H001 | 乘積互斥分數 | REJECT（互斥特徵乘積反效果） |
| H002 | 條件 ACB | REJECT（假性自相關） |
| H003 | Delta ACB | REJECT |
| H004 | Gap Entropy | REJECT |
| H005 | Pairwise Lift | REJECT |
| H006 | 頻率群集 | REJECT |
| H007 | Fourier w=1000 | REJECT |
| H008 | ACB 非線性 Gap | REJECT |

Zone/Sum 白噪音（Ljung-Box 全不顯著），Streak 無效（Lift<1.2x）。
ACB 超參數掃描確認現有設定最優（fd×0.4+gs×0.6, boundary 1.2）。
**MicroFish** McNemar p=0.132 未達標，重測條件：6010 期。

現役策略（持續 RSM 監控）：

| 策略 | 300p Edge | Sharpe | 狀態 |
|------|-----------|--------|------|
| midfreq_acb_2bet | +8.46% | 0.185 | PRODUCTION |
| acb_markov_midfreq_3bet | +8.50% | 0.174 | PRODUCTION |
| f4cold_5bet | +6.61% | 0.132 | PRODUCTION |
| acb_1bet | +3.27% | 0.092 | PRODUCTION |

---

### 大樂透 — 維護模式（L91）

**研究結論**：49C6 組合與公平隨機過程無法區分。

| 檢驗 | 統計量 | 結果 |
|------|--------|------|
| Shannon Entropy | p = 0.916 | 隨機 |
| Ljung-Box | p = 0.229 | 隨機 |
| Chi-Square 頻率 | p = 0.919 | 隨機 |
| Runs Test | p = 0.710 | 隨機 |
| 配對相關（BH校正） | 0 顯著 | 隨機 |
| Permutation Entropy | = 0.9999 | 隨機 |

信號強度：最佳 MI = 0.006 bits（佔基線熵 1.18%）。
MC 模擬：99th percentile edge = +0.778%，最佳觀測 +0.414% 在噪音帶內。
偵測功率：N=1817，最小可偵測邊際 = +0.789%（從未觀測到）。

策略進化嚴重過擬合（L86, L89, L90）：
- MicroFish 500p=+3.14% → full OOS=+0.303%（overfit ratio 10.35x）
- 進化策略 300p=+6.5% → full OOS=+0.12%

現役策略（維護監控，DriftDetector PSI=0.1018）：

| 策略 | 300p Edge | Sharpe | 狀態 |
|------|-----------|--------|------|
| regime_2bet | +3.64% | 0.140 | PRODUCTION |
| ts3_regime_3bet | +3.51% | 0.123 | PRODUCTION |
| p1_dev_sum5bet | +3.71% | 0.112 | PRODUCTION |

---

### 威力彩 — RSM 監控中

**研究結論**：部分信號有效（MidFreq/Fourier 可轉移），策略持正邊際，但 EV 為負。

跨遊戲信號轉移（L83-L84）：
- MidFreq：p=0.010 ✅（成功轉移）
- Fourier：p=0.035 ✅（成功轉移）
- ACB 邊界/mod3：❌（539 專屬，不可轉移）

| 策略 | 300p Edge | Sharpe | 狀態 |
|------|-----------|--------|------|
| fourier_rhythm_3bet | +3.16% | 0.090 | PRODUCTION |
| pp3_freqort_4bet | +3.40% | 0.088 | PRODUCTION |
| orthogonal_5bet | +2.76% | 0.068 | WATCH |

進化策略評估（L88）：full OOS edge=+3.42% p=0.005 三窗口全 PASS，
但 McNemar vs fourier_rhythm_3bet net=+16 p=0.458（等效，不替換）。

---

## 決策層研究（L99-L102）

**研究結論**：決策層降低損失但無法轉正 EV。

| Stage | 策略 | 效果 |
|-------|------|------|
| Stage 1 Gate | 過濾低信心期 | 539 WATCH（perm fail），BIG/POWER REJECT |
| Stage 2 Position Sizing | confidence threshold | edge_per_bet 改善，但 unconditional EV 仍為負 |
| Stage 3 Anti-Crowd | popularity 調整 | BIG_LOTTO delta=+1.04% ROI，perm p=0.257 不顯著 |
| Stage 4 Kelly | Kelly 公式 | Kelly=0（jackpot variance 主導） |

核心限制（L101）：選擇性下注的結構性稀釋——
unconditional_hr = cond_hr × (n_bet/n_oos)，
要讓 uncond_hr > flat_bl 需要 cond_hr ≈ 47%，遠超任何策略的實際達成率（~30-35%）。

---

## RL 研究結案（SB3 Track B）

**研究結論**：REJECTED — 零改善，建議維持靜態 RSM 生產線。

| 模型 | MC p-value | McNemar vs 靜態 | 結果 |
|------|-----------|----------------|------|
| PPO | 0.061 | net=−1 p=1.0 | REJECT |
| DQN | 0.207 | net=0 p=1.0 | REJECT |

失敗原因（L96-L98）：
- 置換測試 bug（shuffling 保留 mean，見 L96）
- 獎勵遊戲：cost-discount 使 agent 選低注低基準策略（L97）
- 資料不足：170 train draws，48 draw test（L98）

重測條件：≥200 新期數 + 獎勵函數修正。

---

## 系統能力邊界

| 能力項目 | 評估 |
|---------|------|
| 統計邊際測量 | ✅ 可靠（三窗口 + permutation + McNemar） |
| 策略監控（RSM） | ✅ 穩定（30/100/300p 滾動 Edge） |
| 信號發現 | ⚠️ 539/大樂透已窮盡，威力彩持續中 |
| 預測準確率 | ❌ 不可操作（EV < 0，ruin_prob = 1） |
| RL 動態策略選擇 | ❌ 資料不足，當前無法部署 |
| 投注建議 | ❌ 不提供，超出系統定位 |

---

## 下一個研究觸發點

1. **200 期 per-agent tracking**（降權評估，L77）
2. **50 期新資料**（假設優先度重評）
3. **RSM 300p Edge 跌破 +4%**（539 緊急假設生成）
4. **MicroFish 重測：6010 期**（McNemar net≥+20 + p<0.05）
5. **PP3-Z3Gap 2026-06 重評**（1500p>+2.43% + McNemar p<0.05）
6. **大樂透 DriftDetector PSI > 0.2**（urgent hypothesis generation）
