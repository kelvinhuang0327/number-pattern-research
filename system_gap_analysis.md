# Phase 1 — Current System Audit（系統缺口分析）

## 1. 架構現況
- 核心引擎 `UnifiedPredictionEngine` 方法總數：87
- 其中 `_predict` 類方法：57
- 程式內隨機呼叫痕跡（`random`/`np.random`）：21
- 研究樣本：Power=1890、Big=2114、539=5800

## 2. 主要盲點
- 策略數量極多但缺乏單一統一的假說註冊與淘汰機制，易出現事後挑選（post-selection bias）。
- 多策略含隨機步驟，但未在所有路徑強制固定種子與輸出實驗指紋（hash）。
- 部分驗證腳本彼此採不同評估指標（M2+/M3+、單注/多注、不同視窗），可比性不足。
- 第二區（特別號）與第一區混合評估時，容易造成樣本空間不一致。

## 3. 過擬合風險
- 高維策略池 + 多重比較，若無 Bonferroni/FDR 強約束，假陽性機率高。
- 若在全樣本調參後回測同一樣本，會產生 leakage。
- 單次最佳化結果若未經三視窗穩定性檢查（150/500/1500），易屬短期噪音。

## 4. 未充分測試的特徵域（以本次 Phase 2 全域掃描結果反推）
- 全部遊戲皆未通過嚴格門檻之特徵域數量：19 / 19
- Frequency-based
- Gap and interval
- Markov chains
- Higher-order Markov
- Fourier / spectral
- Entropy measures
- Regime detection
- Cluster analysis
- Tail / extreme behavior
- Combinatorial covering designs
- Information theory metrics
- Bayesian inference
- Monte Carlo anomaly detection
- Player behavior modeling
- Distribution drift detection
- Interaction and multiplicative signals
- Ensemble weighting
- Non-linear transformations
- Random baseline falsification

## 5. 量化缺口指標
- 特徵檢定通過率：0/57（含跨遊戲）
- 模型檢定通過率：0/24

## 6. 優先修復建議
- 建立統一實驗登錄（假說ID、seed、資料切分、檢定門檻、輸出hash）。
- 把所有新策略預設納入：walk-forward + permutation + Bonferroni + 三視窗穩定性。
- 建立失敗策略記憶庫（禁止重複探索同型失敗假說）。
- 將特別號建模拆成獨立子系統，不與第一區主訊號混合宣稱。
