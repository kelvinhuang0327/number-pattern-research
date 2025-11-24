# 配置測試指南

## ✅ 已完成的自動測試
- Config1 (強化型) - 已測試
- Config2 (平衡型) - 已測試

## 📋 待測試配置

### 當前配置：Config3 (激進型) - 已設定
代碼已切換到Config3，請立即測試：

**測試步驟：**
1. 重新整理頁面（Ctrl+R 或 Cmd+R）
2. 點擊「數據上傳」
3. 點擊「載入範例數據」
4. 點擊「模擬測試」  
5. 確認選擇「戰術接力模式」
6. 點擊「開始模擬」
7. 記錄成功率：_____% ← **請填寫**

---

### Config4 (保守型) - 待設定
測試完Config3後，將代碼第154-163行改為：

```javascript
// 加載權重配置 - Config4 (保守型)
const weights = {
    oddEven: { perfect: 110, good: 45 },
    sum: { best: 140, ok: 100 },
    hotCold: { perfect: 90, good: 55 },
    zones: { zone5: 110, zone4: 75, zone3: 50 },
    consecutive: { none: 60, one: 28 },
    modelWeight: 11,
    tailDiversity: { six: 55, four: 28 }
};
```

**測試步驟：**
1. 重新整理頁面
2. 載入範例數據
3. 運行模擬
4. 記錄成功率：_____% ← **請填寫**

---

### Config5 (區間優先型) - 待設定
測試完Config4後，將代碼第154-163行改為：

```javascript
// 加載權重配置 - Config5 (區間優先)
const weights = {
    oddEven: { perfect: 115, good: 38 },
    sum: { best: 155, ok: 92 },
    hotCold: { perfect: 85, good: 52 },
    zones: { zone5: 140, zone4: 95, zone3: 55 },
    consecutive: { none: 68, one: 27 },
    modelWeight: 12,
    tailDiversity: { six: 58, four: 30 }
};
```

**測試步驟：**
1. 重新整理頁面
2. 載入範例數據
3. 運行模擬
4. 記錄成功率：_____% ← **請填寫**

---

## 📊 測試結果匯總

| 配置 | 成功率 | 特點 |
|------|--------|------|
| Config1 強化型 | ___% | 高權重奇偶和總和 |
| Config2 平衡型 | ___% | 各項平衡 |
| Config3 激進型 | ___% | **當前測試中** |
| Config4 保守型 | ___% | 溫和權重 |
| Config5 區間優先 | ___% | 強化區間分佈 |

## 🎯 選擇最佳配置

測試完成後：
1. **找出成功率最高的配置**
2. **將對應的weights代碼保留在EnsembleStrategy.js中**
3. **如果最高成功率 ≥ 20%，優化完成！**
4. **如果所有配置都 < 20%，選擇最高的那個作為當前最佳方案**

## 快速文件位置
- 配置代碼：`src/engine/strategies/EnsembleStrategy.js` 第154-163行
- 修改後務必重新整理頁面！
