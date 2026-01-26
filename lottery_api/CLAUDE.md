# Lottery Prediction System - Claude Skills

## 🤝 Gemini 合作協議 (2026-01-26)

> **重要**：所有 Gemini 提出的策略必須經 Claude 獨立驗證後才能採納。
>
> 詳細規範見：`.claude/gemini_collaboration_protocol.md`
>
> **核心要求**：
> - 必須提供可執行驗證腳本
> - 最低樣本量 N ≥ 500
> - 報告 Edge vs Random（非單純勝率）
> - 禁止使用 N < 100 的結果作聲稱

---

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
| ✅ 威力彩 | **2注 冷號互補** | **9.00%** | 8.55% | **+0.45%** | **優於舊策略** |

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

predictor = PowerLottoSpecialPredictor(rules)
special_number = predictor.predict_top_n(history, n=1)[0]
```

> ❌ **V4/V6「聯合機率」經 1000 期驗證無效** (2026-01-22)
> - V4 聲稱：主號影響特別號（如「主號 14 → 特別號 3 機率提升 1.41 倍」）
> - 實測：即使作弊使用實際開獎主號，V4 也只比 V3 高 0.20% (14.90% vs 14.70%)
> - 結論：主號與特別號物理獨立，無統計關聯
> - 驗證腳本：`tools/verify_special_v4.py`

### 🏆 大樂透 2注 Markov Transition (新晉 2注王)

| 指標 | 數值 |
|------|------|
| 實測勝率 | **6.00%** |
| 隨機基準 | 3.50% |
| **Edge** | **+2.50%** ✅ |
| 驗證期數 | 150 期 |

**使用方式**:
```bash
python3 tools/predict_smart_entry.py --lottery BIG_LOTTO --num 2
```

### 🏆🏆 大樂透 4注 Zonal Pruning (全系統最強) ⭐ NEW

> **2026-01-26 Gemini 提出，Claude 獨立驗證通過**

| 指標 | 數值 |
|------|------|
| 實測勝率 | **7.10%** |
| 隨機基準 | 3.50% |
| **Edge** | **+3.60%** ✅✅ |
| 驗證期數 | **1000 期** |

**理論基礎**: 大樂透號碼在空間分佈上具備「區域平衡性」，84% 的開獎覆蓋 4-5 個區域。

**使用方式**:
```bash
python3 tools/biglotto_zonal_pruning.py --bets 4
```

**驗證腳本**: `tools/biglotto_zonal_pruning.py --n 1000 --bets 4`

### 🏆 大樂透 4注 Cluster Pivot (舊金標準)

| 指標 | 數值 |
|------|------|
| 實測勝率 | **8.67%** |
| 隨機基準 | 6.97% |
| **Edge** | **+1.70%** ✅ |
| 驗證期數 | 150 期 |

**回測腳本**: `tools/backtest_cluster_pivot_biglotto.py`

> ⚠️ **注意**: Zonal Pruning 經 1000 期驗證 Edge +3.60%，優於 Cluster Pivot 的 +1.70%

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
| 威力彩 2注 Markov+Stat | - | 6.50% (基準 8.55%) | 比隨機差 -2.05% |
| 威力彩 4注 Top4 | 18.00% | 12.67% (基準 14.87%) | 比隨機差 -2.20% |
| 7-Expert Ensemble | 20.67% | 過擬合分數 30/100 | 嚴重過擬合 |
| **特別號 V4/V6** | +2.6%/+2.7% | 14.80% (V3: 14.70%) | **與 V3 差異 < 0.1%，無效** |
| **威力彩 GUM W50** | 9.33% | 6.80% (N=500, 基準 8.55%) | **比隨機差 -1.75%** (2026-01-26) |
| **威力彩 GUM W100** | 9.10% | 7.30% (N=1000, 基準 8.55%) | **比隨機差 -1.25%** (2026-01-26) |

> ⚠️ **教訓**：複雜的集成策略在大樣本下被證明無效，甚至比隨機更差。
>
> ⚠️ **GUM 驗證記錄** (2026-01-26)：Gemini 聲稱 GUM (Grand Unified Model) 達到 9.33%/9.10%，經 Claude 獨立驗證後發現 N=500 實測僅 6.80%，N=1000 實測僅 7.30%，均比隨機基準差。詳見 `tools/verify_gum_claim.py`。

---

## 📊 策略選擇指南 (2026-01-22 更新)

### 威力彩

> 🎉 **2026-01-26 重大突破**：Gemini 發現 Fourier Rhythm 策略，首次實現威力彩主號正 Edge！
> 經 Claude 獨立驗證通過。

| 目標 | 推薦策略 | Edge | 驗證期數 |
|------|---------|------|----------|
| ⭐ **主號** | **Fourier Rhythm** ⭐ NEW | **+0.95%** ✅ | 1000 期 |
| ⭐ **特別號** | **V3 (Bias-Aware)** | **+2.20%** ✅ | 1000 期 |

#### 🏆 威力彩 Fourier Rhythm (主號突破) ⭐ NEW

> **2026-01-26 Gemini 提出，Claude 獨立驗證通過**

| 指標 | 數值 |
|------|------|
| 實測勝率 (N=1000) | **9.50%** |
| 隨機基準 | 8.55% |
| **Edge** | **+0.95%** ✅ |

**理論基礎**: 使用 FFT（快速傅立葉變換）檢測每個球號的週期性回歸規律。

**關鍵特徵**: Edge 隨樣本量增加而增加（正向單調增長）
| N | M3+ | Edge |
|---|-----|------|
| 150 | 9.33% | +0.78% |
| 500 | 9.40% | +0.85% |
| 1000 | 9.50% | +0.95% |

**使用方式**:
```bash
python3 tools/power_fourier_rhythm.py
```

#### 🔬 舊策略 N=1000 驗證結果 (已被 Fourier 取代)

| 策略 | N=1000 結果 | 結論 |
|------|-------------|------|
| 冷號互補 | 7.10% (-1.45%) | ❌ 長期無效 |
| GUM W50 | 6.80% (-1.75%) | ❌ 長期無效 |
| **Fourier Rhythm** | **9.50% (+0.95%)** | ✅ **新王者** |

#### 🎯 威力彩建議策略 (2026-01-26 最新)

```bash
python3 tools/power_fourier_rhythm.py
```

| 注 | 主號策略 | 特別號 | Edge |
|---|---------|--------|------|
| 1 | **Fourier Top 1-6** | V3 Top-1 | +0.95% (主) + +2.20% (特) |
| 2 | **Fourier Top 7-12** | V3 Top-2 | 不重疊覆蓋 |

**舊策略回測結果 (N=200，僅供參考)**：
| 策略 | Z1 M3+ | Edge |
|------|--------|------|
| 冷號互補 (新) | 9.00% | **+0.45%** ✅ |
| Markov+Stat (舊) | 6.50% | -2.05% ❌ |
| 隨機基準 | 8.55% | - |

**組成邏輯**：
```python
# 取近 100 期最冷的 12 個號碼
freq = Counter([n for d in history[-100:] for n in d['numbers']])
sorted_nums = sorted(range(1, 39), key=lambda x: freq.get(x, 0))
bet1 = sorted_nums[:6]   # 最冷 1-6
bet2 = sorted_nums[6:12] # 次冷 7-12
```

#### 🎯 威力彩動態集成預測 (2026-01-25 新增)

> ✅ **持續優化框架 (Continuous Optimization Framework)**：目前最強大的自動化預測入口。

```bash
python3 tools/predict_ensemble_dynamic.py
```

| 目標 | 策略 | Win Rate (N=150) | 狀態 |
|------|---------|------------------|------|
| **最佳窗口** | **Window 50** | **9.33%** | ✅ 當前最強參數 |
| 次佳窗口 | Window 150/200 | 9.33% | 穩定 |
| 弱效窗口 | Window 20 | 6.00% | ❌ 雜訊過多 |

**核心功能**：
- **引數自動調優 (Auto-Tuning)**：實時回測不同窗口，自動切換至當前表現最佳的期數。
- **特徵挖掘**：集成「區塊遺漏 (Cluster)」與「球號關聯 (Companion)」分析。
- **效益**：確保選號邏輯與當前市場週期高度同步。

> 📁 驗證腳本：`tools/strategy_leaderboard.py`

### 大樂透 (2026-01-24 更新)

> ✅ **重要發現 (2026-01-24)**：不同注數有不同最佳策略。1注/4注+ 用 Cluster Pivot，2-3注 用 Apriori。
>
> **核心結論**：簡單策略 (Cluster Pivot, Apriori) 優於複雜集成 (V11, 精銳/衛星)。

#### ⭐ 一鍵預測工具

```bash
# 自動選擇最佳策略
python3 tools/predict_biglotto_best.py -n <注數>

# 範例
python3 tools/predict_biglotto_best.py -n 1   # → Cluster Pivot
python3 tools/predict_biglotto_best.py -n 2   # → Apriori
python3 tools/predict_biglotto_best.py -n 7   # → Cluster Pivot
```

#### 📊 各注數最佳策略排名

| 注數 | 最佳策略 | Match-3+ | Edge | 執行方式 |
|------|---------|----------|------|----------|
| **1注** | **Cluster Pivot** | 3.33% | **+1.60%** | `predict_smart_entry.py -l BIG_LOTTO -n 1` |
| **2注** | **Markov Transition** ⭐ | **6.00%** | **+2.50%** | `predict_smart_entry.py -l BIG_LOTTO -n 2` |
| **3注** | **Apriori** | 8.00% | **+3.20%** | `predict_smart_entry.py -l BIG_LOTTO -n 3` |
| **4注** | **Cluster Pivot** | **8.67%** | **+1.70%** | `predict_smart_entry.py -l BIG_LOTTO -n 4` |
| **7注** | **Cluster Pivot** | **16.67%** | **+4.40%** | `predict_smart_entry.py -l BIG_LOTTO -n 7` |

> 📊 **驗證條件**: 150 期回測, seed=42, lottery_v2.db

#### 🎯 策略切換邏輯

| 注數範圍 | 自動選用策略 | Edge | 原因 |
|----------|-------------|------|------|
| **1注** | Cluster Pivot | +1.60% | 單注聚類中心最穩 |
| **2-3注** | Apriori | +1.93%~+3.20% | 關聯規則的黃金區間 |
| **4注+** | Cluster Pivot | +1.12%~+4.40% | 多中心覆蓋優勢 |

#### ✅ 經驗證有效的方法 (2026-01-24)

| 方法 | 最佳注數 | Edge | 特點 |
|------|---------|------|------|
| **Cluster Pivot** | 1注, 4注+ | +1.60%~+4.40% | 穩定、錨點擴展 |
| **Apriori 關聯規則** | 2-3注 | +1.93%~+3.20% | 規則連鎖、爆發力 |

#### ❌ 已驗證無效的方法 (2026-01-24)

| 方法 | Edge | 原因 |
|------|------|------|
| Gemini 6注精銳 (Hexa-Core) | **-4.33%** | 高重疊、比隨機差 |
| Gemini 7注衛星 (Hepta-Slice) | **-5.00%** | 高重疊、比隨機差 |
| V11 7專家集成 | +0.33% | 複雜但無效，與隨機相當 |
| 負向篩選 (Negative Selection) | -0.87% | 過度排除 |
| 共現圖分析 (PageRank/度中心性) | -3.87% | 不如錨點擴展 |
| Cluster Pivot 混合窗口版 | -1.01% | 不如標準版 |

> 📁 驗證腳本：`tools/backtest_cluster_pivot_biglotto.py`, `tools/backtest_apriori.py`

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



## 🎲 回測驗證規範 (2026-01-22 新增)

> 確保回測結果可復現、可驗證，避免隨機波動造成的誤判。

### 必須遵守的規則

1. **強制固定隨機種子 (SEED = 42)**：
   ```python
   import numpy as np
   import random

   SEED = 42  # 官方基準種子
   np.random.seed(SEED)
   random.seed(SEED)
   ```

2. **多次運行取統計值**：
   ```python
   # 推薦方案：固定種子作基準 + 多次運行報告置信區間
   results = []
   for seed in range(42, 52):  # 10 次不同種子
       np.random.seed(seed)
       roi = run_backtest()
       results.append(roi)

   print(f"ROI: {np.mean(results):.1f}% ± {np.std(results):.1f}%")
   ```

3. **報告格式規範**：
   - ✅ 正確：`ROI: -65.3% ± 3.2% (N=150, seed=42)`
   - ❌ 錯誤：`ROI: -65.3%`（無法復現）

4. **驗證流程**：
   - 提出者運行 → 記錄種子與結果
   - 驗證者使用相同種子 → 結果應完全一致
   - 若結果不一致 → 腳本有問題，需排查

### 為什麼需要這個規範

| 問題 | 後果 |
|------|------|
| 未固定種子 | 每次運行結果不同，無法驗證 |
| 只跑一次 | 可能恰好「運氣好/差」 |
| 不報告誤差 | 無法判斷結論是否穩健 |

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

## 🎯 官方預測報表 (2026-01-22 更新)

### ⭐ `tools/predict_ensemble_dynamic.py` - **動態集成推薦 (推薦入口)** ✅
**最強自動化工具**，自動尋找最佳窗口並生成號碼。

**執行方式**:
```bash
python3 tools/predict_ensemble_dynamic.py
```

### ⭐ `tools/power_twin_strike.py` - 威力彩 2注主力預測
採用冷號互補策略。

**執行方式**:
```bash
python3 tools/power_twin_strike.py
```

**預測組成**:
| 項目 | 模型 | Edge |
|------|------|------|
| 主號 注1 | 冷號 Top 1-6 (近 100 期最冷) | +0.45% |
| 主號 注2 | 冷號 Top 7-12 (次冷，不重疊) | +0.45% |
| 特別號 | V3 Model | +2.20% ✅ |

**輸出範例**:
```
🎯 【威力彩 POWER LOTTO】 - 預測期數: 115000006
📊 策略：冷號互補 + V3 特別號
----------------------------------------------------------------------
注 1: [4, 12, 21, 27, 29, 31] | 特別號: 2
      └─ 主號策略: 冷號 Top 1-6 (近 100 期頻率最低)
注 2: [1, 9, 15, 19, 33, 37] | 特別號: 4
      └─ 主號策略: 冷號 Top 7-12 (次冷，完全不重疊)
```

> ⚠️ **舊版 `power_precision_2bet.py` 已廢棄** (Edge -2.05%)

---

### `tools/scientific_baseline_report.py` - 科學基準報表

**7注完整報表**，包含大樂透與威力彩。

```bash
python3 tools/scientific_baseline_report.py
```

---

## 📁 關鍵檔案索引

### 官方報表
- ⭐ `tools/predict_ensemble_dynamic.py` - **動態集成預測 (自動選優)** ✅
- ⭐ `tools/power_twin_strike.py` - 威力彩 2注主力預測 (冷號互補 + V3)
- `tools/scientific_baseline_report.py` - 科學基準報表 (7注完整版)

### 驗證腳本
- ⭐ `tools/backtest_150_biglotto.py` - **大樂透 150 期回測** (快速驗證)
- ⭐ `tools/backtest_150_power.py` - **威力彩 150 期回測** (快速驗證)
- ⭐ `tools/backtest_500_biglotto.py` - **大樂透 500 期回測** (長期驗證)
- ⭐ `tools/backtest_500_power.py` - **威力彩 500 期回測** (長期驗證)
- `tools/verify_gemini_2bet_claim.py` - 威力彩 2注驗證
- `tools/verify_gemini_3bet_claim.py` - 威力彩 3注驗證
- `tools/verify_special_v4.py` - 特別號 V3 vs V4 驗證 (證明 V4 無效)
- `tools/backtest_cluster_pivot_biglotto.py` - Cluster Pivot 驗證
- `tools/verify_no_data_leakage.py` - 數據洩漏檢測
- `tools/overfitting_detector.py` - 過擬合檢測

### 有效模型
- `lottery_api/models/special_predictor.py` - 特別號 V3 (威力彩)
- `lottery_api/models/unified_predictor.py` - Markov 預測器
- `tools/backtest_cluster_pivot_biglotto.py` - Cluster Pivot (大樂透) ⭐

### 回測框架
- ⭐ `lottery_api/utils/benchmark_framework.py` - **標準化回測框架** (2026-01-23 新增)

### ⭐ 標準回測腳本 (2026-01-23 新增)

> **強制規定**：所有方法回測必須使用以下標準化腳本，禁止自行編寫回測邏輯。
> **架構原則**：各腳本完全獨立，不共用通用框架，避免修改時互相影響。

#### 150 期回測（快速驗證）

| 彩種 | 腳本 | 用途 |
|------|------|------|
| 大樂透 | `tools/backtest_150_biglotto.py` | 快速驗證、初步篩選 |
| 威力彩 | `tools/backtest_150_power.py` | 快速驗證、初步篩選 |

#### 500 期回測（長期驗證）⭐

| 彩種 | 腳本 | 用途 |
|------|------|------|
| 大樂透 | `tools/backtest_500_biglotto.py` | 排除運氣因素、確認策略有效性 |
| 威力彩 | `tools/backtest_500_power.py` | 排除運氣因素、確認策略有效性 |

> ⚠️ **重要**：150 期可能出現「幸運窗口」，500 期驗證才能確認策略真正有效。

#### 大樂透獎項判定（`calc_prize` 函數）

```
預測：6 個號碼
開獎：6 個主號 + 1 個特別號（從剩餘 43 個號碼產生）

判定流程：
1. 預測的 6 個 vs 實際 6 個主號 → match_count
2. 預測的 6 個是否包含特別號 → special_hit
```

```python
# 完整大樂透中獎規則
頭獎: 6 號碼全中
貳獎: 5 號碼 + 特別號    參獎: 5 號碼
肆獎: 4 號碼 + 特別號    伍獎: 4 號碼
陸獎: 3 號碼 + 特別號    柒獎: 3 號碼
普獎: 2 號碼 + 特別號

# 特別號判定：預測的 6 個號碼中是否包含實際特別號
special_hit = actual_special in predicted_numbers
```

**範例**：
```
預測: [1, 2, 3, 4, 5, 6]
實際主號: [1, 2, 7, 8, 9, 10]
實際特別號: 3

判定：
- match_count = 2 (命中 1, 2)
- special_hit = True (預測的 3 = 特別號)
- 結果: 普獎 (2 號碼 + 特別號)
```

#### 威力彩獎項判定（`calc_prize` 函數）

```python
# 完整威力彩中獎規則
頭獎: 6 + 特別號    貳獎: 6
參獎: 5 + 特別號    肆獎: 5
伍獎: 4 + 特別號    陸獎: 4
柒獎: 3 + 特別號    捌獎: 2 + 特別號
玖獎: 3             普獎: 1 + 特別號

# 特別號判定：預測的特別號是否等於實際特別號
special_hit = pred_special == actual_special
```

#### 使用方式

```bash
# 大樂透 - 單一方法
python3 tools/backtest_150_biglotto.py deviation

# 大樂透 - 多注組合
python3 tools/backtest_150_biglotto.py deviation markov statistical

# 威力彩 - 單一方法
python3 tools/backtest_150_power.py markov

# 威力彩 - 多注組合
python3 tools/backtest_150_power.py deviation markov statistical frequency

# 查看可用方法
python3 tools/backtest_150_biglotto.py --list
```

#### 常用方法別名

| 別名 | 實際方法 |
|------|----------|
| dev | deviation_predict |
| stat | statistical_predict |
| freq | frequency_predict |
| bayes | bayesian_predict |
| mc | monte_carlo_predict |
| zone | zone_balance_predict |

#### 內建數據洩漏防護

腳本內建以下防護機制：

```python
# ✅ 正確的滾動式回測（腳本已實作）
for i in range(test_periods):
    target_idx = len(all_draws) - test_periods + i
    target_draw = all_draws[target_idx]      # 實際開獎號碼
    hist = all_draws[:target_idx]            # 只用過去數據預測

    result = method_func(hist, rules)        # 預測
    actual = set(target_draw['numbers'])     # 驗證
```

#### ⚠️ 禁止事項

1. ❌ **禁止自行編寫回測邏輯** - 容易出錯導致數據洩漏
2. ❌ **禁止修改標準腳本的切片邏輯** - 除非經過 code review
3. ❌ **禁止在回測中使用 `all_draws[i:]`** - 這會看到未來數據

#### 異常結果處理

如果回測結果異常高（大樂透 > 10%），立即執行：

```bash
python3 tools/verify_no_data_leakage.py
```

### 已驗證無效模型 (勿使用)
- `lottery_api/models/negative_selection_biglotto.py` - 負向篩選 (Edge -0.87%)
- `lottery_api/models/cooccurrence_graph.py` - 共現圖分析 (Edge -3.87%)

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
7. **~~注數邊際效益遞減~~** - ❌ 已修正 (2026-01-23): Cluster Pivot 6-7 注 Edge 反而最高 (+3.5%~+4.4%)
8. **錨點擴展優於圖分析** - Cluster Pivot > PageRank/度中心性 (2026-01-23 驗證)
9. **使用標準化回測腳本** - 禁止自行編寫回測邏輯，避免數據洩漏 (2026-01-23 新增)
10. **策略與注數要匹配** - V11 7注無效，但 Cluster Pivot 7注有效；策略本身比注數更重要 (2026-01-23 新增)
11. **覆蓋率比複雜度重要** - 威力彩 2注：簡單冷號互補 (Edge +0.45%) 優於複雜 Markov+Stat (Edge -2.05%) (2026-01-25 驗證)
12. **外部建議需獨立驗證** - Gemini 的冷號策略經驗證確實有效，但其他聲稱多數誇大或錯誤 (2026-01-25)
13. **持續優化是唯一出路** - 建立 `strategy_leaderboard.py` 自動辨識最佳窗口 (如 Window 50)，優於固定參數測試。

> 📅 最後更新：2026-01-25 (新增大樂透 2注 Markov 策略，Edge +2.50%，並整合至 predict_smart_entry.py)
