# 🔧 特別號碼預測修復計劃

## 🎯 問題描述

用戶發現數據上傳到後端時遺失特別號碼，經檢查發現：
- ✅ 數據庫已正確處理特別號碼（`special` 字段）
- ✅ 前端已修復上傳邏輯
- ❌ **所有後端預測方法返回時沒有包含特別號碼**

## 📊 影響範圍

需要修復的文件和方法：

### 1. 核心預測引擎
**文件**: `lottery-api/models/unified_predictor.py`

所有預測方法的返回格式：
```python
return {
    'numbers': predicted_numbers,  # 主號碼
    'confidence': 0.75,
    'method': '方法名稱',
    'probabilities': [...]
}
```

**缺失**: `'special': predicted_special_number`

### 2. 策略評估器
**文件**: `lottery-api/models/strategy_evaluator.py`

調用 `unified_predictor` 的方法並返回結果，需確保傳遞特別號碼。

### 3. 機器學習模型
需要修復的文件：
- `lottery-api/models/prophet_model.py`
- `lottery-api/models/xgboost_model.py`
- `lottery-api/models/autogluon_model.py`
- `lottery-api/models/lstm_model.py`

### 4. 自動學習引擎
需要檢查評估時是否考慮特別號碼：
- `lottery-api/models/auto_learning.py`
- `lottery-api/models/advanced_auto_learning.py`

## 🔍 數據格式確認

### 前端格式
```javascript
{
    date: "2025-12-04",
    draw: "114000092",
    numbers: [1, 10, 15, 23, 30, 42],
    special: 35,  // 特別號碼字段名
    lotteryType: "BIG_LOTTO"
}
```

### 數據庫格式
```sql
CREATE TABLE draws (
    ...
    numbers TEXT NOT NULL,     -- JSON 數組: "[1,10,15,23,30,42]"
    special INTEGER DEFAULT 0  -- 特別號碼
    ...
)
```

### 彩票類型配置
```javascript
BIG_LOTTO: {
    hasSpecialNumber: true,
    specialNumberRange: { min: 1, max: 49 }
},
POWER_LOTTO: {
    hasSpecialNumber: true,
    specialNumberRange: { min: 1, max: 8 }
}
```

## 🛠️ 修復方案

### 步驟 1：創建特別號碼預測輔助函數

**位置**: `unified_predictor.py` 頂部

```python
def predict_special_number(
    history: List[Dict],
    lottery_rules: Dict,
    main_predicted_numbers: List[int] = None
) -> int:
    """
    預測特別號碼

    Args:
        history: 歷史數據
        lottery_rules: 彩票規則
        main_predicted_numbers: 主號碼預測結果（用於排除重複）

    Returns:
        預測的特別號碼
    """
    # 檢查是否有特別號碼
    has_special = lottery_rules.get('hasSpecialNumber', False)
    if not has_special:
        return None

    # 獲取特別號碼範圍
    special_range = lottery_rules.get('specialNumberRange', lottery_rules.get('numberRange'))
    min_special = special_range.get('min', 1)
    max_special = special_range.get('max', 49)

    # 統計歷史特別號碼頻率
    special_frequency = Counter()
    for draw in history:
        special = draw.get('special')
        if special and min_special <= special <= max_special:
            special_frequency[special] += 1

    # 如果沒有歷史數據，隨機選擇
    if not special_frequency:
        return random.randint(min_special, max_special)

    # 使用加權隨機選擇（頻率越高，權重越高）
    total = sum(special_frequency.values())
    probabilities = {}
    for num in range(min_special, max_special + 1):
        freq = special_frequency.get(num, 0)
        # 使用頻率分析 + 輕微隨機性
        probabilities[num] = freq / total if total > 0 else 1.0 / (max_special - min_special + 1)

    # 排除與主號碼重複的特別號（如果適用）
    if main_predicted_numbers:
        for num in main_predicted_numbers:
            if num in probabilities:
                probabilities[num] *= 0.1  # 大幅降低重複概率

    # 選擇概率最高的號碼
    sorted_probs = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
    predicted_special = sorted_probs[0][0]

    return predicted_special
```

### 步驟 2：修改所有預測方法返回格式

**模板**：
```python
def some_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
    # ... 主號碼預測邏輯 ...
    predicted_numbers = sorted([...])

    # 🔧 新增：預測特別號碼
    predicted_special = predict_special_number(
        history,
        lottery_rules,
        predicted_numbers
    )

    result = {
        'numbers': predicted_numbers,
        'confidence': 0.75,
        'method': '方法名稱',
        'probabilities': [...]
    }

    # 🔧 新增：添加特別號碼到返回結果
    if predicted_special is not None:
        result['special'] = predicted_special

    return result
```

### 步驟 3：修改自動學習評估邏輯

**文件**: `auto_learning.py` 和 `advanced_auto_learning.py`

評估時需要同時考慮主號碼和特別號碼的命中：

```python
def _evaluate_config(self, config, train_set, val_set, pick_count, min_num, max_num) -> float:
    success_count = 0

    for i, target in enumerate(val_set):
        # 預測主號碼
        predicted = self._predict_with_config(...)

        # 評估主號碼命中數
        hits = len(set(target['numbers']) & set(predicted))

        # 🔧 新增：評估特別號碼
        if target.get('special') and predicted_special:
            if target['special'] == predicted_special:
                hits += 0.5  # 特別號碼命中給予額外0.5分

        if hits >= 3:
            success_count += 1

    return success_count / len(val_set)
```

## 📝 實現檢查清單

### 第一階段：核心預測引擎

- [ ] 添加 `predict_special_number()` 輔助函數
- [ ] 修改 `frequency_predict()` - 頻率分析
- [ ] 修改 `bayesian_predict()` - 貝葉斯統計
- [ ] 修改 `markov_predict()` - 馬可夫鏈
- [ ] 修改 `monte_carlo_predict()` - 蒙特卡洛
- [ ] 修改 `odd_even_balance_predict()` - 奇偶平衡
- [ ] 修改 `zone_balance_predict()` - 區間平衡
- [ ] 修改 `hot_cold_mix_predict()` - 冷熱混合
- [ ] 修改 `random_forest_predict()` - 隨機森林
- [ ] 修改 `ensemble_predict()` - 集成預測
- [ ] 修改 `trend_predict()` - 趨勢分析
- [ ] 修改 `deviation_predict()` - 偏差追蹤

### 第二階段：機器學習模型

- [ ] 修改 `prophet_model.py`
- [ ] 修改 `xgboost_model.py`
- [ ] 修改 `autogluon_model.py`
- [ ] 修改 `lstm_model.py`

### 第三階段：自動學習引擎

- [ ] 修改 `auto_learning.py` 評估邏輯
- [ ] 修改 `advanced_auto_learning.py` 評估邏輯
- [ ] 更新 `_predict_with_config()` 返回特別號碼

### 第四階段：測試驗證

- [ ] 測試大樂透預測（特別號範圍 1-49）
- [ ] 測試威力彩預測（特別號範圍 1-8）
- [ ] 測試其他彩票類型
- [ ] 驗證自動學習優化結果
- [ ] 驗證前端顯示正確

## 🎯 預期結果

修復後的API返回格式：

```json
{
    "numbers": [1, 10, 15, 23, 30, 42],
    "special": 35,
    "confidence": 0.75,
    "method": "頻率分析",
    "probabilities": [0.15, 0.14, 0.13, ...]
}
```

## ⚠️ 注意事項

1. **向後兼容**：沒有特別號碼的彩票類型不應返回 `special` 字段
2. **不重複**：特別號碼應避免與主號碼重複（威力彩除外）
3. **範圍檢查**：確保特別號碼在正確的範圍內
4. **評估公平性**：自動學習評估時，特別號碼的權重應適中

---

**修復計劃創建時間**: 2025-12-04
**預計修復時間**: 1-2 小時
**優先級**: 🔥 高（影響所有預測功能）
