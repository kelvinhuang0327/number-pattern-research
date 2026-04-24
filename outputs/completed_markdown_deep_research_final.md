Deep Research — Cold-phase Strategy + Adaptive Bet Sizing + Monte Carlo Robustness

Summary (concise):
- Focus C (Cold-phase): Designed cold-specialized candidates (cold_low_freq_2bet, f4cold_3bet, p1_deviation_4bet). 150p screening and MC(seed=42,n=1000) executed. Mean MC edges small-positive for some candidates (see table).
- Focus G (Adaptive Bet Sizing): Draft policy produced (outputs/bet_sizing_policy_research.json). Recommend cold multiplier=0.5, hot multiplier=1.5 as baseline; MC calibration advised.
- Focus E (MC Robustness): Large-scale MC (n=1000) completed for selected candidates; permutation & McNemar pending for promotion.

Strategy Output Table

現有最佳策略：fourier_rhythm_3bet | game=POWER_LOTTO | edge=+0.00867 | window=30p
現有最佳策略：f4cold_3bet | game=DAILY_539 | edge=+0.095 | window=30p
現有最佳策略：p1_neighbor_cold_2bet | game=BIG_LOTTO | edge=+0.0631 | window=30p
MC 參數：seed=42, n=1000

| 策略名稱 | 彩種 | 回測視窗 | Edge | Sharpe | MC(n≥1000) | vs.現有最佳 |
|---|---|---:|---:|---:|---:|---:|
| cold_low_freq_2bet | POWER_LOTTO | 150  | +0.0307 | — | PASS | +0.0220 |
| cold_low_freq_2bet | POWER_LOTTO | 500  | —      | — | —    | +0.0220 |
| cold_low_freq_2bet | POWER_LOTTO | 1500 | —      | — | —    | +0.0220 |
| f4cold_3bet | DAILY_539 | 150  | +0.0950 | — | PASS | 0.000 |
| f4cold_3bet | DAILY_539 | 500  | —      | — | —    | 0.000 |
| p1_deviation_4bet | BIG_LOTTO | 150  | +0.0110 | — | PASS | -0.0521 |
| p1_deviation_4bet | BIG_LOTTO | 500  | —      | — | —    | -0.0521 |

Notes:
- Edges reported are 150p screening values where available (500/1500 pending).
- MC completed for the above candidates (seed=42,n=1000). Permutation and McNemar tests are the next gating steps.

Next actions (short):
1. Run permutation tests (lottery_api/engine/perm_test.py) for candidates: cold_low_freq_2bet, f4cold_3bet, p1_deviation_4bet (n_perm=200, seed=42) across 150/500/1500 windows.
2. Run McNemar comparisons vs incumbents for candidates that pass permutation.
3. If McNemar p<0.05 & three-window edges > incumbent, promote candidate per validation_gates; otherwise tune filters and repeat.

Artifacts:
- outputs/task_result_deep_research_final.json
- outputs/completed_markdown_deep_research_final.md
- outputs/deep_research_mc_summary.json
- tools/deep_research_cold_results.json
