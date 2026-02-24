---
name: data-leakage-prevention
description: 數據洩漏防護技能。確保回測中不使用未來數據。當實作回測、驗證邏輯、或進行數據切片時使用。
---

# 數據洩漏防護技能 (2026-02-11 更新)

## 什麼是數據洩漏

數據洩漏（Data Leakage）是指在訓練或預測過程中，accidentally 使用了未來的資訊，導致回測結果虛高。

**範例**：
```python
# ❌ 洩漏：預測115000003期時，使用了包含該期的數據
all_data = load_all()  # 包含 115000003
train_on(all_data)
predict(115000003)  # 虛高！

# ✅ 正確：只使用115000002及之前的數據
hist = load_until(115000002)
train_on(hist)
predict(115000003)  # 真實
```

## 數據排序（關鍵陷阱！）

```python
from lottery_api.database import DatabaseManager
db = DatabaseManager()

# ⚠️ get_all_draws() 返回 DESC（新→舊）
raw = db.get_all_draws('POWER_LOTTO')
# raw[0] = 最新期, raw[-1] = 最舊期

# ✅ 正確做法：轉為 ASC 再操作
history = sorted(raw, key=lambda x: (x['date'], x['draw']))
# history[0] = 最舊期, history[-1] = 最新期

# ✅ ASC 排序後，切片語義清晰：
hist = history[:target_idx]  # 目標期之前的所有數據

# ❌ 常見錯誤：DESC 排序下誤用切片
recent_100 = raw[-100:]  # 實際是最舊的100期！應該用 raw[:100]
```

## 常見洩漏場景

### 場景1：訓練數據包含目標期
```python
# ❌ 錯誤
for target in test_draws:
    train_data = all_history  # 包含 target！
    result = model.train_and_predict(train_data)

# ✅ 正確（ASC 排序）
for i in range(test_periods):
    target_idx = len(history) - test_periods + i
    hist = history[:target_idx]  # 只到 target 之前
    result = predict(hist)
```

### 場景2：特徵計算使用全局統計
```python
# ❌ 錯誤：使用全部歷史計算頻率
all_freq = Counter(all_numbers)  # 包含未來！
for target in test_draws:
    use_frequency(all_freq)  # 洩漏

# ✅ 正確：滾動計算
for i in range(test_periods):
    hist = history[:target_idx]
    hist_freq = Counter(n for d in hist for n in d['numbers'])
    use_frequency(hist_freq)
```

### 場景3：全局 Baseline 計算
```python
# ❌ 錯誤：用全部數據算 sum range
global_sums = [sum(d['numbers']) for d in all_draws]
sum_range = (np.percentile(global_sums, 10), np.percentile(global_sums, 90))

# ✅ 正確：只用訓練數據
train_sums = [sum(d['numbers']) for d in hist]
sum_range = (np.percentile(train_sums, 10), np.percentile(train_sums, 90))
```

## 防護模式

### 模式1：嚴格切片（推薦）
```python
def safe_backtest(predict_func, lottery_type, test_periods=1000):
    db = DatabaseManager()
    raw = db.get_all_draws(lottery_type)
    # 轉為 ASC
    all_draws = sorted(raw, key=lambda x: (x['date'], x['draw']))

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        target_draw = all_draws[target_idx]

        # ✅ 嚴格切片：只到目標期之前
        hist = all_draws[:target_idx]

        # 預測
        bets = predict_func(hist)
        # 驗證...
```

### 模式2：滾動更新
```python
def rolling_backtest(all_draws):
    # 已排序為 ASC
    train_draws = list(all_draws[:500])

    for target in all_draws[500:]:
        # 使用當前訓練集預測
        result = predict(train_draws)

        # 評估...

        # ✅ 預測後才加入訓練集
        train_draws.append(target)
```

### 模式3：時間窗口
```python
def windowed_predict(all_draws, target_idx, window=50):
    # 確保 window 不超過可用數據
    start_idx = max(0, target_idx - window)

    # ✅ 只使用最近 window 期的歷史
    recent_hist = all_draws[start_idx:target_idx]

    return predict(recent_hist)
```

## 驗證工具

### 自動驗證函數
```python
def validate_no_leakage(target_draw, train_data, check_n=20):
    """驗證訓練數據無洩漏"""
    target_date = target_draw['date']
    target_draw_id = target_draw['draw']

    for i, d in enumerate(train_data[-check_n:]):  # 檢查最後N期（ASC排序）
        if d['date'] >= target_date:
            raise ValueError(
                f"[期數{i}] 數據洩漏！\n"
                f"  訓練數據: {d['draw']} ({d['date']})\n"
                f"  >= 目標期: {target_draw_id} ({target_date})"
            )

        if d['draw'] >= target_draw_id:
            raise ValueError(
                f"[期數{i}] 期號洩漏！\n"
                f"  訓練期號: {d['draw']}\n"
                f"  >= 目標期號: {target_draw_id}"
            )

    return True
```

## 檢查清單

回測前檢查：
- [ ] 數據排序是否正確（ASC: 舊→新）
- [ ] 訓練數據切片是否正確（`history[:target_idx]`）
- [ ] 是否使用全局統計（需改為滾動計算）
- [ ] 加入 `validate_no_leakage()` 驗證
- [ ] 特徵（頻率、和值、gap 等）是否只用訓練數據計算

程式碼審查：
- [ ] 搜尋全局 `Counter()` 或 `numpy.mean()` （可能洩漏）
- [ ] 確認預測後才 `rolling_history.append(target)`
- [ ] 確認 `history = sorted(raw, key=...)` 有正確排序

## 常見錯誤模式

```python
# ❌ 錯誤1：包含目標期
train = all_history[idx:]  # 如果是 DESC，包含 idx 之後的舊數據
# ✅ 修正：用 ASC + history[:idx]

# ❌ 錯誤2：預測前更新
rolling.append(target)
predict(rolling)  # 洩漏！
# ✅ 修正
predict(rolling)
rolling.append(target)  # 預測後才加入

# ❌ 錯誤3：全局特徵
global_mean = np.mean([d['sum'] for d in all_draws])
# ✅ 修正
hist_mean = np.mean([d['sum'] for d in train_draws])
```

## 快速檢測

```bash
python3 tools/verify_no_data_leakage.py
```

## 整合其他技能

- `backtest-framework` - 提供正確的回測結構和 Edge 方法論
- `prediction-methods` - 確保方法內部無洩漏
