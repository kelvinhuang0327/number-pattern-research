# Strategies — 採納策略目錄

每個採納策略依生命週期階段維護以下文件：

| 文件 | 階段 | 說明 |
|------|------|------|
| `strategy.yaml` | Idea | 策略描述、參數、設計理念 |
| `sim_result.json` | Simulation | 初步模擬結果 |
| `backtest_report.md` | Backtest | 三窗口回測報告 |
| `stat_test.txt` | Validation | 統計顯著性測試 (P3/McNemar) |
| `version_tag.txt` | Deploy | 版本號與採納日期 |
| `performance_log.json` | Monitor | RSM 滾動監控結果 |

## 目錄結構

```
strategies/
├── big_lotto/
│   ├── 2bet_fourier_rhythm/       Edge +0.51%
│   ├── 2bet_deviation_complement/ Edge +0.51%
│   ├── 3bet_triple_strike_v2/     Edge +1.46% ★
│   ├── 4bet_ts3_markov_w30/       Edge +1.70% ★
│   └── 5bet_ts3_markov_freq/      Edge +1.97% ★ 現役最佳
└── power_lotto/
    ├── 2bet_fourier_rhythm/       Edge +1.91%
    ├── 3bet_power_precision/      Edge +2.30% ★
    └── 5bet_orthogonal/           Edge +3.53% ★ 現役最佳
```

## 採納標準（必須全部通過）

- 1500期三窗口全正（150 / 500 / 1500）
- 統計顯著性 p < 0.05
- Permutation test 通過
- Sharpe Ratio > 0
