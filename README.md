# 🎰 大樂透智能分析系統

專業的大樂透號碼分析與預測系統，使用數學回歸分析和機器學習算法進行智能預測。

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ 功能特色

### 📊 統計分析
- **號碼出現頻率分析**：柱狀圖顯示每個號碼的歷史出現次數
- **冷熱號分析**：識別熱門號碼（Top 10）和冷門號碼（Top 10）
- **號碼遺漏值分析**：折線圖顯示每個號碼距離上次出現的期數
- **號碼分佈趨勢**：環形圖展示號碼在不同區間的分佈

### 🔮 智能預測
提供四種預測算法：

1. **頻率回歸分析**
   - 基於歷史出現頻率
   - 適合長期穩定趨勢分析

2. **趨勢回歸分析**
   - 對近期數據賦予更高權重
   - 適合捕捉最新開獎趨勢

3. **綜合回歸模型**
   - 結合頻率(40%) + 趨勢(30%) + 遺漏值(30%)
   - 多維度全面分析

4. **機器學習模型**
   - 分析連號模式、區間平衡、奇偶比例
   - 智能化多維度分析

### 📜 歷史記錄
- 完整的開獎歷史表格
- 搜尋功能（期數或日期）
- 排序功能（最新/最舊優先）
- 分頁瀏覽

### 🗑️ 數據管理
- 上傳 CSV 檔案
- 載入範例數據
- 清除已載入數據

## 🚀 快速開始

### 方式一：直接開啟（簡單）

```bash
# 在瀏覽器中打開
open index.html
```

或直接雙擊 `index.html` 檔案

### 方式二：使用本地伺服器（推薦）

```bash
# 進入專案目錄
cd /Users/kelvin/Kelvin-WorkSpace/Lottery

# 使用 Python 啟動 HTTP 伺服器
python3 -m http.server 8081

# 在瀏覽器中打開
# http://localhost:8081
```

## 📂 專案結構

```
Lottery/
├── index.html              # 主頁面
├── styles.css              # 完整的 CSS 設計系統
├── README.md              # 本文檔
├── js/                    # JavaScript 模組
│   ├── app.js            # 主應用程式
│   ├── dataProcessor.js  # 數據處理模組
│   ├── analysis.js       # 統計分析引擎
│   └── prediction.js     # 預測引擎
├── data/                  # 數據文件
│   ├── sample-data.csv   # 範例數據
│   ├── converted_2024.csv # 2024年轉換數據
│   └── lotto649_realistic_data.csv
└── tools/                 # Python 工具腳本
    ├── convert_taiwan_lottery_csv.py  # CSV 轉換工具
    ├── download_lottery_data.py       # 數據下載工具
    ├── generate_realistic_data.py     # 數據生成工具
    ├── scrape_lottery_data.py         # 數據爬取工具
    └── universal_downloader.py        # 通用下載器
```

## 📖 使用指南

### 1️⃣ 載入數據

**選項 A：使用範例數據（最快）**
- 點擊「使用範例數據」按鈕
- 系統會自動載入 100 期的模擬大樂透數據

**選項 B：上傳自己的 CSV 檔案**
- 點擊「選擇檔案」按鈕
- 選擇符合格式的 CSV 檔案

**CSV 檔案格式範例：**
```csv
期數,日期,號碼1,號碼2,號碼3,號碼4,號碼5,號碼6,特別號
113000001,2024-01-02,5,12,18,23,35,42,7
113000002,2024-01-05,3,15,22,28,36,44,11
```

**格式要求：**
- 第一行必須是標題行
- 號碼必須在 1-49 之間
- 日期格式：YYYY-MM-DD
- 六個主要號碼不能重複

### 2️⃣ 查看統計分析

點擊導航列的「統計分析」，查看：
- 號碼出現頻率圖表
- 冷熱號分析
- 號碼遺漏值分析
- 號碼分佈趨勢

### 3️⃣ 進行智能預測

1. 點擊導航列的「智能預測」
2. 選擇預測方法（頻率/趨勢/綜合/機器學習）
3. 選擇樣本大小（30/50/100期或全部）
4. 點擊「開始預測」
5. 查看預測結果、信心度和分析報告

### 4️⃣ 查看歷史記錄

點擊導航列的「歷史記錄」：
- 瀏覽完整開獎記錄
- 使用搜尋功能查找特定期數或日期
- 切換排序方式

### 5️⃣ 清除數據

在數據概覽區域點擊「清除數據」按鈕，可以清空所有已載入的數據並重置系統。

## 🛠️ 技術架構

### 前端技術
- **HTML5**：語義化標籤
- **CSS3**：
  - CSS Variables 設計系統
  - Flexbox & Grid 佈局
  - 動畫與過渡效果
  - 玻璃擬態風格
- **JavaScript (ES6+)**：
  - 模組化架構
  - 類別導向設計
  - 事件驅動編程

### 數據視覺化
- **Chart.js 4.4.0**：圖表渲染

### 設計特色
- ✨ 現代化深色主題
- 🎨 漸層色彩設計
- 📱 完全響應式設計
- 🎭 流暢的動畫效果
- 🔮 互動式圖表

## 🔧 開發工具

### CSV 轉換工具
```bash
# 轉換台灣彩券官方 CSV 格式
python3 tools/convert_taiwan_lottery_csv.py
```

### 數據生成工具
```bash
# 生成模擬數據用於測試
python3 tools/generate_realistic_data.py
```

## ⚠️ 重要提醒

1. **僅供參考**：本系統的預測結果僅供學習和研究使用
2. **隨機性**：彩票開獎具有完全的隨機性
3. **理性投注**：請理性看待預測結果，量力而行
4. **無保證**：任何預測方法都無法保證準確性

## 🎯 預測算法說明

### 頻率回歸分析
```javascript
// 計算每個號碼的歷史出現頻率
score = (frequency / totalDraws)
```

### 趨勢回歸分析
```javascript
// 對近期數據賦予更高權重
score = Σ(appearance × weight) / totalWeight
```

### 綜合回歸模型
```javascript
// 多維度加權計算
score = frequency × 0.4 + trend × 0.3 + missing × 0.3
```

### 機器學習模型
- 連號模式分析
- 區間平衡評估
- 奇偶比例優化
- 多維度特徵提取

## 📊 系統架構

```
┌─────────────────────────────────────────┐
│           User Interface (HTML)          │
│  ┌─────────┬──────────┬──────────────┐  │
│  │ Upload  │ Analysis │ Prediction   │  │
│  │ Section │ Section  │ Section      │  │
│  └─────────┴──────────┴──────────────┘  │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│        Application Layer (app.js)        │
│  • Event Handling                        │
│  • UI State Management                   │
│  • Navigation Control                    │
└─────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌──────────────────┐   ┌──────────────────┐
│ DataProcessor    │   │ AnalysisEngine   │
│ • CSV Parsing    │   │ • Chart Rendering│
│ • Data Storage   │   │ • Statistics     │
│ • Validation     │   │ • Visualization  │
└──────────────────┘   └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ PredictionEngine │
                    │ • 4 Algorithms   │
                    │ • Confidence     │
                    │ • Reporting      │
                    └──────────────────┘
```

## 🎨 自訂設定

### 調整預測權重

編輯 `js/prediction.js`：

```javascript
// 綜合模型的權重分配
const freqScore = (frequency[i] / totalDraws) * 0.4;  // 頻率 40%
const trendScore = (weighted[i] / data.length) * 0.3; // 趨勢 30%
const missingScore = (missing[i] / maxMissing) * 0.3; // 遺漏 30%
```

### 修改配色方案

編輯 `styles.css` 中的 CSS Variables：

```css
:root {
    --primary-hue: 260;      /* 主色調 */
    --secondary-hue: 200;    /* 次要色調 */
    --accent-hue: 320;       /* 強調色調 */
}
```

## 🐛 疑難排解

### 問題：無法載入 CSV 檔案
- 確認檔案格式正確
- 檢查是否包含標題行
- 確認數據在有效範圍內（1-49）

### 問題：圖表無法顯示
- 確認已載入數據
- 檢查瀏覽器控制台是否有錯誤
- 確認 Chart.js 已正確載入

### 問題：預測結果不準確
- 這是正常的，彩票具有隨機性
- 增加樣本大小可能提高參考價值
- 嘗試不同的預測方法

## 📝 更新日誌

### v1.0.0 (2025-11-22)
- ✨ 初始版本發布
- 📊 四種預測算法
- 📈 完整統計分析功能
- 🎨 現代化 UI 設計
- 🗑️ 數據清除功能

## 📄 授權

MIT License

## 👨‍💻 開發者

如有問題或建議，歡迎提出 Issue 或 Pull Request。

---

**祝您使用愉快！** 🍀

*請記住：理性投注，娛樂為主。*
