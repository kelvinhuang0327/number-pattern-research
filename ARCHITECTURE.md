# 📐 專案架構文檔

## 目錄結構

```
Lottery/
├── .gitignore              # Git 忽略規則
├── README.md              # 專案主文檔
├── package.json           # 專案元數據
├── index.html             # 主頁面（入口）
├── styles.css             # 全局樣式表
│
├── js/                    # JavaScript 模組
│   ├── app.js            # 主應用程式（UI 控制）
│   ├── dataProcessor.js  # 數據處理模組
│   ├── analysis.js       # 統計分析引擎
│   └── prediction.js     # 預測引擎
│
├── data/                  # 數據文件
│   ├── sample-data.csv   # 範例數據
│   ├── converted_2024.csv # 2024年數據
│   └── lotto649_realistic_data.csv
│
└── tools/                 # Python 工具腳本
    ├── README.md         # 工具說明文檔
    ├── convert_taiwan_lottery_csv.py
    ├── download_lottery_data.py
    ├── generate_realistic_data.py
    ├── scrape_lottery_data.py
    └── universal_downloader.py
```

## 模組說明

### 前端模組

#### 1. index.html
- **職責**：頁面結構和佈局
- **包含**：
  - Header（導航）
  - 四個主要區塊：數據上傳、統計分析、智能預測、歷史記錄
  - Footer

#### 2. styles.css
- **職責**：視覺設計和樣式
- **特色**：
  - CSS Variables 設計系統
  - 深色主題
  - 響應式佈局
  - 動畫效果

#### 3. js/app.js
- **職責**：主應用程式邏輯
- **功能**：
  - 事件處理
  - UI 狀態管理
  - 頁面導航
  - 通知系統
  - 數據清除

**主要類別**：
```javascript
class LotteryApp {
  - init()                 // 初始化
  - setupEventListeners()  // 設置事件
  - showSection()          // 切換頁面
  - handleFileUpload()     // 處理上傳
  - loadSampleData()       // 載入範例
  - clearData()            // 清除數據
  - displayHistory()       // 顯示歷史
  - showNotification()     // 顯示通知
}
```

#### 4. js/dataProcessor.js
- **職責**：數據處理和驗證
- **功能**：
  - CSV 解析
  - 數據驗證
  - 數據存儲
  - 統計計算

**主要類別**：
```javascript
class DataProcessor {
  - parseCSV()              // 解析 CSV
  - loadCSVData()           // 載入數據
  - loadSampleData()        // 載入範例
  - clearData()             // 清除數據
  - getData()               // 獲取數據
  - getDataStats()          // 數據統計
  - calculateFrequency()    // 計算頻率
  - calculateMissingValues() // 計算遺漏值
  - getHotNumbers()         // 熱門號碼
  - getColdNumbers()        // 冷門號碼
  - searchData()            // 搜尋數據
  - sortData()              // 排序數據
}
```

#### 5. js/analysis.js
- **職責**：統計分析和圖表渲染
- **功能**：
  - 圖表初始化
  - 數據視覺化
  - 統計分析

**主要類別**：
```javascript
class AnalysisEngine {
  - initializeCharts()           // 初始化圖表
  - createFrequencyChart()       // 頻率圖表
  - createMissingChart()         // 遺漏值圖表
  - createDistributionChart()    // 分佈圖表
  - displayHotColdNumbers()      // 冷熱號顯示
}
```

#### 6. js/prediction.js
- **職責**：預測算法和結果展示
- **功能**：
  - 四種預測算法
  - 信心度計算
  - 結果展示

**主要類別**：
```javascript
class PredictionEngine {
  - predict()                    // 執行預測
  - frequencyRegression()        // 頻率回歸
  - trendRegression()            // 趨勢回歸
  - combinedRegression()         // 綜合回歸
  - machineLearning()            // 機器學習
  - displayPrediction()          // 顯示結果
  - createProbabilityChart()     // 機率圖表
  - generateReport()             // 生成報告
}
```

### 後端工具

#### tools/ 目錄
包含 Python 工具腳本，用於：
- 數據下載
- 格式轉換
- 數據生成
- 網頁爬取

詳見 `tools/README.md`

## 數據流程

```
用戶上傳 CSV
    ↓
DataProcessor.parseCSV()
    ↓
數據驗證與存儲
    ↓
    ├─→ AnalysisEngine → 圖表渲染
    ├─→ PredictionEngine → 預測計算
    └─→ LotteryApp → 歷史顯示
```

## 預測算法流程

```
選擇預測方法
    ↓
獲取樣本數據
    ↓
    ├─→ 頻率回歸 → 計算出現頻率 → 排序選號
    ├─→ 趨勢回歸 → 加權計算 → 排序選號
    ├─→ 綜合回歸 → 多維度評分 → 排序選號
    └─→ 機器學習 → 模式分析 → 排序選號
    ↓
計算信心度
    ↓
生成報告
    ↓
顯示結果
```

## 設計模式

### 1. 模組化設計
- 每個 JS 文件負責單一職責
- 通過類別封裝功能
- 清晰的接口定義

### 2. 事件驅動
- 用戶交互觸發事件
- 事件監聽器統一管理
- 解耦 UI 和邏輯

### 3. 數據驅動
- 數據與視圖分離
- 數據變更自動更新 UI
- 單一數據源

## 性能優化

### 1. 延遲載入
```javascript
setTimeout(() => {
    this.analysisEngine.initializeCharts();
}, 100);
```

### 2. 分頁顯示
- 歷史記錄分頁（每頁 20 筆）
- 減少 DOM 渲染負擔

### 3. 事件委託
- 使用事件委託減少監聽器數量

## 擴展性

### 添加新的預測算法
1. 在 `PredictionEngine` 類別中添加新方法
2. 在 `index.html` 的 select 中添加選項
3. 在 `predict()` 方法中添加 case

### 添加新的圖表
1. 在 `AnalysisEngine` 類別中添加新方法
2. 在 `index.html` 中添加 canvas 元素
3. 在 `initializeCharts()` 中調用

### 添加新的數據來源
1. 在 `DataProcessor` 中添加解析方法
2. 支持新的 CSV 格式
3. 添加數據驗證規則

## 瀏覽器兼容性

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## 依賴項

### 外部庫
- **Chart.js 4.4.0**：圖表渲染
  - CDN: `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`

### 字體
- **Noto Sans TC**：中文字體
- **Orbitron**：數字顯示字體
- 來源：Google Fonts

## 安全性

### 1. 輸入驗證
- CSV 數據驗證
- 號碼範圍檢查（1-49）
- 格式驗證

### 2. XSS 防護
- 使用 `textContent` 而非 `innerHTML`
- 數據清理

### 3. 本地運行
- 純前端應用
- 無後端服務器
- 數據不上傳

## 維護指南

### 更新 Chart.js
1. 更新 CDN 連結
2. 檢查 API 兼容性
3. 測試所有圖表

### 修改樣式
1. 優先修改 CSS Variables
2. 保持一致的設計語言
3. 測試響應式佈局

### 添加功能
1. 遵循現有架構
2. 保持模組化
3. 添加註釋文檔

## 測試建議

### 功能測試
- [ ] CSV 上傳功能
- [ ] 範例數據載入
- [ ] 數據清除功能
- [ ] 四種預測算法
- [ ] 圖表渲染
- [ ] 歷史記錄搜尋
- [ ] 分頁功能

### 兼容性測試
- [ ] 不同瀏覽器
- [ ] 不同螢幕尺寸
- [ ] 觸控設備

### 性能測試
- [ ] 大數據集載入
- [ ] 圖表渲染速度
- [ ] 記憶體使用

## 未來規劃

### 短期
- [ ] 添加數據導出功能
- [ ] 支持更多彩票類型
- [ ] 改進預測算法

### 長期
- [ ] 後端 API 整合
- [ ] 用戶帳號系統
- [ ] 歷史預測追蹤
- [ ] 移動應用版本

---

**最後更新**：2025-11-22
