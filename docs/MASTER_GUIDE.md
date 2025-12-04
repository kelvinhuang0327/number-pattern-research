# 樂透專案整合指南（2025-11-30）

本指南整合所有關鍵文件，提供：快速上手、系統架構、策略目錄、後端 API、優化與自動學習、效能與記憶體實務、測試流程與疑難排解。

## 快速上手
- 後端：執行 `bash start_backend.sh`，確認 `http://localhost:5001/health`。
- 前端：直接開啟 `index.html`（現代瀏覽器）。
- 上傳數據：使用「上傳」區塊；避免賓果檔案。
- 預測：選擇方法；使用自動優化需啟動後端。

## 系統架構概覽
- 前端：`src/` 下的模組化原生 JS（App、PredictionEngine、UI、各策略）。
- 後端：`lottery-api/` 下的 FastAPI（預測、集成、優化、自動學習）。
- 數據：CSV 匯入；後端持久化；前端讀取展示。
- 韌性：健康檢查指數退避；後端失效自動停用相關策略。

## 策略目錄
- 統計：frequency、trend、bayesian、markov、monte_carlo、deviation、statistical、sum_range。
- 形態：odd_even、zone_balance、hot_cold、wheeling、number_pairs。
- 機器學習：random_forest（forest）、ml_features（映射到 forest）、ml_genetic（映射到 ensemble）。
- 集成：ensemble_weighted、ensemble_combined、ensemble_advanced。
- 後端優化：使用 `POST /api/predict-optimized`（自動學習權重）。
- 說明：Pattern Recognition、Cycle Analysis 為進階集成的內部元件，非獨立端點。

## 後端 API 一覽
- `GET /health` — 服務健康與模型可用性。
- `GET /api/models` — 模型/策略清單。
- `POST /api/predict` — 傳入歷史資料執行策略預測。
- `POST /api/predict-from-backend` — 使用後端資料；支援 `ensemble`、`statistical`、`random_forest` 等。
- `POST /api/predict-optimized` — 後端優化組合；`auto_optimize` 首選。
- `POST /api/auto-learning/optimize` — 執行遺傳演算法優化；Body 需含 `lotteryRules`（可含參數）。
- `POST /api/auto-learning/schedule/start` — 需在 Body 提供排程設定。
- `POST /api/auto-learning/schedule/stop` — 停止排程。
- `GET /api/auto-learning/schedule/status` — 查詢排程狀態。
- `GET /api/auto-learning/best-config` — 取得最佳權重。
- `POST /api/cache/clear` / `GET /api/cache/stats` — 緩存操作。
- `GET /api/data/stats` — 數據集統計；類型不存在時回傳 404。

## 優化與自動學習
- 遺傳演算法調參，結果保存在後端。
- 前端 `auto_optimize` 已改為呼叫 `predict-optimized`，可靠性更高。
- 最佳配置影響後端優化預測。
- 建議流程：上傳 → 優化 → 預測（優化）。

### 優化總結（2025-11-30）
- 信心度領先：`ensemble` 0.75–0.95、`ensemble_advanced` 0.78–0.92、`statistical` ~0.88。
- 集成投票新增：Pattern Recognition、Cycle Analysis。
- 高影響（Phase A）：
  - Bayesian 動態權重（+6–10%）
  - Frequency 自適應衰減（+5–8%）
  - Odd/Even 位置分佈（+8–12%）
  - Hot/Cold 動態窗口（+6–10%）
- 進階（Phase B）：
  - Markov 多階轉移（+8–12%）
  - Zone Balance 動態邊界（+10–15%）
  - Ensemble Advanced 時序關聯（+3–5%）
- 新策略：Entropy-Based（預期 0.75–0.80）。
- 預期整體提升：Phase A +8–15%；Phase B +15–25%（分階段）。

完整細節請參閱 `PREDICTION_OPTIMIZATION_ANALYSIS.md`（此處僅摘要以避免重複）。

## 效能與記憶體實務
- 樣本量保護：重型操作上限 500 期。
- 以後端為主的資料流，前端記憶體佔用較低；IndexedDB 可選。
- 健康檢查使用指數退避。
- 透過通知提示後端狀態與策略可用性。

## 測試流程
- 後端：health、models、predict、predict-optimized、cache、best-config。
- 前端：CSV 上傳（UTF-8/Big5）、快速預測、集成顯示、模擬年份篩選。
- 非功能：延遲採樣、記憶體觀察、基本可及性。

## 疑難排解
- `auto_optimize` 在 `predict-from-backend` 出現 500：改用 `predict-optimized`（已於 `PredictionEngine` 修正）。
- `/api/data/stats` 404：確認資料集存在；前端提供指引訊息。
- LSTM 未實作：透過健康檢查在 UI 中停用。
- Pattern/Cycle 獨立 400：改用集成策略（為內部元件）。

## 檔案地圖與參考
- 前端核心：`src/core/App.js`、`src/engine/PredictionEngine.js`。
- 策略：`src/engine/strategies/*`（含 `BackendOptimizedStrategy.js`）。
- 後端：`lottery-api/`（主應用與 unified predictor）。
- 樣式：`styles.css`、`styles_stats.css`、`styles_autolearning.css`。
- 更多文件：見下方「文件索引」。

---

# 文件索引（整合）

以下彙整原始文件以供深入參考，建議以本整合指南作為入口。

- 快速上手與指南：
  - `GUIDE.md`、`QUICK_START_PYTHON_BACKEND.md`、`BACKEND_OPTIMIZED_QUICKSTART.md`
- 架構與稽核：
  - `ARCHITECTURE.md`、`SYSTEM_ARCHITECTURE_AUDIT.md`、`INTEGRATION_COMPLETE_REPORT.md`
- 策略與預測：
  - `PREDICTION_METHODS_INVENTORY.md`、`LATEST_PREDICTION_METHODS_2025.md`、`PREDICTION_LOGIC_VERIFICATION.md`、`BACKEND_PREDICTION_LOGIC_VERIFICATION.md`
- 優化與自動學習：
  - `PREDICTION_OPTIMIZATION_ANALYSIS.md`、`OPTIMIZATION_COMPLETE_REPORT.md`、`OPTIMIZATION_SUMMARY.md`、`OPTIMIZATION_A_COMPLETE_REPORT.md`、`AUTO_LEARNING_V2_COMPLETE.md`、`SCHEDULE_OPTIMIZATION_GUIDE.md`、`SMART_LEARNING_GUIDE.md`
- 效能與記憶體：
  - `MEMORY_OPTIMIZATION.md`、`INDEXEDDB_OPTIMIZATION.md`、`SYNC_DATA_OPTIMIZATION_PLAN.md`
- 測試與效能評估：
  - `TEST_REPORT.md`、`BROWSER_TESTING_GUIDE.md`、`run_benchmark_and_report.py`
- 修正紀錄與歷史：
  - `ERROR_FIX_REPORT.md`、`HISTORY.md`、`LOTTERY_TYPE_FIX.md`、`AUTOLEARNING_FIX_REPORT.md`、`PYTHON_STRATEGY_MIGRATION.md`
- 工具與數據：
  - `tools/README.md`、`tools/*`、`data/*`

請以本整合指南快速導航，同時保留各原始文件作為深入參考。
