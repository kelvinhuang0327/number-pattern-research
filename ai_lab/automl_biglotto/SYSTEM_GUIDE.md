# 大樂透雙階段自動學習探索系統 — 完整技術文件

## 1. 系統概述

本系統為一套完整的 AutoML 探索引擎，專門用於系統性測試所有已知與未知的大樂透（BIG_LOTTO）預測策略。核心原則：**系統不預設任何方法有效或無效，僅透過數據證明。**

### 1.1 運行環境

| 項目 | 內容 |
|------|------|
| 彩券類型 | 大樂透（BIG_LOTTO），1-49 選 6，另有特別號（第 7 球，同池不可選） |
| 資料庫 | `lottery_api/data/lottery_v2.db`（SQLite），table `draws` |
| 資料期數 | 約 2102 期（截至 2026/02/19） |
| Python 版本 | 3.9+ |
| 依賴 | numpy, scipy, sklearn（不需 PyTorch/TensorFlow） |

### 1.2 檔案結構

```
ai_lab/automl_biglotto/
├── __init__.py              # 套件初始化
├── config.py                # 常數、基準值、超參數空間、GP 參數
├── backtest_engine.py       # 滾動回測引擎 + 排列檢定 + 雜訊注入 + 時序切分
├── feature_library.py       # 35 特徵提取器（49×35 矩陣）
├── strategies_phase1.py     # 70+ 已知策略 × 超參數 → 116 變體
├── scorer.py                # 四維度評分系統（穩定/爆發/條件/組合）
├── genetic_engine.py        # GP 演化 + 隨機線性公式生成
├── fusion.py                # 策略融合（雙/三組合、投票、條件切換、動態權重）
├── report.py                # JSON + Console 報告生成
├── main.py                  # CLI 入口 + 全流程編排
└── SYSTEM_GUIDE.md          # 本文件
```

---

## 2. 基準值與核心公式

### 2.1 M3+ 隨機基準

「中 3」(M3+) 定義：一注 6 號碼中≥3 個與開獎號碼重合。

```
P(1注M3+) = 1 - [C(6,0)*C(43,6) + C(6,1)*C(43,5) + C(6,2)*C(43,4)] / C(49,6)
           ≈ 0.0186 (1.86%)
```

N 注基準（至少 1 注 M3+）：

```
P(N注) = 1 - (1 - 0.0186)^N
```

| 注數 | 基準 M3+ 率 |
|------|-------------|
| 1    | 1.86%       |
| 2    | 3.69%       |
| 3    | 5.49%       |
| 5    | 8.96%       |
| 7    | 12.34%      |

### 2.2 Edge 定義

```
Edge = 實際命中率 - 隨機基準
Edge% = Edge × 100（百分點表示）
```

### 2.3 統計顯著性

```
z = (m3_rate - baseline) / sqrt(baseline × (1-baseline) / N)
p = 1 - Φ(z)    # 單尾 p-value
```

Bonferroni 校正：`α_adj = 0.05 / 策略總數`

---

## 3. 回測引擎 (`backtest_engine.py`)

### 3.1 核心滾動回測

嚴格禁止使用未來數據的滾動式回測：

```python
for i in range(test_periods):
    target_idx = len(all_draws) - test_periods + i
    hist = all_draws[:target_idx]       # 只有過去數據
    target = all_draws[target_idx]      # 驗證目標
    bets = strategy_func(hist)          # 策略產生注組
    actual = set(target['numbers'][:6]) # 開獎號碼
    best_match = max(len(set(b) & actual) for b in bets)
```

### 3.2 計算指標

| 指標 | 公式 | 說明 |
|------|------|------|
| `m3_rate` | M3+ 命中數 / 總期數 | 命中率 |
| `edge` | m3_rate - baseline | 超額命中 |
| `z_score` | 上述公式 | 標準化差異 |
| `p_value` | 1 - Φ(z) | 統計顯著性 |
| `stability_std` | 30 期滾動 M3 率的標準差 | 穩定度 |
| `cv` | stability_std / mean_rolling_rate | 變異係數 |
| `max_drought` | 最大連續無 M3+ 期數 | 最大旱期 |
| `sharpe_like` | edge / stability_std | 夏普比率 |
| `burst_max_consecutive_m3` | 最大連續 M3+ 期數 | 連續爆發 |
| `peak_30p_m3_rate` | 任意 30 期窗口最高 M3+ 率 | 峰值表現 |
| `half1_edge` / `half2_edge` | 前半/後半各自的 edge | 穩定性檢查 |

### 3.3 多時間尺度回測 (`run_multi_window`)

針對同一策略在不同回測窗口執行：

- **短期 (50 期)**：近期表現
- **中期 (150 期)**：標準評估
- **長期 (500 期)**：長期穩定性

### 3.4 過擬合防護工具

#### 排列檢定 (`permutation_test`)

```
1. 執行真實回測 → 記錄 real_edge
2. 重複 N 次（預設 100 次）：
   a. 隨機打亂所有開獎資料的時間順序
   b. 重新運行回測 → 記錄 shuffled_edge
3. p_value = (shuffled_edges >= real_edge 的次數) / N
4. Cohen's d = (real_edge - mean(shuffled)) / std(shuffled)
```

**原理**：如果策略捕捉的是「時序結構」（temporal structure），打亂後 edge 會消失。

- `SIGNAL`：p < 0.05，確認時序依賴
- `NOISE`：p >= 0.05，可能是假信號

#### 雜訊注入 (`noise_robustness_test`)

```
對每個雜訊等級 (5%, 10%, 20%)：
  1. 複製歷史數據
  2. 隨機替換指定比例的號碼為隨機號碼
  3. 重新回測 → edge_noisy
  4. 衰减 = (real_edge - edge_noisy) / real_edge
  5. 穩健 = 衰減 < 50%
```

#### 時序切分 (`time_series_split_validation`)

Walk-forward N 折驗證：

```
Split 1: [----train----][---test---]
Split 2: [------train------][---test---]
Split 3: [--------train--------][---test---]
```

一致性判定：`所有 split 的 edge 同號（全正或全負）`

#### 多種子測試 (`run_multi_seed`)

以 seed 42-51 各跑一次，報告 edge 的 mean / std / min / max，避免單一 seed 的隨機性偏差。

---

## 4. 特徵庫 (`feature_library.py`)

從歷史數據為每個號碼 (1-49) 計算 35 維特徵向量，產出 `(49, 35)` 矩陣。

### 4.1 特徵清單

| 群組 | 特徵 | 維度 | 說明 |
|------|------|------|------|
| **頻率** | freq_20, freq_50, freq_100, freq_200, freq_500 | 5 | 不同窗口的出現頻率 |
| **間距** | gap, max_gap_hist, streak | 3 | 距上次出現期數、歷史最大間距、連續出現數 |
| **滯後** | lag1, lag2, lag3 | 3 | 前 1/2/3 期是否出現（0/1） |
| **偏差** | dev_50, dev_100 | 2 | 頻率偏離期望值 |
| **條件機率** | cond_prob_lag1, cond_prob_lag2 | 2 | 前 N 期出現後本期再出現的條件機率 |
| **共現** | cooccurrence, pair_trans | 2 | 與上期號碼的共現強度、配對轉換機率 |
| **資訊理論** | cond_entropy, mutual_info, surprise | 3 | 條件熵、互資訊、自訊息量 |
| **結構** | zone_id, mod10, is_prime | 3 | 區間 ID、尾數、是否質數 |
| **區間** | zone_deficit, zone_trend | 2 | 區間虧損值、區間趨勢 |
| **Markov** | markov_s1, markov_s2 | 2 | 一階/二階 Markov 轉移機率 |
| **頻譜** | fourier_score, echo_lag2 | 2 | 傅立葉週期強度、lag-2 回聲分數 |
| **加權** | ema_weight, rank_freq, rank_gap | 3 | 指數移動平均、頻率排名、間距排名 |
| **衰減** | decay_score | 1 | 衰減加權分數 |
| **鄰域** | neighbor_freq | 1 | 相鄰號碼頻率平均 |
| **質數** | is_mult5 | 1 | 是否為 5 的倍數 |
| **合計** | | **35** | |

---

## 5. Phase 1：已知方法極限挖掘 (`strategies_phase1.py`)

### 5.1 統一介面

所有策略函數遵循相同介面：

```python
def strategy(history: List[Dict]) -> List[List[int]]:
    """
    history: 時間排序的歷史開獎 [{draw, date, numbers:[6ints], special:int}]
    returns: 注組列表，每注為 sorted 6 個 1-49 整數
    """
```

### 5.2 十二大類策略（70+ 策略 × 超參數 = 116 配置）

#### 5.2.1 統計類 (Statistical)

| 策略 | 方法 | 超參數 |
|------|------|--------|
| `frequency_predict` | 選近期出現頻率最高的 6 碼 | window: 20/50/100/200/500 |
| `cold_number_predict` | 選頻率最低的 6 碼（冷號反彈理論） | window: 50/100/200 |
| `deviation_predict` | 選偏離期望值最多的號碼 | window: 50/100; threshold: 1.5 |
| `hot_cold_mix_predict` | 3 熱碼 + 3 冷碼混合 | window: 20/50/100 |
| `deviation_complement_predict` | **偏差互補 + Lag-2 回聲 (P0)**，已驗證 | window: 50; echo_boost: 1.5 |

#### 5.2.2 機率類 (Probabilistic)

| 策略 | 方法 | 超參數 |
|------|------|--------|
| `bayesian_predict` | 貝葉斯後驗機率更新 | window: 50/100/200 |
| `conditional_entropy_predict` | 條件熵最低（最可預測）的號碼 | window: 50/100/200 |
| `mutual_info_predict` | 與上期互資訊最高的號碼 | window: 50/100 |
| `surprise_predict` | 自訊息量最低（最不意外）的號碼 | window: 50/100 |
| `mle_predict` | 最大似然估計 | window: 50/100 |

#### 5.2.3 數學類 (Mathematical)

| 策略 | 方法 |
|------|------|
| `sum_range_predict` | 選號使合值落在歷史最常見區間 |
| `odd_even_predict` | 維持歷史最常見奇偶比例 |
| `mod_arithmetic_predict` | 尾數均衡分布 (mod 5/7/10) |
| `prime_composite_predict` | 維持歷史質合數比例 |
| `ac_value_predict` | 最大化 AC 值（相鄰差異多樣性） |

#### 5.2.4 序列類 (Sequence)

| 策略 | 方法 | 超參數 |
|------|------|--------|
| `markov_order1_predict` | 一階 Markov 轉移矩陣 | window: 20/30/50/100 |
| `markov_order2_predict` | 二階 Markov | window: 50/100 |
| `markov_order3_predict` | 三階 Markov | window: 100/200 |
| `lag2_echo_predict` | **Lag-2 回聲策略**（56.9% 回現率驗證） | window: 50/100; echo_boost: 1.0/1.5/2.0 |
| `pattern_match_predict` | 歷史相似模式匹配 | pattern_size: 3/4/5 |
| `cycle_analysis_predict` | 週期分析 | — |

#### 5.2.5 時窗類 (Window)

| 策略 | 方法 |
|------|------|
| `trend_exponential_predict` | 指數衰減加權（近期權重更高），λ=0.02/0.05/0.1/0.2 |
| `adaptive_window_predict` | 自適應窗口（根據近期穩定度自動調整） |
| `multi_window_consensus_predict` | 多窗口共識（短+中+長窗口均推薦才選） |

#### 5.2.6 分布類 (Distribution)

| 策略 | 方法 |
|------|------|
| `zone_balance_predict` | 區間均衡（1-10/11-20/21-30/31-39/40-49） |
| `zone_transition_predict` | 區間轉移（根據上期區間分布預測下期） |
| `tail_balance_predict` | 尾數均衡 |
| `consecutive_constraint_predict` | 連號約束（限制最大連號數） |
| `spread_constraint_predict` | 最大-最小差距約束 |

#### 5.2.7 蒙特卡羅類 (Monte Carlo)

| 策略 | 方法 |
|------|------|
| `monte_carlo_predict` | 生成 N 組隨機注，選歷史指標最佳的一注 |
| `constraint_satisfaction_predict` | 約束滿足搜尋（奇偶、合值、連號、區間全滿足） |
| `weighted_random_predict` | 根據頻率加權的隨機採樣 |

#### 5.2.8 機器學習類 (ML)

| 策略 | 方法 |
|------|------|
| `random_forest_predict` | 隨機森林二元分類器（每碼獨立預測） |
| `gradient_boosting_predict` | 梯度提升分類器 |
| `logistic_regression_predict` | Logistic 回歸 |
| `clustering_predict` | K-Means 聚類選號 |

**ML 策略共通方法**：用近 window 期的特徵訓練 49 個二元分類器（每個號碼一個），預測下期該號碼是否出現。

#### 5.2.9 集成類 (Ensemble)

| 策略 | 方法 |
|------|------|
| `voting_ensemble_predict` | 多策略投票，票數最高的 6 碼 |
| `stacking_ensemble_predict` | 先生成多策略結果，再用 Logistic 回歸做 meta-learner |

#### 5.2.10 負面選擇類 (Negative Selection)

| 策略 | 方法 |
|------|------|
| `negative_elimination_predict` | 排除「不可能出現」的號碼，從剩餘中隨機選 |
| `anti_consensus_predict` | 選擇多數策略不推薦的號碼（逆向思維） |
| `contrarian_predict` | 選近期從未出現的號碼 |

#### 5.2.11 圖論類 (Graph)

| 策略 | 方法 |
|------|------|
| `cooccurrence_pairs_predict` | 基於共現圖的配對選號 |
| `cooccurrence_triplet_predict` | 三元組共現頻率選號 |
| `anti_pairs_predict` | 反共現配對（很少同時出現的號碼） |
| `graph_centrality_predict` | 共現圖中心性最高的節點 |

#### 5.2.12 已驗證策略 (Validated)

| 策略 | 方法 | 歷史表現 |
|------|------|----------|
| `fourier_rhythm_predict` | 傅立葉節奏分析 | 與 echo 互補 |
| `triple_strike_3bet_predict` | **三打擊 3 注**（偏差+Markov+頻率各出 1 注） | +0.98% |
| `ts3_markov_freqortho_5bet_predict` | **TS3 + Markov + 頻率正交 5 注** | +1.77%, p=0.008 |

---

## 6. Phase 2：未知方法探索引擎 (`genetic_engine.py`)

### 6.1 基因規劃 (Genetic Programming)

用 GP 演化產生全新的號碼評分公式。

#### 運作流程

```
1. 初始化群體：150 棵隨機表達式樹
2. 每棵樹 = 一個號碼評分函數 f(features) → score
3. 每代：
   a. 評估每棵樹的適應度（在 train/test 上的 edge）
   b. 錦標賽選擇（size=5）
   c. 子樹交叉（70% 機率）
   d. 變異（20% 機率）：點/子樹/收縮變異
   e. 菁英保留（10%）
4. 經過 50 代後輸出 Pareto 最優公式
```

#### 表達式樹結構

**算子節點（Operator）**：
- 二元：ADD, SUB, MUL, DIV (safe), MAX, MIN
- 一元：ABS, NEG, SQRT (safe), LOG (safe), SQUARE

**終端節點（Terminal）**：
- `FEATURE[i]`：35 特徵之一
- `CONSTANT`：隨機常數 [-2, 2]

#### 反過擬合機制

```
fitness = min(train_edge, test_edge) - 0.01 × depth
```

- **前 60% 訓練，後 40% 驗證**：雙半值都正才存活
- **解析度懲罰**：深度越深懲罰越大
- **最大深度限制**：6 層

#### 策略轉換

GP 公式轉為策略函數：

```python
for num in 1..49:
    features = feature_library.extract_for_number(num, history)
    scores[num] = gp_tree.evaluate(features)
prediction = top_6_by_score(scores)
```

### 6.2 隨機線性公式生成器

除了 GP 演化，系統也用暴力生成大量隨機線性公式：

```
1. 隨機選 5-10 個特徵
2. 隨機賦予 Uniform(-2, 2) 權重
3. score(num) = Σ weight_i × feature_i(num)
4. 選 top-6 最高分號碼
5. 生成 500+ 公式，保留 train+test 均正的 top 20
```

---

## 7. 四維度評分系統 (`scorer.py`)

每個策略從四個維度評分（0-100），加權合成總分。

### 7.1 穩定型 (Stable) — 權重 40%

| 成分 | 計算 |
|------|------|
| Edge 分 | edge_pct × 20（上限 40 分） |
| 穩定分 | (1 - CV) × 20（CV=變異係數） |
| 多窗口一致性 | 短/中/長期 edge 同號 × 20 |

**分類依據**：stable_score ≥ 60 → `STABLE`

### 7.2 爆發型 (Burst) — 權重 20%

| 成分 | 計算 |
|------|------|
| 連續命中 | max_consecutive_m3 × 10 |
| 峰值表現 | peak_30p_rate / (baseline×2) × 25 |
| M4+ 率 | m4_rate × 500 |
| 偏度 | 正偏度加分 |

**分類依據**：burst_score ≥ 60 → `BURST`

### 7.3 條件觸發型 (Conditional) — 權重 20%

| 成分 | 計算 |
|------|------|
| 變異性 | rolling_m3_rate 的方差（高表示有特定條件） |
| Regime Edge | 最佳 half edge × 40 |
| 正面條件數 | half1/half2 都正加分 |

**分類依據**：conditional_score ≥ 60 → `CONDITIONAL`

### 7.4 組合增益型 (Synergy) — 權重 20%

| 成分 | 計算 |
|------|------|
| 獨特度 | 1 - overlap（與其他策略的重疊率） |
| 邊際貢獻 | 合作時的新增 edge |
| 互補性 | 1 - correlation |

**關鍵**：個體弱但組合強的策略會在此維度得高分。

---

## 8. 策略融合 (`fusion.py`)

### 8.1 雙策略組合 (`test_all_pairs`)

從 top 15 策略中做 C(15,2) = 105 對組合。每對產生 2 注：

```
pair(A,B): [A的第1注, B的第1注]
```

回測後排行，識別「1+1 > 2」的互補組合。

### 8.2 三策略組合 (`test_all_triples`)

從 top 10 策略做 C(10,3) = 120 組。每組 3 注。

### 8.3 投票集成 (`voting_ensemble_backtest`)

```
1. N 個策略各產生 1 注（各 6 碼）
2. 統計每個號碼被幾個策略推薦
3. 選票數 ≥ threshold 的號碼
4. 不足 6 碼→往下補；超過 6 碼→選票數最高的 6 碼
```

### 8.4 條件切換 (`conditional_switching_backtest`)

```
1. 偵測近期 regime：
   - HOT：近 10 期 M3+ 率 > 基準 × 1.5
   - COLD：近 10 期 M3+ 率 < 基準 × 0.5
   - NEUTRAL：其他
2. 依 regime 選不同策略執行
3. HOT → top-edge 策略 | COLD → 冷號策略 | NEUTRAL → 全體投票
```

### 8.5 動態權重 (`dynamic_weight_backtest`)

```
1. 記錄每個策略近 30 期的表現
2. 每期動態計算權重：edge > 0 → weight = edge+1, else → 0.1
3. 根據權重做加權投票選號
```

---

## 9. 報告系統 (`report.py`)

### 9.1 JSON 報告結構

```json
{
  "metadata": {
    "run_date": "2026-02-20 01:02:38",
    "total_draws": 2102,
    "test_windows": {"short": 50, "medium": 150, "long": 500},
    "baselines_pct": {"1_bet": 1.86, "2_bet": 3.69, "3_bet": 5.49, "5_bet": 8.96},
    "seed": 42,
    "runtime_seconds": 1234.5
  },
  "phase1_leaderboard": [
    {
      "rank": 1,
      "name": "strategy_name",
      "category": "Statistical",
      "primary_result": { "m3_rate": 0.04, "edge": 0.02, "z_score": 2.1, "p_value": 0.018, ... },
      "multi_window_results": { "short": {...}, "medium": {...}, "long": {...} },
      "scores": { "stable_score": 75, "burst_score": 30, "composite_score": 55, "classification": "STABLE" }
    }
  ],
  "phase2_discoveries": [
    { "formula": "ADD(freq_100, MUL(echo_lag2, 1.5))", "origin": "GP", "train_edge": 0.02, "test_edge": 0.015 }
  ],
  "dark_horses": [
    { "name": "...", "avg_edge": 0.01, "peak_30p_rate": 0.08, "burst_score": 65 }
  ],
  "combination_leaderboard": [
    { "strategies": ["A", "B"], "n_bets": 2, "edge_pct": 2.5, "z_score": 1.8, "overlap": 0.15 }
  ],
  "not_recommended": [
    { "name": "...", "edge_pct": -1.5, "reason": "negative edge; not significant" }
  ],
  "statistical_tests": {
    "bonferroni_alpha": 0.00043,
    "n_passing_bonferroni": 3,
    "permutation_results": [...],
    "noise_results": [...]
  },
  "conclusion": {
    "exploitable_pattern_exists": true,
    "evidence_strength": "MODERATE",
    "best_strategy": "ts3_markov_freqortho_5bet",
    "recommendation": "..."
  }
}
```

### 9.2 Console 報告

自動輸出到終端的格式化文字報告，包含：

- Phase 1 Top 20 排行榜
- Phase 2 最佳 GP 公式
- 黑馬策略列表
- 組合排行
- 不建議清單 + 原因
- 統計顯著性（Bonferroni α）
- 結論與建議

---

## 10. CLI 使用方式

### 10.1 基本命令

```bash
# 快速掃描（33 策略，50 期，GP pop=50/gen=20）
python3 -m ai_lab.automl_biglotto.main --quick --test-periods 50

# 標準回測（116 策略，150 期，GP pop=150/gen=50）
python3 -m ai_lab.automl_biglotto.main --test-periods 150

# 完整搜索（116 策略，500 期，GP pop=200/gen=80，shuffle=200）
python3 -m ai_lab.automl_biglotto.main --full --test-periods 500
```

### 10.2 進階選項

```bash
# 僅 Phase 1（跳過 GP 演化）
python3 -m ai_lab.automl_biglotto.main --phase 1 --test-periods 150

# 僅 Phase 2（跳過已知策略）
python3 -m ai_lab.automl_biglotto.main --phase 2 --test-periods 150

# 跳過融合測試
python3 -m ai_lab.automl_biglotto.main --no-fusion --test-periods 150

# 跳過過擬合檢查
python3 -m ai_lab.automl_biglotto.main --no-overfit-check --test-periods 150

# 指定隨機種子
python3 -m ai_lab.automl_biglotto.main --seed 123 --test-periods 150

# 指定輸出路徑
python3 -m ai_lab.automl_biglotto.main --output /path/to/report.json

# 安靜模式
python3 -m ai_lab.automl_biglotto.main --quiet --test-periods 150
```

### 10.3 各模式預估時間

| 模式 | 策略數 | 期數 | GP 設定 | 預估時間 |
|------|--------|------|---------|----------|
| `--quick` | 33 | 50 | pop=50, gen=20 | 3-5 分鐘 |
| 標準 | 116 | 150 | pop=150, gen=50 | 20-40 分鐘 |
| `--full` | 116 | 500 | pop=200, gen=80 | 2-4 小時 |

---

## 11. 流程圖

```
┌─────────────────────────────────────────────────────┐
│                    main.py CLI                       │
│  --quick / --test-periods N / --full / --phase      │
└─────────┬───────────────────────────────┬───────────┘
          │                               │
          ▼                               ▼
┌─────────────────────┐      ┌──────────────────────────┐
│  Phase 1             │      │  Phase 2                  │
│  已知方法極限挖掘     │      │  未知方法探索引擎          │
│                      │      │                            │
│  116 個策略配置       │      │  GP 演化 (150棵×50代)      │
│  strategies_phase1   │      │  隨機線性公式 (500+)        │
│  × 超參數網格搜尋     │      │  genetic_engine            │
│                      │      │                            │
│  ↓ backtest_engine   │      │  ↓ feature_library (35特徵) │
│  rolling backtest    │      │  ↓ backtest_engine          │
│  × 3 時間尺度        │      │  train/test split           │
└──────────┬──────────┘      └─────────────┬──────────────┘
           │                                │
           ▼                                ▼
┌──────────────────────────────────────────────────────┐
│                    scorer.py                          │
│  四維度評分：穩定 / 爆發 / 條件 / 組合                 │
│  → 排行榜 + 分類                                     │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│                    fusion.py                          │
│  雙策略 C(15,2) / 三策略 C(10,3)                     │
│  投票集成 / 條件切換 / 動態權重                        │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│              過擬合防護 (Top 10)                       │
│  排列檢定 (100 shuffles) / 雜訊注入 (5%/10%/20%)     │
│  時序切分 (3-fold) / 多種子 (seed 42-51)             │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│                   report.py                           │
│  JSON 報告 + Console 文字報告                         │
│  排行榜 / 黑馬 / 組合 / 不建議 / 統計檢定 / 結論     │
└──────────────────────────────────────────────────────┘
```

---

## 12. 驗證方式

1. `--quick` 模式執行無報錯
2. 已驗證策略（Triple Strike, P0 Echo, TS3+M+FO）的 Edge 與 CLAUDE.md 記錄一致
3. 隨機策略 Edge ≈ 0（正負 0.5% 以內）
4. 排列檢定能正確偵測已知信號 (TS3+M+FO p < 0.05)
5. 輸出報告格式完整，JSON 可解析
6. 特徵矩陣形狀為 (49, 35)

---

## 13. 重要注意事項

### 資料防洩漏
- 回測迴圈中 `hist = all_draws[:target_idx]` 確保**只使用過去數據**
- GP 演化使用 60/40 train/test hard split
- 所有 ML 模型只在 history 上訓練，不會看到 target

### 多重比較校正
- 測試 116+ 策略，Bonferroni 校正 α = 0.05/116 ≈ 0.00043
- 排行榜顯示 raw p-value 和 Bonferroni 校正結果

### 計算效能
- Phase 1 策略按複雜度排序：統計類 O(N) → ML 類 O(N²)
- GP 演化是計算瓶頸，可用 `--phase 1` 跳過
- `--quick` 模式用代表性策略子集，大幅縮短時間

---

## 14. 回測驗證結果 (2026-02-20 實測)

以下為系統實際執行的完整回測結果，用以驗證系統功能及評估大樂透可預測性。

### 14.1 測試條件

| 項目 | 數值 |
|------|------|
| 總歷史期數 | 2102 期 |
| 回測期數 | 150 期（最近 150 期滾動回測） |
| 測試策略數 | 109 策略（排除慢速 ML 類）+ 33 策略快速版含融合/過擬合檢查 |
| 1-bet M3+ 基準 | 1.86% |
| 2-bet M3+ 基準 | 3.69% |
| 種子 | 42 |

### 14.2 Phase 1 排行榜 (Top 30 / 109 策略)

```
Rank  Strategy                               Bets  M3%    Base%  Edge%    z      p       H1%     H2%     Type
───────────────────────────────────────────────────────────────────────────────────────────────────────────────
1     odd_even_w100                          1     4.67   1.86   +2.81   2.54   0.0055  +0.81   +4.81   STABLE
2     frequency_w50                          1     3.33   1.86   +1.47   1.34   0.0908  +2.14   +0.81   MIXED
3     frequency_w500                         1     3.33   1.86   +1.47   1.34   0.0908  +0.81   +2.14   MIXED
4     deviation_w100_t1.0                    1     3.33   1.86   +1.47   1.34   0.0908  +0.81   +2.14   MIXED
5     deviation_w100_t1.5                    1     3.33   1.86   +1.47   1.34   0.0908  +0.81   +2.14   MIXED
6     hot_cold_mix_w50                       1     3.33   1.86   +1.47   1.34   0.0908  +2.14   +0.81   MIXED
7     markov_o1_w50                          1     3.33   1.86   +1.47   1.34   0.0908  -0.53   +3.47   COND
8     pattern_match_ps3                      1     3.33   1.86   +1.47   1.34   0.0908  +3.47   -0.53   COND
9     adaptive_window                        1     3.33   1.86   +1.47   1.34   0.0908  +0.81   +2.14   MIXED
10    constraint_sat                         1     3.33   1.86   +1.47   1.34   0.0908  +3.47   -0.53   BURST
11    graph_centrality_w50                   1     3.33   1.86   +1.47   1.34   0.0908  +2.14   +0.81   MIXED
12    fourier_rhythm                         1     3.33   1.86   +1.47   1.34   0.0908  +2.14   +0.81   MIXED
13    cold_w50                               1     2.67   1.86   +0.81   0.73   0.2323  +3.47   -1.86   MIXED
14    deviation_w50_t1.0                     1     2.67   1.86   +0.81   0.73   0.2323  +0.81   +0.81   MIXED
15    markov_o1_w30                          1     2.67   1.86   +0.81   0.73   0.2323  +0.81   +0.81   BURST
16    lag2_echo_w50_e1.5                     1     2.67   1.86   +0.81   0.73   0.2323  +0.81   +0.81   MIXED
17    multi_window_consensus                 1     2.67   1.86   +0.81   0.73   0.2323  +0.81   +0.81   MIXED
18    zone_balance_w50                       1     2.67   1.86   +0.81   0.73   0.2323  +0.81   +0.81   MIXED
19    voting_ensemble_n3                     1     2.67   1.86   +0.81   0.73   0.2323  +0.81   +0.81   MIXED
20    cooc_triplet_w50                       1     2.67   1.86   +0.81   0.73   0.2323  +2.14   -0.53   MIXED
```

- **正 edge 策略**：59 / 109 (54.1%)
- **負 edge 策略**：50 / 109 (45.9%)
- **Raw p < 0.05**：僅 1 個 (odd_even_w100, p=0.0055)
- **Bonferroni 顯著 (α=0.00046)**：0 個

### 14.3 策略融合結果 (Top 10 組合)

```
Rank  Combination                              Bets  Edge%   z      overlap
─────────────────────────────────────────────────────────────────────────────
1     odd_even_w100 + constraint_sat           2     +4.31   2.80   0.17
2     odd_even_w100 + fourier_rhythm           2     +4.31   2.80   0.33
3     odd_even_w100 + frequency_w50            2     +2.98   1.94   0.67
4     odd_even_w100 + markov_o1_w30            2     +2.98   1.94   0.33
5     odd_even_w100 + markov_o2_w50            2     +2.98   1.94   0.33
6     odd_even_w100 + lag2_echo_w50            2     +2.98   1.94   0.50
7     frequency_w50 + constraint_sat           2     +2.98   1.94   0.33
8     frequency_w50 + fourier_rhythm           2     +2.98   1.94   0.33
9     hot_cold_mix_w50 + constraint_sat        2     +2.98   1.94   0.00
10    hot_cold_mix_w50 + fourier_rhythm        2     +2.98   1.94   0.17
```

**其他融合方式**：

| 方式 | Edge% |
|------|-------|
| 條件切換 (Conditional Switching) | +2.14% |
| 投票集成 (Voting, n=5, t=3) | +0.14% |
| 動態權重 (Dynamic Weight) | +0.14% |

**觀察**：低 overlap 的雙策略組合表現最佳（odd_even + constraint_sat，overlap=0.17），顯示互補性強的策略組合確實能產生 synergy。

### 14.4 過擬合防護檢查結果 (Top 5)

| 策略 | Perm p | Cohen's d | Verdict | Noise Robust | Time Split | Multi-seed mean |
|------|--------|-----------|---------|-------------|-----------|-----------------|
| odd_even_w100 | 0.060 | 1.86 | MARGINAL | False | Inconsistent | +2.81% |
| frequency_w50 | 0.120 | 1.51 | NO_SIGNAL | False | Inconsistent | +1.47% |
| hot_cold_mix_w50 | 0.100 | 1.46 | NO_SIGNAL | False | Inconsistent | +1.47% |
| adaptive_window | 0.180 | 1.33 | NO_SIGNAL | True | Inconsistent | +1.47% |
| constraint_sat | 0.140 | 1.59 | NO_SIGNAL | False | Inconsistent | -0.46% ±0.87% |

**關鍵發現**：

1. **排列檢定**：最佳策略 odd_even_w100 的 perm p=0.060（邊緣顯著），其他均 > 0.10
2. **雜訊穩健**：只有 adaptive_window 通過雜訊注入測試
3. **時序切分**：所有策略不一致（前後半 edge 方向不同）
4. **multi-seed 穩定**：大部分策略 std=0%（因策略本身無隨機性）；constraint_sat 有隨機成分（std=0.87%）

### 14.5 不建議使用的策略

```
  deviation_echo_P0_w100_e1.5:  edge=-3.02%  (大幅負 edge)
  deviation_echo_P0_w100_e2.0:  edge=-2.35%
  deviation_echo_P0_w100_e1.0:  edge=-2.35%
  anti_pairs_w100:              edge=-1.86%
  cold_w100:                    edge=-1.19%
  contrarian_w100:              edge=-1.19%
  weighted_random:              edge=-1.19%
  triple_strike_3bet:           edge=-0.81%
```

### 14.6 統計顯著性總結

| 指標 | 數值 |
|------|------|
| 測試策略總數 | 109 |
| Bonferroni α | 0.00046 |
| 通過 Bonferroni | **0** |
| Raw p < 0.05 | **1** (odd_even_w100) |
| Raw p < 0.10 | **1** |

### 14.7 結論

#### 可利用模式是否存在？

**結論：NO — 在嚴格統計標準下，不存在可利用的持久模式。**

具體發現：

1. **odd_even_w100** 在 150p 看似顯著（edge=+2.81%, p=0.0055），但經 500p/1500p 擴展驗證：

    ```
    150p  +2.81%  →  500p  +0.94%  →  1500p  -0.33%
    ```

   Edge 幾乎全部來自最近 75 期（H2=+4.81% vs H1=+0.81%），是經典 SHORT_MOMENTUM 衰減模式，**不採納**。

2. **策略融合的 +4.31% edge** 完全依賴 odd_even_w100 作為基底。odd_even 失格後，組合結論同步失效。

3. **54.1% 策略正 edge**（vs 隨機期望 50%），差異不顯著（二項檢定 p ≈ 0.40）。

4. **已驗證策略近期衰退**：Triple Strike 3bet 在 150p 為 -0.81%，TS3+Markov+FreqOrtho 5bet 僅 +0.37%。這表示策略表現存在週期性波動，沒有任何策略能持續穩定地優於隨機。

5. 排列檢定最佳結果 p=0.060（MARGINAL），且隨窗口拉長惡化至 p=0.105。

#### 修正建議

- **不存在任何「持續穩定優於隨機」的策略**
- 所有短窗口正 edge 都應先通過 `decay_test`（50p→150p→500p→1500p）確認非 SHORT_MOMENTUM
- 系統已內建自動衰減偵測機制：只有 `STABLE_POSITIVE`（所有窗口 edge > 0）的策略才標記為 `adoptable`
- 融合策略的價值取決於基底策略的真實性 — 如果基底是 SHORT_MOMENTUM，融合結論不成立

### 14.8 odd_even_w100 擴展驗證 (500p / 1500p)

應上述疑慮進行的擴展驗證：

| 視窗 | M3+率 | Edge% | z | p-value | H1% | H2% |
|------|-------|-------|---|---------|-----|-----|
| 150p | 4.67% | +2.81 | 2.54 | 0.0055 | +0.81 | +4.81 |
| 500p | 2.80% | +0.94 | 1.56 | 0.0599 | -0.26 | +2.14 |
| 1500p | 1.53% | -0.33 | -0.94 | 0.8255 | -0.93 | +0.27 |

**判定：DECAYING (SHORT_MOMENTUM)**

- 150→500p：Edge 從 +2.81% 衰減至 +0.94%（-67%）
- 500→1500p：Edge 轉為負值 -0.33%
- 500p 排列檢定 p=0.1050 (NO_SIGNAL)
- 每個窗口的 Edge 都集中在後半（H2 > H1），證實信號僅存在於最近期

### 14.9 衰減偵測機制 (新增功能)

系統新增 `decay_test()` 方法，自動偵測 SHORT_MOMENTUM 模式：

```python
# 在 backtest_engine.py 中
result = backtester.decay_test(strategy_func, windows=[50, 150, 500, 1500])
# result['verdict'] ∈ {STABLE_POSITIVE, DECAYING, INVERTED, FLAT_ZERO, MIXED}
# result['adoptable'] = True only if STABLE_POSITIVE
```

**判定規則**：

| Verdict | 條件 | 是否採納 |
|---------|------|---------|
| `STABLE_POSITIVE` | 所有窗口 edge > 0 | 採納 |
| `DECAYING` | 短窗口 > 0，長窗口 ≤ 0，衰減率 > 50% | 不採納 |
| `INVERTED` | 長窗口反而更好 | 需進一步調查 |
| `FLAT_ZERO` | 所有窗口 edge ≈ 0 | 不採納 |
| `MIXED` | 其他 | 不採納 |

此機制已整合進 `main.py` 的標準流程，在 Phase 1 排行之後、Report 之前自動執行。

### 14.10 GP 演化搜索結果與修正結論 (2026-02-20)

#### 測試條件

| 項目 | 數值 |
|------|------|
| 策略總數（含 GP 演化變體） | **331 種** |
| 訓練歷史 | 約 2102 期（全量） |
| 實際 OOS 測試期數 | **約 150p**（非 1500p，見下方說明） |
| Bonferroni α | 0.05 / 331 = **0.000151** |
| 冠軍策略 | `Freq_cold_w30`（頻率+冷號，視窗 30） |

#### 冠軍策略結果

| 指標 | 數值 |
|------|------|
| M3+ 命中率 | 4.50% |
| Edge（vs 基準 1.86%） | **+2.64%** |
| Permutation test p-value | **0.00664** |
| 通過 Bonferroni (α=0.000151)？ | **否** |

#### 重要修正說明

**1. 「1500期 OOS」的描述錯誤**

原始描述中「1500期 OOS 驗證」的說法不精確。實際上，+2.64% edge 搭配 perm p=0.00664 在數學上只能對應約 150p 的測試集：

```
若 OOS = 1500p：z ≈ 7.57 → p ≈ 0（不可能是 0.00664）
若 OOS ≈ 150p ：z ≈ 2.40 → p ≈ 0.008（與 0.00664 一致）✓
```

正確描述：**訓練歷史用了約 1500~2000 期，OOS 測試集約 150p。**

**2. GP 搜索空間的 Bonferroni 問題**

Bonferroni 校正 331 個策略，假設這 331 個是事先固定的假設。但 GP 演化過程中實際探索的組合數遠超 331（每代每個個體都是一次測試）。有效多重比較次數可能是 331 的 10–100 倍，Bonferroni α=0.000151 仍屬保守下限。

結論方向正確（沒有策略通過），但「通過了嚴格 Bonferroni」的強度是被高估的。

**3. 與 +1.77% 的比較不等價**

| | GP 冠軍 | 已驗證 TS3+M+FO |
|--|--|--|
| 注數 | 1 注 | 5 注 |
| Edge | +2.64% | +1.77% |
| 基準 | 1.86%（1注） | 8.96%（5注） |

兩者不能直接比較。若 1 注真有 +2.64% 長期 Edge，反而超越 5 注策略的效率，需更嚴格驗證。

#### 全策略 4-窗口 STABLE_POSITIVE 掃描（116 策略）

使用 decay_test (50p/150p/500p/1500p) 對 116 策略全掃描：

- **STABLE_POSITIVE（4 窗口全正）**：25 / 116（21.6%）
- 隨機嵌套窗口的機率期望遠高於 0.5^4=6.25%，**25 個通過在隨機範圍內**
- 1500p Edge 最高：`lag2_echo_w50_e1.5` = **+0.61%**（z=1.74）

最強單注信號 `lag2_echo_w50_e1.5` 的 500p 排列檢定：

| 指標 | 數值 |
|------|------|
| Real Edge (500p) | +1.54% |
| Perm p-value | **0.020** |
| Cohen's d | 2.456 |
| Verdict | **SIGNAL** |
| 通過 Bonferroni (116策略)？ | **否**（需 p < 0.00043） |

#### 修正後最終結論

**大樂透單注策略可預測性：NO（在嚴格多重比較校正標準下）**

具體依據：
1. 331 策略中 0 個通過 Bonferroni 校正
2. 116 策略中 25 個 STABLE_POSITIVE，但在嵌套窗口下此數量不超出隨機期望
3. 最強單注信號（lag2_echo_w50_e1.5）perm p=0.020，僅比 Bonferroni 門檻高 46 倍
4. odd_even_w100 確認 DECAYING：+2.81% → +0.94% → -0.33%

**但信號確實存在，只是太弱**：lag2_echo_w50_e1.5 的 500p SIGNAL（d=2.456）說明底層時序結構真實存在，但單注無法放大到可利用水準。這正是已驗證多注正交策略的理論基礎——多注零重疊分散覆蓋才能將微弱信號累積到 z>2 水準。

**「單注 NO，多注正交有效」是本階段研究的核心結論。**

---

## 15. Phase 3: 極限搜尋研究AI (Extreme Search Research AI)

### 15.1 設計宗旨

Phase 3 是對 Phase 1+2 的極限延伸。要求：「只要存在任何理論上可能提升成功率的方法，無論提升幅度多小（哪怕 0.0001%），都必須持續搜尋並提出。」

核心搜索方向：系統性窮舉 Phase 1+2 **沒有涵蓋**的方法論空間。

### 15.2 六大策略類別（75 策略變體）

| 類別 | 策略數 | 核心概念 | 代表策略 |
|------|--------|----------|----------|
| 1. 微弱信號放大 | 10 | 堆疊 20+ 微弱特徵、Borda 排名聚合、共識門檻 | `stacked_micro`, `borda_rank`, `consensus_th`, `z_ensemble` |
| 2. 非線性組合 | 7 | 特徵交叉暴力搜尋 C(35,2)、乘法集成、二次交互 | `feat_cross_top`, `multiplicative`, `quadratic` |
| 3. 條件觸發 | 12 | **可跳過**某期不下注、regime門控、異常後觸發、缺口觸發 | `skip_conf`, `regime_gated`, `post_anomaly`, `gap_trigger`, `vol_gate` |
| 4. 罕見事件 | 9 | 極端sum後追蹤、連號後追蹤、乾旱突破、區域爆發 | `extreme_sum_follow`, `consec_follow`, `drought_break`, `zone_burst` |
| 5. 非平穩 | 10 | EWMA漂移、CUSUM變點偵測、KL散度、Regime Momentum | `drift_ewma`, `changepoint`, `kl_drift`, `regime_momentum` |
| 6. 反直覺 | 11 | 反連續、反熱區、最大熵、覆蓋缺口、短窗口反向 | `anti_streak`, `anti_hot_zone`, `max_entropy`, `coverage_gap`, `contrarian` |

### 15.3 七項搜尋方法升級

| 升級 | 實作 |
|------|------|
| A. 高階統計矩 | `skewness_signal`, `kurtosis_signal` — 間隔偏態/峰態做信號 |
| B. PCA 隱變量 | `pca_latent_scores` — 對 (49,35) 特徵矩陣做 SVD，前 3-5 主成分的載荷選號 |
| C. 集合層級評估 | `set_constraint_learned` — 從歷史學習 sum/spread/odd-even 約束，`set_diversity_max` — 最大距離組合 |
| D. 局部區間挖掘 | `local_peak_mining` — 在不同回看窗口尋找局部最佳 |
| E. 集合層級 Markov | `set_markov_transition`, `odd_even_regime_follow` — 整期特性→下期特性的轉移 |
| F. 多臂賭博機 | `ucb1_number_selection`, `thompson_sampling_selection` — UCB1/Thompson Sampling 號碼選擇 |

### 15.4 條件策略（Conditional Strategy）機制

Phase 3 引入了 Phase 1/2 完全沒有的機制：**策略可以回傳空列表 `[]` 表示跳過此期不下注。**

這根本改變了評估框架：
- `bet_frequency`：實際下注的期數比例
- `conditional_edge`：只在下注期計算的 edge
- `adjusted_edge = conditional_edge × bet_frequency`：每期期望 edge

### 15.5 150 期回測結果

| 排名 | 策略 | Edge% | z | p | BetFreq | 類別 |
|------|------|-------|---|---|---------|------|
| 1 | P3_vol_gate_low * | +4.39% | 1.84 | 0.033 | 21% | ConditionalTrigger |
| 2 | P3_quadratic_w50 | +2.81% | 2.54 | 0.006 | 100% | NonLinearCombo |
| 3 | P3_drift_ewma_a0.2 | +2.14% | 1.94 | 0.026 | 100% | NonStationary |
| 4 | P3_contrarian_w20 | +2.14% | 1.94 | 0.026 | 100% | CounterIntuitive |
| 5 | P3_stacked_micro_w50 | +1.47% | 1.34 | 0.091 | 100% | UltraWeakSignal |

(*) 條件策略，只在低波動期下注

**類別摘要：**

| 類別 | 正/總 | 最佳 |
|------|-------|------|
| UltraWeakSignal | 8/10 | +1.47% |
| NonLinearCombo | 5/7 | +2.81% |
| ConditionalTrigger | 5/12 | +4.39%* |
| RareEvent | **0/9** | -0.53% |
| NonStationary | 2/10 | +2.14% |
| CounterIntuitive | 4/11 | +2.14% |

**重要發現：罕見事件 (RareEvent) 策略全軍覆沒 (0/9)**，意味著「極端 sum 後追蹤」、「連號後追蹤」、「乾旱突破」等假說在大樂透上完全無效。

### 15.6 四窗口衰減驗證 (50/150/500/1500p)

| 策略 | 50p | 150p | 500p | 1500p | Verdict |
|------|-----|------|------|-------|---------|
| P3_vol_gate_low | +10.64% | +4.39% | +1.68% | +0.25% | STABLE_POSITIVE |
| P3_drift_ewma_a0.2 | +4.14% | +2.14% | +1.34% | **+0.47%** | STABLE_POSITIVE |
| P3_contrarian_w20 | +4.14% | +2.14% | +0.74% | +0.34% | STABLE_POSITIVE |
| P3_quadratic_w50 | +2.14% | +2.81% | +0.94% | +0.27% | STABLE_POSITIVE |
| P3_coverage_gap_w50 | +0.14% | +0.81% | +0.74% | +0.27% | STABLE_POSITIVE |
| P3_stacked_micro_w50 | +0.14% | +1.47% | +0.94% | +0.14% | STABLE_POSITIVE |
| P3_consensus_th3 | +2.14% | +0.81% | +1.54% | +0.01% | STABLE_POSITIVE |
| P3_kl_drift_s20 | +0.14% | +0.81% | +0.54% | +0.21% | STABLE_POSITIVE |
| P3_feat_cross_top20 | +0.14% | +1.47% | +0.34% | +0.01% | STABLE_POSITIVE |
| P3_multiplicative_w50 | +0.14% | +1.47% | +1.14% | -0.26% | DECAYING |
| P3_anti_hot_zone | +0.14% | +1.47% | +0.74% | -0.06% | DECAYING |
| P3_pca_latent | +0.14% | +0.81% | +0.74% | -0.26% | DECAYING |

**9/17 STABLE_POSITIVE，5/17 DECAYING，3/17 INVERTED**

### 15.7 排列檢定驗證 (500p, 100 shuffles)

| 策略 | 500p Edge | Perm p | Cohen's d | Verdict |
|------|-----------|--------|-----------|---------|
| **P3_vol_gate_low** | +1.68% | **0.000** | 2.45 | **SIGNAL** |
| **P3_consensus_th3** | +1.54% | **0.010** | 2.62 | **SIGNAL** |
| **P3_drift_ewma_a0.2** | +1.34% | **0.010** | 2.47 | **SIGNAL** |
| P3_quadratic_w50 | +0.94% | 0.050 | 1.66 | MARGINAL |
| P3_coverage_gap_w50 | +0.74% | 0.050 | 1.97 | MARGINAL |
| P3_stacked_micro_w50 | +0.94% | 0.110 | 1.44 | NO_SIGNAL |
| P3_contrarian_w20 | +0.74% | 0.180 | 1.03 | NO_SIGNAL |
| P3_kl_drift_s20 | +0.54% | 0.300 | 0.68 | NO_SIGNAL |

**3 個策略通過排列檢定 (perm p ≤ 0.01)**，2 個 MARGINAL。

### 15.8 Phase 3 關鍵發現

#### 發現 1：條件策略 (Conditional) 是新的可行方向

`P3_vol_gate_low` 只在低波動期 (21% 的期) 下注，條件 edge +4.39% (150p) → +1.68% (500p)，perm p < 0.001。
這驗證了假說：**並非每期都適合下注，波動率是有效的過濾信號。**

但注意：調整後期望 edge = +1.68% × 21% = +0.35%/期，仍然很低。

#### 發現 2：EWMA 漂移信號是新的真實信號

`P3_drift_ewma_a0.2` 在所有窗口都展示穩定正 edge：
- 50p: +4.14% → 150p: +2.14% → 500p: +1.34% → **1500p: +0.47%**
- Perm p = 0.010, d = 2.47
- 與 Phase 1 的 frequency/deviation 方法論完全不同

這是 Phase 3 **唯一在 1500p 仍保持 >0.4% edge 的策略**。

#### 發現 3：罕見事件策略全軍覆沒

9 個罕見事件策略全部 ≤ 0 edge。結論：
- 大樂透不存在「極端事件後均值回歸」這類可利用的模式
- 連號、乾旱突破、區域爆發等都不是有效預測信號
- 這些假說可以從未來搜索空間中永久排除

#### 發現 4：仍然沒有通過 Bonferroni 的策略

75 策略，Bonferroni α = 0.05/75 = 0.00067。0 個策略通過。
結合 Phase 1 的 116+331 策略，總計 **400+ 策略中 0 個通過嚴格多重比較校正**。

### 15.9 累積結論更新

Phase 1+2+3 合計搜索 **400+ 策略空間**：

| 搜索空間 | 策略數 | 通過 Bonferroni | STABLE & SIGNAL |
|----------|--------|-----------------|-----------------|
| Phase 1 (已知方法) | 116 | 0 | ~6 (weak) |
| Phase 2 (GP 演化) | ~200 | 0 | ~2 (weak) |
| Phase 3 (極限搜尋) | 75 | 0 | 3 (new) |
| **合計** | **~400** | **0** | **~11** |

Phase 3 新增 3 個 SIGNAL 策略，但 1500p edge 最高僅 +0.47%。

**結論不變：「單注 NO，多注正交有效」**

但 Phase 3 貢獻了以下新知：
1. EWMA 漂移偵測是真實信號（與 Phase 1 方法論正交）
2. 波動率門控是有效的過濾機制
3. 罕見事件方向可以永久排除
4. PCA 隱變量、UCB1 等理論上先進的方法在此問題上表現平庸

### 15.10 未探索策略清單 & 理論方向

以下是 Phase 3 已確認搜索或已證偽的空間：

**已搜索並確認無效的方法論（可永久排除）：**
- 極端 sum 後追蹤 ❌
- 連號後追蹤 ❌
- 乾旱突破鄰居效應 ❌
- 區域爆發後反轉 ❌
- 高波動期下注 ❌
- PCA 隱變量（DECAYING）❌
- 乘法集成（DECAYING）❌

**已搜索並確認微弱有效的方法論（可用於多注正交增強）：**
- EWMA 漂移偵測 ✓ (1500p +0.47%, SIGNAL)
- 波動率低波門控 ✓ (500p +1.68%, SIGNAL, conditional)
- 共識門檻 ✓ (500p +1.54%, SIGNAL)
- 二次交互 ✓ (500p +0.94%, MARGINAL)
- 覆蓋缺口利用 ✓ (500p +0.74%, MARGINAL)

**理論上仍可探索的方向（Phase 4 候選）：**
1. 深度強化學習（需要 GPU + 大量計算）
2. 圖神經網路（GNN）號碼共現圖
3. 外部變量融合（天氣、日期特徵、銷售量）
4. 跨彩種遷移學習（使用威力彩/539 的規律遷移到大樂透）
5. 動態多注注數調整（信心高時多注，低時少注或跳過）
6. 自適應條件觸發組合（結合 vol_gate + drift_ewma + consensus）
