# 智能自動學習排程系統使用指南

## 📋 概述

智能自動學習排程系統是一個自動化的策略評估和優化系統，可以：

1. **定期評估所有預測策略**，找出成功率最高的策略
2. **當成功率達到設定標準時**，自動更新為推薦策略
3. **對推薦策略執行參數優化**，進一步提升性能
4. **保存優化後的策略**，供前端智能預測使用

## 🎯 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                     智能排程系統                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  每日 02:00 - 策略評估任務           │
        │  測試所有可用策略，計算成功率        │
        └──────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  檢查成功率是否 >= 閾值 (默認 30%)   │
        └──────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
        ┌─────────────┐         ┌─────────────┐
        │  是：更新   │         │  否：保持   │
        │  最佳策略   │         │  當前策略   │
        └─────────────┘         └─────────────┘
                │
                ▼
        ┌──────────────────────────────────────┐
        │  每日 03:00 - 參數優化任務           │
        │  使用遺傳算法優化策略參數            │
        └──────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  保存優化配置，供預測使用            │
        └──────────────────────────────────────┘
```

## 🚀 API 端點

### 1. 啟動智能排程

**POST** `/api/smart-learning/start`

啟動智能自動學習排程系統。

**請求參數：**
```json
{
  "evaluation_schedule": "02:00",    // 策略評估時間 (HH:MM 格式)
  "learning_schedule": "03:00",      // 參數優化時間 (HH:MM 格式)
  "success_threshold": 0.30          // 成功率閾值 (0.0-1.0)
}
```

**響應示例：**
```json
{
  "success": true,
  "message": "智能排程已啟動",
  "config": {
    "evaluation_schedule": "02:00",
    "learning_schedule": "03:00",
    "success_threshold": 0.30
  }
}
```

**JavaScript 調用示例：**
```javascript
const response = await fetch('http://127.0.0.1:5001/api/smart-learning/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        evaluation_schedule: '02:00',
        learning_schedule: '03:00',
        success_threshold: 0.30
    })
});
const result = await response.json();
console.log('排程已啟動:', result);
```

---

### 2. 停止智能排程

**POST** `/api/smart-learning/stop`

停止智能排程系統。

**響應示例：**
```json
{
  "success": true,
  "message": "智能排程已停止"
}
```

---

### 3. 獲取排程狀態

**GET** `/api/smart-learning/status`

查詢智能排程的當前狀態。

**響應示例：**
```json
{
  "is_running": true,
  "success_threshold": 0.30,
  "jobs": [
    {
      "id": "strategy_evaluation",
      "name": "每日策略評估",
      "next_run": "2025-12-03T02:00:00"
    },
    {
      "id": "parameter_optimization",
      "name": "每日參數優化",
      "next_run": "2025-12-03T03:00:00"
    }
  ],
  "best_strategies": {
    "BIG_LOTTO": {
      "strategy_name": "集成預測",
      "strategy_id": "ensemble",
      "success_rate": 0.35,
      "avg_hits": 2.8,
      "updated_at": "2025-12-02T02:00:00"
    }
  },
  "learning_history": [...],
  "data_available": ["BIG_LOTTO", "POWER_LOTTO"]
}
```

---

### 4. 同步數據到智能排程器

**POST** `/api/smart-learning/sync-data`

將歷史數據同步到智能排程器。

**請求參數：**
```json
{
  "lotteryType": "BIG_LOTTO",
  "history": [
    {
      "date": "2024-01-01",
      "draw": "114000001",
      "numbers": [1, 9, 15, 23, 32, 45],
      "lotteryType": "BIG_LOTTO"
    }
  ],
  "lottery_rules": {
    "pickCount": 6,
    "minNumber": 1,
    "maxNumber": 49
  }
}
```

**響應示例：**
```json
{
  "success": true,
  "message": "數據已同步: 2073 期",
  "lottery_type": "BIG_LOTTO"
}
```

---

### 5. 手動觸發策略評估

**POST** `/api/smart-learning/manual-evaluation`

手動執行策略評估（不等待定時任務）。

**請求參數：**
```json
{
  "lotteryType": "BIG_LOTTO"
}
```

**響應示例：**
```json
{
  "success": true,
  "best_strategy": {
    "strategy_name": "集成預測",
    "strategy_id": "ensemble",
    "metrics": {
      "success_rate": 0.35,
      "avg_hits": 2.8,
      "perfect_hits": 2
    },
    "score": 42.5
  },
  "all_strategies": [...]
}
```

---

### 6. 獲取最佳策略

**GET** `/api/smart-learning/best-strategy/{lottery_type}`

獲取指定彩券類型的最佳策略。

**URL 參數：**
- `lottery_type`: 彩券類型 (例如: `BIG_LOTTO`)

**響應示例：**
```json
{
  "success": true,
  "lottery_type": "BIG_LOTTO",
  "strategy": {
    "strategy_name": "集成預測",
    "strategy_id": "ensemble",
    "success_rate": 0.35,
    "avg_hits": 2.8,
    "updated_at": "2025-12-02T02:00:00",
    "optimized": true,
    "optimization_fitness": 0.78
  }
}
```

---

### 7. 獲取所有最佳策略

**GET** `/api/smart-learning/all-best-strategies`

獲取所有彩券類型的最佳策略。

**響應示例：**
```json
{
  "success": true,
  "strategies": {
    "BIG_LOTTO": {...},
    "POWER_LOTTO": {...}
  },
  "count": 2
}
```

---

### 8. 使用最佳策略預測

**POST** `/api/smart-learning/predict-with-best`

使用智能排程找出的最佳策略進行預測。

**請求參數：**
```json
{
  "lotteryType": "BIG_LOTTO"
}
```

**響應示例：**
```json
{
  "numbers": [3, 12, 18, 27, 35, 42],
  "confidence": 0.78,
  "method": "ensemble",
  "strategy_info": {
    "name": "集成預測",
    "success_rate": 0.35,
    "avg_hits": 2.8,
    "updated_at": "2025-12-02T02:00:00"
  }
}
```

---

## 💡 使用場景

### 場景 1：初始設置

```javascript
// 1. 同步數據
await fetch('http://127.0.0.1:5001/api/smart-learning/sync-data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        lotteryType: 'BIG_LOTTO',
        history: historyData,
        lottery_rules: { pickCount: 6, minNumber: 1, maxNumber: 49 }
    })
});

// 2. 啟動智能排程 (每天凌晨2點評估，3點優化)
await fetch('http://127.0.0.1:5001/api/smart-learning/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        evaluation_schedule: '02:00',
        learning_schedule: '03:00',
        success_threshold: 0.30  // 成功率 >= 30% 時更新策略
    })
});
```

### 場景 2：手動立即評估

```javascript
// 不等待定時任務，立即執行評估
const result = await fetch('http://127.0.0.1:5001/api/smart-learning/manual-evaluation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lotteryType: 'BIG_LOTTO' })
});

const evaluation = await result.json();
console.log('最佳策略:', evaluation.best_strategy.strategy_name);
console.log('成功率:', evaluation.best_strategy.metrics.success_rate);
```

### 場景 3：使用最佳策略預測

```javascript
// 使用智能排程找出的最佳策略進行預測
const result = await fetch('http://127.0.0.1:5001/api/smart-learning/predict-with-best', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lotteryType: 'BIG_LOTTO' })
});

const prediction = await result.json();
console.log('預測號碼:', prediction.numbers);
console.log('使用策略:', prediction.strategy_info.name);
console.log('策略成功率:', prediction.strategy_info.success_rate);
```

### 場景 4：查看排程狀態

```javascript
const status = await fetch('http://127.0.0.1:5001/api/smart-learning/status');
const data = await status.json();

console.log('排程運行中:', data.is_running);
console.log('下次評估:', data.jobs[0].next_run);
console.log('當前最佳策略:', data.best_strategies);
```

---

## ⚙️ 配置說明

### 成功率閾值 (success_threshold)

決定何時更新最佳策略的標準：

- `0.20` (20%): 較寬鬆，更容易更新策略
- `0.30` (30%): **推薦值**，平衡更新頻率和質量
- `0.40` (40%): 較嚴格，只有非常好的策略才會被採用

**計算方式：** 成功率 = 至少命中 3 個號碼的預測次數 / 總預測次數

### 排程時間

建議設置：
- **策略評估：** 凌晨 2:00 (系統負載低)
- **參數優化：** 凌晨 3:00 (評估完成後執行)

---

## 📊 評估指標

系統會根據以下指標評分每個策略：

1. **成功率 (40%)**: 至少命中 3 個號碼的比例
2. **平均命中數 (30%)**: 平均每次預測命中幾個號碼
3. **完全命中次數 (20%)**: 6 個號碼全中的次數
4. **穩定性 (10%)**: 預測結果的一致性

**綜合評分公式：**
```
分數 = (成功率 × 40) + (平均命中數 × 30) + (完全命中次數 × 20) + (穩定性 × 10)
```

---

## 📁 數據文件

智能排程系統會生成以下文件：

1. **data/lottery_history.json** - 歷史數據存儲
2. **data/best_strategy.json** - 最佳策略記錄
3. **data/learning_log.json** - 學習歷史記錄
4. **data/best_config_{lottery_type}.json** - 優化後的參數配置

---

## 🔍 故障排查

### 問題 1：排程未啟動

**檢查：**
```javascript
const status = await fetch('http://127.0.0.1:5001/api/smart-learning/status');
console.log(await status.json());
```

**解決：** 確認 `is_running` 為 `true`

### 問題 2：沒有最佳策略

**原因：** 可能是：
- 數據未同步
- 成功率未達到閾值
- 尚未執行過評估

**解決：**
```javascript
// 1. 檢查數據
const status = await fetch('http://127.0.0.1:5001/api/smart-learning/status');
const data = await status.json();
console.log('可用數據:', data.data_available);

// 2. 手動執行評估
await fetch('http://127.0.0.1:5001/api/smart-learning/manual-evaluation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lotteryType: 'BIG_LOTTO' })
});
```

### 問題 3：評估失敗

**檢查後端日誌：**
- 數據量是否足夠 (至少 50 期)
- 彩券規則是否正確
- 是否有異常錯誤

---

## 🎓 最佳實踐

1. **定期同步數據** - 每次有新開獎數據時同步
2. **設置合理的閾值** - 從 0.30 開始，根據實際情況調整
3. **監控排程狀態** - 定期檢查排程是否正常運行
4. **查看學習歷史** - 了解系統的學習進度
5. **手動觸發評估** - 在重要時刻手動評估以獲取最新結果

---

## 📝 前端整合示例

```javascript
class SmartLearningManager {
    constructor(apiBaseUrl = 'http://127.0.0.1:5001') {
        this.apiBaseUrl = apiBaseUrl;
    }

    async startScheduler(config = {}) {
        const response = await fetch(`${this.apiBaseUrl}/api/smart-learning/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                evaluation_schedule: config.evalTime || '02:00',
                learning_schedule: config.learnTime || '03:00',
                success_threshold: config.threshold || 0.30
            })
        });
        return await response.json();
    }

    async getStatus() {
        const response = await fetch(`${this.apiBaseUrl}/api/smart-learning/status`);
        return await response.json();
    }

    async syncData(lotteryType, history, lotteryRules) {
        const response = await fetch(`${this.apiBaseUrl}/api/smart-learning/sync-data`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lotteryType,
                history,
                lottery_rules: lotteryRules
            })
        });
        return await response.json();
    }

    async evaluateNow(lotteryType) {
        const response = await fetch(`${this.apiBaseUrl}/api/smart-learning/manual-evaluation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lotteryType })
        });
        return await response.json();
    }

    async predictWithBest(lotteryType) {
        const response = await fetch(`${this.apiBaseUrl}/api/smart-learning/predict-with-best`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lotteryType })
        });
        return await response.json();
    }

    async getBestStrategy(lotteryType) {
        const response = await fetch(`${this.apiBaseUrl}/api/smart-learning/best-strategy/${lotteryType}`);
        return await response.json();
    }
}

// 使用示例
const smartLearning = new SmartLearningManager();

// 啟動排程
await smartLearning.startScheduler({
    evalTime: '02:00',
    learnTime: '03:00',
    threshold: 0.30
});

// 同步數據
await smartLearning.syncData('BIG_LOTTO', historyData, lotteryRules);

// 立即評估
const evaluation = await smartLearning.evaluateNow('BIG_LOTTO');
console.log('最佳策略:', evaluation.best_strategy);

// 使用最佳策略預測
const prediction = await smartLearning.predictWithBest('BIG_LOTTO');
console.log('預測號碼:', prediction.numbers);
```

---

## 🎯 總結

智能自動學習排程系統讓您的預測系統能夠：

✅ 自動評估所有策略，找出最佳方案
✅ 持續優化參數，提升預測準確度
✅ 無需人工干預，全自動運行
✅ 靈活配置，適應不同需求
✅ 完整記錄，可追溯學習歷史

**立即開始使用，讓AI自動優化您的彩票預測系統！**
