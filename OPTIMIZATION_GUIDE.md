# 自动优化指南

## 当前配置：Config1（强化型）

权重设置：
- 奇偶3:3：+130
- 总和140-160：+180
- 3热2冷：+80
- 5区覆盖：+120
- 无连号：+70
- AI模型：×12
- 尾数6种：+60

## 测试步骤

### 1. 测试当前配置
```
1. 重新整理页面
2. 点击"载入范例数据"
3. 选择"战术接力模式"
4. 点击"开始模拟"
5. 记录成功率
```

### 2. 如果成功率 < 20%，切换配置

打开 `src/engine/strategies/EnsembleStrategy.js` 第155-165行
更改权重为下一个配置：

**Config2（平衡型）**
```javascript
const weights = {
    oddEven: { perfect: 120, good: 40 },
    sum: { best: 160, ok: 95 },
    hotCold: { perfect: 100, good: 60 },
    zones: { zone5: 100, zone4: 70, zone3: 45 },
    consecutive: { none: 65, one: 30 },
    modelWeight: 13,
    tailDiversity: { six: 50, four: 25 }
};
```

**Config3（激进型）**
```javascript
const weights = {
    oddEven: { perfect: 150, good: 30 },
    sum: { best: 200, ok: 80 },
    hotCold: { perfect: 120, good: 40 },
    zones: { zone5: 150, zone4: 90, zone3: 40 },
    consecutive: { none: 80, one: 20 },
    modelWeight: 15,
    tailDiversity: { six: 80, four: 35 }
};
```

**Config4（保守型）**
```javascript
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

**Config5（区间优先）**
```javascript
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

## 测试记录

| 配置 | 成功率 | 备注 |
|------|--------|------|
| Config1 | ___% | 强化型 |
| Config2 | ___% | 平衡型 |
| Config3 | ___% | 激进型 |
| Config4 | ___% | 保守型 |
| Config5 | ___% | 区间优先 |

## 最佳配置
测试后将最佳配置填写在此：

**最佳：Config___（成功率：____%）**
