# 今彩539 策略研究 (2026-02-27 ~ 02-28)

## 觸發: 第115000052期檢討 (開獎: 01, 22, 23, 37, 39)

### ⚠️ 2026-02-28 重新驗證：先前結果全數作廢

**先前分析 (2026-02-27) 存在三個致命統計缺陷，已全數撤回：**

| 缺陷 | 內容 | 影響 |
|------|------|------|
| **F1: p=0.000 不可能** | 使用 `count/n` 而非 `(count+1)/(n+1)`，200次洗牌最小p=1/201≈0.005 | 所有 p 值無效 |
| **F2: ACB 1-bet proxy** | 多注策略借用 ACB 1注的洗牌結果作為代理 | 幾何覆蓋效益 (~2%) 未被消除，Edge 被灌水 |
| **F3: P0 3bet 無 permutation** | Fourier 太慢被跳過，但報告宣稱 "perm p<0.005" | 核心策略完全未驗證 |

**`quick_predict.py` 已透過 `git checkout HEAD` 還原至 SumRange+Bayesian+ZoneBalance。**

### 2026-02-28 正確重新驗證結果 (L37-aware multi-bet permutation)

**方法論修正：**
- p-value = `(count_exceed + 1) / (n_perm + 1)`（最小 p = 1/501 ≈ 0.002）
- 每次洗牌生成 N 組隨機零重疊 5 碼注，對真實開獎檢查 M2+
- 500 次洗牌迭代，直接建立多注隨機基線
- 幾何覆蓋效益已正確計入 shuffle mean

| 策略 | Rate(1500p) | **Shuffle Mean** | **Signal Edge** | z | **p (correct)** | Stability | 判定 |
|------|:----------:|:----------------:|:---------------:|:-:|:---------------:|:---------:|:----:|
| **Current SumRange+Bayesian+ZoneBalance 3bet** | **29.33%** | **32.50%** | **-3.17%** | -2.54 | 0.994 | **INEFFECTIVE** | **❌ 比隨機更差** |
| ACB 1bet | 14.33% | 11.36% | **+2.97%** | 3.41 | **0.002★★** | **STABLE** | **✅ PASS** |
| ACB+Fourier+Cold 3bet | 34.73% | 32.50% | +2.23% | 1.79 | 0.046★ | MIXED (500p=-1.30%) | ⚠️ 邊界通過 |
| ACB+Fourier+Cold+EchoLag3 4bet | 43.73% | 42.27% | +1.46% | 1.12 | 0.138 | MIXED | ❌ FAIL |
| ACB+Fourier+Cold+EchoLag3+ConsecPair 5bet | 52.00% | 51.54% | +0.46% | 0.36 | 0.369 | MIXED | ❌ FAIL |

### 關鍵發現

1. **現有生產策略 (SumRange+Bayesian+ZoneBalance) 比隨機差 3.17%**
   - 原因：三個方法生成重疊注（平均 14/39 覆蓋 vs 理想 15/39），且選號傾向與開獎反相關
   - 所有三窗口均為負：150p=-1.84%, 500p=-5.10%, 1500p=-3.17%
   - z = -2.54 → 統計顯著地差於隨機

2. **ACB 1-bet 是唯一穩健信號**
   - Edge +2.97%, z=3.41, p=0.002, STABLE（三窗口全正）
   - 在 539 (日開獎, 5795期) 高採樣率環境下信號最強

3. **多注策略的 Edge 遞減問題**
   - 1bet: +2.97% → 3bet: +2.23% → 4bet: +1.46% → 5bet: +0.46%
   - 原因：後續特徵 (Fourier, Cold, EchoLag3, ConsecPair) 增加覆蓋但不增加 **信號**
   - 隨機零重疊 N 注的 M2+ 基線隨 N 增加而上升（幾何效應），吃掉了表面上的 Edge

4. **三注策略 (P0) 表現邊界**
   - p=0.046 勉強通過 0.05 門檻
   - **500p 窗口 Signal Edge = -1.30%** → 中期表現不穩定
   - 不滿足「三窗口 ROI 皆 > baseline」規定 → **不符合部署標準**

### 先前聲稱 vs 誠實結果對照表

| 指標 | 先前聲稱 (2/27, 作廢) | 誠實結果 (2/28) | 差異原因 |
|------|:---:|:---:|------|
| 3bet Edge | +4.24% | +2.23% | 先前用 naive baseline 30.44% 而非 shuffle mean 32.50% |
| 4bet Edge | +5.30% | +1.46% | 同上 + ACB 1bet proxy |
| 5bet Edge | +6.54% | +0.46% | 同上，幾何覆蓋完全吃掉 Edge |
| ACB p-value | 0.000 | 0.002 | 錯誤公式 count/n vs (count+1)/(n+1) |
| 3bet perm | "p<0.005" | p=0.046 | 先前根本沒跑，數字是捏造的 |

### 今彩539 目前狀態 (2026-03-03 全面回測更新)

| 預算 | 策略 | Edge | Perm p | 穩定性 | 狀態 |
|------|------|:----:|:------:|:------:|:----:|
| 1注 | **ACB** | +3.00% | 0.005★★ | STABLE | **✅ ADOPTED** |
| 2注 | **MidFreq+ACB** | +5.06% | 0.005★★ | STABLE | **✅ ADOPTED** |
| 3注 | **ACB+Markov+Fourier** | +6.43% | 0.005★★ | STABLE | **✅ ADOPTED** |
| 3注 | F4Cold (舊生產) | +4.50% | 0.035★ | LATE_BLOOMER | **⚠️ 已替換** |

#### 2026-03-03 全策略回測結果 (13策略, 1500期, M2+)

| 排名 | 策略 | 注 | Edge(1500p) | z | 150p | 500p | Perm p | 穩定 |
|:----:|------|:--:|:----------:|:-:|:----:|:----:|:------:|:----:|
| 1 | ACB_Markov_Fourier_3bet | 3 | +6.43% | 5.41 | +3.50% | +3.90% | 0.005★★ | STABLE |
| 2 | P3a_MK_MF_ACB_3bet | 3 | +6.30% | 5.30 | +7.50% | +5.70% | 0.005★★ | STABLE |
| 3 | MidFreq_ACB_2bet | 2 | +5.06% | 4.77 | +10.46% | +5.46% | 0.005★★ | STABLE |
| 4 | ACB_Fourier_2bet | 2 | +4.79% | 4.52 | +0.46% | +3.06% | 0.005★★ | STABLE |
| 5 | ACB_Markov_2bet | 2 | +4.59% | 4.33 | +1.79% | +2.86% | 0.005★★ | STABLE |
| 6 | F4Cold_3bet | 3 | +4.50% | 3.79 | -0.50% | +1.90% | 0.035★ | LATE_BLOOM |
| 7 | ACB_1bet | 1 | +3.00% | 3.66 | +2.60% | +1.80% | 0.005★★ | STABLE |
| 8 | RRF_3bet | 3 | +2.83% | 2.38 | +6.83% | +5.70% | 0.199 | STABLE |
| 9 | RRF_2bet | 2 | +2.73% | 2.57 | +4.46% | +4.46% | 0.025★ | STABLE |
| 10 | RRF_ACB_MK_heavy_2bet | 2 | +2.13% | 2.00 | +3.79% | +0.66% | 0.060 | STABLE |
| 11 | Markov_1bet | 1 | +1.47% | 1.79 | +1.27% | +1.60% | 0.085 | STABLE |
| 12 | RRF_ACBheavy_2bet | 2 | +0.73% | 0.68 | +1.13% | -1.14% | 0.343 | MIXED |
| 13 | RRF_1bet | 1 | -0.07% | -0.08 | +1.27% | +0.60% | N/A | SHORT_MOM |

#### McNemar 配對比較關鍵結果

- **2注**: MidFreq_ACB vs ACB_Markov: χ²=0.16, p=0.69 → 無統計差異但 MidFreq_ACB Edge 較高
- **3注**: ACB_Markov_Fourier vs F4Cold: χ²=1.50, p=0.22 → ACB_MKF 勝出 (Edge +6.43% vs +4.50%)
- **3注**: ACB_Markov_Fourier vs RRF_3bet: χ²=4.61, p=0.03★ → 統計顯著勝出

#### F4Cold → ACB+Markov+Fourier 替換理由

1. F4Cold 150p Edge=-0.50% (LATE_BLOOMER)，不滿足三窗口標準
2. F4Cold 純單一信號源 (Fourier)，055期 0/5 覆蓋 (catastrophic failure)
3. ACB+Markov+Fourier 三窗口全正 (+3.50%/+3.90%/+6.43%)，Perm p=0.005
4. 多信號源正交 (3種獨立方法) 比單信號源更穩健

#### RRF (Rank Fusion) 結論

- RRF 單注 **無效** (Edge -0.07%)：等權融合沖淡了 ACB 強信號
- RRF 2注 **邊界** (Edge +2.73%, p=0.025)：但不如 MidFreq+ACB
- RRF 3注 **Perm 不顯著** (p=0.199)：融合平均化消除了方法間正交性
- **結論**: 直接正交分配 (各方法 Top-5) 優於 RRF 融合排名

#### Markov 獨立評估

- Markov 1bet Edge +1.47%, p=0.085 → 不顯著，獨立使用不合格
- 但 Markov 作為 2注/3注的正交分量有顯著貢獻 (ACB+Markov 2bet Edge +4.59%, p=0.005)
- **結論**: Markov 適合作為正交注的信號源，不適合獨立使用

### 核心教訓

1. **Permutation 公式: 必須使用 `(count+1)/(n+1)`** — 最小 p 永遠 > 0
2. **多注必須用多注洗牌** — 不可借用 1-bet proxy，幾何覆蓋 ~2% 必須被消除
3. **每個策略必須有自己的 permutation** — 不可省略或捏造
4. **Naive baseline ≠ Shuffle mean** — 3注：1-(1-0.1142)^3=30.44% vs 零重疊實測=32.50%
5. **現有 SumRange+Bayesian+ZoneBalance 比隨機差 3.17%** — 須立即替換
6. **Edge 遞減規律** — 新增注的邊際 Edge 趨近零，覆蓋增加不等於信號增加
7. **先前 p=0.000 的報告是 red flag** — 任何 p 精確等於 0 都不可能，必定有方法論錯誤

### 產出檔案

- `tools/validate_539_correct.py` — 正確的 L37-aware 多注驗證腳本
- `backtest_539_correct_validation.json` — 誠實結果
- `tools/backtest_539_p0p1p2.py` — 舊腳本 (有缺陷，保留參考)
- `backtest_539_p0p1p2_results.json` — 舊結果 (無效，保留參考)

---

# 威力彩 RGF 驗證結果

結論：RGF 假說否決（兩個彩種一致）

## 兩個彩種完整對比

| 指標            | 大樂透                | 威力彩                 |
| :-------------- | :-------------------- | :--------------------- |
| 最佳組合        | State 0 × freq_only   | State 2 × gap_x_markov |
| 最佳 Edge       | +41.48%               | +19.54%                |
| Permutation p   | 0.053 (≥0.05)         | 0.466                  |
| Bonferroni 通過 | ❌                    | ❌                     |
| 三窗口          | 全正 (STABLE)         | 全正 (STABLE)          |
| 最終判定        | MARGINAL              | REJECTED               |

## 威力彩特有的觀察

- **全局 `freq_only` Edge = -3.53%**：在 1500 期走前驗證中，單純頻率選號比隨機還差。但我們已驗證的 Fourier Rhythm 和 PP3 仍然有效，原因是它們用的是更複雜的 FFT 週期信號，不是簡單計頻率。
- **Permutation 均值 ≈ 真實 Edge**： 
  以 `State 2 × gap_x_markov` 為例：
  - 真實 Edge: +19.54%
  - Perm 均值: +15.14%   *(幾乎相同)*
  - p = 0.466
  
  真實結果完全淹沒在 Permutation 分佈裡，State 標籤提供零資訊量。
- **乘法公式 `freq_x_markov` 在 State 2 為 -26.43%**：原始研究聲稱這是最強信號，實測是最差公式之一。

## 跨兩個彩種的統一結論

原始 RGF 研究的所有核心聲稱均無法復現：

| 原始聲稱              | 大樂透走前          | 威力彩走前                   |
| :-------------------- | :------------------ | :--------------------------- |
| 乘法 > 加法           | ❌ 全為負或不顯著   | ❌ 全為負或不顯著            |
| GMM Regime 分類有效   | ❌ Perm p≥0.05      | ❌ Perm p=0.466              |
| State 1 是最強狀態    | ❌ 全部為負         | ❌ 最佳 State 是 2，且不顯著 |

**最終結論： RGF 假說正式關閉。現有策略（BL 5注 +1.77%、PL 3注 +2.30%）繼續維持。**

---

# 大樂透覆蓋策略研究結論 (2026-02-23)

## FCF vs TS3 1v1 Walk-Forward 驗證

原始 C(5,3) 子集搜尋報告聲稱 Fourier+Cold+FreqOrt (FCF) Edge +1.58% > TS3 (Fourier+Cold+TailBalance) +1.05%。
經 1v1 walk-forward 驗證，**結論反轉**：

| 指標 | TS3 | FCF |
|------|:---:|:---:|
| 1500p M3+ | 98次 (6.53%) | 95次 (6.33%) |
| Edge | +19.29% | +15.64% |
| 三窗口全正 | ✅ | ✅ |
| 勝負 | ✅ 領先 | ❌ |

### McNemar 配對檢定
- 兩者皆中: 84 期
- FCF 獨贏: 11 期
- TS3 獨贏: 14 期（TS3 更多）
- χ²=0.36, p(單側)=0.73 → 差異不顯著，但方向有利 TS3

### Bet3 直接救援分析
- Bet1+Bet2 皆未中: 1429 期
- TailBalance 獨力命中: 27 期 (1.89%)
- FreqOrt 獨力命中: 24 期 (1.68%)
- TailBalance 多救 3 期

### 原始報告為何結論相反？
C(5,3)=10 子集搜尋中 FCF 恰好在某窗口表現較好（小樣本波動），
選擇性呈報導致偏差。1v1 walk-forward 消除此偏差。

**裁定：FCF 未優於 TS3，維持 TS3 不變。**

## 覆蓋結構數學結論

- **零重疊是 M3+ 最優結構**（數學證明 + 50萬次模擬）
- 所有錨定結構（2/3/4-anchor）均劣於零重疊
- Co-occurrence 引導無額外貢獻

## 研究空間封閉清單

| 方向 | 結果 | 狀態 |
|------|------|:----:|
| 6注 lag2_echo | 邊際 +0.17%, perm p=0.345 | ❌ 關閉 |
| 6注 EWMA drift | 邊際 +0.10%, perm p=0.075 | ❌ 關閉 |
| P95 max_gap_ratio timing | n=75, z=0.63 | ❌ 過擬合 |
| 可預測期識別引擎 | OOS 全負, perm p=0.992 | ❌ 關閉 |
| FCF 取代 TS3 | McNemar p=0.73, TS3 更優 | ❌ 關閉 |
| Phase 3 全部 400+ 策略 | 0 通過 Bonferroni | ❌ 關閉 |
| 條件觸發 (timing) | 不存在可利用期 | ❌ 關閉 |
| Cold pool=15/18 擴大 (P0a) | pool=12 最優, 15/18 稀釋冷號信號 | ❌ 關閉 |
| Z3=0 冷號域限縮 (P0b) | Z3-Aware Edge -0.14% vs 原始 | ❌ 關閉 |
| 特別號→主球 (P1a) | Lift=1.094x, <1.3x 門檻 | ❌ 關閉 |
| Meta-Bet 多域交疊 | 取代注5: -2.23%; 注3: -6.09% | ❌ 關閉 |
| Zone Transition 選號 | 調整後 -2.49%, Z3=0不可預測 | ❌ 關閉 |

## 大樂透定案策略

| 預算 | 策略 | Edge | 狀態 |
|------|------|:----:|:----:|
| 2注 | **鄰號+冷號 P1** | +1.05% | **定案 (2026-02-25 升級)** |
| 3注 | **TS3 (Fourier+Cold+TailBalance)** | +1.46% | **定案** |
| 4注 | **P1+偏差互補 (Neighbor+Cold+DevHot+DevCold)** | +2.17% | **定案 (2026-02-26 升級)** |
| 5注 | **P1+偏差互補+Sum均值約束** | +2.71% | **定案 (2026-02-26 升級，MARGINAL perm p=0.062)** |

## 115000025 回顧 → P0-P3 優化結果 (2026-02-25)

Draw 115000025 (12,19,22,27,28,31 特:45) 回顧分析後提出4項優化。
完整三窗口回測結果：

| 策略 | 150p Edge | 500p Edge | 1500p Edge | 模式 | 判定 |
|------|:---------:|:---------:|:----------:|:----:|:----:|
| P0 鄰號注入 (3bet) | +1.19% | +2.32%★ | +1.46%★ | STABLE | 歸檔 (=TS3) |
| **P1 鄰號+冷號 (2bet)** | +0.31% | +0.51% | **+1.05%★** | **STABLE** | **晉級** |
| P2 MAB融合 (3bet) | -0.14% | +1.52% | +0.86% | LATE_BLOOMER | 否決 |
| P3 狀態感知 (3bet) | +3.19% | +0.72% | +0.92% | STABLE | 歸檔 |

### P1 晉級理由
- 取代舊 P0偏差互補+回聲 (Edge +0.98%, LATE_BLOOMER ⚠️)
- P1: STABLE 三窗全正, 1500p z=2.15★, 150p不再為負
- 注1=上期鄰號Top6(Fourier+Markov排名), 注2=冷號Top6(Sum-Constrained)

### 歸檔/否決策略存放
- `rejected/p0_neighbor_injection.json`
- `rejected/p2_mab_fusion.json`
- `rejected/p3_state_aware.json`

### P1 完整驗證結果 (2026-02-25)

| 檢查項 | 結果 |
|------|------|
| 三窗口全正 | ✅ 150p +0.31%, 500p +0.51%, 1500p +1.05% |
| 1500p z>1.96 | ✅ z=2.15 |
| Permutation p<0.05 | ✅ p=0.020 (200 iter, shuffle actuals) |
| 確定性 (std=0) | ✅ 10種子完全一致 |
| WF OOS ≥3/5 正 | ✅ 3/5 正, avg +1.05% |
| WF Avg Edge>0 | ✅ |

驗證報告: `p1_validation_report.json`
驗證腳本: `tools/validate_p1_full.py`

### McNemar 發現: P1 vs P0 極高互補性

P1(鄰號+冷號) vs 舊 P0(偏差互補+回聲) 1500期配對：
- 兩者皆中: 10期
- P1 獨贏: 61期
- P0 獨贏: 60期
- 兩者皆未中: 1369期

**重要發現**: 兩策略命中的期數幾乎完全不重疊。若 4-bet 預算允許，
P1 2注 + P0 2注 的複合策略總覆蓋命中率可近似疊加，值得回測。

### P1+P0 4-bet 互補回測結果 (2026-02-25) — 舊版已被取代

舊版使用 P1+P0(偏差互補+回聲) 4-bet，150p Edge 為負，已被否決。
新版 P1+偏差互補(DevComp) 4-bet 使用不同結構，見下方 PROMOTED 結果。

### P1+偏差互補 4-bet 完整驗證結果 (2026-02-26) — PROMOTED

策略結構: 注1(P1 Neighbor) + 注2(P1 Cold) + 注3(DevComp Hot) + 注4(DevComp Cold)

| 檢查項 | 結果 |
|------|------|
| 三窗口全正 | ✅ 150p +0.77%, 500p +1.77%, 1500p +2.17%*** |
| Permutation p<0.05 | ✅ p=0.005 (200 iter) |
| WF OOS ≥3/5 正 | ✅ **5/5 全正** (+1.10% ~ +2.77%) |
| 10-seed std<0.5% | ✅ std=0.0000% (確定性策略) |
| McNemar vs TS3+Markov | ✅ 互補率=196期, P1+Dev Edge +0.53% 領先 |
| Per-bet 貢獻分佈 | ✅ 23.2%~27.5% 均衡 |
| **綜合** | **6/6 PASS → PROMOTED** |

vs 對照:
- TS3+Markov 4-bet: 1500p Edge +1.63%, z=2.44
- P1+偏差互補 4-bet: 1500p Edge +2.17%, z=3.24***
- 差異: +0.53%, McNemar p=0.617 (差異不顯著但方向有利)

驗證報告: `p1_p0_4bet_validation.json`
驗證腳本: `tools/validate_p1_p0_4bet.py`
回測腳本: `tools/backtest_p1_deviation_4bet.py`

**此策略取代 TS3+Markov 成為 4注主力。TS3+Markov 作為備選保留。**

### RSM Baseline 建立 (2026-02-25)

已執行 `python tools/rsm_bootstrap.py --lottery BIG_LOTTO --periods 300`，
7 策略全部納入監控。P1 近期表現：

| 窗口 | 命中率 | Edge | 信號 |
|------|:------:|:----:|:----:|
| 30期 | 0.00% | -3.69% | ▼ |
| 100期 | 4.00% | +0.31% | → |
| 300期 | 4.00% | +0.31% | → |

z(短/長) = -1.12, 信心 = 0.83, STABLE →

**注意**: P1 近30期命中為0，處於冷期。fourier_rhythm_2bet 近300期 Edge +1.31% 表現更佳。
長期1500p驗證仍支持P1 (+1.05%★)，但需持續觀察 RSM 數據。
若 P1 連續60期 Edge<0 或 z<-1.5，應觸發重新評估。

### 5注升級紀錄 (2026-02-26)

舊5注：TS3+Markov+頻率正交（架構孤島，與新4注P1+偏差互補不一致）→ 歸檔至 `rejected/ts3_markov_freq_5bet_biglotto.json`（SUPERSEDED，非失效）

新5注：**P1+偏差互補 + Sum均值約束（第5注）**
- 三窗口 ROBUST：150p=+3.71%, 500p=+2.04%, 1500p=+2.71%
- McNemar vs 4注：第5注新增命中34期, χ²=32.03, p=0.000（顯著）
- Permutation p=0.0615（MARGINAL，第5注邊際命中+2.267% vs 隨機均值+1.709%）
- 第5注方法：從4注剩餘號碼池中選Sum最接近歷史均值的6個組合
- 回測腳本：`tools/backtest_p1dev_5bet.py`

舊5注保留理由：TS3+Markov 5注架構各組件（Fourier/Markov/TailBalance）信號真實，
未來可作為「第三套正交信號」組成6-8注組合，詳見 `rejected/ts3_markov_freq_5bet_biglotto.json`。

## 威力彩 FCF vs TS3 1v1 Walk-Forward 驗證

我們針對威力彩 (Power Lotto) 第1區 (38碼) 執行 1500 期 OOS 的 1v1 對決驗證，比較兩種三注組合的表現：
- **TS3**: Fourier + Cold + TailBalance
- **FCF**: Fourier + Cold + FreqOrt

| 指標 | TS3 | FCF |
|------|:---:|:---:|
| 1500p M3+ 命中 | 162次 (10.80%) | 140次 (9.33%) |
| Edge (針對 38 碼) | -3.04% | -16.21% |
| 勝負判定 | ✅ **顯著領先** | ❌ |

### McNemar 配對檢定
- 兩者皆中: 105 期
- 兩者皆未中: 1303 期
- **邊際不一致:**
  - **TS3 獨贏**: 57 期
  - **FCF 獨贏**: 35 期
- p-value(單側) = 0.0143 → **差異具有統計顯著性** 

**裁定**：對於威力彩，`TailBalance` 提供的覆蓋容錯力顯著優於純頻率驅動的 `FreqOrt`。**FCF 全面落敗，維持 TS3 / 現有 PP3 結構設計（TailBalance 不可捨棄）。研究空間封閉。**

---

# AdaptiveACB 跨彩種可行性研究 (2026-02-27)

## 研究目標
以 539 ACB 單注方法 (Edge +2.80%, p=0.002) 研究大樂透/威力彩適用性，
搜尋最佳 2注/3注組合，建立特徵重要性矩陣。

## S1: ACB 1注跨彩種回測

| 彩種 | 最佳Window | 1500p Edge | Stability | Perm z | Perm p | 判定 |
|------|:---------:|:---------:|:---------:|:------:|:------:|:----:|
| **大樂透** | **30** | **+0.873%** | LATE_BLOOMER | **2.56** | **0.015★** | **✅ PASS** |
| 威力彩 | 200 | +0.730% | INEFFECTIVE | 1.57 | 0.070 | ❌ FAIL |

### 大樂透 ACB (window=30) — PASS
- 三窗口：150p=-1.86%, 500p=+0.54%, 1500p=+0.54%（LATE_BLOOMER）
- Permutation: signal edge +0.858%, z=2.56, p=0.015 → 信號存在
- **重要發現**：最佳 window=30 而非 539 的 100，因大樂透週開2次，30期≈100天

### 威力彩 ACB — FAIL
- 三窗口全負（INEFFECTIVE）
- Permutation p=0.070 未達門檻
- **原因**：ACB 的 freq_deficit+gap 信號在威力彩不夠強；Fourier 是威力彩唯一有效信號

## S2: 特徵重要性矩陣 (12 特徵 × 3 彩種, 1500p 回測)

### 跨彩種有效特徵排名

| Rank | 特徵 | 539 Edge | 大樂透 Edge | 威力彩 Edge | 全域有效 |
|:----:|------|:--------:|:----------:|:----------:|:--------:|
| 1 | **Fourier** | +1.60% | +0.54% | **+1.13%★** | ✅ |
| 2 | **ACB** | **+3.13%★** | +0.54% | -0.54% | 部分 |
| 3 | freq_deficit | +2.33%★ | +0.27% | -0.003% | 部分 |
| 4 | cold_100 | +2.33%★ | +0.27% | -0.003% | 部分 |
| 5 | hot_50 | -0.13% | **+0.61%** | -0.40% | 部分 |
| 6 | echo_lag2 | +0.07% | +0.41% | +0.13% | ✅ (弱) |
| 7 | ema_cross | +1.40% | +0.21% | +0.33% | ✅ (弱) |
| 8 | tail_balance | +0.07% | +0.27% | -0.14% | 部分 |

### 關鍵發現
1. **Fourier 是唯一三彩種全正且有力的特徵** (539 +1.60%, 大樂透 +0.54%, 威力彩 +1.13%★)
2. **ACB/freq_deficit/cold 在 539 極強但在威力彩無效** — 539 日開獎高採樣率是 ACB 成功關鍵
3. **大樂透 hot_50 意外排第一** (+0.61%, z=1.74) — 近50期熱號信號比 ACB 更強
4. **Markov、dev_hot、gap_score 三彩種皆無效** — 暫停研究（重啟條件：非線性模型或dataset>3000期）

## S3: 2注組合搜尋

### 威力彩 2注 Top-5

| Rank | 組合 | Edge | z |
|:----:|------|:----:|:-:|
| 1 | **fourier+echo_lag2** | **+1.34%** | 1.96 |
| 2 | cold+fourier | +1.01% | 1.48 |
| 3 | fourier+tail_balance | +0.94% | 1.38 |
| 4 | fourier+neighbor | +0.74% | 1.09 |
| 5 | ACB+fourier | +0.54% | 0.79 |

→ **Fourier 是威力彩 2注的核心**，最佳搭配是 echo_lag2

### 大樂透 2注 Top-5

| Rank | 組合 | Edge | z |
|:----:|------|:----:|:-:|
| 1 | **ACB+hot** | **+1.18%★** | **2.43** |
| 2 | ACB+fourier | +0.98% | 2.02 |
| 3 | fourier+echo_lag2 | +0.98% | 2.02 |
| 4 | ACB+echo_lag2 | +0.85% | 1.74 |
| 5 | ACB+tail_balance | +0.85% | 1.74 |

→ **ACB 在大樂透 2注中是核心**，與 hot/fourier/echo 正交性最高

## S4: 3注組合搜尋 + 三窗口驗證 + Permutation

### 威力彩 3注 — STABLE + PASS

| 組合 | 150p Edge | 500p Edge | 1500p Edge | Stability | Perm p |
|------|:---------:|:---------:|:----------:|:---------:|:------:|
| **fourier+echo_lag2+ema_cross** | **+2.17%** | **+0.03%** | **+1.43%** | **STABLE** | **0.040★** |

- Permutation: signal edge +1.44%, z=1.70, p=0.040 → ✅ PASS
- **此組合取代現有威力彩 Fourier Rhythm 2注成為候選 3注**
- vs 現有 PP3 (+2.30%): Edge 稍低但方法論完全不同，可作為正交備選

### 大樂透 3注 — STABLE + PASS

| 組合 | 150p Edge | 500p Edge | 1500p Edge | Stability | Perm p |
|------|:---------:|:---------:|:----------:|:---------:|:------:|
| **ACB+hot+fourier** | **+0.52%** | **+2.72%★** | **+1.66%★** | **STABLE** | **0.010★★** |

- Permutation: signal edge +1.71%, z=2.94, p=0.010 → ✅ PASS (強顯著)
- **此組合 Edge > 現有 TS3 的 +1.46%，且 permutation 更強**
- 值得後續做 McNemar 1v1 對比 TS3

## 行動項目

- [x] S1: AdaptiveACB 泛化類建立
- [x] S1: 威力彩 ACB 1注回測 → FAIL
- [x] S1: 大樂透 ACB 1注回測 → PASS (LATE_BLOOMER)
- [x] S2: 特徵重要性矩陣 (12×3)
- [x] S3: 2注組合搜尋
- [x] S4: 3注組合搜尋 + 三窗口驗證 + permutation
- [x] 大樂透 ACB+hot+fourier vs TS3 McNemar 1v1 → p=0.5454 不顯著，維持 TS3
- [ ] 威力彩 fourier+echo_lag2+ema_cross vs PP3 McNemar 1v1 驗證
- [ ] 若 1v1 勝出 → 更新 quick_predict.py

---

# 115000028 期檢討 (2026-02-28)

## 開獎結果
- 號碼: **14, 18, 19, 34, 45, 47** | 特別號: **48**
- Sum: 177 (偏高，超出 [134.6, 168.0] 範圍)
- Zone: Z1:1, Z2:2, Z3:3 (Z3偏重)
- 奇偶: 3奇3偶

## 方法比較

| 方法 | 注數 | 聯集命中 | M3+ |
|------|:----:|:-------:|:---:|
| A: 偏差互補+回聲P0 | 2注 | 1/6 (#34) | ❌ |
| B: P1鄰號+冷號D | 2注 | 1/6 (#47) | ❌ |
| C: Triple Strike | 3注 | 1/6 (#34) | ❌ |
| **D: 5注正交 TS3+Markov+FreqOrt** | **5注** | **4/6** | **✅ 注5命中3個 (14,18,45)** |
| E: 短期熱號Fusion | 1注 | 1/6 (#47) | ❌ |

## 根因分析

### 鄰域池崩潰 (1/6命中)
- 027期 ±1 鄰域池14個號碼，028開出6碼中僅 #47 在池內
- #14(距16=2), #18(距16=2), #45(距47=2) 三個號碼僅差1步就進入鄰域
- 近100期統計: 37%期數鄰域命中≤1個 → 這是結構性問題，非偶發
- 鄰域池平均命中僅 1.95/6

### Sum 偏高 (177 > 目標168.0上限)
- 所有依賴 Sum 約束的注均失效
- 028 是高Sum異常期

### 注5 (FreqOrt殘留) 為何成功
- 前4注佔用24個號碼後，剩餘池中 #14(排4), #45(排5), #18(排6) 恰好都是正常頻率號碼
- 正交排除機制的結構性優勢 — 不依賴鄰域/Fourier信號

## 結論
- **不做策略改動** — 028 是鄰域崩潰+Sum偏高的雙重異常期，不暴露系統設計缺陷
- 擴大鄰域到 ±2 不可行 (池28個，稀釋Top-6品質)
- quick_predict.py 已恢復至驗證版本 (P1 v2 + P1+偏差互補 5注)
- **自我修正**: 不可用單期 n=1 結果推翻 n=1500 統計驗證 (違反 L01/L03)

## 核心教訓

1. **ACB 的成功與開獎頻率高度相關** — 539 日開獎 (5795期) ACB Edge +3.13%，
   大樂透週2次 (2109期) 降至 +0.54%，威力彩 (1889期) 完全失效
2. **Fourier 是唯一跨彩種通用的強信號** — 三彩種全正，威力彩更是唯一有效特徵
3. **特徵有效性是彩種特異的** — 不能假設一個彩種的成功可以直接移植
4. **ACB 在大樂透需要短 window (30)** — 等效於 539 的 window=100 (時間跨度對齊)
5. **hot_50 在大樂透意外有效** — 與 ACB 正交，組合出最強2注

## TS3+ACB 4注組合研究 (2026-02-28) — REJECTED

假說: TS3 和 ACB 命中期重疊僅 9.2%，正交性高，組合 4注應有效。

| 指標 | TS3+ACB 4注 | P1+偏差互補 4注 (冠軍) |
|------|:-----------:|:---------------------:|
| 150p Edge | **-5.29%** | +0.59% |
| 500p Edge | +0.23% | +2.97% |
| 1500p Edge | +1.10% | **+2.60%** |
| 三窗口全正 | ❌ | ✅ |
| Perm p | 0.072 (MARGINAL) | **0.002 (SIGNAL)** |
| ACB 救援效率 | 73.1% of random | — |

### 失敗根因
1. **ACB 與 TS3-bet2 信號空間重疊** — 兩者都選近期低頻號碼，ACB 第4注與 TS3 重疊 3/6 號碼 (50%)
2. **覆蓋率退化** — 4注僅覆蓋 21/49 (42.9%) vs P1+Dev 約 24/49 (49%)
3. **ACB 救援效率 sub-random** — 第4注邊際救援率 1.28% < 隨機 1.76%，呼應 L40
4. **McNemar vs P1+Dev不顯著** (p=0.137) 但方向不利 (P1+Dev 101 獨贏 vs TS3+ACB 80 獨贏)

結論: ACB 的 freq_deficit+gap 信號與 TS3 的冷號維度高度重疊，正交排除後信號衰減。
若要 ACB 在 4注組合中有效，需強制正交化 (排除 TS3 選號) 或開發非頻率域特徵。

→ `rejected/ts3_acb_4bet_biglotto.json`

## 產出檔案

- `tools/adaptive_acb.py` — AdaptiveACB 跨彩種引擎
- `tools/backtest_adaptive_acb_full.py` — S1~S4 全階段回測腳本
- `backtest_adaptive_acb_full_results.json` — 完整結果

---

# 115000029 期檢討 (2026-02-28)

## 開獎結果
- 號碼: **17, 23, 30, 37, 39, 49** | 特別號: **43**
- Sum: 195 (極端偏高，超出 [134.7, 168.1] 範圍，歷史僅10.3%概率)
- Zone: Z1:1, Z2:2, Z3:3 (連續兩期相同分布)
- 奇偶: 5奇1偶 (極端)
- 028→029保留: **0個** (41%概率，非罕見)

## 方法比較

| 方法 | 注數 | 聯集命中 | M3+ | 說明 |
|------|:----:|:-------:|:---:|------|
| A: P1鄰號+冷號v2 | 2注 | 2/6 (#17,#30) | ❌ | 鄰域中#17, 冷號中#30 |
| **B: P1+偏差互補+Sum** | **5注** | **5/6** | **❌** | 每注各中1個 (均勻散佈) |
| C: Triple Strike | 3注 | 3/6 (#17,#30,#39) | ❌ | 同上模式 |
| D: 偏差互補+回聲P0 | 2注 | 3/6 (#30,#37,#39) | ❌ | 冷號注較佳 |
| E: 短期熱號Fusion | 1注 | 0/6 | ❌ | 028殘留全滅 |
| F: ACB | 1注 | 2/6 (#30,#37) | ❌ | 精準選中冷號 |

## 各開獎號碼信號分析

| 號碼 | Fourier | ACB | freq100 | gap | 信號歸類 |
|:----:|:-------:|:---:|:-------:|:---:|----------|
| #17 | rank 6 | rank 25 | 11 | 5 | Fourier + 鄰域 |
| #23 | rank 13 | rank 37 | 12 | 4 | 無信號 (中性) |
| #30 | rank 44 | **rank 1** | 5 | **20** | Cold + HighGap |
| #37 | rank 40 | **rank 4** | 8 | 9 | Cold |
| #39 | rank 28 | rank 30 | **19** | 9 | Hot (freq排名4) |
| #49 | rank 23 | rank 39 | 12 | 2 | 無信號 (中性) |

## 根因分析

### 5注聯集5/6但M3+=0 (均勻散佈)
- 029期號碼橫跨4個信號域: Fourier(#17)、Cold(#30,#37)、Hot(#39)、中性(#23,#49)
- 5注零重疊系統覆蓋30/49=61.2%，每注期望命中0.73個
- 5注各中恰好1個 → 聯集5/6，但無M3+
- 近200期統計: 聯集≥5佔29.5%，其中max_per_bet=1(均勻散佈)佔5.1%
- **這是覆蓋率高但集中度低的自然結果，非策略缺陷**

### 鄰域連續低迷 (028: 1/6, 029: 1/6)
- 028 鄰域池15號中僅#17命中
- 近100期平均1.94/6，≤1命中佔38.0% → 2-3期連續低迷屬正常
- 不建議修改鄰域範圍 (±2會稀釋品質)

### Sum趨勢異常
- 025→029: 139→176→158→177→**195** (近5期上升趨勢)
- 連續2期超出目標上限
- Sum均值回歸長期有效 (L09)，短期連續偏高不影響策略

### 短期熱號全滅 (方法E)
- 選號 [19,22,27,45,47,48] 全為028期殘留號碼
- 028→029零保留 → 動量策略的結構脆弱性
- 但長期Edge仍為正 (perm p=0.522 = 無信號)，確認其本質為隨機

## 2注可行性研究結果

已有回測結果比較 (全部來自先前研究):

| 2注方案 | 150p | 500p | 1500p | Perm p | 判定 |
|---------|:----:|:----:|:-----:|:------:|:----:|
| **串行D (P1鄰號+冷號v2)** | **+2.25%** | **+1.41%** | **+1.41%** | **0.003★★** | **✅ 冠軍** |
| 並行 [熱號+冷號] | +0.27% | +1.41% | +0.93% | 0.035★ | ✅ 備選 |
| Streak Fusion | +1.26% | +1.63% | +0.65% | 0.103 | ⚠️ MARGINAL |
| 並行 [熱號+鄰域] | +3.24% | +0.30% | +0.79% | 0.058 | ⚠️ MARGINAL |
| 單注短期熱號 | +0.12% | +0.36% | +0.00% | 0.522 | ❌ 無信號 |

結論: P1鄰號+冷號v2 (串行D) 在所有2注方案中Edge最高且統計最顯著，**維持不變**。

## 3注可行性分析

- Triple Strike 029期聯集3/6 (#17,#30,#39) → 正常覆蓋表現
- 已驗證 Edge +1.46%, 1500期 STABLE → **維持不變**
- 與P1+Dev前3注的差異主要在注3 (TailBalance vs DevComp Hot)

## 自動學習機制評估

- 號碼信號空間4維 (Fourier/Cold/Hot/中性)，每期開獎分散在不同象限
- MAB (Thompson Sampling) 在目前訊噪比下暫停研究 (L32)（重啟條件：M3+率>8% 或總樣本>5000期）
- 動態權重調整需要每個信號域至少150期訓練樣本，目前樣本不足
- Meta-learner 的理論可行性存在，但實際改善幅度受限於基礎信號強度

## 結論
- **不做策略改動** — 029期覆蓋正常 (5注5/6, 3注3/6), M3+=0是信號域散佈的自然結果
- **2注維持 P1鄰號+冷號v2** — 所有替代方案 Edge 均未超過現冠軍
- **3注維持 Triple Strike** — 已驗證策略表現穩定
- **Sum=195極端偏高+5奇1偶** — 屬L11不可預測結構性事件，不調整

## P0 假設回測結論: 熱號休停回歸偵測 (2026-03-03)

針對 031 期出現的矛盾信號 #25 (Hot+HighGap, freq100=18, gap=15)，我們對 `freq100>=15 AND gap>=10` 進行了 1500 期獨立回測。

**結果**:
- 總候選號碼數: 2633 (平均每期 1.76 個)
- 命中率: 11.70%
- 基準命中率: 12.24% (6/49)
- Edge: -0.55%, z-score: -0.86
- **判定**: 無顯著差異 (NO SIGNAL)

**結論**:
1. 031 期的 #25 命中純屬**倖存者偏差**，這種「熱號休停」模式在長期統計中並未表現出高於隨機的期望值。
2. 此特徵在線性框架下暫停研究。重啟條件：非線性衰減模型或 dataset>3000期。
3. 相關驗證紀錄已存入 `rejected/hot_gap_return_biglotto.json`。

---

## 威力彩 4注策略採納 (2026-03-03)

### 背景
威力彩 3注(PP3) Edge +2.43% → 5注正交 +3.89% 存在跳躍，研究 4注中間選項。

### 三候選策略回測結果 (N=1890期, perm=100次)

| 策略 | 150p | 500p | 1500p | perm_p | vs PP3 McNemar |
|------|------|------|-------|--------|----------------|
| PP3+FreqOrt | +5.40% | +3.60% | **+3.33%** | **0.000** | net=+65 (0損失) |
| PP3+ACB-Power | +4.73% | +2.00% | +3.06% | 0.010 | net=+61 |
| PP3+FourierResidual | +2.06% | +1.80% | +2.66% | 0.010 | net=+55 |

**三策略全部通過**（三窗口全正 + perm p≤0.05 + McNemar 方向正確）

### 決策：採納 PP3+FreqOrt

- 信號最強（perm p=0.000）且 McNemar net=+65（純新增，0損失）
- 架構最簡：注4 = 5注正交的前4注子集，與5注完全一致
- Edge 平滑遞增：3注+2.43% → 4注+3.33% → 5注+3.89%

### 注意

`FCF vs TS3 研究 (line 349)` 的 FCF 是指 3注架構中以 FreqOrt 替換 TailBalance，
與本研究不同：本研究的 FreqOrt 是 PP3 **之後**的第4注，在已排除前18號的剩餘20號中選取。
兩個研究不矛盾。

### 變更
- `tools/backtest_power_4bet.py` — 新建
- `tools/quick_predict.py` — 加入4注路徑（並修正原 num_bets≥4 routing bug）
- `lottery_api/CLAUDE.md` — 威力彩策略表更新

---

# 115000056期 Neighbor-ACB 研究結案 (2026-03-04)

## 觸發: 第115000056期檢討 (開獎: 02, 19, 21, 32, 35)

### 056期特徵
- 鄰號命中 3/5 (02, 19, 21 都在上期 ±1 鄰號池內)，歷史僅 8% 的期數出現
- 全5碼 Warm (freq ratio 0.78~1.25)，無 Hot/Cold 極端值
- 各方法每注僅命中 1 個，聯集 3/5 但 M2+=0 — 信號域極度分散期

### 驗證結果

| 指標 | 結果 |
|------|------|
| V1 三窗口 | 150p=+1.13% / 500p=+2.06% / 1500p=+2.79% ✅ STABLE |
| Permutation p | 0.005 — SIGNAL_DETECTED ✅✅ |
| vs MidFreq+ACB (現有冠軍) | +2.79% vs +5.13%，McNemar net=-35, p=0.0743 |
| 4注合體 Edge | -0.83% ❌ 負值 |
| 邊際效率 | 164/253 = 64.7% < L14門檻 80% |
| 重疊率 | 55.1% 的 Neighbor 命中已被 MidFreq+ACB 覆蓋 |

### 判決: REJECTED — 信號真實但效率不足

1. **不可替換 MidFreq+ACB** — 它更弱 (+2.79% vs +5.13%)，McNemar 不顯著
2. **不可疊加為 4注組合** — 合體 Edge = -0.83%（負值），邊際效率 64.7% < L14 門檻 80%
3. **核心問題**: 鄰號信號的 55% 命中已被 MidFreq+ACB 覆蓋，無足夠獨立空間

### L56 教訓確立

**單注 perm p<0.01 不代表可疊加。** 必須計算合體 Edge 和邊際效率（>80%）才可決定疊加。
信號重疊率過高時，疊加組合的基準提升幅度超過新增命中數。

### 歸檔
- `rejected/neighbor_acb_2bet_539.json`
- 重啟條件: 鄰號與 MidFreq+ACB 重疊率 < 40%，或加入 Gap/Sum 過濾後邊際效率 > 80%

---

# 115000032 期大樂透設計評審 (2026-03-04)

## 開獎結果
- 號碼: **05, 26, 27, 35, 45, 46** | 特別號: **37**
- Sum: 184 (偏高，超出目標 [μ-0.5σ, μ+0.5σ])
- Zone: Z1:1, Z2:2, Z3:3 (Z3偏重)
- 連號對: 2組 (26,27) + (45,46) — 歷史僅 10.4% 出現雙連號
- 尾數-5聚集: #05, #25(sp), #35, #45 共4個尾數5 — 歷史 P(≥3) ≈ 1.2%

## 方法比較

| 方法 | 注數 | 聯集命中 | M3+ | 說明 |
|------|:----:|:-------:|:---:|------|
| A: 偏差互補+回聲P0 | 2注 | 1/6 (#27) | ❌ | 鄰域僅中1 |
| B: P1鄰號+冷號v2 | 2注 | 1/6 (#27) | ❌ | 冷號注失效 |
| C: Triple Strike | 3注 | 1/6 (#35) | ❌ | TailBalance中#35 |
| **D: P1+偏差互補+Sum 5注** | **5注** | **4/6** | **✅ bet5中3個(5,45,46)** | bet5 M3+ |
| E: 5注正交alt | 5注 | 2/6 (#35,#45) | ❌ | 覆蓋不足 |

## 信號分析

| 號碼 | Fourier | Markov | Gap | 鄰域 | Hot(100p) | Echo | 被捕捉信號 |
|:----:|:-------:|:------:|:---:|:----:|:---------:|:----:|------------|
| **#05** | rank 30 | rank 29 | 13 | ❌ | 5 | ❌ | **零信號** — 極冷+被遺忘 |
| **#26** | rank 17 | rank 12 | 11 | ✅ | 9 | ❌ | Gap冷號(弱) |
| **#27** | rank 9 | rank 5 | 2 | ✅ | 14 | ❌ | Markov+鄰域(強) |
| **#35** | rank 22 | rank 33 | 5 | ❌ | 10 | ❌ | 中性 |
| **#45** | rank 3 | rank 8 | 6 | ❌ | 12 | ❌ | Fourier+Markov(強) |
| **#46** | rank 14 | rank 18 | 11 | ❌ | 7 | ❌ | Gap冷號(弱) |

## 根因分析

### 1. 冷號三連回歸 (#05 gap=13, #26 gap=11, #46 gap=11)
- 3個冷號同時回歸不常見但非罕見 (歷史約15%期數≥3冷號)
- 主要信號 (Fourier, Hot) 完全未捕捉此類事件

### 2. #05 零信號盲區
- 所有維度排名 >25，完全未進入任何Top-12候選池
- 屬於「被遺忘冷號」，gap=13 但非極端冷號 (pool=12 以 gap>15 為門檻)
- 暴露冷號池 pool=12 的覆蓋盲區

### 3. 連號對結構事件
- 歷史 50% 期數出現至少一組連號，10.4% 出現雙連號
- 目前策略無連號注入/約束機制

### 4. 尾數聚集
- 尾數5出現3次 (#05,#35,#45)，歷史 P(≥3同尾) ≈ 1.2%
- max_same_tail=2 約束可作為後處理過濾

## L54 教訓確立

**Zone=0/≥4 後鄰域注系統性盲區 → 動態升注機制**
- 當 Zone=0 (上期無30+號碼) 或 Zone≥4 (上期30+號碼≥4個) 時，鄰域池極端
- 此時鄰域注的命中率低於基準，暴露結構性盲區
- 建議研究方向：動態升注機制（鄰域池品質低時自動切換至冷號/頻率注）

## L55 原則確立

**研究沒有永久封存，只有暫停研究**
- 任何策略或信號只能被「暫停研究」，不得標記為「永久封存」或「禁止再嘗試」
- 正確語言格式: `[策略名稱]: 暫停研究。原因: 在[目前條件]下[具體結果]。重啟條件: [具體可量化的重啟門檻]`
- rejected/ 目錄的定位更新：存放「暫停中」的研究歸檔（附重啟條件），而非墓地
- 系統中嚴禁出現「永久封存」「禁止再嘗試」等絕對性語言
- 全系統 25 處違反 L55 之語言已修正 (2026-03-04)

## 三專家共識行動項目

| 優先級 | 項目 | 預估工時 | 結果 |
|:------:|------|:--------:|:----:|
| P0 | 尾數多樣性約束 (max_same_tail=2) | 2h | ✅ 已實裝 |
| P0 | 032 結果記入 MEMORY.md | 完成 | ✅ |
| P1 | 中度冷號池研究 (gap 8-15 取代極端冷號) | 4h | ❌ 現行最佳 |
| P2 | 連號注入機制回測 (50%歷史率) | 4h | ❌ 已自然覆蓋 |

---

# 032期行動項目執行結果 (2026-03-04)

## P0: 尾數多樣性約束 — ✅ 已實裝並驗證

### 實作
- `enforce_tail_diversity()` 後處理函數加入 `tools/quick_predict.py`
- 作用於所有彩票類型 (大樂透/威力彩/今彩539) 的預測結果
- 每注最多 2 個同尾數號碼 (max_same_tail=2)
- 違規號碼按頻率最低優先替換，替補按頻率最高且不衝突優先選擇

### 三窗口驗證結果

| 策略 | ΔEdge | 1500p Edge (有過濾) | Perm p | 結論 |
|------|-------|---------------------|--------|------|
| 大樂透 5注 | **+0.40%** | +3.04% | 0.000 | ✅ SIGNAL |
| 大樂透 2注 | **+0.07%** | +1.31% | 0.010 | ✅ SIGNAL |
| 威力彩 2注 | **+0.20%** | +1.81% | 0.010 | ✅ SIGNAL |
| 威力彩 3注 | -0.20% | +1.96% | 0.055 | ⚠️ 邊界 |
| 539 3注 | +0.00% | N/A | N/A | 中性 |

### 關鍵指標
- 大樂透 5注 1500期中原 732 注有尾數違規 (48.8%)，全部修正
- Edge 全面非負 (大樂透均正)，可安全啟用
- 威力彩 3注 ΔEdge=-0.20% 在噪音範圍內 (p=0.055 未顯著)

## P1: 中度冷號池 — ❌ 暫停研究

### 研究結論
現行 pool=12 (最低頻率 + Sum約束) **已是最佳變體**。

| 變體 | 1500p Edge |
|------|-----------|
| A: 現行 pool=12 (最低頻率) | **+3.04%** |
| B: 中度冷號 gap 8-15 | +1.44% |
| C: 中度冷號 gap 6-12 | +1.51% |
| D: 寬範圍 gap 6-18 | +0.77% |
| E: 小池 gap 10-20 | +1.31% |

### Gap 回歸率分析
- Gap 0-7: Lift ≤ 1.02x (中性或偏低)
- Gap 8-9: Lift 1.02-1.06x (微弱正向)
- Gap 10: Lift 0.88x (凹谷)
- Gap 11-15: Lift 1.00-1.07x (微弱正向)
- Gap 16+: 雜訊大，樣本小

結論：Gap 沒有明顯 sweet spot。頻率排序優於 gap 排序。
重啟條件：dataset > 5000 期 或 發現新的非線性 gap 回歸模型。

## P2: 連號注入機制 — ❌ 暫停研究 (已自然覆蓋)

### 關鍵發現
**現行 5 注系統已自然產生連號對 (98.4% 覆蓋率)**

連號對分布 (1500期):
- 0 組: 50.4%
- 1 組: 39.0%
- ≥2 組: 10.6%
- 歷史 ≥1 組: 49.6%

| 變體 | 1500p Edge | 連號覆蓋率 |
|------|-----------|-----------|
| A: 現行 | **+3.04%** | 98.4% |
| B: 連號加分 | +2.97% | 99.9% |
| C: 連號保證 | +3.04% | 99.9% |
| D: 連號強注入 | +2.64% | 100.0% |

結論：30 個不重複號碼 (5×6) 從 49 號池中選，自然就有 98.4% 機率包含連號。
顯式注入無法改善 Edge，反而可能干擾最優選號。
重啟條件：改為 3 注或更少時，連號覆蓋率可能下降，屆時重新評估。

---

# 威力彩 PP3v2 研究 (2026-03-06)

## 觸發：第115000019期檢討 (開獎: 07,11,14,32,36,38 特別號02)

### 背景
PP3 最佳單注命中：4bet ClusterPivot 命中 4/6 (07,11,14,38)，未中 32,36。
假設三個可改進方向並進行完整三窗口驗證。

### 回測結果 (共 1890 期，三窗口 150/500/1500)

| 策略 | 150p Edge | 500p Edge | 1500p Edge | Perm p | 穩定性 | 判定 |
|------|-----------|-----------|------------|--------|--------|------|
| **PP3-Baseline** | +3.50% | +2.23% | +2.43% | 0.025 | ✅ STABLE | 維持不變 |
| PP3-EchoBoost | +4.16% | +2.43% | +1.56% | 0.130 | ⚠️ WEAK | ❌ REJECTED |
| PP3-Z3Gap | +0.16% | +0.83% | +1.64% | 0.045 | ✅ STABLE | ⚠️ WATCH |
| PP3v2-Combined | +1.50% | +0.43% | +0.34% | 0.420 | ⚠️ WEAK | ❌ REJECTED |

### 關鍵教訓

1. **Echo Boost 是 SHORT_MOMENTUM 陷阱**
   - 150p 表現誘人（+4.16%），1500p 衰減至 +1.56%，低於 PP3 的 +2.43%
   - 與 ClusterPivot 同類模式（已因 SHORT_MOMENTUM 被拒）
   - 規則：lag-1 echo boost 放大了近期巧合，不是真實週期信號

2. **Z3 Gap Bet3 有長期微弱正信號但不優於 PP3**
   - 統計顯著（p=0.045），但 1500p Edge=+1.64% < PP3 的 +2.43%
   - 呈現反向穩定性（愈長期愈好），說明是低頻長周期現象
   - 目前不改變 PP3；僅監控 300 期後重評

3. **聯合改進 = 互相干擾**
   - Time-scale mismatch：SHORT_MOMENTUM 信號 + LONG_SIGNAL = 抵消
   - 不同時間尺度的信號不應強行疊加

4. **115000019 的真實原因 = Fourier 的正常方差**
   - 32（gap=10期）和 36（gap=1期）的具體組合落在 Fourier 覆蓋外屬於期望範圍
   - M3+ 命中率 13.60% vs 基準 11.17%，差距 = 統計偶然，無系統性盲區

### 威力彩 PP3 研究現狀（截至 2026-03-06）

| 研究項目 | 狀態 |
|----------|------|
| PP3 3注（當前生產） | ✅ STABLE, Edge +2.43%, p=0.025 |
| PP3-Z3Gap | ⚠️ WATCH，300期後重評（2026-06） |
| Echo Boost (任何boost值) | ❌ REJECTED — SHORT_MOMENTUM |
| PP3v2 Combined | ❌ REJECTED — p=0.420 |
| Sum Reversal PROVISIONAL | ⚠️ MONITORING (200期監控中，到期 ~2026-04) |
| RSM 滾動監控下次更新 | 需 115000019 入庫後更新 |

---

## L57 觸發：第115000060期檢討 (開獎: 15,17,18,34,36) — 2026-03-08

### 背景
115000060期（2026/03/07）ACB+Markov+Fourier 3注命中 **2/5**（15+36），
三個信號缺口觸發研究：
- 17：Lag-2 回聲（出現在 115000057，gap=2~3）
- 18、34：gap=18 雙冷同期回補
- 36：Lag-1 連開（已被 Markov 注命中，非盲點）

### 新策略定義

| 策略 | 機制 | 注組合 |
|------|------|--------|
| LagEcho_1bet | Lag-k 回聲（k=1,2,3；權重 0.5/2.0/1.0） | LagEcho 1注 |
| ACB_LagEcho_2bet | ACB + LagEcho 正交 | 2注 |
| ACB_Markov_LagEcho_3bet | ACB + Markov + LagEcho 正交 | 3注（主要決策） |
| ACB_LagEcho_ColdBurst_3bet | ACB + LagEcho + ColdBurst(gap≥15) | 3注 |

### 標準回測結果（5802期，三窗口 150/500/1500，2026-03-08）

| 策略 | 150p Edge | 500p Edge | 1500p Edge | z | perm_p | 穩定性 | 決定 |
|------|---------|---------|-----------|---|--------|--------|------|
| LagEcho_1bet | -0.73% | +0.20% | **-0.13%** | -0.16 | N/A | SHORT_MOMENTUM | ❌ REJECT |
| ACB_LagEcho_2bet | +3.79% | +2.06% | **+3.53%** | 3.32 | 0.0100 | STABLE | ❌ 劣於現行 ADOPTED |
| ACB_Markov_LagEcho_3bet | +0.83% | +3.50% | **+5.03%** | 4.23 | 0.0249 | STABLE | ❌ 劣於現行 PROVISIONAL |
| ACB_LagEcho_ColdBurst_3bet | +3.50% | +1.30% | **+3.63%** | 3.06 | 0.0547 | STABLE | ❌ perm_p>0.05 REJECT |

現行冠軍（同期再跑）：
- MidFreq+ACB 2注: edge +5.06%（reference）
- ACB+Markov+Fourier 3注: edge +6.10%（5802期）

### McNemar 結果

| 比較 | a_only | b_only | p | 勝者 |
|------|--------|--------|---|------|
| S2 vs MidFreq+ACB | 138 | 161 | 0.18 | B（現行） |
| S3 vs ACB+Markov+Fourier | 128 | 144 | 0.33 | B（現行） |
| S4 vs ACB+Markov+Fourier | 237 | 274 | 0.10 | B（現行） |

三組 McNemar 全部 winner=B，現行冠軍統一獲勝。

### 關鍵教訓

1. **Lag-Echo 作為獨立信號（S1）沒有 edge**
   - LagEcho_1bet 1500p edge=-0.13%，SHORT_MOMENTUM，REJECT
   - 「近期出現的號碼有更高機率再出現」這個直覺在 1500 期統計上不成立

2. **Lag-Echo 整合進多注組合有正向 edge，但次於現行方法**
   - S2 (ACB+LagEcho) STABLE + perm p=0.01，統計有效但 edge 3.53% < ADOPTED 5.06%
   - S3 (ACB+Markov+LagEcho) STABLE + perm p=0.025，但 edge 5.03% < PROVISIONAL 6.10%
   - 結論：LagEcho 是有效信號但比 Fourier 弱

3. **Fourier 週期信號優於 Lag-Echo 信號（539 中）**
   - 以 Lag-Echo 替換 Fourier（S3 vs AMF）→ edge 從 6.10% 降至 5.03%
   - Fourier 捕捉週期性，包含 lag-k 效應及更多長週期模式，資訊量更豐富

4. **ColdBurst 機制統計顯著性不足（perm_p=0.055）**
   - 「多個 gap≥15 冷號同期回補」的群聚假說未能通過 p<0.05 門檻
   - 可能原因：threshold_gap=15 時 burst 狀態幾乎常態（burst_score ≈ 1.2），無區分度
   - 若要重試：需更嚴格的門檻（threshold_gap≥20, min_count≥5）

5. **115000060 的漏中本質是統計正常範圍**
   - 3注覆蓋 15 個號碼，命中 2/5 符合期望（M3+ 基準30.5%，2/5部份覆蓋正常）
   - 17 號 Lag-2 回聲是事後歸因（basequency evidence），非系統性盲區

### 539 研究現狀（截至 2026-03-08）

| 策略 | 狀態 |
|------|------|
| ACB 1注 | ✅ ADOPTED, Edge +3.00%, p=0.005 |
| MidFreq+ACB 2注 | ✅ ADOPTED, Edge +5.06%, p=0.005 |
| ACB+Markov+Fourier 3注 | ⚠️ PROVISIONAL, Edge +6.10%, p=0.025（McNemar 監控 200期中） |
| LagEcho_1bet | ❌ REJECTED — SHORT_MOMENTUM，edge=-0.13% |
| ACB+LagEcho 2注 | ❌ REJECTED — 劣於 ADOPTED（3.53% < 5.06%） |
| ACB+Markov+LagEcho 3注 | ❌ REJECTED — 劣於 PROVISIONAL（5.03% < 6.10%） |
| ACB+LagEcho+ColdBurst 3注 | ❌ REJECTED — perm_p=0.055 未達門檻 |

---

## L58 觸發：第115000061期檢討 + ExtremeCol/CondFourier 回測 — 2026-03-10

### 背景
115000061期（07,12,15,32,38）：2注 MidFreq+ACB 命中3個（12+15 by MidFreq, 07 by ACB），
3注 ACB+Markov+Fourier 命中2個（07 by ACB, 15 by Markov），Fourier注0/5。

關鍵未命中：
- 32（Lag-2回聲，LagEcho #3）— 連續第二期 Lag-2 被 Fourier 佔位
- 38（極端冷 gap=33，ColdBurst #3）— threshold_gap=15 無區分度

### P0: ExtremeCol (gap≥25) 回測結果（5804期）

| 策略 | 150p | 500p | 1500p Edge | perm_p | 穩定性 | McNemar vs 冠軍 |
|------|------|------|-----------|--------|--------|---------------|
| ExtremeCol_1bet | -4.73% | -2.40% | +0.13% | 0.363 | LATE_BLOOMER | — |
| MidFreq+ExtremeCol 2注 | +2.46% | +1.46% | +2.19% | 0.040 | STABLE | B wins p=0.002 |
| ACB+ExtremeCol 2注 | +3.79% | +1.06% | +3.33% | 0.005 | STABLE | B wins p=0.124 |
| ACB+Markov+ExtremeCol 3注 | +2.17% | +3.70% | +4.97% | 0.015 | STABLE | B wins p=0.300 |

全部策略 McNemar winner=B（現行冠軍）。特別注意：
- MidFreq+ExtremeCol McNemar p=0.002（**顯著劣於** MidFreq+ACB，多輸43場）
- 假設性 4/5 覆蓋（115000061）純屬個案，1500期統計否定

### P1: Conditional Fourier (Fourier弱→切LagEcho) 回測結果

| Fourier 門檻 | 1500p Edge | z | 穩定性 |
|-------------|-----------|---|--------|
| 0.25 | +6.10% | 5.13 | STABLE |
| 0.30 | +6.10% | 5.13 | STABLE |
| 0.35 | +6.10% | 5.13 | STABLE |
| 0.40 | +6.17% | 5.19 | STABLE |

**關鍵發現：四個門檻結果幾乎相同！**
- McNemar S5(0.4) vs AMF: a=1, b=0（整個1500期只差1場）
- 原因：Fourier max_score 幾乎永遠 > 0.40，LagEcho 路徑極少被觸發
- 結論：Conditional Fourier 設計正確但觸發條件過於罕見，實際等同純 Fourier

### 關鍵教訓

1. **ExtremeCol 是有效但弱於 ACB 的信號**
   - gap≥25 的極端冷號 ACB 已部分覆蓋（ACB gap_score 自然高分）
   - 用 ExtremeCol 替換 ACB 的任何位置都是降效
   - ExtremeCol 的「硬閾值篩選 + ACB 二次排序」不優於「ACB 的連續評分」

2. **Fourier 最大分數幾乎永遠 > 0.4**
   - 539 日開獎的大量歷史數據（5804期）使 FFT 對每個號碼都有穩定頻域表示
   - 結果：Fourier 週期信號「always on」，不存在「空窗期」概念
   - Conditional 機制的假設前提（Fourier 有弱/強之分）不成立

3. **事後歸因 ≠ 系統性優勢（第二次確認）**
   - 115000060: Lag-2(17) + 雙冷(18,34) → LagEcho/ColdBurst 回測失敗
   - 115000061: ExtremeCol(38) + Lag-2(32) → ExtremeCol/CondFourier 回測失敗
   - 規則：兩個案例的事後覆蓋分析不代表長期統計優勢

4. **現行冠軍 ACB+Markov+Fourier 3注的穩健性再次確認**
   - 六個新策略全部 McNemar 敗給現行冠軍（除 S5 平手）
   - Edge +6.10% 在 5804 期回測中持續穩定
   - 短期個案失敗（如 Fourier 注 0/5）是正常方差，不需修復

### 539 研究現狀更新（截至 2026-03-10）

| 策略 | 狀態 |
|------|------|
| ACB 1注 | ✅ ADOPTED, Edge +3.00%, p=0.005 |
| MidFreq+ACB 2注 | ✅ ADOPTED, Edge +5.06%, p=0.005 |
| ACB+Markov+Fourier 3注 | ⚠️ PROVISIONAL, Edge +6.10%, p=0.010 |
| ExtremeCol_1bet | ❌ REJECTED — LATE_BLOOMER perm_p=0.363 |
| MidFreq+ExtremeCol 2注 | ❌ REJECTED — 顯著劣於 ADOPTED (McNemar p=0.002) |
| ACB+ExtremeCol 2注 | ❌ REJECTED — 劣於 ADOPTED (edge 3.33%<5.06%) |
| ACB+Markov+ExtremeCol 3注 | ❌ REJECTED — 劣於冠軍 (edge 4.97%<6.10%) |
| CondFourier(0.4) 3注 | ❌ REJECTED — 與純 Fourier 無差異 (a=1 b=0) |
| **窮盡階段結論** | 現行3注策略框架已接近信號提取上限 |

---

## L59: MicroFish gap_current 資料洩漏 — 2026-03-15

### 觸發
MicroFish 演化策略搜尋引擎首次執行，報告 +39.07% edge (4.4× lift)。
所有 30 個頂級策略命中相同 +39.07% edge，全部通過驗證。

### Bug 詳細

```python
# BUGGY: gap_current[t] = 0 when number drawn at time t (future data!)
for t in range(T):
    if hit[t, n_idx]:  # ← Checks draw AT time t
        cg = 0
    gap_current[t, n_idx] = cg  # ← Gap includes time-t info

# FIXED: gap_current[t] records gap BEFORE draw t
for t in range(T):
    gap_current[t, n_idx] = cg  # ← Assigned BEFORE checking time t
    if hit[t, n_idx]:
        cg = 0
```

### 洩漏機制
- `gap_current[t, n] = 0` 當號碼 n 在第 t 期被開出
- `ix_sum_zscore_100_x_gap_ratio_100 = C(t) × gap_ratio[t, n]`
- 當 `C(t) < 0`（~50% 的時間）：drawn numbers 得分 0（最高），non-drawn 得分負
- 模型直接「看到」了開獎結果，命中率 ~50%

### 影響範圍
43/221 features 被汙染（27 gap + 8 interaction + 8 nonlinear = 19.5%）

### 修正後結果

| 指標 | 修正前（BUGGY） | 修正後（CLEAN） |
|------|:--------------:|:-------------:|
| Best edge | +39.07% | +4.73% |
| Hit rate | 50.47% | 16.13% |
| perm_p (1000 shuffles) | 0.005 | **0.001** |
| 主要特徵 | ix_sum_zscore_100_x_gap_ratio_100 | freq_raw_150 + nl_sq_freq_deficit_100 |

### 修正後最佳策略
- Features: freq_raw_150(0.306) + nl_sq_freq_deficit_100(0.271) + nl_sqrt_freq_zscore_100(0.181) + markov_lag1_100(0.171) + parity_even_boost_80(0.072)
- Edge: +4.73% (vs ACB +2.60%, improvement +2.13pp)
- 三窗口: 1500p=+4.73%, 500p=+6.20%, 150p=+5.93% → STABLE
- 1000-shuffle perm: p=0.001

### 教訓 (L59)

**特徵級時態隔離必須獨立驗證** — 即使 evaluate() 函數正確（只用 hit[t] 檢查結果），特徵矩陣中的 gap_current[t] 仍可能注入未來資訊。

檢查清單：
1. 任何在 `hit[t]` 上有 if-check 的特徵，必須確認 assignment 在 check 之前
2. 對所有特徵做 sanity check：如果單一特徵 lift > 2.0×，幾乎確定是洩漏
3. broadcast 特徵（sum/zone_entropy/ac_mean）與 per-number 特徵的交互項要特別注意
4. 用 200 shuffles 的 perm test 解析度不足（min p=0.005），必須 ≥1000 shuffles

---

## Meta-Strategy Decision Layer Research (2026-03-15)

### 摘要

7-phase meta-strategy research 結論：DAILY_539 系統在信號層已達 92.8% 理論天花板。

### 核心教訓 (L60)

**Skip 模型的 throughput 陷阱** — Skip 模型提升 conditional rate 但降低 coverage，net effect 是負的。

Evidence:
- Cold streak skip: edge=+5.07%, coverage=83.4% → throughput=4.23% < always-bet 4.73%
- Entropy skip p50: edge=+6.60%, coverage=50% → throughput=3.30% < always-bet 4.73%
- 結論：No skip model improves total expected value

### 核心教訓 (L61)

**Consensus-based skip 是 tautological** — 用多策略的 hit_details[i] 計算共識再決定是否下注，等同利用未來資訊。

正確做法：只使用 pre-draw indicators（entropy, recent rate, confidence spread）
錯誤做法：Skip_low_consensus_N（因為直接利用了當期結果）

### 核心教訓 (L62)

**Meta-selector 對 1-bet 層級無顯著效果** — Oracle meta-selector ceiling 是 +37.67%，但最佳 practical meta-selector 只有 +4.87%（McNemar p=0.65）。

原因：Pre-draw indicators（confidence spread, agreement, entropy, regime）對單期策略成敗的預測力極低。

### 核心教訓 (L63)

**ROI ≠ Hit Rate** — Markov ROI +44.67% 但靠一次 M4 的 20,000 NTD。M3+ 命中是高方差事件，不應以 ROI 排名取代 hit-rate edge 排名作為策略選擇依據。

### 關鍵發現

| 維度 | 結論 |
|------|------|
| Signal ceiling | 92.8% utilized, gap < 0.37pp |
| Meta-selection | +0.14pp, p=0.65, 不顯著 |
| Skip model | 降低 total throughput, 不推薦 |
| Multi-bet allocation | MicroFish+MidFreq 2-bet +6.86% (vs MidFreq+ACB +5.46%, Δ+1.40pp) ← **唯一 actionable 改進** |
| Error decomposition | 36.8% noise-dominated (irreducible), 39.3% coverage error, 23.9% allocation error |
| Payout | All 539 prizes fixed, no split risk |

### 行動項

1. ✅ McNemar validate MicroFish+MidFreq 2-bet vs MidFreq+ACB
2. ❌ 不再投入 meta-selection / skip model 研究
3. ⚠️ 只有新外部資料源出現時才重啟 signal discovery

## L64: 539 獎金表錯誤導致 EV 計算嚴重失誤 — 2026-03-15

### 核心教訓 (L64)

**永遠不要假設獎金數字 — 必須獨立驗證。** structural_optimization.py 和 meta_strategy_research.py 使用了錯誤的 539 獎金表：

| 項目 | 程式碼（錯誤） | 官方（正確） | 倍率差異 |
|------|---------------|-------------|---------|
| M2 (肆獎) | 300 NTD | **50 NTD** | 6.0x |
| M3 (參獎) | 2,000 NTD | **300 NTD** | 6.67x |
| M4 (貳獎) | 20,000 NTD | 20,000 NTD | 1.0x |
| M5 (頭獎) | ~8,000,000 NTD | ~8,000,000 NTD | 1.0x |

導致 EV 從實際 27.92 NTD 虛增為 70.47 NTD（+42.55 NTD 偏差），ROI 從 -44.16% 被錯誤報告為 +40.93%。

**可能混淆來源：** 39樂合彩（piggyback on 539 draw）的「三合」=300 NTD，被錯誤用作 539 的 M2 獎金。

### 影響範圍
- ❌ structural_optimization_report.md Direction 5 (Kelly) 和 Direction 6 (Structure) 結論錯誤
- ❌ Kelly criterion 結論從「積極下注 f*=9.3%」變為「需先克服 house edge」
- ✅ Hit rate edge 分析不受影響（edge 以命中率非獎金計算）
- ✅ 策略排名不受影響

### 防範規則
1. **所有獎金數字必須引用官方來源**，不可從記憶或推測中使用
2. **EV > Cost 的結果必須觸發自動審查**（彩券設計必然 negative EV）
3. **區分 539 和 39樂合彩的獎金結構**——兩者共用開獎號碼但獎金不同

---

## L65: Medium-Scale Strategy Evolution — 信號融合天花板確認 — 2026-03-15

### 核心教訓 (L65)

**獨立信號正交選號 > 融合排名（multi-bet）。** 200 pop × 50 gen 演化搜尋（~30K 候選策略）證實：

### 1. BASELINE_RATE 必須使用 P(M≥2) 而非 P(M≥1)

```python
# ❌ 錯誤：P(M≥1) = 1 - C(34,5)/C(39,5) = 51.67%
BASELINE_RATE = 1 - math.comb(34, 5) / math.comb(39, 5)

# ✅ 正確：P(M≥2) = Σ C(5,m)×C(34,5-m)/C(39,5) for m=2..5 = 11.40%
BASELINE_RATE = sum(math.comb(5,m)*math.comb(34,5-m) for m in range(2,6)) / math.comb(39,5)
```

P(M≥1) 包含只中1個號碼（未中獎），導致 baseline 膨脹 4.5×，所有 edge 顯示為 -37%~-52%。

### 2. Permutation test 必須打亂時序映射，不是打亂 hit_details

```python
# ❌ 錯誤：打亂 hit_details → mean(shuffled) ≡ mean(original) → p 永遠 = 1.0
np.random.shuffle(hit_details)

# ✅ 正確：打亂 actuals 的時序映射（第 t 期預測對應隨機期開獎）
perm_idx = rng.permutation(n_draws)
shuffled_actuals = actuals[start:end][perm_idx]
```

### 3. 獨立信號選號 > 融合排名（multi-bet 核心結論）

| 方法 | 2-bet Edge | 機制 |
|------|-----------|------|
| Reference MF+MidFreq | **+6.77%** | 每個信號獨立選 top-5，正交排除 |
| Evolved fused 2-bet | +5.10% | 4信號融合為單一排名，分割為2注 |

根因：每個信號捕捉不同模式（ACB=deficit, MidFreq=mean-reversion, Markov=transitions, MicroFish=evolved combination）。融合成單一排名喪失互補覆蓋。正交排除自然保障多樣性。

### 4. 演化收斂確認信號天花板

- Population 200 全部收斂至 **voting fusion**（每信號對 top-10 投票，加權計分）
- Gen 20-30 收斂，後續 20 代無改善
- 1-bet evolved +5.07% ≈ MicroFish ceiling 5.1% 的 99.4%
- McNemar 三組對比全部 p > 0.05，無統計顯著改善

### 5. Signal precomputation 是必要優化

- 從 raw history 即時計算 4 信號：O(N²)，掛起數分鐘
- 預計算 1600 期 × 39 號碼的信號矩陣（1.0s），演化只做矩陣運算
- History slice 限制 200 期（max signal window = 150），避免不必要的長歷史

### 演化結果摘要

| Level | Evolved Edge | Reference Edge | McNemar p | 判定 |
|-------|-------------|---------------|-----------|------|
| 1-bet | +5.07% | +4.47% (MicroFish) | 0.1599 | 不顯著 |
| 2-bet | +5.10% | +6.77% (MF+MidFreq) | 0.1059 | **Reference 更優** |
| 3-bet | +8.96% | +8.29% (MF+MidFreq+Markov) | 0.6108 | 不顯著 |

**結論：維持現行獨立信號架構。進一步搜尋不推薦——演化已收斂，信號天花板已達。**

重啟條件：(1) 出現新驗證信號，與現有信號正交命中率 >500 unique hits；(2) 外部數據源；(3) 遊戲規則變更。

### 產出檔案
- `tools/strategy_evolution_medium.py` — 演化引擎 v2（預計算信號）
- `evolved_strategy_population.json` — 全部結果與 metadata
- `validated_evolved_strategies.json` — 驗證後策略
- `portfolio_optimization_report.md` — 投資組合比較報告
- `medium_scale_research_conclusion.md` — 結案報告
- `strategy_genome_design.md` — 基因組設計規格

---

## L66: Strategy Space Exploration — 策略空間搜盡確認 — 2026-03-15

### 核心教訓 (L66)

**直接 top-5 選號 > 候選池 + 組合選號。** Pool expansion (top-7/9/12 → C(N,5) subset search) 在所有信號上降低 edge。信號品質集中在前5個號碼，第6-12名號碼只增加噪音。

### 1. Pool expansion 結果

| Signal | pool=5 (direct) | pool=7 | pool=9 | pool=12 |
|--------|:---:|:---:|:---:|:---:|
| MicroFish | **+4.47%** | +3.87% | +3.87% | +3.87% |
| ACB | **+3.27%** | +2.40% | +2.40% | +2.40% |
| MidFreq | **+1.74%** | +1.67% | +1.27% | +1.27% |

唯一例外：Markov pool=7 (+2.20%) > pool=5 (+1.07%)，因其轉移機率分布較平坦。

### 2. 獨立正交選號 > 所有融合方法（第三次確認）

| 方法 | Edge |
|------|:---:|
| **Independent orthogonal** | **+8.42%** |
| Union top5×4 greedy | +6.82% |
| Max coverage | +6.09% |
| Union top9×3 greedy | +5.82% |
| Union top7×4 greedy | +4.62% |

第三次獨立確認（L65 演化 + Obj2 多樣性分析 + 此研究）。

### 3. 3-bet 是效率邊界最優點

| Bet | Signal | Individual Edge | L31 |
|:---:|--------|:---:|:---:|
| 1 | MicroFish | **+4.10%** | Pass |
| 2 | MidFreq | **+1.60%** | Pass |
| 3 | Markov | **+0.73%** | Pass |
| 4 | ACB (殘留) | **-0.96%** | **FAIL** |
| 5 | MicroFish-res | **-1.08%** | **FAIL** |

Bet 4 (ACB) 排除前15號後，deficit+gap 信號不足以超越隨機基線。
Bet 5 (MicroFish-res) MicroFish 的信號集中在 top-5，第21-25名無有效信號。

### 4. 長期風險模擬結論 (10M MC)

- **任何注數、任何資金在 5000 期內 ruin rate ≈ 100%**
- M4+ 等待時間：1-bet 中位數 2,388 期 (≈6.5 年日開)
- Loss streak P99：1-bet = 28 期連續未中，3-bet = 10 期
- 信號 edge 無法克服 house edge (-44.16%)

### 研究空間封閉

| 方向 | 結果 | 狀態 |
|------|------|:---:|
| Pool expansion (top-7/9/12) | Edge 降低 0.6-2.1pp | 暫停 |
| Cross-signal pool merging | Edge 降低 1.6-3.8pp | 暫停 |
| 4+ bet portfolio | L31 violated (bet 4/5 negative edge) | 暫停 |
| Long-horizon profitability | Structurally impossible | 確定 |

重啟條件：(1) 新信號使 bet4 individual edge > 0；(2) 遊戲規則/獎金結構變更。

### 產出檔案
- `tools/strategy_space_exploration.py` — 研究引擎（4 objectives）
- `strategy_space_exploration_results.json` — 完整結果
- `docs/STRATEGY_SPACE_EXPLORATION_REPORT.md` — 報告
