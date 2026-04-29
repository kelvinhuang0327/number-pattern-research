# DAILY_539

## Regime Status (2026-04-23) — COLD_PHASE_NORMAL

> **Micro-Volatility Normal**: 3/6 strategies in negative edge (50%), avg 1.3-period streaks (brief transients). Portfolio anchor strategy `midfreq_acb_2bet` maintaining +5.127% edge_30p. **Classification: NORMAL_LOW** — within 25th-50th percentile. **Expected recovery: 1 week** (confidence: high). **Action: NORMAL_MONITORING** — no action required, self-recovery expected. Analysis: `analysis/results/cold_phase_regime_analysis_20260423.md`

## 現況

- 維護模式；L82 確認 H001~H008 全部 REJECT，既有頻率族信號空間高度飽和。
- 目前保留 ACB / MidFreq / Markov-MidFreq 組合作為主監控策略。
- 2026-04-22：H011 weekday / calendar regime 驗證結論為 **REJECT**；weekday 全局 chi-square p=0.9281、Bonferroni survivors=0，calendar overlay 雖有 1500p raw edge，但 150/500p permutation 與對現役 McNemar 未過，維持不進 RSM。
- 2026-04-22：H012 cross-draw cluster / transition 驗證結論為 **REJECT**；lag-1/2/3 overlap 幾乎等於隨機基準，2bet/3bet 只在 1500p 出現正 raw edge，但 150/500p permutation 未過，無一候選進入 McNemar 替換閘。
- 2026-04-23：**H013 pool-size / market-behavior 驗證結論為 REJECT（弱訊號）**；官方 API 已補齊 100% trusted pool-size data (`sell_amount`, `total_amount`)，正式驗證完成。H013、H013b、H013c 三個候選在 150/500/1500 三窗口全數失敗：edge≈0%、p=1.0、Cohen's d≈0。結論：pool-size 對 539 無預測力，不是資料問題而是假說本身不成立。詳見：`analysis/results/daily539_h013_backfill_final_report_20260423.md`
- 2026-04-23：`microfish_midfreq_2bet` 升格驗證結論為 **REJECT**；active-code mapping 為 `MicroFish+MidFreq 2-bet`，雖 150/500/1500p raw edge、permutation 與 bet2 邊際效率全過，且 leakage audit PASS，但 150p 對 `midfreq_acb_2bet` 的 McNemar 僅 `p=0.1797`（net `+5`），未證明短窗穩定替換優勢，因此維持現役 2 注主線不變。結果檔：`analysis/results/daily539_microfish_midfreq_promotion_validation_20260423.json`

## 2026-04-23 信號窮盡審計

- **結論**: 全域審計確認 DAILY_539 無新可行研究方向
- **理由**:
  - H001~H008 全部 REJECT (L82)
  - H011 (weekday/calendar) REJECT 2026-04-22 (L117)
  - H012 (cross-draw cluster) REJECT 2026-04-22 (L118)
  - H013 (pool-size) REJECT 2026-04-23, 100% data 確認假說失效 (L129)
  - MicroFish+MidFreq 2-bet McNemar 未過 2026-04-23 (L128)
  - 頻率族信號空間高度飽和 (L82)
- **維護模式確認**: 繼續保留現役三策略，無新升格候選
- **審計參考**: analysis/results/signal_exhaustion_audit_20260423.md (games.daily_539 章節)

## 策略表

| 策略 | 注數 | Edge | Sharpe | 來源 |
|---|---:|---:|---:|---|
| acb_1bet | 1 | +3.38% | 0.095 | analysis/results/stage0_baseline.json |
| midfreq_acb_2bet | 2 | +8.65% | 0.188 | analysis/results/stage0_baseline.json |
| acb_markov_midfreq_3bet | 3 | +8.81% | 0.180 | analysis/results/stage0_baseline.json |

## 近期候選驗證

| 候選 | 注數 | 結論 | 關鍵阻塞 | 來源 |
|---|---:|---|---|---|
| microfish_midfreq_2bet | 2 | REJECT | 150p McNemar vs `midfreq_acb_2bet` `p=0.1797` | analysis/results/daily539_microfish_midfreq_promotion_validation_20260423.json |

## MicroFish WATCH 條件

- 目前唯一具行動價值的 MicroFish 路徑是「MicroFish+MidFreq 2-bet」。
- 只有在 McNemar 驗證可穩定優於 MidFreq+ACB 時才可升格；否則不重新分配 539 主策略。
- 若無新外部資料源，停止投入 meta-selection / skip model 類研究。

## 重要教訓索引

- L73：539 的 Zone / Sum 序列是白噪音，ZPI v1/v2 全數 REJECT。
- L74：Consecutive Streak 不具可操作訊號。
- L79：ACB × MidFreq 乘積分數因定義互斥而失敗。
- L80：數學構造的自相關不等於預測訊號。
- L81：弱信號乘法疊加不會放大 Edge，反而常退化。
- L82：H001~H008 全軍覆沒，539 進入維護模式。
- L117：weekday / calendar overlay 在 539 缺乏可升格的穩定正交訊號，不要重試 weekday 題。
- L118：cross-draw cluster / transition 在 539 長窗可出現 raw edge，但若跨期 overlap 與隨機近乎一致且 150/500p permutation 未過，仍應直接 REJECT。
- L125：539 的 pool-size / market-behavior 題若 trusted active data 沒有 pool/sales 欄位，就應做資料可用性 REJECT，不得用 proxy 補做偽驗證。
- L128：MicroFish+MidFreq 2-bet 即使三窗口 raw edge / permutation / 邊際效率全過，只要 150p McNemar 未證明穩定優於 `midfreq_acb_2bet`，仍應維持現役不升格。
- L130：EXPLORE-B constraint_postprocess 結構性 bucket 在 2026-04-29 驗證，23 bucket 全數 BH FDR q=1.0，目前證據不足，WATCH_ARCHIVED，REOPEN_ALLOWED_IF_NEW_EVIDENCE。

## 2026-04-29 Constraint Postprocess Validation

- **Validation result**: REJECT_FILTER_VALIDATION
- **Operational status**: WATCH_ARCHIVED
- **Current action**: DO_NOT_IMPLEMENT_NOW
- **No active strategy change**: 現役三策略不受影響。

### Tested features

| Feature | Description |
|---|---|
| sum band | Sum of 5 numbers, quartile buckets |
| odd/even ratio | Odd count 0-5 |
| span | max - min, tertile buckets |
| consecutive count | Longest consecutive run length |
| AC value | Unique pairwise differences minus (k-1) |
| zone coverage | Distinct zones covered (3 equal-width zones, 1-39) |

### Statistical result

- Buckets tested: 23 (pre-registered on 350 training draws; no holdout leakage)
- Null: 100,000 simulated random 5-from-39 combinations
- All raw p-values > 0.15
- All BH q-values = 1.0
- No bucket advanced to holdout validation
- Reproducible script: `scripts/diagnostics/compute_constraint_buckets.py` (seed=42)
- Full report: `research/constraint_validation_report_2026-04-29.md`

### Decision

- Do not implement constraint postprocess filter
- No active strategy change
- No A/B test at this time

### Reopen conditions (REOPEN_ALLOWED_IF_NEW_EVIDENCE)

- New candidate generator changes candidate distribution
- New external data source added
- ≥ 300–500 new draws accumulated
- Active strategy becomes DEGRADED
- Multi-feature interaction model proposed (instead of single-bucket filtering)
- Another lottery type shows a comparable structural signal
- **L129：539 的 pool-size 研究即使補齊了 100% trusted data (sell_amount, total_amount from official API)，也未必產生預測訊號。此案例中 H013/H013b/H013c 全部 p=1.0、edge≈0，說明外生市場特徵對 539 的數字生成無預測力。不重試此家族除非有新假說方向。**
- L103：目前 checkout 無正文；backlog 仍保留 L79~L106 範圍引用，需待原始來源補回。
- L104：目前 checkout 無正文；僅有其他研究類比引用，未見正式 lesson 條目。
- L105：目前 checkout 無正文；無法在現有倉庫中還原原文。

## Planner 提示

- 新 539 任務預設為監控、McNemar 驗證、外部新信號或 pool-size / market-behavior 類研究；不重複 H001~H008 類頻率變體，也不重試 H011/H012 已否決家族。
- 若要重啟 pool-size / market-behavior 題，前置條件是先補齊 trusted ingestion/backfill 的 pool 或 sales 欄位；在資料未補齊前，不派同家族重測。
- 若要動到現役策略，必須附帶三窗口、perm、McNemar 三重驗證。

## 2026-04-28 長窗驗證與系統狀態

| 研究 | 結論 |
|------|------|
| H_NEW_01 changepoint | NO_SIGNIFICANT_CHANGEPOINT |
| H_NEW_02 sum constraint | WATCH_SUM_CONSTRAINT（不實施 sum 後處理） |
| H_NEW_03 long-window | WATCH_LONG_WINDOW（3000p edge=+4.50pp，斜率=-1.53pp/1000draws） |

**系統狀態**: WATCH_MAINTENANCE（active=`acb_markov_midfreq_3bet`，shadow=`midfreq_acb_2bet`）

**Watchdog 條件**: 若 3000p edge ≤ +2.0pp → 標記 DEGRADED，觸發策略重評（禁止自動替換，需 CTO review）

**監控頻率**: weekly 或每 50 筆新 draw

詳細數據：`research/daily539_long_window_validation_report_20260428.md`

## 2026-04-29 長窗延伸驗證（H-LW-01 + H-LW-02）

| 研究 | 結論 |
|------|------|
| H-LW-01 (4000p + full-history) | STABLE_LONG_WINDOW |
| H-LW-02 (rolling 500p trend)   | SMOOTH_DECAY（CUSUM p=0.9855，無 regime shift） |

### 長窗回測結果（EXPLORE-C lane）

| 窗口 | Active Edge (pp) | Watchdog |
|------|---|---|
| 3000p | +4.50 | OK |
| 4000p | +3.77 | OK |
| 5000p（全歷史 max）| +3.68 | OK |

- Edge 斜率: -0.41 pp / 1000 draws（r=-0.914，monotonic=True）
- **結論**: 邊際遞減但仍高於 DEGRADED 閾值（+2.0pp），不需 CTO review

### Rolling 500p 結果

- 27 個 500p 滾動窗口，步長 200p
- Breach（≤+2.0pp）窗口: 11/27（40.7%）；多數集中在 2010–2019 早期低峰
- Mean edge: +3.47 pp，近期（2020+）均大幅正值（+4.5 ~ +10.3 pp）
- CUSUM break index: 22（2021/09/20），但 bootstrap p=0.9855（方向為正增）→ 非衰退跡象

### 系統狀態更新

**系統狀態**: STABLE_LONG_WINDOW（active=`acb_markov_midfreq_3bet`，shadow=`midfreq_acb_2bet`）

**策略不變**: 現役三策略維持不動，無需 CTO review

**Watchdog 條件（更新）**: 若 4000p 或 5000p edge ≤ +2.0pp → 標記 DEGRADED，觸發策略重評

**監控頻率**: weekly 或每 50 筆新 draw（不變）

詳細數據：`research/daily539_4000p_full_history_validation_report_2026-04-29.md`
CSV 輸出：`outputs/daily539_long_window_4000p_results_2026-04-29.csv`、`outputs/daily539_rolling_500p_edge_2026-04-29.csv`
