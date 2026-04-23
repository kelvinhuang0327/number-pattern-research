# 策略晉級驗證閘（Validation Gates）

> Source-of-truth：本檔。數字結論與實驗日誌在 `docs/` 對應報告；歸檔版本見 `docs/archive/INDEX.md`。

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
