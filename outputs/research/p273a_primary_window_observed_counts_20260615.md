# P273A — Primary-Window Prize-Aware Observed-Counts Export

> **Read-only observed-counts artifact.** No random baseline, expected successes, probability, p-value, correction, confidence interval, BH-FDR, edge classification, or GO recommendation is computed here. P273A inferential validation is a separate, future, separately authorized task.

## Owner-approved primary-window policy

- policy_version: `primary_window_policy_v1_50_300_750` (owner_approved: `true`)
- **Primary decision windows:** 50 (SHORT), 300 (MID), 750 (LONG)
- **Reference-only (excluded from this export):** 1500 draws, all-history frequency or distribution, any longer-horizon aggregate not in 50 / 300 / 750
- Reference-only evidence must NOT drive: strategy_promotion, strategy_elimination, stability_pass_or_fail, go_recommendation, production_deployment_screening
- correction_family_planned: **108** (36 cells × 3 primary windows; correction/inference NOT performed)
- window_adjustment_rule: primary windows are frozen as 50/300/750 for this task; any statistical-expert adjustment requires a separate pre-outcome owner-approved task and a new export; do not adjust windows after viewing results
- prior 100/500/1500 artifact (now reference-only, immutable): `outputs/research/p273a_prizeaware_observed_counts_20260614.json`

## Run metadata

- task_id: `P273A_PRIMARY_WINDOW_OBSERVED_COUNTS_EXPORT`
- artifact_version: `p273a_primary_window_observed_counts_v1`
- scoring_version: `prize_aware_v1`
- adapter_version: `prize_aware_adapter_v1`
- generated_at: `2026-06-15T02:39:00.976163+00:00`
- frozen_strategy_cell_count: **36**
- lotteries: DAILY_539, BIG_LOTTO, POWER_LOTTO
- primary_windows: 50, 300, 750
- source_verification_status: `MANUAL_VERIFICATION_REQUIRED`

## Safety flags

- db_read_only: `true`
- production_write: `false`
- services_controlled: `false`
- inference_performed: `false`
- edge_claim_made: `false`
- go_recommendation_made: `false`
- registry_mutation: `false`
- baseline_computed: `false`
- p_value_computed: `false`
- second_zone_manufactured: `false`

## Provenance

- source_db_path: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db`
- db_open_mode: `sqlite3 URI mode=ro + PRAGMA query_only=ON`
- query_only_enabled: `true`
- single_snapshot: `true` (one connection, one read transaction)
- permitted_tables: draws, strategy_prediction_replays
- reused_export_module: `analysis/p273a_prizeaware_replay_export.py`
- schema user_version: `0`
- schema_fingerprint_sha256: `a08e78b9cf24fb97bb62d5d11c347464ab3c116b600e356b34e7dbbd9d7fb343`
- P271A spec SHA-256: `73517f8be239a5638489b1b6291e2bb6a382b59be82d353e63916472939329ab`
- P267C artifact SHA-256: `3769596df51f6eaab5ef98cdf799ba9915f0c0349810f0899a7516004639a241`
- P271C scorer src SHA-256: `907bdfa514aa18b33defe44869673cf43ce82fe143260564635cfc7284a76659`
- P271E adapter src SHA-256: `3297481a05736dcefd79ed67b1f820651b723cd906e46e10a187b8433bf9e484`
- canonical_payload_digest: `65a4cc59f5ab64d685890566e38493b0295e622f351e0527782f1dce2f38645f`

## Governed endpoint (verified against P271A)

| lottery | endpoint_id | condition (committed) | min tier |
|---|---|---|---|
| DAILY_539 | `D539_ANY_PRIZE_AWARE_WIN` | `hit_count >= 2` | 肆獎 (2-match) |
| BIG_LOTTO | `BIG_ANY_PRIZE_AWARE_WIN` | `hit_count >= 3 OR (hit_count = 2 AND special_hit = 1)` | 普獎 (2-match + special) |
| POWER_LOTTO | `POWER_ANY_PRIZE_AWARE_WIN` | `hit_count >= 3 OR (hit_count >= 1 AND special_hit = 1)` | 普獎 (1-match + second-zone) |

## Per-cell observed counts (primary windows 50 / 300 / 750)

| lottery | strategy_id | window | label | support_draws | observed_successes | success_rate | scoreable_rows | excluded_rows | excl_missing_special | bet_count(min..max) | latest..earliest |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|
| DAILY_539 | 539_3bet_orthogonal | 50 | SHORT | 50 | 8 | 0.160000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | 539_3bet_orthogonal | 300 | MID | 300 | 39 | 0.130000 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | 539_3bet_orthogonal | 750 | LONG | 750 | 93 | 0.124000 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| DAILY_539 | acb_1bet | 50 | SHORT | 50 | 8 | 0.160000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | acb_1bet | 300 | MID | 300 | 39 | 0.130000 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | acb_1bet | 750 | LONG | 750 | 93 | 0.124000 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| DAILY_539 | acb_markov_midfreq | 50 | SHORT | 50 | 0 | 0.000000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | acb_markov_midfreq | 300 | MID | 300 | 32 | 0.106667 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | acb_markov_midfreq | 750 | LONG | 750 | 74 | 0.098667 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| DAILY_539 | acb_markov_midfreq_3bet | 50 | SHORT | 50 | 18 | 0.360000 | 150 | 0 | 0 | 3..3 | 115000121..115000072 |
| DAILY_539 | acb_markov_midfreq_3bet | 300 | MID | 300 | 120 | 0.400000 | 900 | 0 | 0 | 3..3 | 115000121..114000138 |
| DAILY_539 | acb_markov_midfreq_3bet | 750 | LONG | 750 | 268 | 0.357333 | 2250 | 0 | 0 | 3..3 | 115000121..113000002 |
| DAILY_539 | acb_single_539 | 50 | SHORT | 50 | 8 | 0.160000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | acb_single_539 | 300 | MID | 300 | 39 | 0.130000 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | acb_single_539 | 750 | LONG | 750 | 93 | 0.124000 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| DAILY_539 | daily539_f4cold | 50 | SHORT | 50 | 11 | 0.220000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | daily539_f4cold | 300 | MID | 300 | 44 | 0.146667 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | daily539_f4cold | 750 | LONG | 750 | 105 | 0.140000 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| DAILY_539 | daily539_f4cold_3bet | 50 | SHORT | 50 | 23 | 0.460000 | 150 | 0 | 0 | 3..3 | 115000121..115000072 |
| DAILY_539 | daily539_f4cold_3bet | 300 | MID | 300 | 101 | 0.336667 | 900 | 0 | 0 | 3..3 | 115000121..114000138 |
| DAILY_539 | daily539_f4cold_3bet | 750 | LONG | 750 | 275 | 0.366667 | 2250 | 0 | 0 | 3..3 | 115000121..113000002 |
| DAILY_539 | daily539_f4cold_5bet | 50 | SHORT | 50 | 35 | 0.700000 | 250 | 0 | 0 | 5..5 | 115000121..115000072 |
| DAILY_539 | daily539_f4cold_5bet | 300 | MID | 300 | 170 | 0.566667 | 1500 | 0 | 0 | 5..5 | 115000121..114000138 |
| DAILY_539 | daily539_f4cold_5bet | 750 | LONG | 750 | 425 | 0.566667 | 3750 | 0 | 0 | 5..5 | 115000121..113000002 |
| DAILY_539 | daily539_markov_cold | 50 | SHORT | 50 | 4 | 0.080000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | daily539_markov_cold | 300 | MID | 300 | 38 | 0.126667 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | daily539_markov_cold | 750 | LONG | 750 | 81 | 0.108000 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| DAILY_539 | markov_1bet_539 | 50 | SHORT | 50 | 4 | 0.080000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | markov_1bet_539 | 300 | MID | 300 | 38 | 0.126667 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | markov_1bet_539 | 750 | LONG | 750 | 81 | 0.108000 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| DAILY_539 | midfreq_acb_2bet | 50 | SHORT | 50 | 6 | 0.120000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | midfreq_acb_2bet | 300 | MID | 300 | 48 | 0.160000 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | midfreq_acb_2bet | 750 | LONG | 750 | 101 | 0.134667 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| DAILY_539 | midfreq_fourier_2bet | 50 | SHORT | 50 | 6 | 0.120000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | midfreq_fourier_2bet | 300 | MID | 300 | 48 | 0.160000 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | midfreq_fourier_2bet | 750 | LONG | 750 | 101 | 0.134667 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 50 | SHORT | 50 | 11 | 0.220000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 300 | MID | 300 | 45 | 0.150000 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 750 | LONG | 750 | 106 | 0.141333 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 50 | SHORT | 50 | 11 | 0.220000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 300 | MID | 300 | 45 | 0.150000 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 750 | LONG | 750 | 106 | 0.141333 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| DAILY_539 | zone_gap_3bet_539 | 50 | SHORT | 50 | 8 | 0.160000 | 50 | 0 | 0 | 1..1 | 115000121..115000072 |
| DAILY_539 | zone_gap_3bet_539 | 300 | MID | 300 | 31 | 0.103333 | 300 | 0 | 0 | 1..1 | 115000121..114000138 |
| DAILY_539 | zone_gap_3bet_539 | 750 | LONG | 750 | 76 | 0.101333 | 750 | 0 | 0 | 1..1 | 115000121..113000002 |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 50 | SHORT | 50 | 4 | 0.080000 | 50 | 0 | 0 | 1..1 | 115000054..115000005 |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 300 | MID | 300 | 10 | 0.033333 | 300 | 0 | 0 | 1..1 | 115000054..112000107 |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 750 | LONG | 750 | 25 | 0.033333 | 750 | 0 | 0 | 1..1 | 115000054..108000109 |
| BIG_LOTTO | biglotto_deviation_2bet | 50 | SHORT | 50 | 2 | 0.040000 | 50 | 0 | 0 | 1..1 | 115000053..115000004 |
| BIG_LOTTO | biglotto_deviation_2bet | 300 | MID | 300 | 10 | 0.033333 | 300 | 0 | 0 | 1..1 | 115000053..112000106 |
| BIG_LOTTO | biglotto_deviation_2bet | 750 | LONG | 750 | 32 | 0.042667 | 750 | 0 | 0 | 1..1 | 115000053..108000108 |
| BIG_LOTTO | biglotto_echo_aware_3bet | 50 | SHORT | 50 | 4 | 0.080000 | 150 | 0 | 0 | 3..3 | 115000055..115000006 |
| BIG_LOTTO | biglotto_echo_aware_3bet | 300 | MID | 300 | 33 | 0.110000 | 900 | 0 | 0 | 3..3 | 115000055..112000108 |
| BIG_LOTTO | biglotto_echo_aware_3bet | 750 | LONG | 750 | 75 | 0.100000 | 2250 | 0 | 0 | 3..3 | 115000055..108000110 |
| BIG_LOTTO | biglotto_triple_strike | 50 | SHORT | 50 | 4 | 0.080000 | 50 | 0 | 0 | 1..1 | 115000053..115000004 |
| BIG_LOTTO | biglotto_triple_strike | 300 | MID | 300 | 10 | 0.033333 | 300 | 0 | 0 | 1..1 | 115000053..112000106 |
| BIG_LOTTO | biglotto_triple_strike | 750 | LONG | 750 | 22 | 0.029333 | 750 | 0 | 0 | 1..1 | 115000053..108000108 |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 50 | SHORT | 50 | 5 | 0.100000 | 200 | 0 | 0 | 4..4 | 115000055..115000006 |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 300 | MID | 300 | 38 | 0.126667 | 1200 | 0 | 0 | 4..4 | 115000055..112000108 |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 750 | LONG | 750 | 99 | 0.132000 | 3000 | 0 | 0 | 4..4 | 115000055..108000110 |
| BIG_LOTTO | cold_complement_biglotto | 50 | SHORT | 50 | 2 | 0.040000 | 50 | 0 | 0 | 1..1 | 115000054..115000005 |
| BIG_LOTTO | cold_complement_biglotto | 300 | MID | 300 | 10 | 0.033333 | 300 | 0 | 0 | 1..1 | 115000054..112000107 |
| BIG_LOTTO | cold_complement_biglotto | 750 | LONG | 750 | 21 | 0.028000 | 750 | 0 | 0 | 1..1 | 115000054..108000109 |
| BIG_LOTTO | coldpool15_biglotto | 50 | SHORT | 50 | 2 | 0.040000 | 50 | 0 | 0 | 1..1 | 115000054..115000005 |
| BIG_LOTTO | coldpool15_biglotto | 300 | MID | 300 | 10 | 0.033333 | 300 | 0 | 0 | 1..1 | 115000054..112000107 |
| BIG_LOTTO | coldpool15_biglotto | 750 | LONG | 750 | 21 | 0.028000 | 750 | 0 | 0 | 1..1 | 115000054..108000109 |
| BIG_LOTTO | fourier30_markov30_biglotto | 50 | SHORT | 50 | 1 | 0.020000 | 50 | 0 | 0 | 1..1 | 115000054..115000005 |
| BIG_LOTTO | fourier30_markov30_biglotto | 300 | MID | 300 | 6 | 0.020000 | 300 | 0 | 0 | 1..1 | 115000054..112000107 |
| BIG_LOTTO | fourier30_markov30_biglotto | 750 | LONG | 750 | 19 | 0.025333 | 750 | 0 | 0 | 1..1 | 115000054..108000109 |
| BIG_LOTTO | markov_2bet_biglotto | 50 | SHORT | 50 | 1 | 0.020000 | 50 | 0 | 0 | 1..1 | 115000054..115000005 |
| BIG_LOTTO | markov_2bet_biglotto | 300 | MID | 300 | 9 | 0.030000 | 300 | 0 | 0 | 1..1 | 115000054..112000107 |
| BIG_LOTTO | markov_2bet_biglotto | 750 | LONG | 750 | 18 | 0.024000 | 750 | 0 | 0 | 1..1 | 115000054..108000109 |
| BIG_LOTTO | markov_single_biglotto | 50 | SHORT | 50 | 1 | 0.020000 | 50 | 0 | 0 | 1..1 | 115000054..115000005 |
| BIG_LOTTO | markov_single_biglotto | 300 | MID | 300 | 9 | 0.030000 | 300 | 0 | 0 | 1..1 | 115000054..112000107 |
| BIG_LOTTO | markov_single_biglotto | 750 | LONG | 750 | 18 | 0.024000 | 750 | 0 | 0 | 1..1 | 115000054..108000109 |
| BIG_LOTTO | ts3_regime_3bet | 50 | SHORT | 50 | 4 | 0.080000 | 50 | 0 | 0 | 1..1 | 115000053..115000004 |
| BIG_LOTTO | ts3_regime_3bet | 300 | MID | 300 | 10 | 0.033333 | 300 | 0 | 0 | 1..1 | 115000053..112000106 |
| BIG_LOTTO | ts3_regime_3bet | 750 | LONG | 750 | 22 | 0.029333 | 750 | 0 | 0 | 1..1 | 115000053..108000108 |
| POWER_LOTTO | cold_complement_2bet | 50 | SHORT | 50 | 3 | 0.060000 | 50 | 0 | 0 | 1..1 | 115000040..114000095 |
| POWER_LOTTO | cold_complement_2bet | 300 | MID | 300 | 36 | 0.120000 | 300 | 0 | 0 | 1..1 | 115000040..112000054 |
| POWER_LOTTO | cold_complement_2bet | 750 | LONG | 750 | 86 | 0.114667 | 750 | 0 | 0 | 1..1 | 115000040..108000021 |
| POWER_LOTTO | fourier30_markov30_2bet | 50 | SHORT | 49 | 4 | 0.081633 | 49 | 1 | 1 | 1..1 | 115000041..114000096 |
| POWER_LOTTO | fourier30_markov30_2bet | 300 | MID | 299 | 35 | 0.117057 | 299 | 1 | 1 | 1..1 | 115000041..112000055 |
| POWER_LOTTO | fourier30_markov30_2bet | 750 | LONG | 749 | 84 | 0.112150 | 749 | 1 | 1 | 1..1 | 115000041..108000022 |
| POWER_LOTTO | fourier_rhythm_3bet | 50 | SHORT | 0 | 0 | — | 0 | 150 | 150 | — | 115000041..114000096 |
| POWER_LOTTO | fourier_rhythm_3bet | 300 | MID | 0 | 0 | — | 0 | 900 | 900 | — | 115000041..112000055 |
| POWER_LOTTO | fourier_rhythm_3bet | 750 | LONG | 0 | 0 | — | 0 | 2250 | 2250 | — | 115000041..108000022 |
| POWER_LOTTO | midfreq_fourier_2bet | 50 | SHORT | 50 | 5 | 0.100000 | 50 | 0 | 0 | 1..1 | 115000040..114000095 |
| POWER_LOTTO | midfreq_fourier_2bet | 300 | MID | 300 | 30 | 0.100000 | 300 | 0 | 0 | 1..1 | 115000040..112000054 |
| POWER_LOTTO | midfreq_fourier_2bet | 750 | LONG | 750 | 84 | 0.112000 | 750 | 0 | 0 | 1..1 | 115000040..108000021 |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 50 | SHORT | 50 | 7 | 0.140000 | 50 | 100 | 100 | 1..1 | 115000040..114000095 |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 300 | MID | 300 | 34 | 0.113333 | 300 | 600 | 600 | 1..1 | 115000040..112000054 |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 750 | LONG | 750 | 101 | 0.134667 | 750 | 1500 | 1500 | 1..1 | 115000040..108000021 |
| POWER_LOTTO | power_fourier_rhythm_2bet | 50 | SHORT | 0 | 0 | — | 0 | 100 | 100 | — | 115000041..114000096 |
| POWER_LOTTO | power_fourier_rhythm_2bet | 300 | MID | 0 | 0 | — | 0 | 600 | 600 | — | 115000041..112000055 |
| POWER_LOTTO | power_fourier_rhythm_2bet | 750 | LONG | 0 | 0 | — | 0 | 1500 | 1500 | — | 115000041..108000022 |
| POWER_LOTTO | power_orthogonal_5bet | 50 | SHORT | 0 | 0 | — | 0 | 250 | 250 | — | 115000040..114000095 |
| POWER_LOTTO | power_orthogonal_5bet | 300 | MID | 0 | 0 | — | 0 | 1500 | 1500 | — | 115000040..112000054 |
| POWER_LOTTO | power_orthogonal_5bet | 750 | LONG | 0 | 0 | — | 0 | 3750 | 3750 | — | 115000040..108000021 |
| POWER_LOTTO | power_precision_3bet | 50 | SHORT | 0 | 0 | — | 0 | 150 | 150 | — | 115000040..114000095 |
| POWER_LOTTO | power_precision_3bet | 300 | MID | 0 | 0 | — | 0 | 900 | 900 | — | 115000040..112000054 |
| POWER_LOTTO | power_precision_3bet | 750 | LONG | 0 | 0 | — | 0 | 2250 | 2250 | — | 115000040..108000021 |
| POWER_LOTTO | pp3_freqort_4bet | 50 | SHORT | 50 | 6 | 0.120000 | 50 | 150 | 150 | 1..1 | 115000040..114000095 |
| POWER_LOTTO | pp3_freqort_4bet | 300 | MID | 300 | 28 | 0.093333 | 300 | 900 | 900 | 1..1 | 115000040..112000054 |
| POWER_LOTTO | pp3_freqort_4bet | 750 | LONG | 750 | 95 | 0.126667 | 750 | 2250 | 2250 | 1..1 | 115000040..108000021 |
| POWER_LOTTO | zonal_entropy_2bet | 50 | SHORT | 50 | 6 | 0.120000 | 50 | 0 | 0 | 1..1 | 115000040..114000095 |
| POWER_LOTTO | zonal_entropy_2bet | 300 | MID | 300 | 35 | 0.116667 | 300 | 0 | 0 | 1..1 | 115000040..112000054 |
| POWER_LOTTO | zonal_entropy_2bet | 750 | LONG | 750 | 80 | 0.106667 | 750 | 0 | 0 | 1..1 | 115000040..108000021 |

