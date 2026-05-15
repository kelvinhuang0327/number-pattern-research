## Strategy Output Table

| strategy_name | game | edge_150 | edge_500 | edge_1000 | mc_status | vs_incumbent | validation_tier | promotion_blocker | next_action |
|---|---|---:|---:|---:|---|---:|---|---:|---|
| cold_lowfreq_2bet | POWER_LOTTO | -0.00667 | — | — | FAIL | -0.01567 | T0_IDEA | negative_edge | reject |
| shadow_gap_daily_3bet | DAILY_539 | +0.04667 | — | — | PASS | -0.04833 | T1_MC_PASS | vs_incumbent_non_positive | run_500w |
| anti_reverse_freq_4bet | BIG_LOTTO | +0.06667 | — | — | PASS | +0.00367 | T1_MC_PASS | multi-window unverified | run_500w |

現有最佳策略：fourier_rhythm_3bet | game=POWER_LOTTO | edge=+0.009 | window=30p
現有最佳策略：midfreq_acb_2bet | game=DAILY_539 | edge=+0.095 | window=300p
現有最佳策略：p1_deviation_4bet | game=BIG_LOTTO | edge=+0.063 | window=300p

MC 參數：seed=42, n=1000
