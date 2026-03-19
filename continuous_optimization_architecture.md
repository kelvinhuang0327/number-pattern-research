# Phase 6 — Sustainable Optimization Framework（永續優化架構）

## 1. Strategy Lifecycle Management
1. 假說註冊：每個新策略先建立 `hypothesis_id`、理論來源、預期方向、檢定指標。
2. 沙盒驗證：先跑 150 期 smoke test（可執行性與資料完整性）。
3. 正式驗證：150/500/1500 walk-forward + permutation + Bonferroni。
4. 上線門檻：三視窗全正且 Bonferroni 通過。
5. 退場規則：連續 N 次重驗失敗即降級為 archived。

## 2. Automated Revalidation Triggers
- 觸發 A：新開獎資料入庫後（事件觸發）。
- 觸發 B：每週固定重驗（時間觸發）。
- 觸發 C：漂移警報（PSI/KS 超門檻）觸發即時重驗。

## 3. Drift Detection System
- 監控層：號碼邊際分布、區間分布、奇偶、和值、重號率。
- 漂移指標：PSI、KS、Jensen-Shannon divergence。
- 門檻策略：Warning / Critical 雙層級，Critical 直接凍結策略權重更新。

## 4. Version Control Structure
- `experiments/registry.jsonl`：每次實驗 append-only，不覆寫。
- `strategies/<id>/`：策略版本化（特徵、參數、驗證報告、hash）。
- `reports/`：phase 輸出與審計報告固定檔名 + 日期戳備份。

## 5. Failure Memory Archive
- 失敗策略必須記錄：失敗原因、失敗窗口、p-value、effect size、重現指令。
- 新策略提交前先比對失敗記憶，避免重複探索同型失敗。

## 6. Continuous Evolution Mode
- 探索池：僅允許小幅 mutation（防止高維暴衝）。
- 利用池：只保留通過嚴格門檻的信號，採風險預算加權。
- Online learning：僅在通過資料完整性與漂移檢查後才更新權重。
- 守門規則：任一核心檢定失敗即回退到上一個穩定版本。

## 7. Reproducibility Contract
- 每次運行強制固定 seed。
- 所有輸出檔附 SHA256 指紋。
- 每次研究必須附 assumptions log 與環境資訊（Python/NumPy/Sklearn 版本）。
