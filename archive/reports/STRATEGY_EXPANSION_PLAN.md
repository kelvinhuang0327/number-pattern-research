# 🎯 進階優化系統策略擴展計劃

## 📖 目標

將進階優化系統從優化 **11 種統計方法權重** 升級為優化 **23 種完整預測策略組合**，大幅提升預測準確率。

## 🔍 當前架構分析

### 現有系統（11 種統計方法）

**位置**: `lottery-api/models/auto_learning.py` 和 `advanced_auto_learning.py`

**優化對象**：
```python
weight_keys = [
    'frequency_weight',      # 頻率分析
    'missing_weight',        # 遺漏值分析
    'hot_cold_weight',       # 冷熱號平衡
    'trend_weight',          # 趨勢分析
    'zone_weight',           # 區間分析
    'last_digit_weight',     # 尾數分析
    'odd_even_weight',       # 奇偶分析
    'pair_weight',           # 配對分析
    'sum_band_weight',       # 和值分段
    'ac_band_weight',        # AC值分段
    'dynamic_zone_weight'    # 動態區間
]
```

**遺傳算法個體結構**：
```python
individual = {
    'frequency_weight': 0.144,
    'missing_weight': 0.163,
    # ... 其他 9 個權重
    'recent_window': 93,
    'long_window': 236
}
```

**適應度評估**：
- 使用這 11 種方法的加權組合預測
- 在驗證集上計算成功率（≥3個號碼）
- 返回成功率作為適應度

### 可用策略（23 種完整預測方法）

**位置**: `lottery-api/models/strategy_evaluator.py`

```python
available_strategies = [
    ('frequency', '頻率分析'),
    ('hot_cold', '冷熱分析'),
    ('gap', '間距分析'),
    ('pattern', '型態分析'),
    ('sum_range', '和值範圍'),
    ('odd_even', '奇偶分析'),
    ('high_low', '大小分析'),
    ('sequential', '連號分析'),
    ('cycle', '週期分析'),
    ('matrix', '矩陣走勢'),
    ('ac_value', 'AC值分析'),
    ('span_value', '跨度分析'),
    ('same_tail', '同尾分析'),
    ('same_number', '重號分析'),
    ('adjacent', '鄰號分析'),
    ('distance', '距離分析'),
    ('sum_tail', '和值尾數'),
    ('balanced', '均衡分析'),
    ('trending', '趨勢追蹤'),
    ('contrarian', '逆向思維'),
    ('composite', '複合分析'),
    ('ensemble', '集成預測'),
    ('ml', '機器學習')
]
```

## 🎯 升級方案：雙層優化架構

### 架構設計

```
┌─────────────────────────────────────────────────────┐
│          進階優化系統 v2.0                            │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │  第一層：策略選擇與權重優化                    │  │
│  │                                                │  │
│  │  遺傳算法個體 = {                              │  │
│  │    'enabled_strategies': [                    │  │
│  │      'frequency', 'hot_cold', 'ml', ...      │  │
│  │    ],  // 從 23 種中選擇 5-10 種              │  │
│  │    'strategy_weights': {                      │  │
│  │      'frequency': 0.15,                       │  │
│  │      'hot_cold': 0.20,                        │  │
│  │      'ml': 0.30,                               │  │
│  │      ...                                       │  │
│  │    },  // 選中策略的權重                      │  │
│  │    'ensemble_method': 'weighted',  // 集成方法 │  │
│  │    'meta_params': { ... }  // 元參數          │  │
│  │  }                                              │  │
│  └──────────────────────────────────────────────┘  │
│                        ↓                            │
│  ┌──────────────────────────────────────────────┐  │
│  │  第二層：各策略內部參數優化（可選）            │  │
│  │                                                │  │
│  │  針對選中的策略，進一步優化其內部參數：        │  │
│  │  - frequency: window_size, decay_factor       │  │
│  │  - hot_cold: threshold, ratio                 │  │
│  │  - ml: model_type, hyperparameters            │  │
│  └──────────────────────────────────────────────┘  │
│                        ↓                            │
│  ┌──────────────────────────────────────────────┐  │
│  │  預測執行：集成多策略結果                      │  │
│  │                                                │  │
│  │  1. 每個選中的策略獨立預測                    │  │
│  │  2. 根據策略權重加權組合                      │  │
│  │  3. 輸出最終預測結果                          │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 實現步驟

#### 階段 1：基礎策略集成優化（推薦先實現）

**目標**：優化哪些策略組合效果最好，以及各策略的權重

**遺傳算法個體結構**：
```python
individual = {
    # 策略啟用開關（23 個布爾值）
    'strategy_enabled': {
        'frequency': True,
        'hot_cold': True,
        'gap': False,
        'pattern': True,
        # ... 其他 20 個策略
    },

    # 啟用策略的權重（自動歸一化）
    'strategy_weights': {
        'frequency': 0.15,
        'hot_cold': 0.20,
        'pattern': 0.18,
        # ... 其他啟用的策略
    },

    # 集成方法選擇
    'ensemble_method': 'weighted_voting',  # 或 'stacking', 'boosting'

    # 策略數量限制
    'min_strategies': 5,
    'max_strategies': 10
}
```

**優化流程**：
1. 初始化種群（隨機啟用 5-10 種策略）
2. 評估適應度：
   - 使用選中的策略進行集成預測
   - 計算驗證集成功率
3. 進化操作：
   - **交叉**: 交換策略選擇和權重
   - **變異**: 隨機啟用/禁用策略，調整權重
4. 保存最佳策略組合

**預期效果**：
- ✅ 發現最佳策略組合（如 frequency + hot_cold + ml + pattern）
- ✅ 優化各策略權重
- ✅ 適應度提升 30-60%（從 4.5% → 6-8%）

#### 階段 2：深度參數優化（進階）

**目標**：針對選中的策略，進一步優化其內部參數

**遺傳算法個體結構**：
```python
individual = {
    # 階段 1 的結果
    'enabled_strategies': ['frequency', 'hot_cold', 'ml'],
    'strategy_weights': {'frequency': 0.2, 'hot_cold': 0.3, 'ml': 0.5},

    # 階段 2 新增：各策略的內部參數
    'strategy_params': {
        'frequency': {
            'window_size': 50,
            'decay_factor': 0.95,
            'smoothing': True
        },
        'hot_cold': {
            'hot_threshold': 0.7,
            'cold_threshold': 0.3,
            'balance_ratio': 0.6
        },
        'ml': {
            'model_type': 'xgboost',
            'max_depth': 5,
            'learning_rate': 0.1
        }
    }
}
```

**預期效果**：
- ✅ 精細調整每個策略的表現
- ✅ 適應度再提升 10-20%（從 6-8% → 7-10%）

## 📝 實現計劃

### 第一步：創建擴展優化引擎

**文件**: `lottery-api/models/ensemble_auto_learning.py` (新建)

**核心功能**：
1. `_initialize_ensemble_population()` - 初始化種群（策略組合）
2. `_evaluate_ensemble_config()` - 評估策略組合的適應度
3. `_predict_with_ensemble()` - 使用多策略集成預測
4. `optimize_ensemble()` - 執行集成優化

### 第二步：整合到進階優化系統

修改 `advanced_auto_learning.py`，添加新的優化模式：

```python
async def ensemble_optimize(
    self,
    history: List[Dict],
    lottery_rules: Dict,
    strategy_pool: List[str] = None  # 可選：指定策略池
) -> Dict:
    """
    集成策略優化

    從 23 種策略中選擇最佳組合
    """
    # 1. 初始化策略池
    if not strategy_pool:
        strategy_pool = self._get_all_available_strategies()

    # 2. 遺傳算法優化策略選擇與權重
    best_ensemble = await self._optimize_strategy_ensemble(
        history, lottery_rules, strategy_pool
    )

    # 3. 保存最佳配置
    self.best_ensemble_config = best_ensemble

    return best_ensemble
```

### 第三步：添加 API 端點

**文件**: `lottery-api/app.py`

```python
@app.post("/api/auto-learning/advanced/ensemble")
async def run_ensemble_optimization_api(background_tasks: BackgroundTasks, request: dict):
    """
    🎯 執行集成策略優化

    從 23 種預測策略中選擇最佳組合
    優化各策略的權重分配

    預期效果：相比單一方法提升 30-60% 適應度
    耗時：20-30 分鐘
    """
    # ... 實現邏輯
```

### 第四步：更新前端 UI

**文件**: `index.html` 和 `src/ui/AutoLearningManager.js`

添加第三個優化按鈕：

```html
<button id="advanced-ensemble-btn" class="btn">
    🎯 執行集成策略優化
    <span style="font-size: 0.85em; opacity: 0.8;">
        (整合 23 種預測方法)
    </span>
</button>
```

## 🔧 技術細節

### 策略集成方法

#### 1. 加權投票 (Weighted Voting)

```python
def weighted_voting(predictions, weights):
    """
    各策略預測結果按權重投票
    """
    number_votes = defaultdict(float)

    for strategy_id, predicted_numbers in predictions.items():
        weight = weights.get(strategy_id, 0)
        for number in predicted_numbers:
            number_votes[number] += weight

    # 返回得票最高的 N 個號碼
    sorted_numbers = sorted(number_votes.items(), key=lambda x: x[1], reverse=True)
    return [num for num, _ in sorted_numbers[:pick_count]]
```

#### 2. 疊加集成 (Stacking)

```python
def stacking_ensemble(predictions, meta_model):
    """
    使用元學習器組合各策略結果
    """
    # 特徵：各策略的預測結果
    features = []
    for strategy_id, predicted_numbers in predictions.items():
        features.append(encode_prediction(predicted_numbers))

    # 元模型預測
    final_prediction = meta_model.predict(features)
    return final_prediction
```

#### 3. 提升集成 (Boosting)

```python
def boosting_ensemble(predictions, strategy_weights, history):
    """
    動態調整策略權重，強化表現好的策略
    """
    # 根據最近的預測準確率動態調整權重
    adjusted_weights = {}
    for strategy_id, weight in strategy_weights.items():
        recent_accuracy = evaluate_recent_performance(strategy_id, history)
        adjusted_weights[strategy_id] = weight * (1 + recent_accuracy)

    # 使用調整後的權重進行加權投票
    return weighted_voting(predictions, adjusted_weights)
```

### 遺傳算法改進

#### 策略選擇交叉

```python
def strategy_crossover(parent1, parent2):
    """
    交叉操作：交換策略選擇
    """
    child = {}

    # 隨機選擇交叉點
    all_strategies = list(parent1['strategy_enabled'].keys())
    crossover_point = random.randint(0, len(all_strategies))

    # 交叉策略啟用狀態
    child['strategy_enabled'] = {}
    for i, strategy in enumerate(all_strategies):
        if i < crossover_point:
            child['strategy_enabled'][strategy] = parent1['strategy_enabled'][strategy]
        else:
            child['strategy_enabled'][strategy] = parent2['strategy_enabled'][strategy]

    # 交叉權重（僅針對啟用的策略）
    enabled_strategies = [s for s, enabled in child['strategy_enabled'].items() if enabled]
    child['strategy_weights'] = {}
    for strategy in enabled_strategies:
        if random.random() < 0.5:
            child['strategy_weights'][strategy] = parent1['strategy_weights'].get(strategy, 0.1)
        else:
            child['strategy_weights'][strategy] = parent2['strategy_weights'].get(strategy, 0.1)

    # 歸一化權重
    normalize_weights(child['strategy_weights'])

    return child
```

#### 策略變異

```python
def strategy_mutation(individual, mutation_rate=0.2):
    """
    變異操作：隨機啟用/禁用策略，調整權重
    """
    mutated = copy.deepcopy(individual)

    # 策略啟用變異
    for strategy in mutated['strategy_enabled']:
        if random.random() < mutation_rate:
            # 翻轉啟用狀態
            mutated['strategy_enabled'][strategy] = not mutated['strategy_enabled'][strategy]

    # 確保至少有 min_strategies 個策略啟用
    enabled_count = sum(mutated['strategy_enabled'].values())
    if enabled_count < mutated['min_strategies']:
        # 隨機啟用一些策略
        disabled_strategies = [s for s, enabled in mutated['strategy_enabled'].items() if not enabled]
        for _ in range(mutated['min_strategies'] - enabled_count):
            strategy = random.choice(disabled_strategies)
            mutated['strategy_enabled'][strategy] = True
            disabled_strategies.remove(strategy)

    # 權重變異
    for strategy in mutated['strategy_weights']:
        if random.random() < mutation_rate:
            mutated['strategy_weights'][strategy] *= random.uniform(0.7, 1.3)

    # 歸一化權重
    normalize_weights(mutated['strategy_weights'])

    return mutated
```

## 📊 預期效果對比

| 指標 | 當前系統<br>(11 種統計方法) | 擴展系統<br>(23 種策略集成) | 提升幅度 |
|------|---------------------------|---------------------------|----------|
| 命中 3 個號碼 | 4.58% | **7-10%** | 1.5-2.2x |
| 命中 4 個號碼 | 0.5% | **1.5-3%** | 3-6x |
| 命中 5 個號碼 | 0.05% | **0.2-0.5%** | 4-10x |
| 優化時間 | 15 分鐘 | **25-30 分鐘** | 1.7-2x |
| 參數空間 | ~11 個權重 | **~23 個策略 + 23 個權重** | 46x |

## 📚 參考文檔

- [策略評估器實現](lottery-api/models/strategy_evaluator.py)
- [統一預測引擎](lottery-api/models/unified_predictor.py)
- [進階自動學習](lottery-api/models/advanced_auto_learning.py)
- [基礎自動學習](lottery-api/models/auto_learning.py)

## ✅ 實現檢查清單

### 階段 1：基礎集成優化（優先）

- [ ] 創建 `ensemble_auto_learning.py` 引擎
- [ ] 實現策略選擇的遺傳算法
- [ ] 實現加權投票集成方法
- [ ] 添加 API 端點 `/api/auto-learning/advanced/ensemble`
- [ ] 更新前端 UI（添加集成優化按鈕）
- [ ] 測試完整流程

### 階段 2：深度參數優化（可選）

- [ ] 為各策略定義可優化參數
- [ ] 擴展遺傳算法個體結構
- [ ] 實現雙層優化流程
- [ ] 添加參數優化 API 端點
- [ ] 測試效果提升

### 階段 3：高級集成方法（進階）

- [ ] 實現 Stacking 集成
- [ ] 實現 Boosting 集成
- [ ] 動態策略權重調整
- [ ] 自適應集成方法選擇

---

**計劃創建時間**: 2025-12-04
**預計完成時間**: 2-3 天（階段 1）
**狀態**: 📝 計劃中
