# Lottery Prediction System

This repository now includes a consolidated documentation entry point: `docs/MASTER_GUIDE.md`. Start there for architecture, strategy catalog, backend APIs, optimization flow, performance practices, testing, and troubleshooting.

## Quick Links
- Master Guide: `docs/MASTER_GUIDE.md`
- Frontend entry: `index.html`
- Backend start: `start_backend.sh` and `http://localhost:5001/health`
- Data samples: `data/` folder and upload UI

For detailed historical and specialized docs, see the index inside the master guide.
# 🎰 大數據智能分析系統

專業的大樂透號碼分析與預測系統，採用協作預測與統計分析技術。

![Version](https://img.shields.io/badge/version-2.0-blue.svg)
![Tests](https://img.shields.io/badge/tests-109%20passed-success.svg)
![Coverage](https://img.shields.io/badge/coverage-74%25-yellow.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ 核心功能

### 🎯 智能預測（13種策略）

#### 協作預測系統 ⭐ 推薦
- **🧠 自適應接力** - 智能分析數據特徵，自動選擇最佳策略
- **🏃 接力預測** - 三階段層層篩選（49→20→10→6）
- **🤝 協作預測** - 七模型投票共識決策

#### 核心統計方法（6種）
- 頻率分析、趨勢分析、綜合回歸
- 偏差追蹤、蒙地卡羅、馬可夫鏈

#### 統一集成策略（5種模式）
- 加權集成、提升集成、綜合集成
- 共現分析、特徵加權

#### 機器學習（3種算法）
- 特徵加權機器學習
- 隨機森林
- 遺傳算法

#### 民間策略（4種）
- 奇偶平衡、區間分佈
- 冷熱混合、和值範圍

### 📊 統計分析
- 號碼出現頻率分析（柱狀圖）
- 冷熱號分析（Top 10）
- 號碼遺漏值分析（折線圖）
- 號碼分佈趨勢（環形圖）

### 📜 數據管理
- 上傳 CSV 檔案
- 載入範例數據
- 完整歷史記錄查詢

## 🚀 快速開始

```bash
# 1. 安裝依賴
npm install

# 2. 運行測試（可選）
npm test

# 3. 啟動應用
npm start
# 訪問 http://localhost:8081

# 或使用 Python
python3 -m http.server 8081

# 或直接開啟
open index.html
```

### 基本流程
```
1. 載入數據（範例或上傳 CSV）
2. 選擇預測方法（推薦：🧠 自適應接力）
3. 開始預測
4. 查看結果和統計圖表
```

### ⚡ 記憶體優化
處理大量數據時，系統已內建雙重優化機制：

#### 1. IndexedDB 按需載入 ⭐ 推薦
- **主存儲**：所有數據存儲在 IndexedDB（磁碟）
- **按需載入**：記憶體只保留當前需要的數據
- **效果**：支援無限量數據，記憶體使用減少 98%

#### 2. 記憶體自動限制
- **自動限制**：記憶體中最多保留 30,000 筆數據
- **智能監控**：每 10 秒檢查記憶體使用率
- **建議系統**：自動提供優化建議

**詳細說明**：
- [INDEXEDDB_OPTIMIZATION.md](./INDEXEDDB_OPTIMIZATION.md) - IndexedDB 按需載入原理 ⭐
- [MEMORY_OPTIMIZATION.md](./MEMORY_OPTIMIZATION.md) - 記憶體優化指南

### CSV 格式
```csv
期號,日期,號碼1,號碼2,號碼3,號碼4,號碼5,號碼6,特別號
113000001,2024-01-01,05,12,18,23,35,42,16
```

---

## 📚 文檔

- **[GUIDE.md](./GUIDE.md)** - 完整使用與開發指南（含測試指南）
- **[TEST_REPORT.md](./TEST_REPORT.md)** - 詳細測試報告（109 測試案例）
- **[INDEXEDDB_OPTIMIZATION.md](./INDEXEDDB_OPTIMIZATION.md)** - IndexedDB 按需載入原理 ⚡ NEW
- **[MEMORY_OPTIMIZATION.md](./MEMORY_OPTIMIZATION.md)** - 記憶體優化指南 ⚡ NEW
- **[HISTORY.md](./HISTORY.md)** - 重構歷史、架構演進
- **[tools/README.md](./tools/README.md)** - Python 數據工具說明
- **[docs/STRATEGY_AND_OPTIMIZATION.md](./docs/STRATEGY_AND_OPTIMIZATION.md)** - 策略矩陣 + 優化計劃（整合文件）

## 📂 專案架構

```
Lottery/
├── README.md               # 本文件
├── GUIDE.md                # 完整使用與開發指南（含測試）
├── HISTORY.md              # 重構歷史與架構
├── TEST_REPORT.md          # 測試報告（109 測試）
├── index.html              # 主頁面
├── styles.css              # 樣式
├── package.json            # 專案配置
├── jest.config.js          # Jest 測試配置
├── babel.config.js         # Babel 轉譯配置
│
├── src/                    # 主程式碼（v2.0 重構）
│   ├── main.js
│   ├── core/               # 核心功能
│   │   ├── App.js
│   │   └── DataProcessor.js
│   ├── engine/             # 預測引擎
│   │   ├── PredictionEngine.js
│   │   └── strategies/     # 21 種策略
│   ├── data/               # 數據服務
│   │   └── StatisticsService.js
│   ├── ui/                 # UI組件
│   │   ├── UIManager.js
│   │   └── ChartManager.js
│   └── utils/              # 工具
│       └── Constants.js
│
├── __tests__/              # 測試檔案（6 套件）
│   ├── Constants.test.js
│   ├── DataProcessor.test.js
│   ├── StatisticsService.test.js
│   ├── FrequencyStrategy.test.js
│   ├── CollaborativeStrategy.test.js
│   └── PredictionEngine.integration.test.js
│
├── data/                   # 數據檔案
├── archive/                # 歸檔檔案
└── tools/                  # Python 工具腳本
    └── *.py
```

**詳細架構說明**：請參考 [HISTORY.md](./HISTORY.md#系統架構)

---

## 🎯 預測方法推薦

| 使用場景 | 推薦方法 | 原因 |
|---------|---------|------|
| 新手使用 | 🧠 自適應接力 | 自動選擇最佳策略 |
| 數據 < 50期 | 🧠 自適應接力 | 智能適應小樣本 |
| 數據 50-500期 | 🏃 接力預測 | 三階段高效篩選 |
| 數據 500+期 | 🤝 協作預測 | 多模型交叉驗證 |
| 快速參考 | 綜合回歸 | 平衡穩健 |

**詳細說明**：請參考 [GUIDE.md](./GUIDE.md#預測方法)

---

## ⚠️ 重要提醒

**理性認知**：
- 樂透是純隨機事件，無法保證預測準確性
- 預測結果僅供學習研究參考
- 請理性投注，適度娛樂

---

## 🔧 技術棧

- **前端**：HTML5 + CSS3 + JavaScript ES6+
- **圖表**：Chart.js 4.4.0
- **架構**：MVC + Strategy Pattern
- **環境**：瀏覽器（無需構建工具）

---

## 📝 更新日誌

### v2.1.0 (2025-12-02) 🚀 性能與穩定性更新

#### ⚡ 連線穩定性優化
- **後端異步處理**：引入 Thread Pool Executor，將 CPU 密集型預測任務移出主事件循環，徹底解決高負載時的阻塞問題。
- **前端自動重試**：實作指數退避（Exponential Backoff）重試機制，自動處理瞬時網絡錯誤與超時。
- **非阻塞架構**：健康檢查與輕量請求不再受重型預測任務影響，系統響應速度顯著提升。

#### 🔧 技術改進
- **並發處理**：支援多個預測請求並發執行。
- **錯誤處理**：優化超時與網絡錯誤的提示訊息。

### v2.0.0 (2025-11-25) ⭐ 重大更新

#### ✨ 新功能
- **測試框架** - Jest 整合，109 測試案例（100% 通過）
- **協作預測系統** - 3 種模式（接力/合作/混合）
- **統一集成策略** - 5 種集成模式
- **機器學習策略** - 3 種 ML 算法

#### 🔧 重構改進
- **Phase 1** - 基礎清理（29→21 策略）
- **Phase 2** - 協作預測整合
- **Phase 3** - 文檔整理（13→3 核心文檔）
- **Phase 4** - 測試框架建立（109 測試全通過）

#### 📊 測試統計
- ✅ **測試案例**: 109 個（100% 通過）
- ✅ **測試套件**: 6 個
- ✅ **核心引擎覆蓋率**: 100%
- ✅ **策略覆蓋率**: 97.9%
- ✅ **執行時間**: 1.47 秒

#### 🏗️ 架構優化
- 模組化設計
- ES6+ 語法
- 策略模式
- 依賴注入
- 完整測試覆蓋

詳細內容請參閱：
- [重構歷程](./HISTORY.md)
- [測試報告](./TEST_REPORT.md)

### v1.0.0 (2025-11-22)
- ✨ 初始版本發布

---

## 📄 授權

MIT License

---

**祝您使用愉快！** 🍀

*請記住：理性投注，娛樂為主。*
