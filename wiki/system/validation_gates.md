# 策略晉級驗證閘（Validation Gates）

> Source-of-truth：本檔。數字結論與實驗日誌在 `docs/` 對應報告；歸檔版本見 `docs/archive/INDEX.md`。

---

## Validation Tier 晉級層級（強制）

每個策略在任何時間點必須有且只能有一個 Tier 標籤。**不得跳 Tier 升格。**

| Tier | 名稱 | 進入條件 | 允許操作 |
|------|------|----------|----------|
| T0_IDEA | 假說 | 尚未執行任何回測 | 加入 backlog，命名，定義信號 |
| T1_MC_PASS | MC通過 | MC PASS（n≥1000, p<0.05），但三窗口或 McNemar 尚未驗證 | shadow/watch 模式；不得標記為 promotion candidate |
| T2_THREE_WINDOW_PASS | 三窗口通過 | 150/500/1000 或 150/500/1500 三窗口 edge > baseline；permutation p<0.05 | 可進入 McNemar 對現役的比較 |
| T3_INCUMBENT_PASS | 對抗現役通過 | McNemar vs 現役 p<0.05 且 net > 0；三窗口全正 | 可標記為 promotion_candidate；進入 CTO 審查 |
| T4_DEPLOYABLE | 可部署 | T3 通過 + CTO APPROVE + rolling slice 穩定 | 進入 RSM / production |

### 強制封鎖規則

- **T1_MC_PASS 策略**：禁止在任何 task 輸出、backlog、或 completed_text 中標記為 `promotion_candidate`。
- **未達 T3_INCUMBENT_PASS**：禁止標記 `promotion_candidate`；必須標記 `validation_tier` 對應值。
- **vs_incumbent ≤ 0**：即使 MC PASS、三窗口全正，也不得啟動 promotion。必須在 `promotion_blocker` 欄填入 `"vs_incumbent <= 0"`。
- **McNemar 未驗證**：缺乏 McNemar 結果的策略上限為 T2；不得晉升至 T3 或 T4。

---

## 必要通過條件（缺一不可）

| 閘 | 規則 |
|----|------|
| 三窗口回測 | 150 / 500 / 1500 期，ROI 皆須 > baseline |
| 統計顯著性 | p < 0.05 |
| Permutation test | 必須通過 |
| Walk-forward OOS | 必須通過 |
| Sharpe Ratio | Sharpe > 0 才可標記為有效策略 |

## 策略生命週期

```
Idea → Simulation → Backtest → Validation → Deploy → Monitor → Re-evaluate
```

各階段產出文件：

| 階段 | 文件 |
|------|------|
| Idea | `strategies/{name}/strategy.yaml` |
| Simulation | `strategies/{name}/sim_result.json` |
| Backtest | `strategies/{name}/backtest_report.md` |
| Validation | `strategies/{name}/stat_test.txt` |
| Deploy | `strategies/{name}/version_tag.txt` |
| Monitor | `strategies/{name}/performance_log.json` |

## 晉級目錄

- 通過驗證 → `validated/`
- 尚在觀察 → `provisional/`
- 驗證失敗 → `rejected/{strategy_name}.json`（含失敗原因、統計結果、適用條件、重測條件）

## 重新驗證觸發條件

以下任一條件發生時，觸發全策略重新測試：
- 新資料加入
- 遊戲規則變更
- 中獎率分布異常
- 頭獎金額分布偏移
- 玩家行為分布改變

## 評分公式

```
Score = (ROI × Stability × Significance) ÷ Complexity
```

- ROI = 平均回報率
- Stability = 三窗口一致性
- Significance = −log10(p)
- Complexity = 特徵數 × 參數數
- Score > baseline 才可晉級

## 已知邊界結論

- 三款遊戲（BIG_LOTTO、DAILY_539、POWER_LOTTO）決策層皆為 ADVISORY_ONLY，無法轉換為正 EV。
- Kelly 結果趨近 0，原因是 jackpot variance 主導且 monetary ROI 深負。
- 詳見 `wiki/system/decision_engine.md`。

## Backtest Integrity Checklist (extracted)

- Temporal Isolation: predictors and selectors must never access the target draw or any subsequent draws; always slice history strictly before the target.
- State Immobility: ranking/selection of strategies must use only pre-target performance; update component stats only after scoring the target.
- Use rolling/backtester frameworks (e.g., `RollingBacktester`) that enforce index checks and raise `DataLeakageError` on violations.
- Multi-window validation: run short/medium/long windows (e.g., short/150/500) to check consistency across horizons.
- Permutation test: include a shuffled-time permutation test for temporal structure (p < 0.05 indicates signal); record p and Cohen's d but do not treat single-run numbers as canonical.
- Noise robustness: test controlled noise injection levels and require strategies to show robustness (define pass/fail thresholds in deployment checklist).
- Enforce walk-forward / time-series split (WF OOS) as standard part of validation pipeline.

---

## Circular-Bias CI Gate

**Added:** 2026-05-06 | **Authority:** P1-Rank1 Governance Lock-in

> This gate prevents historical-pool max-hit and circular-match bias from polluting
> the validation pipeline. It does NOT prohibit edge discovery — it prohibits the
> use of biased evidence.

### What is Circular-Match Bias?

When a prediction P_T is derived from history H[<T] (e.g., by extracting hot/cold
numbers, frequency deviations, or co-occurrence patterns), comparing P_T against
the ENTIRE pool H[<T] to find the maximum-matching draw is **circular**:

> The strategy uses H[<T] as input AND H[<T] as the comparison target.
> "Does the pool contain a draw that looks like the patterns I extracted from the pool?"
> → Answer is almost always YES, with no predictive value.

The Monte Carlo null baseline (uniform random) does NOT have this selection bias, so
the resulting p-values are meaningless. This was confirmed when v1 analysis showed a
46× baseline for power_lotto — physically impossible for a certified lottery.

**Formal reference:** `outputs/prediction_hit_analysis/INVALID.md`

### Forbidden Pattern (v1 — DO NOT USE)

```python
# VIOLATION: comparing prediction against entire historical pool
prediction = [1, 2, 3, 4, 5]
historical_draws = [...]       # entire history pool
max_hit = max(len(set(prediction) & set(draw)) for draw in historical_draws)
# VIOLATION: using max_hit as edge/signal evidence
if max_hit >= 4:
    return {"signal": "EDGE_FOUND"}
```

Any variant of this pattern — loop-based, numpy matrix, lambda, class method — is forbidden.

### Correct Pattern (v2 — predict-vs-actual)

```python
# CORRECT: compare prediction only against its specific target draw
for period_T in test_periods:
    history = all_draws[:period_T.index]   # training data only
    prediction = model.predict(history)    # predict before target
    actual = set(period_T.draw.numbers)    # single target draw
    hit = len(set(prediction) & actual)    # predict-vs-actual
```

Use `scripts/predict_vs_actual.py` — the only authorized evaluation method.  
SOP: `wiki/system/predict_vs_actual_sop.md`

### CI Gate Scope

The CI test scans the following directories for circular-bias patterns:

| Directory | Covered | Notes |
|-----------|---------|-------|
| `scripts/` | YES | Excludes `scripts/prediction_hit_analysis.py` (already deprecated — see INVALID.md) |
| `tools/` | YES | Excludes `tools/archive/` |
| `lottery_api/` | YES | Excludes `lottery_api/archive/` |

**CI test:** `tests/test_no_circular_match.py`  
**Violation fixture:** `tests/fixtures/circular_match_violation.py`

The test must:
- PASS when scanning the active codebase (no new violations)
- FAIL when scanning the violation fixture (scanner works correctly)

### What This Gate Does NOT Prohibit

This gate does NOT prohibit:
- Using historical draws as **training data** for model fitting
- Walk-forward backtest (each period: prediction vs that period's actual draw)
- Computing hit counts **per bet** for a **single** actual draw
- Randomness audit iterating draws for statistical distribution analysis
- Retrospective analysis of a **specific known draw** (not a max-pool scan)

### Violation Response

If CI gate detects a violation:
1. Classify affected research as `STOP_FOR_BIAS`
2. Discard all outputs from that research run
3. Fix the source code to use `predict_vs_actual.py`
4. Re-run clean CI gate before any further research

---
