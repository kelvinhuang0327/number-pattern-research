# Lottery Prediction System - Claude Skills

## ⚠️ 重要規則 (每次開發前必讀)

1. **報告統一存放**：所有分析報告統一放在 `docs/` 目錄下
2. **更新而非新增**：同性質的內容需要與原文件整合更新，不要創建新檔案
3. **回測標準化**：使用 `models/backtest_framework.py` 進行所有回測
4. **配置集中管理**：最佳配置存放在 `data/auto_optimal_configs.json`

---

## Project Context

這是一個台灣彩票預測系統，支援三種彩票類型：
- **威力彩 (POWER_LOTTO)**: 6 個號碼 (1-38) + 特別號 (1-8)
- **今彩539 (DAILY_539)**: 5 個號碼 (1-39)，無特別號
- **大樂透 (BIG_LOTTO)**: 6 個號碼 (1-49) + 特別號 (1-49)

## Optimal Configurations (2025年回測驗證)

### 單注預測 (Single Bet)

| 彩票類型 | 最佳方法 | 最佳窗口 | 中獎率 | 每N期中1次 |
|----------|----------|----------|--------|-----------|
| BIG_LOTTO | `zone_balance` | 500 期 | 4.31% | 23.2 期 |
| DAILY_539 | `sum_range` | 300 期 | 2.25% | 44.4 期 |
| POWER_LOTTO | `ensemble` | 100 期 | ~3.5% | ~28 期 |

### 多注覆蓋策略 (Multi-Bet) ⭐ 推薦

| 注數 | BIG_LOTTO 中獎率 | 每N期中1次 | 預期成本 |
|------|-----------------|-----------|---------|
| 2 注 | 6.03% | 16.6 期 | $830 |
| 3 注 | 8.62% | 11.6 期 | $870 |
| **6 注** | **13.79%** | **7.3 期** | **$1,095** ⭐ |
| 8 注 | 15.52% | 6.4 期 | $1,280 |

---

# Core Skills

## 1. Statistical Reasoning (統計推理)

### Skill: Anomaly Detection (異常檢測)
識別號碼的統計異常與趨勢轉移。

**執行流程:**
```python
# 比較全歷史與近100期的頻率差異
from database import DatabaseManager
from collections import Counter

db = DatabaseManager()
draws = db.get_all_draws(lottery_type)

# 全歷史頻率
all_freq = Counter()
for d in draws:
    all_freq.update(d['numbers'])

# 近100期頻率
recent_freq = Counter()
for d in draws[:100]:
    recent_freq.update(d['numbers'])

# 計算偏離度 = (近期頻率 - 期望頻率) / 標準差
# 偏離度 > 2: 熱轉冷警告
# 偏離度 < -2: 冷轉熱信號
```

**判斷標準:**
- `熱轉冷`: 近期出現頻率顯著低於歷史平均 (z-score < -2)
- `冷轉熱`: 近期出現頻率顯著高於歷史平均 (z-score > 2)
- `穩定`: z-score 在 [-1, 1] 範圍內

### Skill: Trend Shift Detection (趨勢轉移檢測)
```python
# 短期窗口 (20期) vs 中期窗口 (50期) vs 長期窗口 (100期)
# 如果短期 >> 長期: 上升趨勢
# 如果短期 << 長期: 下降趨勢
```

---

## 2. Strategy Synthesis (策略綜效)

### Skill: Conflict Resolution (衝突解決)
當多個模型產生不同預測時的權重判斷邏輯。

**權重分配 (基於回測結果):**
```python
MODEL_WEIGHTS = {
    'bayesian_predict': 2.2,      # 大樂透最佳
    'ensemble_predict': 2.0,      # 威力彩最佳
    'monte_carlo_predict': 1.8,   # 今彩539最佳
    'trend_predict': 1.5,
    'hot_cold_predict': 1.2,
    'frequency_predict': 0.8,     # 回測表現較差
    'deviation_predict': 0.5,     # 回測表現最差
}
```

**共識等級:**
- `鐵膽 (Iron Pick)`: 4+ 方法同時推薦
- `高度共識 (Strong Consensus)`: 3 方法推薦
- `中度共識 (Medium Consensus)`: 2 方法推薦
- `單一推薦 (Single Recommendation)`: 僅 1 方法推薦

### Skill: Multi-Model Voting (多模型投票)
```python
# 執行所有策略並收集結果
strategies = [
    unified.bayesian_predict,
    unified.trend_predict,
    unified.monte_carlo_predict,
    unified.hot_cold_mix_predict,
    unified.ensemble_predict,
]

# 加權投票
number_scores = defaultdict(float)
for method, weight in zip(strategies, weights):
    result = method(history, rules)
    for num in result['numbers']:
        number_scores[num] += weight

# 選擇得分最高的 N 個號碼
predicted = sorted(number_scores, key=number_scores.get, reverse=True)[:pick_count]
```

---

## 3. Predict & Verify Workflow (預測驗證流)

### 標準作業程序 (SOP)

#### Step 1: Audit (查核)
```python
# 確認數據新鮮度
db = DatabaseManager()
stats = db.get_stats()
latest_draw = db.get_all_draws(lottery_type)[0]

print(f"資料庫最後更新: {latest_draw['date']}")
print(f"最新期號: {latest_draw['draw']}")
print(f"總期數: {stats['by_type'].get(lottery_type, 0)}")

# 驗證是否為最新
from datetime import datetime
today = datetime.now().strftime('%Y/%m/%d')
is_fresh = latest_draw['date'] >= today or (datetime.now().weekday() not in [0, 3])  # 開獎日
```

#### Step 2: Execute (執行)
```python
from config import optimal_prediction_config

# 自動選擇最佳配置
config = optimal_prediction_config.get_optimal_config(lottery_type)
optimal_method = config['optimal_method']
optimal_window = config['optimal_window']

# 執行預測
history = draws[:optimal_window]
result = getattr(unified, optimal_method)(history, rules)
```

#### Step 3: Cross-Check (交叉驗證)
```python
# 至少用 3 種不同方法驗證
validation_methods = [
    ('Bayesian', unified.bayesian_predict),
    ('Monte Carlo', unified.monte_carlo_predict),
    ('Ensemble', unified.ensemble_predict),
]

all_predictions = []
for name, method in validation_methods:
    pred = method(history, rules)
    all_predictions.append(set(pred['numbers']))

# 計算共識
from collections import Counter
all_nums = [n for pred in all_predictions for n in pred]
consensus = Counter(all_nums)
high_consensus = [n for n, c in consensus.items() if c >= 3]
```

#### Step 4: Output (輸出)
```python
output = {
    "lottery_type": lottery_type,
    "prediction": {
        "numbers": sorted(result['numbers']),
        "special": result.get('special'),
        "confidence": result['confidence'],
        "method": optimal_method,
    },
    "validation": {
        "consensus_numbers": sorted(high_consensus),
        "consensus_level": len(high_consensus),
        "cross_check_methods": len(validation_methods),
    },
    "data_info": {
        "latest_draw": latest_draw['draw'],
        "data_window": optimal_window,
        "is_fresh": is_fresh,
    },
    "analysis": {
        "hot_numbers": [...],  # 近期熱門
        "cold_numbers": [...],  # 近期冷門
        "trend_shifts": [...],  # 趨勢轉移
    }
}
```

---

## 4. Game Logic Isolation (遊戲邏輯隔離)

### Critical Rule: 永遠使用 lottery_rules 參數

```python
# 正確做法
rules = get_lottery_rules(lottery_type)
result = unified.ensemble_predict(history, rules)

# 驗證邏輯隔離
assert len(result['numbers']) == rules['pickCount']
assert all(rules['minNumber'] <= n <= rules['maxNumber'] for n in result['numbers'])
if rules['hasSpecialNumber']:
    assert rules['specialMinNumber'] <= result.get('special', 0) <= rules['specialMaxNumber']
```

### 各彩票類型規則速查
```python
LOTTERY_RULES = {
    'POWER_LOTTO': {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 38,
        'hasSpecialNumber': True,
        'specialMin': 1,
        'specialMax': 8,
    },
    'DAILY_539': {
        'pickCount': 5,
        'minNumber': 1,
        'maxNumber': 39,
        'hasSpecialNumber': False,
    },
    'BIG_LOTTO': {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49,
        'hasSpecialNumber': True,
        'specialMin': 1,
        'specialMax': 49,
    },
}
```

---

## 5. Advanced Analytics (進階分析)

### Skill: Coverage Analysis (覆蓋率分析)
```python
# 計算多組號碼的覆蓋率
def calculate_coverage(bets, max_num):
    all_numbers = set()
    for bet in bets:
        all_numbers.update(bet)
    return len(all_numbers) / max_num

# 目標: 6-8 組號碼覆蓋 60%+ 號碼池
```

### Skill: Historical Match Analysis (歷史匹配分析)
```python
# 回測預測準確度
def backtest(method, history, test_periods=30):
    results = []
    for i in range(test_periods):
        target = history[i]
        train_data = history[i+1:]
        prediction = method(train_data, rules)
        matches = len(set(prediction['numbers']) & set(target['numbers']))
        results.append(matches)
    return {
        'avg_match': sum(results) / len(results),
        'win_count': sum(1 for r in results if r >= 3),
        'win_rate': sum(1 for r in results if r >= 3) / len(results),
    }
```

### Skill: Special Number Analysis (特別號分析)
```python
# 威力彩/大樂透特別號熱度
def analyze_special(history, window=50):
    special_counts = Counter([d['special_number'] for d in history[:window]])
    total = sum(special_counts.values())
    return {
        num: {'count': count, 'rate': count/total}
        for num, count in special_counts.most_common()
    }
```

---

## Quick Commands

### 預測命令
```bash
# 最佳配置預測
curl -X POST http://localhost:8000/api/predict-optimal \
  -H "Content-Type: application/json" \
  -d '{"lotteryType": "POWER_LOTTO"}'

# 查看最佳配置
curl http://localhost:8000/api/optimal-configs

# 多組號碼預測
curl -X POST "http://localhost:8000/api/predict-smart-multi-bet?num_bets=6" \
  -H "Content-Type: application/json" \
  -d '{"lotteryType": "POWER_LOTTO"}'
```

### 資料庫命令
```bash
# 查看資料庫統計
python3 -c "from database import DatabaseManager; print(DatabaseManager().get_stats())"

# 查看最新期號
python3 -c "from database import DatabaseManager; d=DatabaseManager().get_all_draws('POWER_LOTTO')[0]; print(f'{d[\"draw\"]} - {d[\"date\"]} - {d[\"numbers\"]}')"
```

---

## Error Handling

### 常見問題排查

1. **資料不足錯誤**
   ```python
   if len(history) < 10:
       raise ValueError("至少需要 10 期歷史數據")
   ```

2. **模型載入失敗**
   ```python
   try:
       from models.lstm_model import LSTMPredictor
   except ImportError:
       logger.warning("LSTM 模型未安裝，跳過")
   ```

3. **API 連接問題**
   ```bash
   # 檢查後端狀態
   lsof -i :8000
   curl http://localhost:8000/api/health
   ```

---

## File Structure

```
lottery-api/
├── app.py                 # FastAPI 主程式
├── config.py              # 配置管理
├── database.py            # 資料庫操作
├── common.py              # 共用函數
├── data/
│   ├── lottery_v2.db      # SQLite 資料庫
│   ├── lottery_types.json # 彩票規則定義
│   ├── auto_optimal_configs.json  # 自動優化最佳配置 ⭐
│   └── backtest_results/  # 回測結果存放 ⭐
├── models/
│   ├── unified_predictor.py      # 統一預測引擎
│   ├── backtest_framework.py     # 標準化回測框架 ⭐
│   ├── auto_optimizer.py         # 自動優化器 ⭐
│   ├── multi_bet_optimizer.py    # 多注覆蓋優化器 ⭐
│   ├── optimized_predictor.py    # 優化預測器入口 ⭐
│   ├── enhanced_predictor.py     # 增強型預測方法
│   ├── lstm_attention_predictor.py  # LSTM+Attention 模型
│   └── ...
└── routes/
    ├── prediction.py      # 預測 API
    ├── data.py            # 資料 API
    ├── backtest.py        # 回測與優化 API ⭐
    └── admin.py           # 管理 API
```

## Backtest API Endpoints (新增)

```bash
# 獲取最佳配置
GET /api/backtest/optimal-config/{lottery_type}

# 執行自動優化
POST /api/backtest/run-optimization
  Body: {"lottery_type": "BIG_LOTTO", "test_year": 2025}

# 單一方法回測
POST /api/backtest/single-method
  Body: {"lottery_type": "BIG_LOTTO", "method": "zone_balance", "window": 500}

# 多注策略回測
POST /api/backtest/multi-bet
  Body: {"lottery_type": "BIG_LOTTO", "num_bets": 6}

# 比較所有方法
GET /api/backtest/compare-all/{lottery_type}?test_year=2025

# 使用最佳配置預測
POST /api/backtest/predict-optimal
  Body: {"lottery_type": "BIG_LOTTO", "num_bets": 6}

# 獲取投注建議
GET /api/backtest/recommendations/{lottery_type}?budget=400
```

---

## Version History

- **2025-12-29**: 🎉 完成優化目標
  - 新增標準化滾動回測框架 (`backtest_framework.py`)
  - 新增自動優化器 (`auto_optimizer.py`)
  - 新增多注覆蓋策略 (`multi_bet_optimizer.py`) - 達成 13.79%+ 中獎率
  - 新增回測 API 路由 (`routes/backtest.py`)
  - 更新最佳配置: BIG_LOTTO 使用 zone_balance(500期) = 4.31%
- **2025-12-22**: 新增最佳配置系統，整合三種彩票類型的回測驗證結果
- **2025-12-16**: 完成 2025 年大樂透 113 期回測，確認 Bayesian 為最佳方法
- **2025-12-15**: Phase 2 優化完成，多維度偏差分析驗證通過
