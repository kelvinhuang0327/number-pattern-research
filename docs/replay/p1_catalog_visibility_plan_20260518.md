# P1 Catalog Visibility Plan (20260518)

**Generated**: 2026-05-18T08:15:00.751183Z

## Summary

| Metric | Value |
|--------|-------|
| Runtime canonical strategies (before) | 18 |
| Artifact candidates found | 71 |
| Planned new registry entries | 71 |
| Planned existing registry updates (no change) | 18 |
| Planned NO_DATA entries | 83 |
| Skipped (bogus/unsafe) | 4 |

## Safety Constraints

| Constraint | Status |
|------------|--------|
| DB write | DISABLED (dry-run only) |
| Draw import | DISABLED |
| Replay row generation | DISABLED |
| Prediction update | DISABLED |
| Strategy execution | DISABLED |

## By Lottery Type

| Lottery | Total | New | NO_DATA |
|---------|-------|-----|---------|
| BIG_LOTTO | 26 | 21 | 24 |
| DAILY_539 | 33 | 25 | 31 |
| POWER_LOTTO | 16 | 11 | 14 |
| UNKNOWN | 14 | 14 | 14 |

## By Lifecycle State

| Lifecycle | Total | New | NO_DATA |
|-----------|-------|-----|---------|
| OBSERVATION | 1 | 0 | 1 |
| ONLINE | 8 | 0 | 2 |
| REJECTED | 75 | 71 | 75 |
| RETIRED | 5 | 0 | 5 |

## Entries

| strategy_id | lottery_type | lifecycle | visibility | new | has_rows |
|-------------|--------------|-----------|------------|-----|----------|
| 539_3bet_orthogonal | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| H001 | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| H002 | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| H003 | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| H004 | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| H005 | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| H006 | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| H007 | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| H008 | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| acb_1bet | DAILY_539 | RETIRED | REGISTERED_NO_DATA | no | no |
| acb_extremecol_2bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| acb_hot_fourier_3bet_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| acb_lag_echo_2bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| acb_markov_extremecol_3bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| acb_markov_midfreq | DAILY_539 | RETIRED | REGISTERED_NO_DATA | no | no |
| acb_markov_midfreq_3bet | DAILY_539 | RETIRED | REGISTERED_NO_DATA | no | no |
| acb_single_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| apriori_3bet_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| bandit_ucb1_2bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| bet2_fourier_expansion_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| biglotto_6bet_zone_residual | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| biglotto_deviation_2bet | BIG_LOTTO | ONLINE | REGISTERED_WITH_REPLAY_ROWS | no | YES |
| biglotto_triple_strike | BIG_LOTTO | ONLINE | REGISTERED_WITH_REPLAY_ROWS | no | YES |
| biglotto_ts3_acb_4bet | BIG_LOTTO | REJECTED | REGISTERED_NO_DATA | no | no |
| biglotto_ts3_markov_freq_5bet | BIG_LOTTO | REJECTED | REGISTERED_NO_DATA | no | no |
| cluster_pivot_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| cold_burst_3bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| cold_complement_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| coldpool15_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| condfourier_3bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| conditional_fourier_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| consecutive_pair_detector_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| core_satellite_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| daily539_f4cold | DAILY_539 | ONLINE | REGISTERED_WITH_REPLAY_ROWS | no | YES |
| daily539_markov_cold | DAILY_539 | ONLINE | REGISTERED_WITH_REPLAY_ROWS | no | YES |
| ewma_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| extreme_col_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| extremecol_1bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| fourier30_markov30_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| fourier_rhythm_3bet | POWER_LOTTO | ONLINE | REGISTERED_NO_DATA | no | no |
| fourier_w100_pp3_power | POWER_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| gap_dynamic_threshold_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| gap_rebound_powerlotto | POWER_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| h6_gate_mk20_ew85 | POWER_LOTTO | OBSERVATION | REGISTERED_NO_DATA | no | no |
| habit_aware_fourier_v8_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| hot_gap_return_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| hot_stop_rebound_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| hot_streak_override_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| lag_echo_1bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| lag_echo_acb_markov_3bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| lift_pair_single_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| mab_ucb1_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| markov_1bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| markov_2bet_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| markov_repeat_exception_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| markov_single_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| midfreq_acb_2bet | DAILY_539 | RETIRED | REGISTERED_NO_DATA | no | no |
| midfreq_extremecol_2bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| midfreq_fourier_2bet | DAILY_539 | RETIRED | REGISTERED_NO_DATA | no | no |
| momentum_regime_switching_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| multiwindow_fourier_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| neighbor_acb_2bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| neighbor_injection_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| p0_neighbor_injection | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| p0b_539_3bet_f_cold_fmid | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| p0c_539_3bet_f_cold_x2 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| p1_conditional_branch_powerlotto | POWER_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| p1_deviation_2bet_539 | DAILY_539 | REJECTED | REGISTERED_NO_DATA | no | no |
| p2_mab_fusion | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| p3_state_aware | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| power_echo_boost | POWER_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| power_orthogonal_5bet | POWER_LOTTO | ONLINE | REGISTERED_WITH_REPLAY_ROWS | no | YES |
| power_pp3v2_combined | POWER_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| power_precision_3bet | POWER_LOTTO | ONLINE | REGISTERED_WITH_REPLAY_ROWS | no | YES |
| power_shlc_midfreq | POWER_LOTTO | REJECTED | REGISTERED_NO_DATA | no | no |
| power_z3gap_watch | POWER_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| sgp_power_017_research | POWER_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| sgp_v9_apex_powerlotto | POWER_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| shlc_midfreq_power | POWER_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| short_term_hot_independent_bet | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| special_mab_decay_adjustment_power | POWER_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| streak_boost_neighbor_bet1 | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| structural_zone_guard_pp3_power | POWER_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| ts3_acb_4bet_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| ts3_markov_freq_5bet_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| ts3_regime_3bet | BIG_LOTTO | ONLINE | REGISTERED_NO_DATA | no | no |
| zone_cascade_guard_biglotto | BIG_LOTTO | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| zone_constraint_cold_bet2 | UNKNOWN | REJECTED | ARTIFACT_CANDIDATE | YES | no |
| zone_gap_3bet_539 | DAILY_539 | REJECTED | ARTIFACT_CANDIDATE | YES | no |

## Skipped Entries

| strategy_id | reason |
|-------------|--------|
| big_lotto | BOGUS_ID: generic name from inventory scan (MEMORY.md or strategy.yaml) |
| daily_539 | BOGUS_ID: generic name from inventory scan (MEMORY.md or strategy.yaml) |
| power_lotto | BOGUS_ID: generic name from inventory scan (MEMORY.md or strategy.yaml) |
| strategy | BOGUS_ID: generic name from inventory scan (MEMORY.md or strategy.yaml) |