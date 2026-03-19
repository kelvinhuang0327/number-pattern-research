# SYSTEM_MAP.md

## 1. 文件目的
本文件用於描述本專案的系統架構、模組用途、依賴關係、API、資料庫、外部服務、環境配置、測試方式與高風險區域。

本文件的目的是幫助：
- 新進工程師快速理解專案
- AI Agent 正確分析與修改程式
- 降低因不熟悉架構造成的誤改風險
- 提升需求分析、開發與測試效率

---

## 2. 專案摘要

### 2.1 專案名稱
- 專案名稱：Lottery AI Quant Research Platform
- 專案代號：LotteryNew
- 專案類型：Hybrid (Web Frontend + Python Backend + AI Prediction)

### 2.2 核心目的
- 提供全自動化的彩券量化研究與預測系統。
- 實現策略發現、統計驗證、遺傳演算法演化與集成預測。
- 提供動態方差監控 (Waterline Monitor) 以偵測系統效能區間。

### 2.3 主要使用者
- 一般用戶：進行彩券號碼預測與統計分析。
- 研發工程師：開發新預測策略與特徵工程。
- 量化研究員：進行回測與統計顯著性驗證。

---

## 3. 技術棧總覽

### 3.1 Backend
- 語言：Python 3.9+
- 框架：FastAPI
- ORM / SQL 工具：SQLite3, Pandas
- API 規格：RESTful (JSON)
- 任務排程工具：APScheduler / Internal polling
- Queue / MQ：N/A
- Cache：N/A (Local JSON persistence)

### 3.2 Frontend
- 語言：HTML5, JavaScript (ESM)
- 框架：Vanilla JS (No Framework)
- UI Library：Lucide Icons, Chart.js
- 狀態管理：Internal App Class (State Pattern)
- Router：UIManager (Section-based)
- 打包工具：N/A (ES Modules)

### 3.3 Data / AI / Prediction
- 資料處理工具：Pandas, NumPy
- 模型訓練工具：Scikit-learn (Random Forest, etc.), XGBoost (Integrated)
- 特徵工程框架：Custom implementation in `features/`
- 回測工具：Internal Simulation Engine
- 排程流程：Idea -> Simulation -> Backtest -> Validation -> Evolution -> Ensemble
- 模型輸出位置：JSON files under `strategies/` or `data/`

### 3.4 Infra / DevOps
- Runtime：Localhost / Python Runtime
- Container：N/A
- CI/CD：N/A
- 部署方式：Manual execution
- Observability：Logging to console / Internal dashboard
- Secret 管理：N/A (Local config)

---

## 4. 目錄結構說明

```text
/Users/kelvin/Kelvin-WorkSpace/LotteryNew/
├─ src/
│  ├─ core/              # 核心邏輯 (App, DataProcessor)
│  ├─ engine/            # 預測引擎 (PredictionEngine, QuickPrediction)
│  ├─ ui/                # UI 組件與處理器
│  ├─ data/              # 前端資料服務
│  └─ utils/             # 工具函數
├─ lottery_api/
│  ├─ routes/            # API 路由
│  ├─ models/            # 後端模型 (RegimeMonitor)
│  └─ ...
├─ data/                 # SQLite 資料庫與 JSON 歷史數據
├─ features/             # 特徵工程邏輯
├─ strategies/           # 策略註冊表與輸出
├─ rejected/             # 遭拒絕的策略存檔
├─ memory/               # 任務記錄 (todo.md)
├─ index.html            # 主入口
├─ professional-design.css # 主樣式 (Premium Dark Blue Glow)
└─ ...
```

---

## 5. 功能顯隱狀態紀錄
部分功能目前處於隱藏或受限狀態：
- **智能預測 (Prediction)**：部分高級 AI 模型（如 LSTM/Transformer）需依賴後端權重文件。
- **自動學習 (AutoLearning)**：需確保後端伺服器在 8002 端口運行。
- **聰明包牌 (Smart Betting)**：部分生成邏輯在特定彩種下隱藏。
- **歷史記錄 (History)**：僅在數據加載成功後顯示。
