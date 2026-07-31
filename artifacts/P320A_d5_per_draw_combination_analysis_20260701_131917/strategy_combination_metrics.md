# P320A Per-Draw Strategy Combination Metrics

Classification: `DESCRIPTIVE_ONLY`

Each draw-level combination pools the constituent strategies' stored tickets. `max_hit_count` is the largest main-number match count among those tickets. `hit_at_least_N_rate` is the fraction of common target draws whose maximum is at least N. This is an any-ticket portfolio metric, not a union-number ticket. Deltas compare the combination with its strongest constituent single-strategy rate in the same frozen sample and are descriptive only.

Overlap metrics enumerate cross-strategy ticket pairs per draw. `mean_number_overlap_fraction` is intersection size divided by the lottery's ticket size; exact duplicates are separately reported. Random baselines and inference were not computed.

## Descriptive candidate rows

| Lottery | Window | Size | Strategy IDs | Hit>=2 | Hit>=3 | Delta hit>=3 | Mean overlap |
|---|---:|---:|---|---:|---:|---:|---:|
| BIG_LOTTO | recent_50 | 2 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30 | 0.760000000000 | 0.140000000000 | 0.060000000000 | 0.121388888889 |
| BIG_LOTTO | recent_50 | 2 | bet2_fourier_expansion_biglotto|biglotto_echo_aware_3bet | 0.620000000000 | 0.120000000000 | 0.060000000000 | 0.094444444444 |
| BIG_LOTTO | recent_50 | 2 | biglotto_echo_aware_3bet|biglotto_triple_strike | 0.620000000000 | 0.120000000000 | 0.060000000000 | 0.094444444444 |
| BIG_LOTTO | recent_50 | 2 | biglotto_echo_aware_3bet|ts3_regime_3bet | 0.620000000000 | 0.120000000000 | 0.060000000000 | 0.094444444444 |
| BIG_LOTTO | recent_50 | 2 | biglotto_echo_aware_3bet|cold_complement_biglotto | 0.580000000000 | 0.100000000000 | 0.040000000000 | 0.128888888889 |
| BIG_LOTTO | recent_50 | 3 | biglotto_deviation_2bet|biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30 | 0.760000000000 | 0.160000000000 | 0.080000000000 | 0.138245614035 |
| BIG_LOTTO | recent_50 | 3 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30|cold_complement_biglotto | 0.760000000000 | 0.160000000000 | 0.080000000000 | 0.146315789474 |
| BIG_LOTTO | recent_50 | 3 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30|coldpool15_biglotto | 0.760000000000 | 0.160000000000 | 0.080000000000 | 0.146315789474 |
| BIG_LOTTO | recent_50 | 3 | bet2_fourier_expansion_biglotto|biglotto_echo_aware_3bet|cold_complement_biglotto | 0.700000000000 | 0.160000000000 | 0.100000000000 | 0.111428571429 |
| BIG_LOTTO | recent_50 | 3 | bet2_fourier_expansion_biglotto|biglotto_echo_aware_3bet|coldpool15_biglotto | 0.700000000000 | 0.160000000000 | 0.100000000000 | 0.111428571429 |
| BIG_LOTTO | recent_300 | 2 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30 | 0.676666666667 | 0.170000000000 | 0.083333333333 | 0.124953703704 |
| BIG_LOTTO | recent_300 | 2 | biglotto_echo_aware_3bet|biglotto_triple_strike | 0.496666666667 | 0.110000000000 | 0.026666666667 | 0.101851851852 |
| BIG_LOTTO | recent_300 | 2 | biglotto_echo_aware_3bet|ts3_regime_3bet | 0.496666666667 | 0.110000000000 | 0.026666666667 | 0.101851851852 |
| BIG_LOTTO | recent_300 | 2 | bet2_fourier_expansion_biglotto|biglotto_echo_aware_3bet | 0.493333333333 | 0.110000000000 | 0.026666666667 | 0.101851851852 |
| BIG_LOTTO | recent_300 | 2 | biglotto_echo_aware_3bet|cold_complement_biglotto | 0.503333333333 | 0.106666666667 | 0.023333333334 | 0.137222222222 |
| BIG_LOTTO | recent_300 | 3 | biglotto_deviation_2bet|biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30 | 0.716666666667 | 0.183333333333 | 0.096666666666 | 0.144298245614 |
| BIG_LOTTO | recent_300 | 3 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30|cold_complement_biglotto | 0.693333333333 | 0.183333333333 | 0.096666666666 | 0.149327485380 |
| BIG_LOTTO | recent_300 | 3 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30|coldpool15_biglotto | 0.693333333333 | 0.183333333333 | 0.096666666666 | 0.149327485380 |
| BIG_LOTTO | recent_300 | 3 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30|markov_2bet_biglotto | 0.700000000000 | 0.180000000000 | 0.093333333333 | 0.140438596491 |
| BIG_LOTTO | recent_300 | 3 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30|markov_single_biglotto | 0.700000000000 | 0.180000000000 | 0.093333333333 | 0.140438596491 |
| BIG_LOTTO | recent_750 | 2 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30 | 0.702666666667 | 0.153333333333 | 0.062666666666 | 0.125129629630 |
| BIG_LOTTO | recent_750 | 2 | biglotto_deviation_2bet|biglotto_ts3_markov_4bet_w30 | 0.565333333333 | 0.114666666667 | 0.024000000000 | 0.201111111111 |
| BIG_LOTTO | recent_750 | 2 | biglotto_ts3_markov_4bet_w30|fourier30_markov30_biglotto | 0.544000000000 | 0.100000000000 | 0.009333333333 | 0.190611111111 |
| BIG_LOTTO | recent_750 | 2 | biglotto_ts3_markov_4bet_w30|markov_2bet_biglotto | 0.536000000000 | 0.098666666667 | 0.008000000000 | 0.195055555556 |
| BIG_LOTTO | recent_750 | 2 | biglotto_ts3_markov_4bet_w30|markov_single_biglotto | 0.536000000000 | 0.098666666667 | 0.008000000000 | 0.195055555556 |
| BIG_LOTTO | recent_750 | 3 | biglotto_deviation_2bet|biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30 | 0.737333333333 | 0.176000000000 | 0.085333333333 | 0.144421052632 |
| BIG_LOTTO | recent_750 | 3 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30|markov_2bet_biglotto | 0.725333333333 | 0.161333333333 | 0.070666666666 | 0.139169590643 |
| BIG_LOTTO | recent_750 | 3 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30|markov_single_biglotto | 0.725333333333 | 0.161333333333 | 0.070666666666 | 0.139169590643 |
| BIG_LOTTO | recent_750 | 3 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30|cold_complement_biglotto | 0.721333333333 | 0.161333333333 | 0.070666666666 | 0.148830409357 |
| BIG_LOTTO | recent_750 | 3 | biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30|coldpool15_biglotto | 0.721333333333 | 0.161333333333 | 0.070666666666 | 0.148830409357 |
| DAILY_539 | recent_50 | 2 | acb_markov_midfreq_3bet|daily539_f4cold_5bet | 0.840000000000 | 0.020000000000 | 0.000000000000 | 0.133600000000 |
| DAILY_539 | recent_50 | 2 | daily539_f4cold_5bet|midfreq_acb_2bet | 0.780000000000 | 0.020000000000 | 0.000000000000 | 0.084800000000 |
| DAILY_539 | recent_50 | 2 | daily539_f4cold_5bet|midfreq_fourier_2bet | 0.780000000000 | 0.020000000000 | 0.000000000000 | 0.084800000000 |
| DAILY_539 | recent_50 | 2 | daily539_f4cold_5bet|zone_gap_3bet_539 | 0.760000000000 | 0.020000000000 | 0.000000000000 | 0.088800000000 |
| DAILY_539 | recent_50 | 2 | 539_3bet_orthogonal|daily539_f4cold_5bet | 0.740000000000 | 0.020000000000 | 0.000000000000 | 0.180000000000 |
| DAILY_539 | recent_50 | 3 | acb_markov_midfreq_3bet|daily539_f4cold_5bet|zone_gap_3bet_539 | 0.860000000000 | 0.020000000000 | 0.000000000000 | 0.132347826087 |
| DAILY_539 | recent_50 | 3 | acb_markov_midfreq_3bet|daily539_f4cold_5bet|p0b_539_3bet_f_cold_fmid | 0.840000000000 | 0.020000000000 | 0.000000000000 | 0.146782608696 |
| DAILY_539 | recent_50 | 3 | acb_markov_midfreq_3bet|daily539_f4cold_5bet|p0c_539_3bet_f_cold_x2 | 0.840000000000 | 0.020000000000 | 0.000000000000 | 0.146782608696 |
| DAILY_539 | recent_50 | 3 | acb_markov_midfreq_3bet|daily539_f4cold|daily539_f4cold_5bet | 0.840000000000 | 0.020000000000 | 0.000000000000 | 0.146782608696 |
| DAILY_539 | recent_50 | 3 | acb_markov_midfreq_3bet|daily539_f4cold_5bet|midfreq_acb_2bet | 0.840000000000 | 0.020000000000 | 0.000000000000 | 0.153913043478 |
| DAILY_539 | recent_300 | 2 | acb_markov_midfreq_3bet|daily539_f4cold_5bet | 0.716666666667 | 0.086666666667 | 0.033333333334 | 0.135111111111 |
| DAILY_539 | recent_300 | 2 | daily539_f4cold_5bet|midfreq_acb_2bet | 0.650000000000 | 0.066666666667 | 0.013333333334 | 0.102266666667 |
| DAILY_539 | recent_300 | 2 | daily539_f4cold_5bet|midfreq_fourier_2bet | 0.650000000000 | 0.066666666667 | 0.013333333334 | 0.102266666667 |
| DAILY_539 | recent_300 | 2 | daily539_f4cold_5bet|daily539_markov_cold | 0.620000000000 | 0.066666666667 | 0.013333333334 | 0.132933333333 |
| DAILY_539 | recent_300 | 2 | daily539_f4cold_5bet|markov_1bet_539 | 0.620000000000 | 0.066666666667 | 0.013333333334 | 0.132933333333 |
| DAILY_539 | recent_300 | 3 | acb_markov_midfreq|acb_markov_midfreq_3bet|daily539_f4cold_5bet | 0.733333333333 | 0.096666666667 | 0.043333333334 | 0.151739130435 |
| DAILY_539 | recent_300 | 3 | acb_markov_midfreq_3bet|daily539_f4cold_5bet|zone_gap_3bet_539 | 0.740000000000 | 0.090000000000 | 0.036666666667 | 0.138347826087 |
| DAILY_539 | recent_300 | 3 | acb_markov_midfreq_3bet|daily539_f4cold_5bet|p0b_539_3bet_f_cold_fmid | 0.720000000000 | 0.086666666667 | 0.033333333334 | 0.145420289855 |
| DAILY_539 | recent_300 | 3 | acb_markov_midfreq_3bet|daily539_f4cold_5bet|p0c_539_3bet_f_cold_x2 | 0.720000000000 | 0.086666666667 | 0.033333333334 | 0.145420289855 |
| DAILY_539 | recent_300 | 3 | acb_markov_midfreq_3bet|daily539_f4cold|daily539_f4cold_5bet | 0.716666666667 | 0.086666666667 | 0.033333333334 | 0.145797101449 |
| DAILY_539 | recent_750 | 2 | acb_markov_midfreq_3bet|daily539_f4cold_5bet | 0.710666666667 | 0.092000000000 | 0.030666666667 | 0.134524444444 |
| DAILY_539 | recent_750 | 2 | daily539_f4cold_5bet|midfreq_acb_2bet | 0.632000000000 | 0.073333333333 | 0.012000000000 | 0.107573333333 |
| DAILY_539 | recent_750 | 2 | daily539_f4cold_5bet|midfreq_fourier_2bet | 0.632000000000 | 0.073333333333 | 0.012000000000 | 0.107573333333 |
| DAILY_539 | recent_750 | 2 | acb_markov_midfreq|daily539_f4cold_5bet | 0.610666666667 | 0.073333333333 | 0.012000000000 | 0.120906666667 |
| DAILY_539 | recent_750 | 2 | daily539_f4cold_5bet|daily539_markov_cold | 0.620000000000 | 0.070666666667 | 0.009333333334 | 0.128906666667 |
| DAILY_539 | recent_750 | 3 | acb_markov_midfreq|acb_markov_midfreq_3bet|daily539_f4cold_5bet | 0.728000000000 | 0.104000000000 | 0.042666666667 | 0.150400000000 |
| DAILY_539 | recent_750 | 3 | acb_markov_midfreq_3bet|daily539_f4cold_5bet|zone_gap_3bet_539 | 0.733333333333 | 0.094666666667 | 0.033333333334 | 0.135200000000 |
| DAILY_539 | recent_750 | 3 | acb_markov_midfreq_3bet|daily539_f4cold_5bet|p0b_539_3bet_f_cold_fmid | 0.712000000000 | 0.092000000000 | 0.030666666667 | 0.145600000000 |
| DAILY_539 | recent_750 | 3 | acb_markov_midfreq_3bet|daily539_f4cold_5bet|p0c_539_3bet_f_cold_x2 | 0.712000000000 | 0.092000000000 | 0.030666666667 | 0.145600000000 |
| DAILY_539 | recent_750 | 3 | acb_markov_midfreq_3bet|daily539_f4cold_5bet|daily539_markov_cold | 0.712000000000 | 0.092000000000 | 0.030666666667 | 0.164417391304 |
