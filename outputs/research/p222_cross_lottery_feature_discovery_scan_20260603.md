# P222 — Cross-Lottery Feature Discovery Read-Only Scan

**Date:** 2026-06-03  
**Task:** `P222_CROSS_LOTTERY_FEATURE_DISCOVERY_READ_ONLY_SCAN`  
**Status:** COMPLETE / READ-ONLY  
**Classification:** `P222_CANDIDATES_FOUND_NEED_MORE_OOS`  
**Authorized by:** User explicit task prompt 2026-06-03  

This report uses the frozen P221F protocol only. It does not write the DB, mutate the registry, change production state, or promote any strategy. Historical replay evidence only, not betting advice.

## Phase 0 Verification

| Check | Result |
|---|---|
| repo root | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` |
| branch | `main` |
| git dir | `.git` |
| HEAD | `9a3abf3213ceb710b58355009741f38c00db4d83` |
| origin/main | `9a3abf3213ceb710b58355009741f38c00db4d83` |
| staged files | `0` |
| replay rows | `94924` |
| BIG_LOTTO rows | `24140` |
| DAILY_539 rows | `34680` |
| POWER_LOTTO rows | `36104` |
| bet_index nulls | `0` |
| duplicate replay keys | `0` |
| PRAGMA integrity_check | `ok` |
| drift guard | `Status: PASS` |
| P221F artifacts tracked | `outputs/research/p221_cross_lottery_feature_discovery_protocol_20260603.md, outputs/research/p221_cross_lottery_feature_discovery_protocol_20260603.json` |

## Universe Inventory

- Replay lottery types: `BIG_LOTTO, DAILY_539, POWER_LOTTO`
- Draw-side lottery types: `38_LOTTO, 39_LOTTO, 3_STAR, 49_LOTTO, 4_STAR, BIG_LOTTO, BIG_LOTTO_BONUS, DAILY_539, DOUBLE_WIN, LOTTO_6_38, POWER_LOTTO`
- Registry strategies: `18` total, lifecycle counts `{"ONLINE": 8, "REJECTED": 4, "OBSERVATION": 1, "RETIRED": 5}`
- Replay strategy_ids: `35` total
- Replay lifecycle labels: `LIFECYCLE_UNRESOLVED, ONLINE, RETIRED`
- Bet indexes observed: `1, 2, 3, 4, 5`
- Zero-row registry strategies: `biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet, power_shlc_midfreq, p1_deviation_2bet_539, h6_gate_mk20_ew85`
- Replay strategy_ids not in registry: `539_3bet_orthogonal, acb_single_539, bet2_fourier_expansion_biglotto, biglotto_echo_aware_3bet, biglotto_ts3_markov_4bet_w30, cold_complement_2bet, cold_complement_biglotto, coldpool15_biglotto, daily539_f4cold_3bet, daily539_f4cold_5bet, fourier30_markov30_2bet, fourier30_markov30_biglotto, markov_1bet_539, markov_2bet_biglotto, markov_single_biglotto, midfreq_fourier_mk_3bet, p0b_539_3bet_f_cold_fmid, p0c_539_3bet_f_cold_x2, power_fourier_rhythm_2bet, pp3_freqort_4bet, zonal_entropy_2bet, zone_gap_3bet_539`

### Replay Strategy Coverage

| strategy_id | lifecycle | lottery_type | rows | distinct draws | bet indexes |
|---|---|---|---:|---:|---|
| bet2_fourier_expansion_biglotto | LIFECYCLE_UNRESOLVED | BIG_LOTTO | 1500 | 1500 | 1 |
| biglotto_deviation_2bet | ONLINE | BIG_LOTTO | 1570 | 1550 | 1,2 |
| biglotto_echo_aware_3bet | LIFECYCLE_UNRESOLVED | BIG_LOTTO | 4500 | 1500 | 1,2,3 |
| biglotto_triple_strike | ONLINE | BIG_LOTTO | 1570 | 1550 | 1,2 |
| biglotto_ts3_markov_4bet_w30 | LIFECYCLE_UNRESOLVED | BIG_LOTTO | 6000 | 1500 | 1,2,3,4 |
| cold_complement_biglotto | LIFECYCLE_UNRESOLVED | BIG_LOTTO | 1500 | 1500 | 1 |
| coldpool15_biglotto | LIFECYCLE_UNRESOLVED | BIG_LOTTO | 1500 | 1500 | 1 |
| fourier30_markov30_biglotto | LIFECYCLE_UNRESOLVED | BIG_LOTTO | 1500 | 1500 | 1 |
| markov_2bet_biglotto | LIFECYCLE_UNRESOLVED | BIG_LOTTO | 1500 | 1500 | 1 |
| markov_single_biglotto | LIFECYCLE_UNRESOLVED | BIG_LOTTO | 1500 | 1500 | 1 |
| ts3_regime_3bet | ONLINE | BIG_LOTTO | 1500 | 1500 | 1 |
| 539_3bet_orthogonal | LIFECYCLE_UNRESOLVED | DAILY_539 | 1500 | 1500 | 1 |
| acb_1bet | RETIRED | DAILY_539 | 1500 | 1500 | 1 |
| acb_markov_midfreq | RETIRED | DAILY_539 | 1500 | 1500 | 1 |
| acb_markov_midfreq_3bet | RETIRED | DAILY_539 | 4500 | 1500 | 1,2,3 |
| acb_single_539 | LIFECYCLE_UNRESOLVED | DAILY_539 | 1500 | 1500 | 1 |
| daily539_f4cold | ONLINE | DAILY_539 | 1590 | 1550 | 1,2,3 |
| daily539_f4cold_3bet | LIFECYCLE_UNRESOLVED | DAILY_539 | 4500 | 1500 | 1,2,3 |
| daily539_f4cold_5bet | LIFECYCLE_UNRESOLVED | DAILY_539 | 7500 | 1500 | 1,2,3,4,5 |
| daily539_markov_cold | ONLINE | DAILY_539 | 1590 | 1550 | 1,2,3 |
| markov_1bet_539 | LIFECYCLE_UNRESOLVED | DAILY_539 | 1500 | 1500 | 1 |
| midfreq_acb_2bet | RETIRED | DAILY_539 | 1500 | 1500 | 1 |
| midfreq_fourier_2bet | RETIRED | DAILY_539 | 3000 | 2543 | 1 |
| p0b_539_3bet_f_cold_fmid | LIFECYCLE_UNRESOLVED | DAILY_539 | 1500 | 1500 | 1 |
| p0c_539_3bet_f_cold_x2 | LIFECYCLE_UNRESOLVED | DAILY_539 | 1500 | 1500 | 1 |
| zone_gap_3bet_539 | LIFECYCLE_UNRESOLVED | DAILY_539 | 1500 | 1500 | 1 |
| cold_complement_2bet | LIFECYCLE_UNRESOLVED | POWER_LOTTO | 1500 | 1500 | 1 |
| fourier30_markov30_2bet | LIFECYCLE_UNRESOLVED | POWER_LOTTO | 1501 | 1501 | 1 |
| fourier_rhythm_3bet | ONLINE | POWER_LOTTO | 4503 | 1501 | 1,2,3 |
| midfreq_fourier_mk_3bet | LIFECYCLE_UNRESOLVED | POWER_LOTTO | 4500 | 1500 | 1,2,3 |
| power_fourier_rhythm_2bet | LIFECYCLE_UNRESOLVED | POWER_LOTTO | 3000 | 1500 | 1,2 |
| power_orthogonal_5bet | ONLINE | POWER_LOTTO | 7550 | 1550 | 1,2,3,4,5 |
| power_precision_3bet | ONLINE | POWER_LOTTO | 4550 | 1550 | 1,2,3 |
| pp3_freqort_4bet | LIFECYCLE_UNRESOLVED | POWER_LOTTO | 6000 | 1500 | 1,2,3,4 |
| zonal_entropy_2bet | LIFECYCLE_UNRESOLVED | POWER_LOTTO | 1500 | 1500 | 1 |

## Window Inventory

- Short: `100`, `125`, `150`
- Mid: `500`, `750`, `1000`
- All-history: baseline / reference only

## Feature Inventory

### Frequency / Recency
- hot number frequency
- cold number frequency
- frequency delta short vs mid
- frequency delta mid vs all-history
- EWMA frequency
- overdue / gap length
- last-seen distance

### Distribution / Structure
- odd/even balance
- high/low balance
- sum range
- span
- consecutive count
- repeated last digit
- modulo bucket
- prime count
- number-zone coverage

### Co-occurrence
- pair frequency
- triple frequency
- number cluster stability
- co-hit patterns by strategy

### Strategy Behavior
- strategy_id
- lifecycle
- bet_index
- strategy family
- prediction concentration
- prediction entropy
- strategy diversity
- consensus between strategies

### Time Stability
- draw era
- rolling-window stability
- OOS block stability
- monthly drift if dates exist
- yearly drift if dates exist
- cross-year validation if enough data exists

### Special-Zone
- POWER_LOTTO second-zone remains display-only
- special-zone metrics are reported separately
- special-zone metrics must not affect scoring
- special-zone metrics must not affect recommendation promotion

## Metrics by Labeled Unit

### Row-Level Summary by Lottery Type

| lottery_type | n_rows | mean hit_count | 95% CI | baseline | p-value | M1+ | M2+ | M3+ | exact |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| BIG_LOTTO | 24140 | 0.7347 | [0.7251, 0.7443] | 0.7347 | 0.9967 | 0.5655 | 0.1475 | 0.0202 | 0.0000 |
| DAILY_539 | 34680 | 0.6571 | [0.6495, 0.6647] | 0.6410 | 3.377e-05 | 0.5208 | 0.1249 | 0.0112 | 0.0000 |
| POWER_LOTTO | 36104 | 0.9674 | [0.9588, 0.9760] | 0.9474 | 5.073e-06 | 0.6822 | 0.2394 | 0.0435 | 0.0000 |

### Special-Zone Summary

| lottery_type | n_rows | mean special_hit | 95% CI | baseline | p-value |
|---|---:|---:|---|---:|---:|
| POWER_LOTTO | 9000 | 0.1181 | [0.1114, 0.1248] | 0.1250 | 0.04287 |

### Strategy-Level Corrected Results

Bonferroni threshold: `0.001429`; BH-FDR used across `35` strategy hypotheses.

| strategy_id | lifecycle | lottery_type | n_rows | mean hit_count | baseline | p-value | Bonf q | BH q | tail OOS |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| midfreq_fourier_2bet | RETIRED | DAILY_539 | 3000 | 0.8210 | 0.6410 | 5.188e-35 | 1.816e-33 | 1.816e-33 | 150:0.867/above, 300:0.957/above, 500:0.974/above |
| midfreq_fourier_mk_3bet | LIFECYCLE_UNRESOLVED | POWER_LOTTO | 4500 | 0.9896 | 0.9474 | 0.0008438 | 0.02953 | 0.01477 | 150:0.993/above, 300:0.967/above, 500:0.970/above |
| fourier_rhythm_3bet | ONLINE | POWER_LOTTO | 4503 | 0.9749 | 0.9474 | 0.02745 | 0.9606 | 0.2588 | 150:0.900/below, 300:0.917/below, 500:0.940/below |
| pp3_freqort_4bet | LIFECYCLE_UNRESOLVED | POWER_LOTTO | 6000 | 0.9710 | 0.9474 | 0.02958 | 1 | 0.2588 | 150:0.933/below, 300:0.963/above, 500:0.906/below |
| daily539_f4cold | ONLINE | DAILY_539 | 1590 | 0.6786 | 0.6410 | 0.03904 | 1 | 0.2722 | 150:0.653/above, 300:0.673/above, 500:0.664/above |
| p0b_539_3bet_f_cold_fmid | LIFECYCLE_UNRESOLVED | DAILY_539 | 1500 | 0.6773 | 0.6410 | 0.05444 | 1 | 0.2722 | 150:0.653/above, 300:0.690/above, 500:0.674/above |
| p0c_539_3bet_f_cold_x2 | LIFECYCLE_UNRESOLVED | DAILY_539 | 1500 | 0.6773 | 0.6410 | 0.05444 | 1 | 0.2722 | 150:0.653/above, 300:0.690/above, 500:0.674/above |
| acb_markov_midfreq_3bet | RETIRED | DAILY_539 | 4500 | 0.6600 | 0.6410 | 0.07753 | 1 | 0.2811 | 150:0.647/above, 300:0.643/above, 500:0.678/above |
| 539_3bet_orthogonal | LIFECYCLE_UNRESOLVED | DAILY_539 | 1500 | 0.6720 | 0.6410 | 0.09035 | 1 | 0.2811 | 150:0.673/above, 300:0.627/below, 500:0.636/below |
| acb_1bet | RETIRED | DAILY_539 | 1500 | 0.6720 | 0.6410 | 0.09035 | 1 | 0.2811 | 150:0.673/above, 300:0.627/below, 500:0.636/below |
| acb_single_539 | LIFECYCLE_UNRESOLVED | DAILY_539 | 1500 | 0.6720 | 0.6410 | 0.09035 | 1 | 0.2811 | 150:0.673/above, 300:0.627/below, 500:0.636/below |
| power_orthogonal_5bet | ONLINE | POWER_LOTTO | 7550 | 0.9633 | 0.9474 | 0.09637 | 1 | 0.2811 | 150:0.933/below, 300:0.943/below, 500:0.904/below |
| midfreq_acb_2bet | RETIRED | DAILY_539 | 1500 | 0.6693 | 0.6410 | 0.1347 | 1 | 0.3628 | 150:0.760/above, 300:0.757/above, 500:0.710/above |
| daily539_f4cold_3bet | LIFECYCLE_UNRESOLVED | DAILY_539 | 4500 | 0.6558 | 0.6410 | 0.1727 | 1 | 0.4317 | 150:0.600/below, 300:0.637/below, 500:0.630/below |
| biglotto_deviation_2bet | ONLINE | BIG_LOTTO | 1570 | 0.7573 | 0.7347 | 0.2421 | 1 | 0.5649 | 150:0.873/above, 300:0.827/above, 500:0.828/above |

### Bet-Index-Level Corrected Results

Bonferroni threshold: `0.003571`; BH-FDR used across `14` bet-index hypotheses.

| lottery_type | bet_index | n_rows | mean hit_count | baseline | p-value | Bonf q | BH q | special | tail OOS |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| POWER_LOTTO | 1 | 15102 | 0.9825 | 0.9474 | 2.594e-07 | 3.631e-06 | 3.631e-06 | 0.1181 (p=0.04287) | 150:0.867/below, 300:0.923/below, 500:0.950/above |
| DAILY_539 | 1 | 22600 | 0.6622 | 0.6410 | 9.783e-06 | 0.000137 | 6.848e-05 | n/a | 150:0.693/above, 300:0.580/below, 500:0.662/above |
| POWER_LOTTO | 2 | 9001 | 0.9788 | 0.9474 | 0.0004276 | 0.005987 | 0.001996 | n/a | 150:0.913/below, 300:0.940/below, 500:0.942/below |
| BIG_LOTTO | 2 | 3040 | 0.7638 | 0.7347 | 0.03958 | 0.5542 | 0.1385 | n/a | 150:0.673/below, 300:0.700/below, 500:0.734/below |
| DAILY_539 | 4 | 1500 | 0.6060 | 0.6410 | 0.05443 | 0.7621 | 0.1524 | n/a | 150:0.713/above, 300:0.687/above, 500:0.648/above |
| DAILY_539 | 3 | 4540 | 0.6601 | 0.6410 | 0.07531 | 1 | 0.1757 | n/a | 150:0.667/above, 300:0.680/above, 500:0.682/above |
| DAILY_539 | 5 | 1500 | 0.6727 | 0.6410 | 0.0979 | 1 | 0.1958 | n/a | 150:0.713/above, 300:0.620/below, 500:0.636/below |
| BIG_LOTTO | 4 | 1500 | 0.7160 | 0.7347 | 0.3409 | 1 | 0.5966 | n/a | 150:0.793/above, 300:0.720/below, 500:0.744/above |
| POWER_LOTTO | 3 | 7501 | 0.9400 | 0.9474 | 0.4372 | 1 | 0.68 | n/a | 150:1.053/above, 300:1.013/above, 500:0.948/above |
| BIG_LOTTO | 1 | 16600 | 0.7309 | 0.7347 | 0.5191 | 1 | 0.7268 | n/a | 150:0.720/below, 300:0.733/below, 500:0.806/above |
| POWER_LOTTO | 4 | 3000 | 0.9393 | 0.9474 | 0.5981 | 1 | 0.7612 | n/a | 150:1.133/above, 300:1.033/above, 500:1.000/above |
| POWER_LOTTO | 5 | 1500 | 0.9407 | 0.9474 | 0.7488 | 1 | 0.8736 | n/a | 150:0.933/below, 300:0.903/below, 500:0.920/below |
| BIG_LOTTO | 3 | 3000 | 0.7357 | 0.7347 | 0.9445 | 1 | 0.9468 | n/a | 150:0.707/below, 300:0.763/above, 500:0.754/above |
| DAILY_539 | 2 | 4540 | 0.6403 | 0.6410 | 0.9468 | 1 | 0.9468 | n/a | 150:0.513/below, 300:0.600/below, 500:0.578/below |

### Baseline Comparisons

#### BIG_LOTTO

| baseline | n_eval_draws | mean hit_count | 95% CI | p-value | M1+ | M2+ | M3+ | exact |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| all_history | 1552 | 0.7416 | [0.7046, 0.7786] | 0.7134 | 0.5805 | 0.1430 | 0.0168 | 0.0000 |
| w100 | 1552 | 0.7481 | [0.7109, 0.7853] | 0.4813 | 0.5786 | 0.1540 | 0.0148 | 0.0000 |
| w125 | 1552 | 0.7539 | [0.7167, 0.7910] | 0.312 | 0.5844 | 0.1527 | 0.0168 | 0.0000 |
| w150 | 1552 | 0.7468 | [0.7100, 0.7835] | 0.5194 | 0.5870 | 0.1411 | 0.0187 | 0.0000 |
| w500 | 1552 | 0.7236 | [0.6863, 0.7609] | 0.5593 | 0.5612 | 0.1450 | 0.0161 | 0.0000 |
| w750 | 1552 | 0.7223 | [0.6850, 0.7596] | 0.5149 | 0.5638 | 0.1372 | 0.0200 | 0.0000 |
| w1000 | 1552 | 0.7345 | [0.6978, 0.7712] | 0.9933 | 0.5786 | 0.1392 | 0.0148 | 0.0000 |
| consensus | 1552 | 0.7545 | [0.7165, 0.7926] | 0.3073 | 0.5780 | 0.1540 | 0.0219 | 0.0000 |

#### DAILY_539

| baseline | n_eval_draws | mean hit_count | 95% CI | p-value | M1+ | M2+ | M3+ | exact |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| all_history | 1550 | 0.6252 | [0.5904, 0.6600] | 0.3715 | 0.5097 | 0.1039 | 0.0116 | 0.0000 |
| w100 | 1550 | 0.6097 | [0.5756, 0.6438] | 0.0715 | 0.5013 | 0.1013 | 0.0071 | 0.0000 |
| w125 | 1550 | 0.6135 | [0.5796, 0.6475] | 0.1128 | 0.5058 | 0.1013 | 0.0065 | 0.0000 |
| w150 | 1550 | 0.6290 | [0.5937, 0.6644] | 0.5061 | 0.5077 | 0.1071 | 0.0142 | 0.0000 |
| w500 | 1550 | 0.6471 | [0.6119, 0.6823] | 0.7352 | 0.5219 | 0.1155 | 0.0090 | 0.0000 |
| w750 | 1550 | 0.6355 | [0.6006, 0.6704] | 0.7558 | 0.5155 | 0.1097 | 0.0103 | 0.0000 |
| w1000 | 1550 | 0.6226 | [0.5879, 0.6573] | 0.2979 | 0.5071 | 0.1052 | 0.0103 | 0.0000 |
| consensus | 1550 | 0.6800 | [0.6437, 0.7163] | 0.03548 | 0.5387 | 0.1252 | 0.0161 | 0.0000 |

#### POWER_LOTTO

| baseline | n_eval_draws | mean hit_count | 95% CI | p-value | M1+ | M2+ | M3+ | exact |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| all_history | 1551 | 0.9465 | [0.9046, 0.9884] | 0.9671 | 0.6673 | 0.2334 | 0.0419 | 0.0000 |
| w100 | 1551 | 0.9426 | [0.9019, 0.9834] | 0.8193 | 0.6783 | 0.2244 | 0.0368 | 0.0000 |
| w125 | 1551 | 0.9342 | [0.8935, 0.9750] | 0.5275 | 0.6712 | 0.2257 | 0.0342 | 0.0000 |
| w150 | 1551 | 0.9226 | [0.8816, 0.9636] | 0.237 | 0.6628 | 0.2192 | 0.0374 | 0.0000 |
| w500 | 1551 | 0.9446 | [0.9022, 0.9869] | 0.8962 | 0.6570 | 0.2437 | 0.0400 | 0.0000 |
| w750 | 1551 | 0.9355 | [0.8922, 0.9789] | 0.5925 | 0.6409 | 0.2424 | 0.0496 | 0.0000 |
| w1000 | 1551 | 0.9381 | [0.8951, 0.9811] | 0.6729 | 0.6473 | 0.2411 | 0.0464 | 0.0000 |
| consensus | 1551 | 1.0006 | [0.9579, 1.0434] | 0.01461 | 0.6847 | 0.2631 | 0.0522 | 0.0000 |

### Draw-Side Structural Summary

| lottery_type | draws | draw size | max number | odd mean | low mean | prime mean | span mean | consec mean | repeated last-digit mean | zone coverage mean | sum mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38_LOTTO | 1774 | 6 | 38 | 2.968 | 3.007 | 1.884 | 27.914 | 0.769 | 0.191 | 3.379 | 116.639 |
| 39_LOTTO | 4890 | 5 | 39 | 2.563 | 2.445 | 1.543 | 26.685 | 0.506 | 0.196 | 3.138 | 99.797 |
| 3_STAR | 4179 | 3 | 9 | 1.494 | 1.496 | 1.194 | 5.556 | 0.574 | 0.000 | 1.000 | 13.509 |
| 49_LOTTO | 2130 | 6 | 49 | 3.092 | 2.932 | 1.863 | 35.717 | 0.626 | 0.248 | 3.768 | 150.073 |
| 4_STAR | 2922 | 4 | 9 | 2.003 | 2.006 | 1.595 | 6.590 | 1.203 | 0.000 | 1.000 | 17.958 |
| BIG_LOTTO | 22237 | 6 | 49 | 3.073 | 3.106 | 1.933 | 35.393 | 0.592 | 0.224 | 3.760 | 145.989 |
| BIG_LOTTO_BONUS | 11941 | 6 | 49 | 3.166 | 3.066 | 1.770 | 35.290 | 0.531 | 0.269 | 3.863 | 147.722 |
| DAILY_539 | 5876 | 5 | 39 | 2.570 | 2.441 | 1.547 | 26.738 | 0.509 | 0.193 | 3.138 | 99.895 |
| DOUBLE_WIN | 1782 | 12 | 24 | 5.946 | 5.980 | 4.474 | 21.177 | 5.476 | 0.002 | 2.959 | 150.221 |
| LOTTO_6_38 | 111 | 6 | 38 | 2.946 | 2.937 | 1.919 | 28.054 | 0.847 | 0.180 | 3.441 | 117.559 |
| POWER_LOTTO | 1915 | 6 | 38 | 2.988 | 3.014 | 1.891 | 27.926 | 0.758 | 0.190 | 3.380 | 116.719 |

### Candidate Signals Requiring More OOS

| kind | identifier | lottery_type | lifecycle / bet | overall mean | baseline | p-value | Bonf q | BH q | tail check |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| strategy | midfreq_fourier_2bet | DAILY_539 | RETIRED | 0.8210 | 0.6410 | 5.188e-35 | 1.816e-33 | 1.816e-33 | 150:0.867/above, 300:0.957/above, 500:0.974/above |
| strategy | midfreq_fourier_mk_3bet | POWER_LOTTO | LIFECYCLE_UNRESOLVED | 0.9896 | 0.9474 | 0.0008438 | 0.02953 | 0.01477 | 150:0.993/above, 300:0.967/above, 500:0.970/above |
| bet-index | POWER_LOTTO bet1 | POWER_LOTTO | 1 | 0.9825 | 0.9474 | 2.594e-07 | 3.631e-06 | 3.631e-06 | tail: 150:0.867/below, 300:0.923/below, 500:0.950/above; special: 150:0.093/below, 300:0.110/below, 500:0.092/below |
| bet-index | DAILY_539 bet1 | DAILY_539 | 1 | 0.6622 | 0.6410 | 9.783e-06 | 0.000137 | 6.848e-05 | tail: 150:0.693/above, 300:0.580/below, 500:0.662/above; special: n/a |
| bet-index | POWER_LOTTO bet2 | POWER_LOTTO | 2 | 0.9788 | 0.9474 | 0.0004276 | 0.005987 | 0.001996 | tail: 150:0.913/below, 300:0.940/below, 500:0.942/below; special: n/a |

## Findings

- Corrected in-sample candidates exist at both the strategy and bet-index levels, especially in DAILY_539 and POWER_LOTTO.
- The strongest strategy-level candidate is `midfreq_fourier_2bet`, but its tail OOS windows fall below baseline, so it is not cross-year confirmed.
- `midfreq_fourier_mk_3bet` remains only a weak observation: corrected in-sample positive, tail OOS neutral.
- POWER_LOTTO and DAILY_539 row-level means are slightly above random baseline, but tail windows and consensus checks do not confirm a stable edge.
- BIG_LOTTO is effectively baseline-equivalent at the row level.
- POWER_LOTTO special-zone remains display-only; special-hit evidence is not strong enough for scoring promotion.
- `3_STAR` and `4_STAR` are present in the draw table, but there are no replay rows for them in the strategy universe, so replay-based discovery is insufficient for those types.

## Risks

- Historical replay evidence can overstate significance when a candidate is not stable under tail OOS validation.
- Lifecycle-unresolved replay strategies must remain visible because they can carry the strongest in-sample signals.
- Cross-year stability is the decisive gate here; the strongest in-sample candidate does not pass it.

## Recommendation

- Treat the current result set as candidate-only, not deployable.
- If the project wants to continue, the next step should be a narrower OOS-focused validation of the strategy and bet-index candidates, especially the POWER_LOTTO and DAILY_539 families.
- Do not promote any strategy or special-zone behavior from this scan.

## Required Completion Check

1. 是否真的完成: YES — P222 scan completed with read-only analysis and output artifacts.
2. 測試結果: PASS for Phase 0 / read-only guard checks; full test suite NOT RUN.
3. 仍卡住的唯一問題: Candidates exist but none are cross-year confirmed; more OOS is needed before any promotion.
4. 修改檔案清單:
   - `outputs/research/p222_cross_lottery_feature_discovery_scan_20260603.json`
   - `outputs/research/p222_cross_lottery_feature_discovery_scan_20260603.md`
5. staged / commit / push 狀態: 0 / 0 / 0 (no staging, no commit, no push)
6. 是否允許進入下一輪: YES
7. Final Classification: `P222_CANDIDATES_FOUND_NEED_MORE_OOS`
