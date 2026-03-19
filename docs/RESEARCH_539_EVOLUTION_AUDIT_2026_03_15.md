# 539 策略演化 & EV 審計 完整研究報告

## 2026-03-15 | DAILY_539 | Session Report

---

## 目錄

1. [539 EV 數學審計](#1-539-ev-數學審計)
2. [Medium-Scale 策略演化研究](#2-medium-scale-策略演化研究)
   - [Phase 1: 基因組設計](#phase-1-基因組設計)
   - [Phase 2: 演化搜尋](#phase-2-演化搜尋)
   - [Phase 3: 驗證](#phase-3-驗證)
   - [Phase 4: 投資組合優化](#phase-4-投資組合優化)
   - [Phase 5: 結論](#phase-5-結論)
3. [Bug 修正紀錄](#3-bug-修正紀錄)
4. [教訓總結 (L64-L65)](#4-教訓總結)
5. [產出檔案清單](#5-產出檔案清單)

---

## 1. 539 EV 數學審計

### 背景

`structural_optimization.py` 報告 539 基礎 ROI 為 +40.93%，即 EV = 70.47 NTD > 票價 50 NTD。
對彩券而言這不合理（彩券設計必然 negative EV），觸發獨立數學審計。

### 精確概率計算

遊戲規則：從 39 個號碼中選 5 個，開獎 5 個。
總組合數：C(39,5) = 575,757

| 命中數 | 精確概率 | 組合數 | 1/P |
|:------:|:--------:|:------:|:---:|
| 0 | 48.329% | 278,256 | 2.07 |
| 1 | 40.274% | 231,880 | 2.48 |
| 2 | 10.393% | 59,840 | 9.62 |
| 3 | 0.974% | 5,610 | 102.6 |
| 4 | 0.0295% | 170 | 3,387 |
| 5 | 0.000174% | 1 | 575,757 |

### 獎金表比較

| 獎項 | 程式碼（錯誤） | 官方（正確） | 倍率差異 |
|------|:-------------:|:----------:|:--------:|
| M2 (肆獎) | 300 NTD | **50 NTD** | 6.0x |
| M3 (參獎) | 2,000 NTD | **300 NTD** | 6.67x |
| M4 (貳獎) | 20,000 NTD | 20,000 NTD | 1.0x |
| M5 (頭獎) | ~8,000,000 NTD | ~8,000,000 NTD | 1.0x |

**可能混淆來源：** 39 樂合彩（piggyback on 539 draw）的「三合」= 300 NTD，被錯誤用作 539 的 M2 獎金。

### EV 計算結果

| 計算方式 | EV (NTD) | ROI |
|----------|:--------:|:---:|
| 程式碼獎金（**錯誤**） | 70.47 | +40.93% |
| 官方獎金（**正確**） | 27.92 | **-44.16%** |
| 含稅後（20%稅） | 25.14 | -49.72% |

### Monte Carlo 驗證（10M simulations, seed=42）

| 指標 | MC 結果 | 精確計算 | 偏差 |
|------|:-------:|:-------:|:----:|
| EV (程式碼) | 69.45 | 70.47 | -1.4% |
| EV (官方) | 26.80 | 27.92 | -4.0% |

MC 結果與精確計算一致，確認錯誤來自獎金表而非概率計算。

### 損益平衡分析

- 頭獎需達 **25,891,062 NTD**（基礎值 8M 的 3.24 倍）才能 EV = 50 NTD
- 歷史上 539 頭獎很少超過 2,000 萬，損益平衡幾乎不可能達到

### 影響評估

| 項目 | 影響 |
|------|------|
| Hit rate edge 排名 | **無影響** — edge 以命中率計算，與獎金無關 |
| 策略排名 | **無影響** |
| Kelly criterion | **嚴重錯誤** — 從「積極下注 f*=9.3%」→「需先克服 house edge」 |
| structural_optimization_report.md Direction 5/6 | **結論錯誤** |

### 受影響檔案

- `tools/structural_optimization.py` (line 34)
- `tools/meta_strategy_research.py` (lines 1270-1273)
- `structural_optimization_report.md`
- `structural_optimization_results.json`
- `meta_strategy_report.md`
- `meta_strategy_results.json`

---

## 2. Medium-Scale 策略演化研究

### 研究目標

使用演化搜尋探索 4 個已驗證信號（MicroFish, MidFreq, Markov, ACB）的最佳組合方式。
回答：是否存在比現行「獨立信號 + 正交排除」更好的融合方法？

### 研究參數

| 參數 | 值 |
|------|---|
| Population | 200 |
| Generations | 50 |
| 候選策略總數 | ~30,000 (10K per bet level) |
| 驗證期數 | 1,500 (walk-forward) |
| 三窗口 | 150 / 500 / 1500 |
| Permutation test | 99 shuffles, 時序打亂 |
| 使用信號 | MicroFish, MidFreq, Markov, ACB |
| 新增特徵 | **0**（僅重組現有信號） |
| 總計算時間 | 734s (~12 min) |

---

### Phase 1: 基因組設計

#### 基因組欄位定義

| 欄位 | 型別 | 範圍 | 說明 |
|------|------|------|------|
| `signal_weights` | float[4] | [0.01, 1.0] 正規化 | [MicroFish, MidFreq, Markov, ACB] 權重 |
| `fusion_type` | enum | weighted_rank, score_blend, voting, rank_product | 信號融合方式 |
| `nonlinear` | enum | none, sqrt, square, log, sigmoid | 融合前非線性轉換 |
| `gate_signal` | int | -1..3 | 門控信號 (-1=無) |
| `gate_threshold` | float | [0.3, 0.9] | 門控百分位數 |
| `n_bets` | int | 1..3 | 注數 |
| `orthogonal` | bool | True | 注間零重疊 |
| `top_k_method` | enum | direct | Top-5 選取方式 |
| `diversity_bonus` | float | [0.0, 0.3] | Zone 多樣性加分 |

#### 融合方式說明

| 融合類型 | 公式 | 特性 |
|----------|------|------|
| **voting** | `combined[n] = Σ w_i × (10 - rank_in_top10)` | 保留排名資訊，自然處理不同尺度 |
| weighted_rank | `combined[n] = Σ w_i × (39 - rank_i(n))` | 平滑但損失極端值資訊 |
| score_blend | `combined[n] = Σ w_i × normalized_score_i(n)` | 受尺度差異影響 |
| rank_product | `combined[n] = 1 / Π rank_i(n)^w_i` | 幾何平均，對離群值敏感 |

#### 搜索空間

- 連續維度：4 weights + 1 gate threshold + 1 diversity bonus = **6 維**
- 離散組合：4 fusion × 5 nonlinear × 5 gate = **100 組合**
- 每注水平評估 10,000 候選，三級共 ~30,000

#### 演化算子

| 算子 | 比例 | 說明 |
|------|------|------|
| Elitism | 10% | Top 20 直接保留 |
| Crossover | 55% | 權重混合 + 離散基因交換 |
| Mutation | 35% | 單基因擾動 |
| Immigration | 10% | 隨機新個體保持多樣性 |
| Tournament | k=5 | 選擇壓力 |

---

### Phase 2: 演化搜尋

#### 信號預計算優化

為避免 O(N²) 計算瓶頸，採用信號預計算架構：

```python
# 預計算 4 信號的 [T × 39] 矩陣（1.0s）
for t in range(start, end):
    hist_slice = draws[max(0, t - 200):t]  # 限制 200 期歷史
    sig_mf[idx]  = compute_microfish(hist_slice, features, weights)
    sig_mid[idx] = compute_midfreq(hist_slice)
    sig_mk[idx]  = compute_markov(hist_slice)
    sig_acb[idx] = compute_acb(hist_slice)

# 演化只做矩陣運算（純算術，極快）
```

#### 收斂曲線

| 注數 | Gen 0 Best | Gen 10 Best | Gen 49 Best | 收斂代 |
|------|:----------:|:-----------:|:-----------:|:------:|
| 1-bet | +7.27% | +8.60% | +8.94% | Gen 20 |
| 2-bet | +8.84% | +11.50% | +12.17% | Gen 30 |
| 3-bet | +10.22% | +14.22% | +15.22% | Gen 20 |

*註：快速評估 300 期 edge 高於最終 1500 期 edge。*

所有注數在 Gen 20-30 收斂，族群趨近同質化，確認適應度景觀只有單一主要峰值。

#### 收斂基因組

三個注數全部收斂至 **voting fusion**：

| Level | Fusion | NL | Gate | MF | MidFreq | Markov | ACB |
|:-----:|:------:|:--:|:----:|:--:|:-------:|:------:|:---:|
| 1-bet | voting | square | MF@thresh | 0.095 | 0.274 | **0.345** | 0.287 |
| 2-bet | voting | square | none | **0.366** | 0.325 | 0.081 | 0.228 |
| 3-bet | voting | none | none | **0.394** | 0.231 | 0.208 | 0.166 |

觀察：
- 1-bet 最重 Markov；2/3-bet 最重 MicroFish
- Nonlinear 對結果影響 < 0.1pp
- Gating 僅在 1-bet 出現，且門檻幾乎不過濾

---

### Phase 3: 驗證

每個注數 Top-10 候選策略（共 30 個）接受完整驗證：

#### 驗證清單

| 檢查項 | 方法 | 結果 |
|--------|------|------|
| 三窗口穩定性 | 150/500/1500 期 Edge 全正 | 30/30 PASS |
| Permutation test | 99 shuffles, 時序打亂 | 30/30 p=0.010 |
| Walk-forward OOS | 1500 期滾動驗證 | 30/30 PASS |
| 資料洩漏檢查 | 預計算信號只用 t 之前資料 | 無洩漏 |

#### Permutation Test 方法論

```python
# 正確：打亂 actuals 的時序映射
def permutation_test_genome(genome, sigs, actuals, start, end, n_perm=99):
    real_rate = evaluate(genome, sigs, actuals, start, end)
    count = 0
    for _ in range(n_perm):
        perm_idx = rng.permutation(n_draws)
        shuffled_actuals = actuals[start:end][perm_idx]
        perm_rate = evaluate(genome, sigs, shuffled_actuals, start, end)
        if perm_rate >= real_rate:
            count += 1
    return (count + 1) / (n_perm + 1)
```

---

### Phase 4: 投資組合優化

#### 1-Bet 比較

| 指標 | Evolved | Reference (MicroFish) | 判定 |
|------|:-------:|:--------------------:|:----:|
| Edge (1500p) | +5.07% | +4.47% | +0.60pp |
| z-score | 6.18 | 5.45 | — |
| McNemar | a=25 vs b=16 | **p=0.1599** | **不顯著** |

**結論：不部署。** 改善在噪音範圍內。

#### 2-Bet 比較

| 指標 | Evolved | Reference (MF+MidFreq) | 判定 |
|------|:-------:|:---------------------:|:----:|
| Edge (1500p) | +5.10% | **+6.77%** | **-1.67pp** |
| z-score | 4.81 | 6.38 | — |
| McNemar | a=107 vs b=132 | **p=0.1059** | **Reference 勝** |

**結論：不部署。Reference 更優。** 融合排名劣於獨立選號。

#### 3-Bet 比較

| 指標 | Evolved | Reference (MF+MidFreq+Markov) | 判定 |
|------|:-------:|:---------------------------:|:----:|
| Edge (1500p) | +8.96% | +8.29% | +0.67pp |
| z-score | 7.54 | 6.98 | — |
| McNemar | a=198 vs b=188 | **p=0.6108** | **不顯著** |

**結論：不部署。** 差異等同擲硬幣。

#### 邊際效用分析

```
Evolved     1→2: +0.04pp (近乎零 — 第2注幾乎無新增貢獻)
            2→3: +3.85pp (顯著跳躍)

Reference   1→2: +2.30pp (有意義的提升)
            2→3: +1.52pp (適度提升)
```

**核心發現：** Evolved 2-bet 邊際效用近乎零，因為融合排名產生重疊選號。
Reference 的獨立信號方法確保每注覆蓋不同號碼。

---

### Phase 5: 結論

#### 四大研究問題回答

**Q1: 演化是否找到改善？**
邊際改善存在但不可部署。1-bet +0.60pp、3-bet +0.67pp 在噪音範圍內。2-bet Reference 更優。

**Q2: 改善是否統計顯著？**
否。McNemar p 值：0.1599 / 0.1059 / 0.6108，全部 > 0.05。

**Q3: 是否值得部署？**
否。退化風險大於潛在微小收益。

**Q4: 更大規模搜尋是否有意義？**
否。三重證據：
1. **收斂飽和** — Gen 20-30 全族群趨同
2. **融合天花板** — voting 是最佳融合法，但仍不如獨立信號選號
3. **信號飽和** — MicroFish Phase 2 已確認 1-bet 天花板 ~5.1%，evolved 達 99.4%

#### 核心科學發現

| # | 發現 | 說明 |
|---|------|------|
| 1 | **Voting fusion 是最優融合方式** | Score blend / rank fusion / rank product 全部劣於 voting |
| 2 | **獨立信號 > 融合信號（multi-bet）** | 每個信號捕捉正交模式，融合喪失互補覆蓋 |
| 3 | **非線性轉換效益邊際** | square vs none 差異 < 0.1pp |
| 4 | **門控效果可忽略** | 信號永遠 "on"，門檻幾乎不過濾 |
| 5 | **信號天花板已達** | 1-bet evolved 99.4% of theoretical ceiling |

#### 架構定案

```
現行（維持不變）:
  1-bet: MicroFish (純)                      → +4.47%
  2-bet: MicroFish ‖ MidFreq (正交)           → +6.77%
  3-bet: MicroFish ‖ MidFreq ‖ Markov (正交)  → +8.29%
```

#### 重啟條件

1. 出現新驗證信號，與現有信號正交命中率 > 500 unique hits
2. 外部數據源（社群/行為信號）
3. 遊戲規則變更

---

## 3. Bug 修正紀錄

### Bug 1: f-string 反斜線語法錯誤

```python
# ❌ Python 3.9 不允許 f-string 中使用反斜線
f"{[f'{w}p={tw_results[w][\"edge\"]:+.2f}%' for w in WINDOWS]}"

# ✅ 改用 join + format
', '.join(str(w) + 'p=' + format(tw[w]['edge'], '+.2f') + '%' for w in WINDOWS)
```

### Bug 2: KeyError `validated_genomes`

```python
# ❌ 錯誤 key path
vss['validated_genomes'][0]['genome']

# ✅ 正確 key path（validated_strategy_set.json 實際結構）
vss['valid'][0]  # 直接含 'features' 和 'weights'
```

### Bug 3: BASELINE_RATE P(M>=1) vs P(M>=2)

```python
# ❌ P(M>=1) = 51.67%（包含只中1個=未中獎）→ 基線膨脹 4.5×
BASELINE_RATE = 1 - math.comb(34, 5) / math.comb(39, 5)

# ✅ P(M>=2) = 11.40%（只計入中獎組合）
BASELINE_RATE = sum(
    math.comb(5,m) * math.comb(34,5-m)
    for m in range(2, 6)
) / math.comb(39, 5)
```
所有 edge 從 -37%~-52% 修正為 +5%~+9%。

### Bug 4: 計算效能 O(N^2)

```python
# ❌ v1: 每個候選策略從頭計算信號，掛起數分鐘
for candidate in population:
    for t in range(T):
        history = draws[:t]  # O(N) per draw
        signals = compute_all(history)  # 重複計算

# ✅ v2: 預計算信號矩陣，演化只做矩陣運算
precompute_all_signals()  # 1.0s
for candidate in population:
    score = combine_precomputed(candidate.weights)  # O(1) per draw
```

### Bug 5: Permutation test p=1.000

```python
# ❌ 打亂 hit_details → mean 不變 → p 永遠 = 1.0
np.random.shuffle(hit_details)

# ✅ 打亂 actuals 時序映射（破壞預測-結果對應關係）
perm_idx = rng.permutation(n_draws)
shuffled_actuals = actuals[start:end][perm_idx]
```

### Bug 6: NumPy 型別 JSON 序列化失敗

```python
# ❌ TypeError: Object of type bool_ is not JSON serializable

# ✅ 自定義 encoder
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.bool_): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super().default(obj)
```

### Bug 7: 信號陣列原地修改導致汙染

```python
# ❌ apply_nl_vec 修改了預計算的共享陣列
transformed = [apply_nl_vec(s, nl) for s in sigs_at_t]

# ✅ 複製後再轉換
transformed = [apply_nl_vec(s.copy(), nl) for s in sigs_at_t]
```

---

## 4. 教訓總結

### L64: 539 獎金表錯誤

**永遠不要假設獎金數字 — 必須獨立驗證。**

- M2 被灌水 6x（300 vs 50），M3 被灌水 6.67x（2000 vs 300）
- EV 從 27.92 → 70.47 NTD，ROI 從 -44.16% → +40.93%（85pp 偏差）
- Hit rate edge 分析**不受影響**，策略排名**不受影響**

防範規則：
1. 所有獎金數字必須引用官方來源
2. EV > Cost 結果必須觸發自動審查
3. 區分 539 和 39 樂合彩的獎金結構

### L65: 策略演化信號天花板

**獨立信號正交選號 > 融合排名（multi-bet）。**

五項子教訓：

| # | 教訓 | 影響 |
|---|------|------|
| 1 | BASELINE_RATE 必須用 P(M>=2) 非 P(M>=1) | 避免 4.5× 基線膨脹 |
| 2 | Permutation test 打亂時序映射非 hit_details | 避免 p=1.0 假象 |
| 3 | 獨立信號 + 正交排除 > 融合排名 | 2-bet: +6.77% vs +5.10% |
| 4 | 演化 Gen 20-30 收斂 = 信號天花板已達 | 不建議進一步搜尋 |
| 5 | 信號預計算是必要優化 | O(N^2) → O(N)，從掛起到 1.0s |

---

## 5. 產出檔案清單

### EV 審計

| 檔案 | 說明 |
|------|------|
| `tools/ev_audit_539.py` | 獨立 EV 數學審計腳本 |
| `ev_audit_539_results.json` | 審計結果（概率、EV、MC 驗證） |

### 策略演化

| 檔案 | 說明 |
|------|------|
| `tools/strategy_evolution_medium.py` | 演化引擎 v2（預計算信號） |
| `evolved_strategy_population.json` | 全部演化結果與 metadata |
| `validated_evolved_strategies.json` | 驗證後策略與比較 |
| `strategy_genome_design.md` | Phase 1: 基因組設計規格 |
| `portfolio_optimization_report.md` | Phase 4: 投資組合優化報告 |
| `medium_scale_research_conclusion.md` | Phase 5: 結案報告 |

### 知識庫更新

| 檔案 | 更新內容 |
|------|---------|
| `MEMORY.md` | L64 (獎金表錯誤) + L65 (演化天花板) |

---

*Generated: 2026-03-15 | Total session: EV Audit + Medium-Scale Evolution (734s compute)*
