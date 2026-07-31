# P273A — Prize-Aware Observed-Counts Export

> **Read-only observed-counts artifact.** No random baseline, probability, p-value, correction, confidence interval, edge classification, or prediction-success claim is computed here. P273A inferential validation is a separate, future, separately authorized task.

## Run metadata

- task_id: `P273A_OBSERVED_COUNTS_EXPORT`
- artifact_version: `p273a_observed_counts_v1`
- scoring_version: `prize_aware_v1`
- adapter_version: `prize_aware_adapter_v1`
- generated_at: `2026-06-15T01:37:49.506406+00:00`
- frozen_strategy_cell_count: **36**
- lotteries: DAILY_539, BIG_LOTTO, POWER_LOTTO
- windows: 100, 500, 1500
- source_verification_status: `MANUAL_VERIFICATION_REQUIRED`

## Safety flags

- production_write: `false`
- services_controlled: `false`
- inference_performed: `false`
- edge_claim_made: `false`
- registry_mutation: `false`
- db_read_only: `true`

## Provenance

- source_db_path: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db`
- db_open_mode: `sqlite3 URI mode=ro + PRAGMA query_only=ON`
- query_only_enabled: `true`
- single_snapshot: `true` (one connection, one read transaction)
- schema user_version: `0`
- schema_fingerprint_sha256: `a08e78b9cf24fb97bb62d5d11c347464ab3c116b600e356b34e7dbbd9d7fb343`
- P271A spec SHA-256: `73517f8be239a5638489b1b6291e2bb6a382b59be82d353e63916472939329ab`
- P267C artifact SHA-256: `3769596df51f6eaab5ef98cdf799ba9915f0c0349810f0899a7516004639a241`
- P271C scorer src SHA-256: `907bdfa514aa18b33defe44869673cf43ce82fe143260564635cfc7284a76659`
- P271E adapter src SHA-256: `3297481a05736dcefd79ed67b1f820651b723cd906e46e10a187b8433bf9e484`
- canonical_payload_digest: `859c3889f2c698a27d16caf4195bbd0fd032cad80d8c44e990958658624b3103`

## Governed endpoint (verified against P271A)

| lottery | endpoint_id | condition (committed) | min tier |
|---|---|---|---|
| DAILY_539 | `D539_ANY_PRIZE_AWARE_WIN` | `hit_count >= 2` | 肆獎 (2-match) |
| BIG_LOTTO | `BIG_ANY_PRIZE_AWARE_WIN` | `hit_count >= 3 OR (hit_count = 2 AND special_hit = 1)` | 普獎 (2-match + special) |
| POWER_LOTTO | `POWER_ANY_PRIZE_AWARE_WIN` | `hit_count >= 3 OR (hit_count >= 1 AND special_hit = 1)` | 普獎 (1-match + second-zone) |

## Per-cell observed counts

| lottery | strategy_id | window | support_draws | observed_successes | success_rate | scoreable_rows | excluded_rows | excl_missing_special | bet_count(min..max) | latest..earliest |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| DAILY_539 | 539_3bet_orthogonal | 100 | 100 | 13 | 0.130000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | 539_3bet_orthogonal | 500 | 500 | 63 | 0.126000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | 539_3bet_orthogonal | 1500 | 1500 | 179 | 0.119333 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| DAILY_539 | acb_1bet | 100 | 100 | 13 | 0.130000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | acb_1bet | 500 | 500 | 63 | 0.126000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | acb_1bet | 1500 | 1500 | 179 | 0.119333 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| DAILY_539 | acb_markov_midfreq | 100 | 100 | 5 | 0.050000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | acb_markov_midfreq | 500 | 500 | 54 | 0.108000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | acb_markov_midfreq | 1500 | 1500 | 170 | 0.113333 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| DAILY_539 | acb_markov_midfreq_3bet | 100 | 100 | 40 | 0.400000 | 300 | 0 | 0 | 3..3 | 115000121..115000022 |
| DAILY_539 | acb_markov_midfreq_3bet | 500 | 500 | 188 | 0.376000 | 1500 | 0 | 0 | 3..3 | 115000121..113000252 |
| DAILY_539 | acb_markov_midfreq_3bet | 1500 | 1500 | 526 | 0.350667 | 4500 | 0 | 0 | 3..3 | 115000121..110000190 |
| DAILY_539 | acb_single_539 | 100 | 100 | 13 | 0.130000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | acb_single_539 | 500 | 500 | 63 | 0.126000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | acb_single_539 | 1500 | 1500 | 179 | 0.119333 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| DAILY_539 | daily539_f4cold | 100 | 100 | 17 | 0.170000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | daily539_f4cold | 500 | 500 | 73 | 0.146000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | daily539_f4cold | 1500 | 1500 | 209 | 0.139333 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| DAILY_539 | daily539_f4cold_3bet | 100 | 100 | 39 | 0.390000 | 300 | 0 | 0 | 3..3 | 115000121..115000022 |
| DAILY_539 | daily539_f4cold_3bet | 500 | 500 | 176 | 0.352000 | 1500 | 0 | 0 | 3..3 | 115000121..113000252 |
| DAILY_539 | daily539_f4cold_3bet | 1500 | 1500 | 543 | 0.362000 | 4500 | 0 | 0 | 3..3 | 115000121..110000190 |
| DAILY_539 | daily539_f4cold_5bet | 100 | 100 | 66 | 0.660000 | 500 | 0 | 0 | 5..5 | 115000121..115000022 |
| DAILY_539 | daily539_f4cold_5bet | 500 | 500 | 280 | 0.560000 | 2500 | 0 | 0 | 5..5 | 115000121..113000252 |
| DAILY_539 | daily539_f4cold_5bet | 1500 | 1500 | 831 | 0.554000 | 7500 | 0 | 0 | 5..5 | 115000121..110000190 |
| DAILY_539 | daily539_markov_cold | 100 | 100 | 12 | 0.120000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | daily539_markov_cold | 500 | 500 | 57 | 0.114000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | daily539_markov_cold | 1500 | 1500 | 181 | 0.120667 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| DAILY_539 | markov_1bet_539 | 100 | 100 | 12 | 0.120000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | markov_1bet_539 | 500 | 500 | 57 | 0.114000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | markov_1bet_539 | 1500 | 1500 | 181 | 0.120667 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| DAILY_539 | midfreq_acb_2bet | 100 | 100 | 15 | 0.150000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | midfreq_acb_2bet | 500 | 500 | 73 | 0.146000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | midfreq_acb_2bet | 1500 | 1500 | 199 | 0.132667 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| DAILY_539 | midfreq_fourier_2bet | 100 | 100 | 15 | 0.150000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | midfreq_fourier_2bet | 500 | 500 | 73 | 0.146000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | midfreq_fourier_2bet | 1500 | 1500 | 199 | 0.132667 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 100 | 100 | 17 | 0.170000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 500 | 500 | 74 | 0.148000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 1500 | 1500 | 211 | 0.140667 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 100 | 100 | 17 | 0.170000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 500 | 500 | 74 | 0.148000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 1500 | 1500 | 211 | 0.140667 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| DAILY_539 | zone_gap_3bet_539 | 100 | 100 | 13 | 0.130000 | 100 | 0 | 0 | 1..1 | 115000121..115000022 |
| DAILY_539 | zone_gap_3bet_539 | 500 | 500 | 51 | 0.102000 | 500 | 0 | 0 | 1..1 | 115000121..113000252 |
| DAILY_539 | zone_gap_3bet_539 | 1500 | 1500 | 157 | 0.104667 | 1500 | 0 | 0 | 1..1 | 115000121..110000190 |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 100 | 100 | 6 | 0.060000 | 100 | 0 | 0 | 1..1 | 115000054..114000073 |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 500 | 500 | 17 | 0.034000 | 500 | 0 | 0 | 1..1 | 115000054..111000021 |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 1500 | 1500 | 54 | 0.036000 | 1500 | 0 | 0 | 1..1 | 115000054..102000011 |
| BIG_LOTTO | biglotto_deviation_2bet | 100 | 100 | 3 | 0.030000 | 100 | 0 | 0 | 1..1 | 115000053..114000072 |
| BIG_LOTTO | biglotto_deviation_2bet | 500 | 500 | 24 | 0.048000 | 500 | 0 | 0 | 1..1 | 115000053..111000020 |
| BIG_LOTTO | biglotto_deviation_2bet | 1500 | 1500 | 54 | 0.036000 | 1500 | 0 | 0 | 1..1 | 115000053..102000010 |
| BIG_LOTTO | biglotto_echo_aware_3bet | 100 | 100 | 8 | 0.080000 | 300 | 0 | 0 | 3..3 | 115000055..114000074 |
| BIG_LOTTO | biglotto_echo_aware_3bet | 500 | 500 | 52 | 0.104000 | 1500 | 0 | 0 | 3..3 | 115000055..111000022 |
| BIG_LOTTO | biglotto_echo_aware_3bet | 1500 | 1500 | 145 | 0.096667 | 4500 | 0 | 0 | 3..3 | 115000055..102000012 |
| BIG_LOTTO | biglotto_triple_strike | 100 | 100 | 6 | 0.060000 | 100 | 0 | 0 | 1..1 | 115000053..114000072 |
| BIG_LOTTO | biglotto_triple_strike | 500 | 500 | 15 | 0.030000 | 500 | 0 | 0 | 1..1 | 115000053..111000020 |
| BIG_LOTTO | biglotto_triple_strike | 1500 | 1500 | 53 | 0.035333 | 1500 | 0 | 0 | 1..1 | 115000053..102000010 |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 100 | 100 | 12 | 0.120000 | 400 | 0 | 0 | 4..4 | 115000055..114000074 |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 500 | 500 | 67 | 0.134000 | 2000 | 0 | 0 | 4..4 | 115000055..111000022 |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 1500 | 1500 | 196 | 0.130667 | 6000 | 0 | 0 | 4..4 | 115000055..102000012 |
| BIG_LOTTO | cold_complement_biglotto | 100 | 100 | 2 | 0.020000 | 100 | 0 | 0 | 1..1 | 115000054..114000073 |
| BIG_LOTTO | cold_complement_biglotto | 500 | 500 | 18 | 0.036000 | 500 | 0 | 0 | 1..1 | 115000054..111000021 |
| BIG_LOTTO | cold_complement_biglotto | 1500 | 1500 | 40 | 0.026667 | 1500 | 0 | 0 | 1..1 | 115000054..102000011 |
| BIG_LOTTO | coldpool15_biglotto | 100 | 100 | 2 | 0.020000 | 100 | 0 | 0 | 1..1 | 115000054..114000073 |
| BIG_LOTTO | coldpool15_biglotto | 500 | 500 | 18 | 0.036000 | 500 | 0 | 0 | 1..1 | 115000054..111000021 |
| BIG_LOTTO | coldpool15_biglotto | 1500 | 1500 | 40 | 0.026667 | 1500 | 0 | 0 | 1..1 | 115000054..102000011 |
| BIG_LOTTO | fourier30_markov30_biglotto | 100 | 100 | 3 | 0.030000 | 100 | 0 | 0 | 1..1 | 115000054..114000073 |
| BIG_LOTTO | fourier30_markov30_biglotto | 500 | 500 | 10 | 0.020000 | 500 | 0 | 0 | 1..1 | 115000054..111000021 |
| BIG_LOTTO | fourier30_markov30_biglotto | 1500 | 1500 | 36 | 0.024000 | 1500 | 0 | 0 | 1..1 | 115000054..102000011 |
| BIG_LOTTO | markov_2bet_biglotto | 100 | 100 | 2 | 0.020000 | 100 | 0 | 0 | 1..1 | 115000054..114000073 |
| BIG_LOTTO | markov_2bet_biglotto | 500 | 500 | 13 | 0.026000 | 500 | 0 | 0 | 1..1 | 115000054..111000021 |
| BIG_LOTTO | markov_2bet_biglotto | 1500 | 1500 | 38 | 0.025333 | 1500 | 0 | 0 | 1..1 | 115000054..102000011 |
| BIG_LOTTO | markov_single_biglotto | 100 | 100 | 2 | 0.020000 | 100 | 0 | 0 | 1..1 | 115000054..114000073 |
| BIG_LOTTO | markov_single_biglotto | 500 | 500 | 13 | 0.026000 | 500 | 0 | 0 | 1..1 | 115000054..111000021 |
| BIG_LOTTO | markov_single_biglotto | 1500 | 1500 | 38 | 0.025333 | 1500 | 0 | 0 | 1..1 | 115000054..102000011 |
| BIG_LOTTO | ts3_regime_3bet | 100 | 100 | 6 | 0.060000 | 100 | 0 | 0 | 1..1 | 115000053..114000072 |
| BIG_LOTTO | ts3_regime_3bet | 500 | 500 | 15 | 0.030000 | 500 | 0 | 0 | 1..1 | 115000053..111000020 |
| BIG_LOTTO | ts3_regime_3bet | 1500 | 1500 | 53 | 0.035333 | 1500 | 0 | 0 | 1..1 | 115000053..102000010 |
| POWER_LOTTO | cold_complement_2bet | 100 | 100 | 12 | 0.120000 | 100 | 0 | 0 | 1..1 | 115000040..114000045 |
| POWER_LOTTO | cold_complement_2bet | 500 | 500 | 55 | 0.110000 | 500 | 0 | 0 | 1..1 | 115000040..110000062 |
| POWER_LOTTO | cold_complement_2bet | 1500 | 1500 | 158 | 0.105333 | 1500 | 0 | 0 | 1..1 | 115000040..101000002 |
| POWER_LOTTO | fourier30_markov30_2bet | 100 | 99 | 7 | 0.070707 | 99 | 1 | 1 | 1..1 | 115000041..114000046 |
| POWER_LOTTO | fourier30_markov30_2bet | 500 | 499 | 55 | 0.110220 | 499 | 1 | 1 | 1..1 | 115000041..110000063 |
| POWER_LOTTO | fourier30_markov30_2bet | 1500 | 1499 | 184 | 0.122748 | 1499 | 1 | 1 | 1..1 | 115000041..101000003 |
| POWER_LOTTO | fourier_rhythm_3bet | 100 | 0 | 0 | — | 0 | 300 | 300 | — | 115000041..114000046 |
| POWER_LOTTO | fourier_rhythm_3bet | 500 | 0 | 0 | — | 0 | 1500 | 1500 | — | 115000041..110000063 |
| POWER_LOTTO | fourier_rhythm_3bet | 1500 | 0 | 0 | — | 0 | 4500 | 4500 | — | 115000041..101000003 |
| POWER_LOTTO | midfreq_fourier_2bet | 100 | 100 | 11 | 0.110000 | 100 | 0 | 0 | 1..1 | 115000040..114000045 |
| POWER_LOTTO | midfreq_fourier_2bet | 500 | 500 | 58 | 0.116000 | 500 | 0 | 0 | 1..1 | 115000040..110000062 |
| POWER_LOTTO | midfreq_fourier_2bet | 1500 | 1500 | 182 | 0.121333 | 1500 | 0 | 0 | 1..1 | 115000040..101000002 |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 100 | 100 | 13 | 0.130000 | 100 | 200 | 200 | 1..1 | 115000040..114000045 |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 500 | 500 | 64 | 0.128000 | 500 | 1000 | 1000 | 1..1 | 115000040..110000062 |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 1500 | 1500 | 192 | 0.128000 | 1500 | 3000 | 3000 | 1..1 | 115000040..101000002 |
| POWER_LOTTO | power_fourier_rhythm_2bet | 100 | 0 | 0 | — | 0 | 200 | 200 | — | 115000041..114000046 |
| POWER_LOTTO | power_fourier_rhythm_2bet | 500 | 0 | 0 | — | 0 | 1000 | 1000 | — | 115000041..110000063 |
| POWER_LOTTO | power_fourier_rhythm_2bet | 1500 | 0 | 0 | — | 0 | 3000 | 3000 | — | 115000041..101000003 |
| POWER_LOTTO | power_orthogonal_5bet | 100 | 0 | 0 | — | 0 | 500 | 500 | — | 115000040..114000045 |
| POWER_LOTTO | power_orthogonal_5bet | 500 | 0 | 0 | — | 0 | 2500 | 2500 | — | 115000040..110000062 |
| POWER_LOTTO | power_orthogonal_5bet | 1500 | 0 | 0 | — | 0 | 7500 | 7500 | — | 115000040..101000002 |
| POWER_LOTTO | power_precision_3bet | 100 | 0 | 0 | — | 0 | 300 | 300 | — | 115000040..114000045 |
| POWER_LOTTO | power_precision_3bet | 500 | 0 | 0 | — | 0 | 1500 | 1500 | — | 115000040..110000062 |
| POWER_LOTTO | power_precision_3bet | 1500 | 0 | 0 | — | 0 | 4500 | 4500 | — | 115000040..101000002 |
| POWER_LOTTO | pp3_freqort_4bet | 100 | 100 | 9 | 0.090000 | 100 | 300 | 300 | 1..1 | 115000040..114000045 |
| POWER_LOTTO | pp3_freqort_4bet | 500 | 500 | 60 | 0.120000 | 500 | 1500 | 1500 | 1..1 | 115000040..110000062 |
| POWER_LOTTO | pp3_freqort_4bet | 1500 | 1500 | 194 | 0.129333 | 1500 | 4500 | 4500 | 1..1 | 115000040..101000002 |
| POWER_LOTTO | zonal_entropy_2bet | 100 | 100 | 13 | 0.130000 | 100 | 0 | 0 | 1..1 | 115000040..114000045 |
| POWER_LOTTO | zonal_entropy_2bet | 500 | 500 | 59 | 0.118000 | 500 | 0 | 0 | 1..1 | 115000040..110000062 |
| POWER_LOTTO | zonal_entropy_2bet | 1500 | 1500 | 159 | 0.106000 | 1500 | 0 | 0 | 1..1 | 115000040..101000002 |

