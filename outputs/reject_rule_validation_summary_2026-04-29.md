# Reject Rule Validation Summary — 2026-04-29

Baseline (validated median edge_long): None

Matched candidates: 71

Missing metadata / blockers (candidates without sim_result or edges): ['hot_gap_return_biglotto', 'multiwindow_fourier_biglotto', 'acb_single_539', 'fourier_w100_pp3_power', 'ewma_539', 'h008_acb_nonlinear_gap_539', 'shlc_midfreq_power', 'habit_aware_fourier_v8_539', 'consecutive_pair_detector_539', 'hot_streak_override_biglotto', 'sgp_v9_apex_powerlotto', 'neighbor_injection_biglotto', 'extreme_col_539', 'markov_2bet_biglotto', 'markov_single_biglotto', 'acb_hot_fourier_3bet_biglotto', 'lag_echo_acb_markov_3bet_539', 'acb_markov_extremecol_3bet_539', 'p0b_539_3bet_f_cold_fmid', 'p1_conditional_branch_powerlotto', 'power_echo_boost', 'neighbor_acb_2bet_539', 'streak_boost_neighbor_bet1', 'gap_rebound_powerlotto', 'zone_gap_3bet_539', 'coldpool15_biglotto', 'cluster_pivot_biglotto', 'markov_repeat_exception_biglotto', 'ts3_markov_freq_5bet_biglotto', 'apriori_3bet_biglotto', 'p0c_539_3bet_f_cold_x2', 'bandit_ucb1_2bet_539', 'p2_mab_fusion', 'fourier30_markov30_biglotto', 'acb_extremecol_2bet_539', 'h005_pairwise_lift_539', 'cold_burst_3bet_539', '539_3bet_orthogonal', 'ts3_acb_4bet_biglotto', 'h002_conditional_acb_539', 'h003_delta_acb_539', 'h001_product_score_539', 'extremecol_1bet_539', 'cold_complement_biglotto', 'p0_neighbor_injection', 'special_mab_decay_adjustment_power', 'zone_cascade_guard_biglotto', 'markov_1bet_539', 'power_z3gap_watch', 'hot_stop_rebound_biglotto', 'conditional_fourier_539', 'short_term_hot_independent_bet', 'zone_constraint_cold_bet2', 'midfreq_extremecol_2bet_539', 'lift_pair_single_539', 'gap_dynamic_threshold_biglotto', 'structural_zone_guard_pp3_power', 'lag_echo_1bet_539', 'bet2_fourier_expansion_biglotto', 'condfourier_3bet_539', 'acb_lag_echo_2bet_539', 'mab_ucb1_539', 'h006_frequency_cluster_539', 'power_pp3v2_combined', 'h007_fourier_w1000_539', 'sgp_power_017_research', 'biglotto_6bet_zone_residual', 'core_satellite_biglotto', 'momentum_regime_switching_539', 'h004_gap_entropy_539', 'p3_state_aware']

Unable to select thresholds satisfying recall>=0.6 with current available metadata.


Notes:
- Many sim_result.json lack rolling-slice details, support_count, or tunable parameter counts.
- Bootstrap/permutation/McNemar tests could not be executed for candidates lacking per-slice/raw-hit data.
- Actionable follow-up: extract rolling slice outputs from backtester, and ensure sim_result includes `support_count` and `tunable_params_count`.