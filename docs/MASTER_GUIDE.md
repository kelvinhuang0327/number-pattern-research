# 系統整合指南

**最後更新**：2026-03-19
**版本**：v3（RSM 2026-03 架構）

本指南描述 Lotto Insight Platform 當前架構、服務入口、策略現況與開發規範。

---

## 1. 快速啟動

```bash
# 啟動所有服務
./start_all.sh

# 停止所有服務
./stop_all.sh

# 手動啟動後端
cd lottery_api && uvicorn main:app --host 0.0.0.0 --port 8002 --reload

# 手動啟動前端
python3 -m http.server 8081
```

服務地址：
- 後端 API：http://localhost:8002
- 前端介面：http://localhost:8081
- API 文件（Swagger）：http://localhost:8002/docs

---

## 2. 系統架構

```
frontend (src/)
    ↓ fetch
backend API (lottery_api/main.py, port 8002)
    ↓ routes/prediction.py
    ↓ routes/data.py
    ↓ engine/strategy_coordinator.py  ← RSM 加權協調
    ↓ engine/rolling_strategy_monitor.py  ← 策略監控
    ↓ data/lottery_v2.db  ← SQLite 歷史資料
    ↓ data/strategy_states_*.json  ← RSM 狀態（Edge/Trend/Alert）
```

### 前端（Vanilla JS SPA）

```
index.html
└── src/main.js
    └── src/core/App.js
        ├── handlers/NextDrawHandler.js   ← 下期預測頁
        ├── handlers/PredictionHandler.js
        ├── handlers/SimulationHandler.js
        ├── ui/UIManager.js
        └── services/ApiClient.js
```

### 後端（FastAPI）

| 模組 | 路徑 | 說明 |
|------|------|------|
| 主應用 | `lottery_api/main.py` | FastAPI app，路由掛載 |
| 預測端點 | `lottery_api/routes/prediction.py` | 所有預測 API |
| 資料端點 | `lottery_api/routes/data.py` | 歷史資料 API |
| 策略協調器 | `lottery_api/engine/strategy_coordinator.py` | RSM 加權多代理人 |
| RSM 監控 | `lottery_api/engine/rolling_strategy_monitor.py` | 滾動策略監控 |
| 漂移偵測 | `lottery_api/models/regime_monitor.py` | DriftDetector + RegimeMonitor |

---

## 3. 核心 API 端點

| 端點 | 說明 |
|------|------|
| `GET /health` | 服務健康檢查 |
| `GET /api/next-draw-summary` | 下期預測（RSM 協調器輸出，三遊戲） |
| `GET /api/predict-coordinator` | 單遊戲協調器預測 |
| `GET /api/history/{lottery_type}` | 歷史開獎記錄 |
| `GET /api/strategy-states/{lottery_type}` | RSM 策略狀態 |
| `POST /api/update-results` | 更新最新開獎結果 |

---

## 4. 預測入口

**唯一正式預測入口**：`tools/quick_predict.py`

```bash
# 預測所有彩票（各遊戲最佳策略）
python3 tools/quick_predict.py all

# 指定遊戲與注數
python3 tools/quick_predict.py 539 3
python3 tools/quick_predict.py biglotto 5
python3 tools/quick_predict.py power 4
```

---

## 5. 策略現況（2026-03-19）

### 今彩 539（維護模式）

信號空間已窮盡（L82）：H001~H008 全部 REJECT，Zone/Sum 白噪音，Streak 無效。
現有策略持續 RSM 監控，無新假設可測試。

| 策略鍵 | 注數 | 300p Edge | Sharpe | 狀態 |
|-------|------|-----------|--------|------|
| acb_1bet | 1注 | +3.27% | 0.092 | PRODUCTION |
| midfreq_acb_2bet | 2注 | +8.46% | 0.185 | PRODUCTION |
| acb_markov_midfreq_3bet | 3注 | +8.50% | 0.174 | PRODUCTION |
| f4cold_5bet | 5注 | +6.61% | 0.132 | PRODUCTION |

### 大樂透（維護模式）

信號邊界研究確認（L91）：49C6 與公平隨機過程無法區分。6 項隨機性檢驗全通過。
零信號達 p<0.05，進入維護模式。DriftDetector 監控中（PSI=0.1018，輕微偏移）。

| 策略鍵 | 注數 | 300p Edge | Sharpe | 狀態 |
|-------|------|-----------|--------|------|
| regime_2bet | 2注 | +3.64% | 0.140 | PRODUCTION |
| ts3_regime_3bet | 3注 | +3.51% | 0.123 | PRODUCTION |
| p1_dev_sum5bet | 5注 | +3.71% | 0.112 | PRODUCTION |

### 威力彩（RSM 監控中）

部分策略持正邊際。MidFreq+Fourier 信號組合 VALIDATED，監控中。
PP3-Z3Gap WATCH（2026-06 重評）。

| 策略鍵 | 注數 | 300p Edge | Sharpe | 狀態 |
|-------|------|-----------|--------|------|
| fourier_rhythm_3bet | 3注 | +3.16% | 0.090 | PRODUCTION |
| pp3_freqort_4bet | 4注 | +3.40% | 0.088 | PRODUCTION |
| orthogonal_5bet | 5注 | +2.76% | 0.068 | WATCH |

---

## 6. RSM 狀態檔案

策略狀態保存於 `lottery_api/data/strategy_states_*.json`。
欄位：`edge_300p`、`edge_100p`、`edge_30p`、`trend`、`alert`、`sharpe_300p`、`update_count`。

狀態衍生規則（`_derive_strategy_status()`）：
- `edge_300p ≥ 0.03` + `STABLE/IMPROVING` → **PRODUCTION**
- `0 < edge_300p < 0.03` → **WATCH**
- `edge_300p ≤ 0` → **ADVISORY_ONLY**
- `alert = True` → 降為 **WATCH**

---

## 7. 研究結果摘要

| 結論 | 詳細 |
|------|------|
| 今彩 539 信號空間窮盡 | L82：H001-H008 全部 REJECT，ACB 設計無改善空間 |
| 大樂透與隨機無差異 | L91：Shannon/LB/Chi2/Runs/Pairs/PE 全通過，最佳 MI=0.006 bits |
| 決策層效果有限 | L99-L102：Stage 2 position sizing 降低損失但無法轉正 EV |
| RL 研究結案 | SB3 PPO/DQN：零改善，McNemar net=−1/0，REJECTED |
| 所有遊戲負 EV | ruin_prob = 1.000，長期必然虧損 |

---

## 8. 開發規範

- 新策略需通過 1500期三窗口驗證（150/500/1500）
- 統計顯著性 p < 0.05 + permutation test + walk-forward OOS
- 替換現有策略需 McNemar p < 0.05（L48）
- 邊際效率 > 80% 才合格（L14）
- 詳細規範見 [lottery_api/CLAUDE.md](../lottery_api/CLAUDE.md)

---

## 9. 文件索引

| 文件 | 類型 | 說明 |
|------|------|------|
| `docs/EXECUTIVE_SUMMARY_2026.md` | 摘要 | 2026 研究成果 |
| `docs/BACKTEST_PROTOCOL.md` | 規範 | 回測標準 |
| `docs/BACKTEST_REPORTS_INDEX.md` | 索引 | 所有回測結果 |
| `docs/next_draw_page_release_summary.md` | 功能說明 | 下期預測頁 |
| `docs/sb3_final_recommendation.md` | 研究結案 | RL Track B 結案 |
| `docs/decision_payout_report.md` | 研究結案 | 決策層分析 |
| `docs/failure_pattern_analysis.md` | 研究洞察 | 失敗模式分類 |
| `memory/MEMORY.md` | AI 記憶 | 跨 session 狀態 |
| `memory/lessons.md` | 教訓 | L1-L102 完整記錄 |
