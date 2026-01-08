# 📖 大樂透智能分析系統 - 完整指南

## 📚 目錄
- [快速開始](#快速開始)
- [使用說明](#使用說明)
- [預測方法](#預測方法)
- [開發指南](#開發指南)
- [測試指南](#測試指南)
- [工具腳本](#工具腳本)

---

## 🚀 快速開始

### 啟動方式

```bash
# 方法 1: 本地伺服器（推薦）
python3 -m http.server 8000
# 訪問 http://localhost:8000

# 方法 2: 直接開啟
open index.html
```

### 基本流程

```
1. 載入數據（範例數據或上傳 CSV）
   ↓
2. 選擇預測方法
   ↓
3. 開始預測
   ↓
4. 查看結果和統計圖表
```

---

## 📊 使用說明

### 載入數據

#### 使用範例數據
點擊「載入範例數據」→ 自動載入 100+ 期測試數據

#### 上傳 CSV 檔案
**格式要求**：
```csv
期號,日期,號碼1,號碼2,號碼3,號碼4,號碼5,號碼6,特別號
113000001,2024-01-01,05,12,18,23,35,42,16
```

**規則**：
- ✅ 包含標頭行
- ✅ 號碼範圍 1-49
- ✅ 日期格式 YYYY-MM-DD
- ✅ 號碼前置零（如 05）

### 統計分析

查看圖表：
- **頻率圖**：號碼出現次數
- **遺漏值圖**：距上次出現期數
- **分布圖**：號碼區間分布
- **冷熱號**：熱門 Top 10 + 冷門 Top 10

---

## 🎯 預測方法

### 核心統計（6種）

#### 1. 頻率分析
```
原理：統計號碼歷史出現次數
適用：長期數據（100+ 期）
```

#### 2. 趨勢分析
```
原理：分析近期號碼變化趨勢
適用：中短期數據（50-200 期）
```

#### 3. 綜合回歸 ⭐
```
原理：結合頻率、趨勢、位置等多維特徵
適用：所有數據量
推薦：新手使用
```

#### 4. 偏差追蹤
```
原理：尋找偏離平均值的號碼
適用：大樣本（200+ 期）
```

#### 5. 蒙地卡羅
```
原理：隨機模擬 10,000 次抽樣
適用：機率分析
```

#### 6. 馬可夫鏈
```
原理：狀態轉移機率分析
適用：序列預測
```

### 統一集成（5種）

#### 7-11. UnifiedEnsemble
```
模式 1: weighted - 加權集成
模式 2: boosting - 提升集成
模式 3: combined - 綜合集成
模式 4: cooccurrence - 共現分析
模式 5: feature_weighted - 特徵加權
```

### 機器學習（3種）

#### 12-14. ML Strategy
```
算法 1: feature_weighted - 特徵加權機器學習
算法 2: random_forest - 隨機森林
算法 3: genetic - 遺傳算法
```

### 協作預測（3種）⭐ 推薦

#### 15. 接力預測 🏃
```
流程：49 → 20 → 10 → 6（三階段篩選）
特點：層層過濾，結果可追溯
適用：中樣本（50-500 期）
```

#### 16. 協作預測 🤝
```
流程：七模型投票 → 共識篩選 → 最終決策
特點：多模型交叉驗證，最穩健
適用：大樣本（500+ 期）
```

#### 17. 自適應接力 🧠 ⭐ 最推薦
```
流程：分析數據特徵 → 智能選擇策略 → 動態調整
特點：自動適應，因材施教
適用：所有數據量
```

### 民間策略（4種）

```
18. 奇偶平衡 - 3:3 或 4:2 分佈
19. 區間分佈 - 號碼分散度分析
20. 冷熱混合 - 結合冷熱號
21. 和值範圍 - 總和 120-180 + AC 值
```

### 方法選擇建議

| 數據量 | 推薦方法 |
|--------|---------|
| < 50期 | 🧠 自適應接力 |
| 50-500期 | 🏃 接力預測、綜合回歸 |
| 500+期 | 🤝 協作預測 |
| 不確定 | 🧠 自適應接力 |

---

## 💻 開發指南

### 專案架構

```
src/
├── core/           # 核心功能
│   ├── App.js              # 主控制器
│   └── DataProcessor.js    # 數據處理
├── engine/         # 預測引擎
│   ├── PredictionEngine.js
│   └── strategies/         # 13個策略
├── data/           # 數據服務
│   └── StatisticsService.js
├── ui/             # UI組件
│   ├── UIManager.js
│   └── ChartManager.js
└── utils/          # 工具
    └── constants.js
```

### 技術棧

```
前端：HTML5 + CSS3 + JavaScript ES6+
圖表：Chart.js 4.4.0
模式：Strategy Pattern + MVC
環境：瀏覽器（無需構建）
```

### 添加新策略

**步驟 1**：創建策略文件
```javascript
// src/engine/strategies/MyStrategy.js
import BaseStrategy from './BaseStrategy.js';

export default class MyStrategy extends BaseStrategy {
    constructor() {
        super('MyStrategy');
    }
    
    async predict(data) {
        const numbers = this.analyze(data);
        return {
            numbers: numbers.slice(0, 6),
            confidence: 75,
            description: '我的策略'
        };
    }
}
```

**步驟 2**：註冊策略
```javascript
// src/engine/PredictionEngine.js
import MyStrategy from './strategies/MyStrategy.js';

this.strategies = {
    'my-strategy': new MyStrategy(),
    // ... 其他策略
};
```

**步驟 3**：更新 UI
```html
<!-- index.html -->
<option value="my-strategy">我的策略</option>
```

### 配置測試

**測試不同權重配置**：

編輯 `src/engine/strategies/UnifiedEnsembleStrategy.js`：

```javascript
// 配置範例
const weights = {
    oddEven: { perfect: 120, good: 40 },
    sum: { best: 160, ok: 95 },
    hotCold: { perfect: 100, good: 60 },
    zones: { zone5: 120, zone4: 80, zone3: 50 },
    consecutive: { none: 65, one: 30 },
    modelWeight: 13,
    tailDiversity: { six: 55, four: 28 }
};
```

**測試流程**：
```
1. 修改權重參數
2. 重新整理頁面
3. 載入數據
4. 運行預測
5. 記錄成功率
```

### 調試技巧

**瀏覽器開發者工具**：
```javascript
// 添加斷點
debugger;

// 日誌輸出
console.log('Data:', data);
console.time('Prediction');
// ... 代碼
console.timeEnd('Prediction');
```

**性能優化**：
```javascript
// 使用緩存
class Strategy {
    constructor() {
        this.cache = new Map();
    }
    
    predict(data) {
        const key = this.getCacheKey(data);
        if (this.cache.has(key)) {
            return this.cache.get(key);
        }
        // 計算...
    }
}
```

---

## 🛠️ 工具腳本

### Python 工具（tools/ 目錄）

#### 1. universal_downloader.py
```bash
# 自動下載台灣彩券官方數據
python3 tools/universal_downloader.py
```

**功能**：
- 自動下載最新數據
- 轉換為系統格式
- 保存到 data/lotto649_latest.csv

#### 2. convert_taiwan_lottery_csv.py
```bash
# 轉換官方 CSV 格式
python3 tools/convert_taiwan_lottery_csv.py input.csv output.csv
```

**輸入格式**（官方）：
```csv
遊戲名稱,期別,開獎日期,銷售額,號碼1,號碼2,...
```

**輸出格式**（系統）：
```csv
期號,日期,號碼1,號碼2,號碼3,號碼4,號碼5,號碼6,特別號
```

#### 3. generate_realistic_data.py
```bash
# 生成測試數據
python3 tools/generate_realistic_data.py
```

**特點**：
- 符合真實分佈
- 號碼範圍 1-49
- 總和範圍 120-180

#### 4. 依賴安裝
```bash
# 創建虛擬環境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 安裝依賴
pip3 install requests beautifulsoup4 pandas openpyxl
```

---

## 📈 優化建議

### 配置優化

**5種預設配置**：
1. **強化型**：高權重奇偶和總和
2. **平衡型**：各項平衡
3. **激進型**：高權重所有加分項
4. **保守型**：溫和權重
5. **區間優先**：強化區間分佈

**選擇標準**：
- 成功率 ≥ 20%：優秀
- 成功率 10-20%：良好
- 成功率 < 10%：需改進

### 真實數據獲取

**台灣彩券官網**：https://www.taiwanlottery.com.tw/

**下載步驟**：
1. 進入「大樂透」專區
2. 選擇「歷史開獎結果」
3. 下載 CSV 或 Excel

**建議數據量**：
- 最少 20 期
- 建議 100+ 期
- 最佳 200+ 期

---

## ⚠️ 重要提醒

### 理性認知

```
1. 樂透是純隨機事件
2. 任何方法都無法保證中獎
3. 預測僅供學習研究參考
4. 請理性投注，適度娛樂
```

### 系統限制

```
1. 無法預測真正隨機事件
2. 15-20% 成功率已屬優秀
3. 不應期望過高準確率
4. 僅作為決策參考工具
```

---

## 📞 技術支援

### 常見問題

**Q: 需要多少數據？**
```
A: 最少 20 期，建議 100+ 期
```

**Q: 哪種方法最準？**
```
A: 
- 新手：綜合回歸、自適應接力
- 進階：協作預測（需 500+ 期）
```

**Q: 信心度含義？**
```
A: 系統對預測的相信程度
- 80%+ : 高信心
- 60-80%: 中等信心
- <60% : 低信心
```

**Q: 可以上傳 CSV？**
```
A: 可以，格式見「使用說明」章節
```

---

## 🧪 測試指南

### 測試框架

本專案使用 **Jest** 進行單元測試和整合測試。

#### 安裝測試依賴

```bash
npm install --save-dev jest @babel/core @babel/preset-env babel-jest
```

#### 執行測試

```bash
# 運行所有測試
npm test

# 監視模式 (開發時使用)
npm run test:watch

# 查看覆蓋率報告
npm run test:coverage

# 詳細輸出
npm run test:verbose
```

### 測試結構

```
__tests__/
├── Constants.test.js              # 常數配置測試
├── DataProcessor.test.js          # 數據處理測試
├── StatisticsService.test.js      # 統計服務測試
├── FrequencyStrategy.test.js      # 策略單元測試
├── CollaborativeStrategy.test.js  # 協作策略測試
└── PredictionEngine.integration.test.js  # 整合測試
```

### 測試覆蓋率

目前測試覆蓋率：
- **測試案例**: 109 個 (100% 通過)
- **測試套件**: 6 個
- **核心引擎**: 100% 覆蓋
- **統計服務**: 100% 覆蓋
- **預測策略**: 97.9% 覆蓋

詳細測試報告請參閱 [TEST_REPORT.md](TEST_REPORT.md)

### 新增測試範例

```javascript
// 範例：新增策略測試
import { YourStrategy } from '../src/engine/strategies/YourStrategy.js';
import { StatisticsService } from '../src/data/StatisticsService.js';
import { DataProcessor } from '../src/core/DataProcessor.js';

describe('YourStrategy', () => {
  let dataProcessor;
  let statisticsService;
  let strategy;
  
  beforeEach(() => {
    dataProcessor = new DataProcessor();
    dataProcessor.loadSampleData();
    statisticsService = new StatisticsService(dataProcessor);
    strategy = new YourStrategy(statisticsService);
  });
  
  test('should predict 6 unique numbers', () => {
    const data = dataProcessor.getDataRange(50);
    const result = strategy.predict(data);
    
    expect(result.numbers).toHaveLength(6);
    expect(new Set(result.numbers).size).toBe(6);
  });
  
  test('numbers should be within valid range', () => {
    const data = dataProcessor.getDataRange(50);
    const result = strategy.predict(data);
    
    result.numbers.forEach(num => {
      expect(num).toBeGreaterThanOrEqual(1);
      expect(num).toBeLessThanOrEqual(49);
    });
  });
});
```

### 測試最佳實踐

1. **每個模組都要有測試**
2. **測試要獨立**（不依賴其他測試）
3. **使用 beforeEach 初始化**
4. **測試邊界條件**（空數據、極端值）
5. **驗證錯誤處理**

---

### 疑難排解

**問題 1**：策略未顯示
```
檢查：
✓ PredictionEngine 已註冊？
✓ index.html 已添加選項？
✓ 頁面已重新載入？
```

**問題 2**：預測返回錯誤
```
檢查：
✓ 數據格式正確？
✓ 至少 20 期數據？
✓ Console 錯誤信息？
```

**問題 3**：圖表不顯示
```
檢查：
✓ Chart.js 已載入？
✓ canvas 元素存在？
✓ 數據格式符合要求？
```

**問題 4**：測試失敗
```
檢查：
✓ npm install 已執行？
✓ Jest 配置正確？
✓ ES6 模組路徑正確？
✓ Babel 已配置？
```

---

## 📚 參考資源

### 官方文檔
- [Chart.js](https://www.chartjs.org/docs/)
- [MDN JavaScript](https://developer.mozilla.org/zh-TW/docs/Web/JavaScript)
- [ES6 特性](https://github.com/lukehoban/es6features)

### 內部文檔
- `README.md` - 專案概覽
- `HISTORY.md` - 重構歷史
- `tools/README.md` - 工具說明

---

**版本**：v2.0  
**最後更新**：2025-11-25  
**授權**：MIT License

**祝您使用愉快！** 🍀
