> ⚠️ **本專案為學術統計研究，不提供投注建議，與台灣彩券股份有限公司無關。**

# Lotto Insight Platform

台灣彩券（今彩539 / 大樂透 / 威力彩）統計研究與分析平台。
本系統以實證研究為導向，追蹤策略表現並記錄研究發現。

**本系統不是預測工具，不提供投注建議。**

---

## 系統截圖

| 預測模擬測試 | 歷史開獎記錄 | 數據上傳中心 |
|---|---|---|
| ![模擬測試](docs/screenshots/simulation.png) | ![歷史記錄](docs/screenshots/history.png) | ![數據上傳](docs/screenshots/upload.png) |

---

## 研究核心結論（2026-03-19 更新）

| 遊戲 | 研究狀態 | 核心結論 |
|------|---------|---------|
| 今彩 539 | 維護模式 | 信號空間窮盡（L82）：H001~H008 全部 REJECT，現有策略 RSM 監控中 |
| 大樂透 | 維護模式 | 與公平隨機過程無法區分（L91）：6 項隨機性檢驗全通過，49C6 無可操作信號 |
| 威力彩 | RSM 監控中 | 部分策略持正 300p Edge，但所有遊戲 ruin_prob = 1.000 |

**重要**：所有遊戲長期負期望值已確認。「下期預測」頁面為研究成果視覺化，非投注推薦。

---

## 系統架構

```
後端 API   → http://localhost:8002   (FastAPI, lottery_api/)
前端介面   → http://localhost:8081   (Vanilla JS SPA, src/)
預測入口   → tools/quick_predict.py
策略監控   → RSM (lottery_api/engine/rolling_strategy_monitor.py)
```

---

## 專案規模

| 類型 | 檔案數 | 行數 |
|------|--------|------|
| Python `.py` | 4,551 | 1,811,215 |
| JavaScript `.js` | 112 | 30,385 |
| Markdown `.md` | 365 | 73,018 |
| HTML `.html` | 37 | 17,846 |
| CSS | — | 6,186 |
| **總計** | **8,293 檔** | **~190 萬行** |

---

## 快速啟動

```bash
# 啟動所有服務（前端 + 後端）
./start_all.sh

# 停止所有服務
./stop_all.sh

# 執行預測（命令列）
python3 tools/quick_predict.py all

# 查看前端介面
open http://localhost:8081
```

服務啟動後開啟 http://localhost:8081，在「下期預測」頁面查看 RSM 協調器輸出。

---

## 目錄結構

| 路徑 | 說明 |
|------|------|
| `lottery_api/` | FastAPI 後端、預測引擎、RSM 監控 |
| `src/` | Vanilla JS 前端單頁應用 |
| `tools/` | 回測、研究、維護腳本 |
| `docs/` | 技術文件與研究報告 |
| `memory/` | AI 自動記憶（跨 session 保存） |
| `research/` | 研究腳本與探索性分析 |
| `rejected/` | 已拒絕策略歸檔（含失敗原因） |
| `data/` | 策略監控快取（RSM 狀態） |

---

## 文件導覽

| 文件 | 說明 |
|------|------|
| [docs/MASTER_GUIDE.md](docs/MASTER_GUIDE.md) | 系統架構與當前策略現況 |
| [docs/EXECUTIVE_SUMMARY_2026.md](docs/EXECUTIVE_SUMMARY_2026.md) | 2026 研究成果執行摘要 |
| [docs/BACKTEST_PROTOCOL.md](docs/BACKTEST_PROTOCOL.md) | 回測規範與驗證標準 |
| [docs/BACKTEST_REPORTS_INDEX.md](docs/BACKTEST_REPORTS_INDEX.md) | 回測報告索引 |
| [docs/next_draw_page_release_summary.md](docs/next_draw_page_release_summary.md) | 下期預測頁面說明 |
| [docs/sb3_final_recommendation.md](docs/sb3_final_recommendation.md) | RL 研究最終結案 |
| [docs/decision_payout_report.md](docs/decision_payout_report.md) | 決策層分析報告 |
| [lottery_api/CLAUDE.md](lottery_api/CLAUDE.md) | 策略規範（主要參考） |

---

## 現役策略快覽

### 今彩 539（維護模式）

| 注數 | 策略 | 300p Edge | 狀態 |
|------|------|-----------|------|
| 1注 | acb_1bet | +3.27% | PRODUCTION |
| 2注 | midfreq_acb_2bet | +8.46% | PRODUCTION |
| 3注 | acb_markov_midfreq_3bet | +8.50% | PRODUCTION |
| 5注 | f4cold_5bet | +6.61% | PRODUCTION |

### 大樂透（維護模式）

| 注數 | 策略 | 300p Edge | 狀態 |
|------|------|-----------|------|
| 2注 | regime_2bet | +3.64% | PRODUCTION |
| 3注 | ts3_regime_3bet | +3.51% | PRODUCTION |
| 5注 | p1_dev_sum5bet | +3.71% | PRODUCTION |

### 威力彩（RSM 監控中）

| 注數 | 策略 | 300p Edge | 狀態 |
|------|------|-----------|------|
| 3注 | fourier_rhythm_3bet | +3.16% | PRODUCTION |
| 4注 | pp3_freqort_4bet | +3.40% | PRODUCTION |
| 5注 | orthogonal_5bet | +2.76% | WATCH |

---

## 風險聲明

### 繁體中文

> 本專案為學術研究與統計分析用途，**不構成任何投資或投注建議**。
>
> - 本系統不保證任何形式的中獎或盈利
> - 所有彩種均為負期望值遊戲（Expected Value < 0），持續參與必然虧損
> - 所有策略分析僅反映歷史統計特性，不代表未來表現
> - 使用本系統所衍生的任何損失，概由使用者自行承擔
> - 本系統為研究平台，非投注工具；「下期預測」頁面為研究成果視覺化，非中獎號碼推薦

**請理性對待彩券，量力而為。如有賭博問題，請聯繫：1800 諮詢專線。**

### English

> This project is for **research and statistical analysis purposes only**.
>
> - **Not financial advice**: Nothing in this system constitutes investment or betting advice
> - **No guarantee of winning**: Past statistical patterns do not predict future lottery outcomes
> - **Negative expected value**: All lottery games have negative EV; continued play results in guaranteed long-term losses (ruin probability = 1.000)
> - **Use at your own risk**: The authors are not liable for any financial losses incurred from using this system
> - **Research system only**: The "Next Draw" page visualizes research outputs, not winning number recommendations

**If you have a gambling problem, please seek help.**

---

## 交流與貢獻

本專案在統計信號探索上已遇到瓶頸（今彩539 L82 / 大樂透 L91），若你對機率分析、時間序列、彩券統計有興趣，歡迎一起交流新思路。

- 有新的分析角度或假設？歡迎開 **Issue** 討論
- 發現 bug 或資料問題？**PR 歡迎**
- 純粹想聊聊研究方向？也可以直接開 Issue

---

## 授權條款 / License

MIT License — Copyright (c) 2026 Kelvin. See [LICENSE](LICENSE) for details.
