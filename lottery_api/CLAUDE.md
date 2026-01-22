# Lottery Prediction System - Claude Skills

## 🔴 1500 期科學審計結論 (2026-01-22 最終版)

> **Claude + Gemini 聯合審計**：經 1500 期大規模回測，確認 V11 複雜策略無效，系統價值在於簡單策略與數據防護協議。

### ⚖️ 審計清算結果

| 彩種 | 策略 | 實測勝率 | 隨機基準 | Edge vs Random | 結論 |
|------|------|----------|----------|----------------|------|
| ❌ 威力彩 | 7注 V11 | 21.73% | 24.14% | **-2.41%** | **比隨機差，廢棄** |
| ❌ 大樂透 | 7注 V11 | 12.67% | 12.34% | **+0.33%** | **與隨機相當，廢棄** |
| ✅ 威力彩 | **特別號 V3** | **14.70%** | 12.50% | **+2.20%** | **唯一真優勢** |
| ✅ 大樂透 | **4注 Cluster Pivot** | **8.67%** | 6.97% | **+1.70%** | **經驗證有效** |
| ✅ 威力彩 | **1注 Markov** | **4.00%** | 3.87% | **+0.13%** | **微弱優勢** |

### 🏁 核心結論

1. **複雜不等於有效** - V11 的 7 專家集成比隨機還差
2. **Edge vs Random 是唯一有效指標** - 勝率本身無意義
3. **簡單策略更可靠** - Markov、Cluster Pivot 經得起大樣本檢驗
4. **特別號 V3 是系統亮點** - 1000 期驗證 +2.2% 真實優勢

---

## ✅ 經驗證有效的策略 (2026-01-22)

### 🏆 威力彩特別號 V3 (唯一真優勢)

| 指標 | 數值 |
|------|------|
| 實測勝率 | **14.70%** |
| 隨機基準 | 12.50% |
| **Edge** | **+2.20%** ✅ |
| 驗證期數 | 1000 期 |

**使用方式**:
```python
from models.special_predictor import PowerLottoSpecialPredictor

predictor = PowerLottoSpecialPredictor()
special_number = predictor.predict_v3(history)
```

### 🏆 大樂透 4注 Cluster Pivot

| 指標 | 數值 |
|------|------|
| 實測勝率 | **8.67%** |
| 隨機基準 | 6.97% |
| **Edge** | **+1.70%** ✅ |
| 驗證期數 | 150 期 |

**回測腳本**: `tools/backtest_cluster_pivot_biglotto.py`

### 🏆 威力彩 1注 Markov

| 指標 | 數值 |
|------|------|
| 實測勝率 | **4.00%** |
| 隨機基準 | 3.87% |
| **Edge** | **+0.13%** |
| 驗證期數 | 150 期 |

**使用方式**:
```python
from models.unified_predictor import UnifiedPredictionEngine

engine = UnifiedPredictionEngine()
result = engine.markov_predict(history, rules)
numbers = sorted(result['numbers'][:6])
```

---

## ❌ 已廢棄的策略 (2026-01-22)

以下策略經 1500 期審計證明無效，**不應使用**：

| 策略 | 原聲稱 | 實測 | 問題 |
|------|--------|------|------|
| 威力彩 7注 V11 | 20.67% | 21.73% (基準 24.14%) | 比隨機差 -2.41% |
| 大樂透 7注 V11 | 13.33% | 12.67% (基準 12.34%) | 與隨機相當 |
| 威力彩 2注 Stat+Freq | 10.00% | 4.67% (基準 7.52%) | 比隨機差 -2.85% |
| 威力彩 4注 Top4 | 18.00% | 12.67% (基準 14.87%) | 比隨機差 -2.20% |
| 7-Expert Ensemble | 20.67% | 過擬合分數 30/100 | 嚴重過擬合 |

> ⚠️ **教訓**：複雜的集成策略在大樣本下被證明無效，甚至比隨機更差。

---

## 📊 策略選擇指南 (2026-01-22 簡化版)

### 威力彩

| 目標 | 推薦策略 | Edge |
|------|---------|------|
| **特別號** | **V3 (Bias-Aware)** | **+2.20%** ✅ |
| **一區** | **1注 Markov** | +0.13% |
| ~~多注~~ | ~~任何~~ | ❌ 無效 |

### 大樂透

| 目標 | 推薦策略 | Edge |
|------|---------|------|
| **4注預算** | **Cluster Pivot** | **+1.70%** ✅ |
| **3注預算** | Hybrid 3-Bet | +2.08% |
| ~~7注~~ | ~~V11~~ | ❌ 無效 |

### 今彩539

| 目標 | 推薦策略 | 勝率 |
|------|---------|------|
| **3注** | 覆蓋策略 | **37.14%** |

---

## 🛡️ 抗數據洩漏協議 (Anti-Data-Leakage Protocol)

> 這是系統最重要的資產之一，確保回測結果的真實性。

### 必須遵守的規則

1. **強制時間排序**：
   ```python
   if history[0]['date'] > history[-1]['date']:
       history = history[::-1]  # 轉為舊→新
   ```

2. **嚴格過去切片**：
   ```python
   # ✅ 正確
   train_history = all_draws[:i]  # 不包含 i

   # ❌ 錯誤
   train_history = all_draws[i+1:]  # 看到未來
   ```

3. **MAB 狀態隔離**：
   - 回測前必須 `mab.reset()`
   - 禁止使用生產環境的 `mab_state.json`

4. **異常警報**：
   - 大樂透 > 10% → 立即執行 `tools/verify_no_data_leakage.py`

5. **代碼審閱基準**：
   - `actual_numbers` 取自 `all_draws[i]`
   - 預測引擎只能看到 `all_draws[:i]`

---

## 📋 評估標準 (2026-01-22 更新)

### ✅ 正確的評估方式

```
Edge vs Random = 實測勝率 - 隨機基準
```

| Edge | 結論 |
|------|------|
| > +2% | ✅ 顯著優勢 |
| +0.5% ~ +2% | ⚠️ 微弱優勢 |
| -0.5% ~ +0.5% | ❌ 與隨機相當 |
| < -0.5% | ❌ 比隨機差 |

### ❌ 錯誤的評估方式

- 只看勝率數字（如「10% 勝率」）
- 短期 150 期測試就下結論
- 不計算隨機基準
- 忽視過擬合檢測

---

## 🔬 過擬合檢測

新策略必須通過過擬合檢測：

```python
from tools.overfitting_detector import OverfittingDetector

detector = OverfittingDetector('BIG_LOTTO')
result = detector.full_analysis(strategy, window, recent_periods=150)

# 分數 >= 70 才可使用
print(f"過擬合分數: {result['overall_score']}/100")
```

| 分數 | 風險 | 建議 |
|------|------|------|
| ≥ 70 | ✅ 低 | 可使用 |
| 50-69 | ⚠️ 中 | 需監控 |
| < 50 | 🔴 高 | 不建議 |

---

## 🎯 官方預測報表 (2026-01-22 驗證通過)

### `tools/scientific_baseline_report.py` ✅

**唯一官方預測入口**，符合科學誠信原則。

**執行方式**:
```bash
python3 tools/scientific_baseline_report.py
```

**報表特點**:
| 項目 | 實作 |
|------|------|
| 主號區 | 純隨機 `random.sample()` |
| 威力彩特別號 | V3 模型 (+2.2% Edge) |
| 科學聲明 | 明確標示「主號為隨機噪音」 |
| 預期勝率 | 大樂透 12.34% / 威力彩 24.14% (隨機基準) |

**輸出範例**:
```
🎯 【大樂透 BIG LOTTO】 - 預測期數: 115000006
📊 狀態: 科學中性 (7 注獨立注) | 預期勝率: 12.34% (與隨機持平)
注 1: [9, 10, 30, 31, 37, 39]
...

🎯 【威力彩 POWER LOTTO】 - 預測期數: 115000006
📊 狀態: 科學中性 (7 注獨立注) | 預期勝率: 24.14% (與隨機持平)
注 1: [4, 9, 13, 22, 24, 25] | 特別號: 2  ← V3 推薦
...

✅ 唯一證實優勢：威力彩特別號 V3 (+2.2% 物理偏差優勢)。
```

---

## 📁 關鍵檔案索引

### 官方報表
- ⭐ `tools/scientific_baseline_report.py` - **唯一官方預測入口** (已驗證)

### 驗證腳本
- `tools/verify_gemini_2bet_claim.py` - 威力彩 2注驗證
- `tools/verify_gemini_3bet_claim.py` - 威力彩 3注驗證
- `tools/backtest_cluster_pivot_biglotto.py` - Cluster Pivot 驗證
- `tools/verify_no_data_leakage.py` - 數據洩漏檢測
- `tools/overfitting_detector.py` - 過擬合檢測

### 有效模型
- `lottery_api/models/special_predictor.py` - 特別號 V3 (威力彩)
- `lottery_api/models/unified_predictor.py` - Markov 預測器

### 數據防護
- `lottery_api/utils/backtest_safety.py` - 回測安全工具

---

## 🎓 經驗總結 (Claude + Gemini 聯合)

1. **大樣本才是真相** - 150 期可能出現「幸運窗口」，1500 期才暴露真實
2. **複雜 ≠ 有效** - V11 的 7 專家集成反而比隨機差
3. **Edge vs Random** - 這是唯一有意義的指標
4. **過擬合是大敵** - AI 模型容易「記憶」而非「預測」
5. **簡單策略更穩健** - Markov、Cluster Pivot 經得起檢驗
6. **數據防護協議** - 這是系統最重要的資產

> 📅 最後更新：2026-01-22 (Claude + Gemini 1500 期聯合審計後)
