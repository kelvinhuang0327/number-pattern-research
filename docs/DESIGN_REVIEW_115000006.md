# 設計評審會議記錄：大樂透 1-2 注極致優化方案 (Design Review 115000006)

**日期**: 2026-01-15
**目標**: 在大樂透 (Big Lotto) 僅使用 **1-2 注** 的情況下，將成功率 (Match-3+) 提升 **5% 以上** (目標: >7.6%)，並提高大獎機率。
**出席人員**:
1.  **張架構 (程式架構派)** - 專注系統邊界、模組化
2.  **李理論 (方法理論派)** - 專注演算法、數學模型
3.  **王務實 (技術務實派)** - 專注落地、回測驗證

---

## 議程一：如何提升預測方法的成功率？(目標 > 7.6% @ 1-2 Bets)

**現狀**: 單注 ~2.67%, 雙注 (TME) ~5.33%。距離目標 7.6% 仍有差距。

### 🗣️ 專家發言

**李理論 (方法理論派)**:
"要用 2 注達到 7.6% (接近目前 4 注的效果)，傳統方法均值回歸已經到頂了。我們必須改變『賽道』。
我提出 **『精英縮圈 + 正交覆蓋』(Elite Shrinkage & Orthogonal Coverage)** 理論：
1.  **縮圈**: 先用機器學習 (XGBoost/LightGBM) 將 49 碼排除掉『絕對廢碼』，鎖定 18-20 碼的『精英池』。
2.  **正交**: 2 注不能是隨機的 2 注。第一注打『熱點』(Trend)，第二注必須打『盲點』(Gap/Cold)，兩者相關係數要趨近於 0。
這樣 2 注的覆蓋效率能達到一般 4 注的效果。"

**王務實 (技術務實派)**:
"理論好聽，但實作有風險。先前『7-Expert』過擬合就是教訓。
如果要提升勝率，我建議 **『動態視窗鎖定』(Dynamic Window Locking)**。我們發現某些策略在特定視窗 (如 500期) 表現特別好 (10%)。
我們可以實作一個 `WindowSelector`，每期自動跑 50-1000 期回測，選出『當下狀況』最好的視窗來預測。這比死守固定參數有效。"

**張架構 (程式架構派)**:
"系統上，我們需要支援 **『策略管道』(Strategy Pipeline)**。目前的 `UnifiedPredictionEngine` 比較像大雜燴。
建議重構為：`DataPreprocessor` (縮圈) -> `StrategyGenerator` (正交生成) -> `ConflictResolver` (去重/最佳化)。
這樣我們能把李理論的『縮圈』變成一個獨立的過濾層，所有策略都能受惠。"

**🏆 結論 (Action Item)**:
實作 **Smart-2Bet 系統**：
1.  **Layer 1**: 使用 **HPSB (基於頻率/遺漏)** 鎖定 24 碼高潛力區。
2.  **Layer 2**: 生成 2 注 **『互補型』** 號碼 (一注追熱、一注補冷)。
3.  預期目標：雙注合力突破 8.0%。

---

## 議程二：如何讓系統自動找出目前既有的最佳成功率？

### 🗣️ 專家發言

**張架構**:
"這題我來。我們需要一個 **『AutoML 搜尋代理』(Auto-Discovery Agent)**。
目前我們是手動改 `quick_predict.py`。系統應該有一個 `StrategyRegistry` (策略註冊表)，並配合一個背景運行的 `OptimizationWorker`。
它會 24 小時不斷排列組合：`[Method A, Method B, Window X, Weight Y]`，然後把結果寫入 `Leaderboard`。
`quick_predict.py` 只需要讀取 Leaderboard 的 No.1 即可。"

**王務實**:
"同意，但要考慮運算成本。大樂透 2000+ 期，全排列跑不完。
建議採用 **『遺傳算法』(Genetic Algorithm)** 的思路。先隨機生成 50 組策略參數，回測優勝劣汰，只需幾代就能收斂到最佳解，不用暴力破解。"

**🏆 結論 (Action Item)**:
開發 `tools/auto_discovery_agent.py`:
- 使用遺傳算法搜尋最佳 (Method, Window, Count) 組合。
- 自動更新 `docs/BEST_STRATEGY_LEADERBOARD.json`。

---

## 議程三：如何找出尚未規劃的有效預測方法？

### 🗣️ 專家發言

**李理論**:
"這是最困難的。我們需要引入 **『非結構化數據』** 的思考。
目前的預測都是基於『號碼』(1, 2, 3...)。
新方向：
1.  **圖特徵 (Graph Features)**: 號碼共現網路的 `PageRank` 或 `Community Detection`。號碼不是獨立的，是有社交圈的。
2.  **拓撲特徵 (Topological)**: 把開獎視為 49 維空間的點，看『持續同調』(Persistent Homology)。
3.  **Transformer Sequence**: 把開獎當作 NLP 句子處理，訓練一個小型 GPT 來預測『下一個詞』。"

**王務實**:
"GNN (圖神經網絡) 我們之前試過，效果一般。但我看好 **Transformer**。
只要模型夠小 (防過擬合)，它能捕捉到統計學看不到的『非線性序列模式』。我們可以用 `minGPT` 訓練一個 `LottoGPT-Lite`。"

**張架構**:
"要支援這個，系統需要開一個 **『AI Lab』實驗區**，與主預測引擎解耦。
新方法先在 Lab 跑 Sandbox 回測，勝率 > 基準線 + 10% 才能合併進主線。"

**🏆 結論 (Action Item)**:
1.  啟動 **"Lotto-Transformer"** 專案 (AI Lab)：將歷史開獎序列化，訓練 Transformer 模型。
2.  研究 **"Graph Clique"** (圖論)：找出高頻共現的號碼「幫派」。

---

## 議程四：一個有效的預測方法必須要經過滾動式資料的回測

### 🗣️ 專家發言

**王務實**:
"這是我的底線。所有新方法上線前，必須通過 `StandardBenchmark (seed=42)`。
規則非常簡單且殘酷：
1.  **Zero Leakage**: 預測第 N 期時，資料庫只能看到 1 到 N-1 期。
2.  **Hard Metrics**: 不看『感覺』，只看 Match-3+ 率、ROI、最大連敗 (Max Drawdown)。
3.  **Overfitting Check**: 全期勝率 vs 近 150 期勝率，衰減超過 10% 直接打回票 (如 7-Expert)。"

**李理論**:
"同意。另外建議加入 **『隨機性檢驗』**。
對比同參數下的『隨機選號』策略。如果你的策略勝率 5%，隨機也是 5%，那就是無效策略。"

**🏆 結論 (Action Item)**:
建立 **CI/CD Pipeline for Strategy**：
- 任何 PR 或新策略提交，自動觸發 `verify_backtest.py`。
- 輸出報告必須包含：`Win Rate`, `Leakage Check`, `Overfitting Score`。

---

## ✨ 最終決議 (Executive Summary)

針對使用者的 **1-2 注、提升 5%** 目標，評審團達成以下共識方案：

1.  **策略升級**: 開發 **"Smart-2Bet (Orthogonal)"** 系統。
    - **注1**: **Trend-Master** (統計+頻率, Window=500) -> 負責抓基本盤。
    - **注2**: **Gap-Hunter** (遺漏+偏差, Window=50) -> 負責抓回補號。
    - **縮圈**: 強制過濾掉近 50 期冷熱極端值，鎖定 24 碼精英區。
    - **預期**: 透過互補效應，將雙注聯集勝率推升至 **8% - 10%**。

2.  **自動化**: 部署 `auto_discovery` 腳本，每週自動尋找最佳參數配置。

3.  **新武器**: 在 AI Lab 嘗試 `Transformer` 模型，尋找非線性突破口。

4.  **守門員**: 嚴格執行 `OverfittingDetector`，低於 70 分的策略禁止上線。

---
**簽署**:
- 張架構 (Valid)
- 李理論 (Valid)
- 王務實 (Valid)
