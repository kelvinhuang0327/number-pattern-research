# P275B — Unified Prize-Aware Success Matrix

- **Task:** `P275B_UNIFIED_PRIZE_AWARE_SUCCESS_MATRIX`
- **Schema:** `p275b_unified_prize_aware_success_matrix_v1`
- **Source commit:** `77994824d1c1e5e4d4db14f0c7d5cb64bf933ead`
- **Canonical digest:** `c1b99e57024f528e39e4beeca03cb22dd3278eb1d356aafbe48d8485695102f6`
- **Retrospective only:** True · **Prediction-success claim:** False · **Production DB opened:** False

> Retrospective re-presentation of committed P273A evidence. No betting recommendation. No future-success claim. No strategy-combination search.

## Capability & Missingness Overview

- Supported lotteries: BIG_LOTTO, DAILY_539, POWER_LOTTO
- Frozen strategy cells: 36 · matrix rows: 108 (= cells × 3 primary windows)
- Primary windows: SHORT=50 / MID=300 / LONG=750 (1500 & all-history are reference-only, excluded)
- Evaluable windows: 86 / 108
- Bonferroni confirmatory family m = 108
- Rows reproduced (CI + Bonferroni re-derived vs committed): 108/108 · evidence-status counts match committed P273A: True

### Lifecycle status distribution (states kept visible)

| Lifecycle status | Cells |
|---|---|
| ONLINE | 8 |
| REJECTED | 12 |
| RETIRED | 13 |
| UNREGISTERED_IN_CANONICAL_LIFECYCLE_REGISTRY | 3 |

### Evidence-status distribution (window decisions)

| Evidence status | Windows |
|---|---|
| PRIZE_AWARE_DESCRIPTIVE_ONLY | 17 |
| PRIZE_AWARE_EDGE_CORRECTION_SURVIVING | 4 |
| PRIZE_AWARE_INSUFFICIENT_SUPPORT | 22 |
| PRIZE_AWARE_NULL | 65 |

## Per-Lottery Findings

### BIG_LOTTO

- Endpoint `BIG_ANY_PRIZE_AWARE_WIN`: `hit_count >= 3 OR (hit_count = 2 AND special_hit = 1)` (min tier: 普獎 (2-match + special))
- Cells: 11 · rows: 33 · evaluable windows: 23/33

### DAILY_539

- Endpoint `D539_ANY_PRIZE_AWARE_WIN`: `hit_count >= 2` (min tier: 肆獎 (2-match))
- Cells: 15 · rows: 45 · evaluable windows: 45/45

### POWER_LOTTO

- Endpoint `POWER_ANY_PRIZE_AWARE_WIN`: `hit_count >= 3 OR (hit_count >= 1 AND special_hit = 1)` (min tier: 普獎 (1-match + second-zone))
- Cells: 10 · rows: 30 · evaluable windows: 18/30
- Second-zone excluded bet-rows (missing eligibility, never losses): 19803
- Cells with fully-excluded windows (no eligible second-zone bets): fourier_rhythm_3bet, power_fourier_rhythm_2bet, power_orthogonal_5bet, power_precision_3bet

## Per-Window Matrix Summary (correction-surviving edges)

| Lottery | Strategy | Window | Corrected p (Bonferroni m=108) |
|---|---|---|---|
| DAILY_539 | acb_markov_midfreq_3bet | MID | 0.029543 |
| DAILY_539 | daily539_f4cold_3bet | LONG | 0.016700 |
| DAILY_539 | daily539_f4cold_5bet | MID | 0.006287 |
| DAILY_539 | daily539_f4cold_5bet | LONG | 0.000000 |

### Research-only GO candidate groups (NOT deployment, NOT betting advice)

- DAILY_539 / `acb_markov_midfreq_3bet`
- DAILY_539 / `daily539_f4cold_3bet`
- DAILY_539 / `daily539_f4cold_5bet`

## Full Matrix (per strategy × window)

| Lottery | Strategy | Life | Win | Budget | Elig | Succ | Rate | Base | AbsLift | p | corr-p | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BIG_LOTTO | bet2_fourier_expansion_biglotto | REJECTED | SHORT | 1 | 50 | 4 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | REJECTED | MID | 1 | 300 | 10 | 0.0333 | 0.0310 | 0.0024 | 0.4507 | 1.0000 | NULL |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | REJECTED | LONG | 1 | 750 | 25 | 0.0333 | 0.0310 | 0.0024 | 0.3815 | 1.0000 | NULL |
| BIG_LOTTO | biglotto_deviation_2bet | ONLINE | SHORT | 1 | 50 | 2 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| BIG_LOTTO | biglotto_deviation_2bet | ONLINE | MID | 1 | 300 | 10 | 0.0333 | 0.0310 | 0.0024 | 0.4507 | 1.0000 | NULL |
| BIG_LOTTO | biglotto_deviation_2bet | ONLINE | LONG | 1 | 750 | 32 | 0.0427 | 0.0310 | 0.0117 | 0.0455 | 1.0000 | DESCRIPTIVE_ONLY |
| BIG_LOTTO | biglotto_echo_aware_3bet | RETIRED | SHORT | 3 | 50 | 4 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| BIG_LOTTO | biglotto_echo_aware_3bet | RETIRED | MID | 3 | 300 | 33 | 0.1100 | 0.0900 | 0.0200 | 0.1347 | 1.0000 | NULL |
| BIG_LOTTO | biglotto_echo_aware_3bet | RETIRED | LONG | 3 | 750 | 75 | 0.1000 | 0.0900 | 0.0100 | 0.1852 | 1.0000 | NULL |
| BIG_LOTTO | biglotto_triple_strike | ONLINE | SHORT | 1 | 50 | 4 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| BIG_LOTTO | biglotto_triple_strike | ONLINE | MID | 1 | 300 | 10 | 0.0333 | 0.0310 | 0.0024 | 0.4507 | 1.0000 | NULL |
| BIG_LOTTO | biglotto_triple_strike | ONLINE | LONG | 1 | 750 | 22 | 0.0293 | 0.0310 | -0.0016 | 0.6301 | 1.0000 | NULL |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | RETIRED | SHORT | 4 | 50 | 5 | 0.1000 | 0.1182 | -0.0182 | 0.7191 | 1.0000 | NULL |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | RETIRED | MID | 4 | 300 | 38 | 0.1267 | 0.1182 | 0.0085 | 0.3499 | 1.0000 | NULL |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | RETIRED | LONG | 4 | 750 | 99 | 0.1320 | 0.1182 | 0.0138 | 0.1328 | 1.0000 | NULL |
| BIG_LOTTO | cold_complement_biglotto | REJECTED | SHORT | 1 | 50 | 2 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| BIG_LOTTO | cold_complement_biglotto | REJECTED | MID | 1 | 300 | 10 | 0.0333 | 0.0310 | 0.0024 | 0.4507 | 1.0000 | NULL |
| BIG_LOTTO | cold_complement_biglotto | REJECTED | LONG | 1 | 750 | 21 | 0.0280 | 0.0310 | -0.0030 | 0.7087 | 1.0000 | NULL |
| BIG_LOTTO | coldpool15_biglotto | REJECTED | SHORT | 1 | 50 | 2 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| BIG_LOTTO | coldpool15_biglotto | REJECTED | MID | 1 | 300 | 10 | 0.0333 | 0.0310 | 0.0024 | 0.4507 | 1.0000 | NULL |
| BIG_LOTTO | coldpool15_biglotto | REJECTED | LONG | 1 | 750 | 21 | 0.0280 | 0.0310 | -0.0030 | 0.7087 | 1.0000 | NULL |
| BIG_LOTTO | fourier30_markov30_biglotto | REJECTED | SHORT | 1 | 50 | 1 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| BIG_LOTTO | fourier30_markov30_biglotto | REJECTED | MID | 1 | 300 | 6 | 0.0200 | 0.0310 | -0.0110 | 0.9041 | 1.0000 | NULL |
| BIG_LOTTO | fourier30_markov30_biglotto | REJECTED | LONG | 1 | 750 | 19 | 0.0253 | 0.0310 | -0.0056 | 0.8401 | 1.0000 | NULL |
| BIG_LOTTO | markov_2bet_biglotto | REJECTED | SHORT | 1 | 50 | 1 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| BIG_LOTTO | markov_2bet_biglotto | REJECTED | MID | 1 | 300 | 9 | 0.0300 | 0.0310 | -0.0010 | 0.5839 | 1.0000 | NULL |
| BIG_LOTTO | markov_2bet_biglotto | REJECTED | LONG | 1 | 750 | 18 | 0.0240 | 0.0310 | -0.0070 | 0.8894 | 1.0000 | NULL |
| BIG_LOTTO | markov_single_biglotto | REJECTED | SHORT | 1 | 50 | 1 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| BIG_LOTTO | markov_single_biglotto | REJECTED | MID | 1 | 300 | 9 | 0.0300 | 0.0310 | -0.0010 | 0.5839 | 1.0000 | NULL |
| BIG_LOTTO | markov_single_biglotto | REJECTED | LONG | 1 | 750 | 18 | 0.0240 | 0.0310 | -0.0070 | 0.8894 | 1.0000 | NULL |
| BIG_LOTTO | ts3_regime_3bet | ONLINE | SHORT | 1 | 50 | 4 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| BIG_LOTTO | ts3_regime_3bet | ONLINE | MID | 1 | 300 | 10 | 0.0333 | 0.0310 | 0.0024 | 0.4507 | 1.0000 | NULL |
| BIG_LOTTO | ts3_regime_3bet | ONLINE | LONG | 1 | 750 | 22 | 0.0293 | 0.0310 | -0.0016 | 0.6301 | 1.0000 | NULL |
| DAILY_539 | 539_3bet_orthogonal | REJECTED | SHORT | 1 | 50 | 8 | 0.1600 | 0.1140 | 0.0460 | 0.2050 | 1.0000 | NULL |
| DAILY_539 | 539_3bet_orthogonal | REJECTED | MID | 1 | 300 | 39 | 0.1300 | 0.1140 | 0.0160 | 0.2142 | 1.0000 | NULL |
| DAILY_539 | 539_3bet_orthogonal | REJECTED | LONG | 1 | 750 | 93 | 0.1240 | 0.1140 | 0.0100 | 0.2084 | 1.0000 | NULL |
| DAILY_539 | acb_1bet | RETIRED | SHORT | 1 | 50 | 8 | 0.1600 | 0.1140 | 0.0460 | 0.2050 | 1.0000 | NULL |
| DAILY_539 | acb_1bet | RETIRED | MID | 1 | 300 | 39 | 0.1300 | 0.1140 | 0.0160 | 0.2142 | 1.0000 | NULL |
| DAILY_539 | acb_1bet | RETIRED | LONG | 1 | 750 | 93 | 0.1240 | 0.1140 | 0.0100 | 0.2084 | 1.0000 | NULL |
| DAILY_539 | acb_markov_midfreq | RETIRED | SHORT | 1 | 50 | 0 | 0.0000 | 0.1140 | -0.1140 | 1.0000 | 1.0000 | NULL |
| DAILY_539 | acb_markov_midfreq | RETIRED | MID | 1 | 300 | 32 | 0.1067 | 0.1140 | -0.0073 | 0.6812 | 1.0000 | NULL |
| DAILY_539 | acb_markov_midfreq | RETIRED | LONG | 1 | 750 | 74 | 0.0987 | 0.1140 | -0.0153 | 0.9179 | 1.0000 | NULL |
| DAILY_539 | acb_markov_midfreq_3bet | RETIRED | SHORT | 3 | 50 | 18 | 0.3600 | 0.3044 | 0.0556 | 0.2388 | 1.0000 | NULL |
| DAILY_539 | acb_markov_midfreq_3bet | RETIRED | MID | 3 | 300 | 120 | 0.4000 | 0.3044 | 0.0956 | 0.0003 | 0.0295 | EDGE_CORRECTION_SURVIVING |
| DAILY_539 | acb_markov_midfreq_3bet | RETIRED | LONG | 3 | 750 | 268 | 0.3573 | 0.3044 | 0.0529 | 0.0011 | 0.1162 | DESCRIPTIVE_ONLY |
| DAILY_539 | acb_single_539 | REJECTED | SHORT | 1 | 50 | 8 | 0.1600 | 0.1140 | 0.0460 | 0.2050 | 1.0000 | NULL |
| DAILY_539 | acb_single_539 | REJECTED | MID | 1 | 300 | 39 | 0.1300 | 0.1140 | 0.0160 | 0.2142 | 1.0000 | NULL |
| DAILY_539 | acb_single_539 | REJECTED | LONG | 1 | 750 | 93 | 0.1240 | 0.1140 | 0.0100 | 0.2084 | 1.0000 | NULL |
| DAILY_539 | daily539_f4cold | ONLINE | SHORT | 1 | 50 | 11 | 0.2200 | 0.1140 | 0.1060 | 0.0232 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | daily539_f4cold | ONLINE | MID | 1 | 300 | 44 | 0.1467 | 0.1140 | 0.0327 | 0.0491 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | daily539_f4cold | ONLINE | LONG | 1 | 750 | 105 | 0.1400 | 0.1140 | 0.0260 | 0.0164 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | daily539_f4cold_3bet | RETIRED | SHORT | 3 | 50 | 23 | 0.4600 | 0.3044 | 0.1556 | 0.0147 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | daily539_f4cold_3bet | RETIRED | MID | 3 | 300 | 101 | 0.3367 | 0.3044 | 0.0322 | 0.1254 | 1.0000 | NULL |
| DAILY_539 | daily539_f4cold_3bet | RETIRED | LONG | 3 | 750 | 275 | 0.3667 | 0.3044 | 0.0622 | 0.0002 | 0.0167 | EDGE_CORRECTION_SURVIVING |
| DAILY_539 | daily539_f4cold_5bet | RETIRED | SHORT | 5 | 50 | 35 | 0.7000 | 0.4539 | 0.2461 | 0.0004 | 0.0412 | DESCRIPTIVE_ONLY |
| DAILY_539 | daily539_f4cold_5bet | RETIRED | MID | 5 | 300 | 170 | 0.5667 | 0.4539 | 0.1127 | 0.0001 | 0.0063 | EDGE_CORRECTION_SURVIVING |
| DAILY_539 | daily539_f4cold_5bet | RETIRED | LONG | 5 | 750 | 425 | 0.5667 | 0.4539 | 0.1127 | 0.0000 | 0.0000 | EDGE_CORRECTION_SURVIVING |
| DAILY_539 | daily539_markov_cold | ONLINE | SHORT | 1 | 50 | 4 | 0.0800 | 0.1140 | -0.0340 | 0.8364 | 1.0000 | NULL |
| DAILY_539 | daily539_markov_cold | ONLINE | MID | 1 | 300 | 38 | 0.1267 | 0.1140 | 0.0127 | 0.2690 | 1.0000 | NULL |
| DAILY_539 | daily539_markov_cold | ONLINE | LONG | 1 | 750 | 81 | 0.1080 | 0.1140 | -0.0060 | 0.7130 | 1.0000 | NULL |
| DAILY_539 | markov_1bet_539 | REJECTED | SHORT | 1 | 50 | 4 | 0.0800 | 0.1140 | -0.0340 | 0.8364 | 1.0000 | NULL |
| DAILY_539 | markov_1bet_539 | REJECTED | MID | 1 | 300 | 38 | 0.1267 | 0.1140 | 0.0127 | 0.2690 | 1.0000 | NULL |
| DAILY_539 | markov_1bet_539 | REJECTED | LONG | 1 | 750 | 81 | 0.1080 | 0.1140 | -0.0060 | 0.7130 | 1.0000 | NULL |
| DAILY_539 | midfreq_acb_2bet | RETIRED | SHORT | 1 | 50 | 6 | 0.1200 | 0.1140 | 0.0060 | 0.5119 | 1.0000 | NULL |
| DAILY_539 | midfreq_acb_2bet | RETIRED | MID | 1 | 300 | 48 | 0.1600 | 0.1140 | 0.0460 | 0.0101 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | midfreq_acb_2bet | RETIRED | LONG | 1 | 750 | 101 | 0.1347 | 0.1140 | 0.0207 | 0.0446 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | midfreq_fourier_2bet | RETIRED | SHORT | 1 | 50 | 6 | 0.1200 | 0.1140 | 0.0060 | 0.5119 | 1.0000 | NULL |
| DAILY_539 | midfreq_fourier_2bet | RETIRED | MID | 1 | 300 | 48 | 0.1600 | 0.1140 | 0.0460 | 0.0101 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | midfreq_fourier_2bet | RETIRED | LONG | 1 | 750 | 101 | 0.1347 | 0.1140 | 0.0207 | 0.0446 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | REJECTED | SHORT | 1 | 50 | 11 | 0.2200 | 0.1140 | 0.1060 | 0.0232 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | REJECTED | MID | 1 | 300 | 45 | 0.1500 | 0.1140 | 0.0360 | 0.0342 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | REJECTED | LONG | 1 | 750 | 106 | 0.1413 | 0.1140 | 0.0274 | 0.0124 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | REJECTED | SHORT | 1 | 50 | 11 | 0.2200 | 0.1140 | 0.1060 | 0.0232 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | REJECTED | MID | 1 | 300 | 45 | 0.1500 | 0.1140 | 0.0360 | 0.0342 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | REJECTED | LONG | 1 | 750 | 106 | 0.1413 | 0.1140 | 0.0274 | 0.0124 | 1.0000 | DESCRIPTIVE_ONLY |
| DAILY_539 | zone_gap_3bet_539 | REJECTED | SHORT | 1 | 50 | 8 | 0.1600 | 0.1140 | 0.0460 | 0.2050 | 1.0000 | NULL |
| DAILY_539 | zone_gap_3bet_539 | REJECTED | MID | 1 | 300 | 31 | 0.1033 | 0.1140 | -0.0106 | 0.7447 | 1.0000 | NULL |
| DAILY_539 | zone_gap_3bet_539 | REJECTED | LONG | 1 | 750 | 76 | 0.1013 | 0.1140 | -0.0126 | 0.8754 | 1.0000 | NULL |
| POWER_LOTTO | cold_complement_2bet | RETIRED | SHORT | 1 | 50 | 3 | 0.0600 | 0.1178 | -0.0578 | 0.9440 | 1.0000 | NULL |
| POWER_LOTTO | cold_complement_2bet | RETIRED | MID | 1 | 300 | 36 | 0.1200 | 0.1178 | 0.0022 | 0.4801 | 1.0000 | NULL |
| POWER_LOTTO | cold_complement_2bet | RETIRED | LONG | 1 | 750 | 86 | 0.1147 | 0.1178 | -0.0032 | 0.6226 | 1.0000 | NULL |
| POWER_LOTTO | fourier30_markov30_2bet | RETIRED | SHORT | 1 | 49 | 4 | 0.0816 | 0.1178 | -0.0362 | 0.8444 | 1.0000 | NULL |
| POWER_LOTTO | fourier30_markov30_2bet | RETIRED | MID | 1 | 299 | 35 | 0.1171 | 0.1178 | -0.0008 | 0.5432 | 1.0000 | NULL |
| POWER_LOTTO | fourier30_markov30_2bet | RETIRED | LONG | 1 | 749 | 84 | 0.1121 | 0.1178 | -0.0057 | 0.7014 | 1.0000 | NULL |
| POWER_LOTTO | fourier_rhythm_3bet | ONLINE | SHORT | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | fourier_rhythm_3bet | ONLINE | MID | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | fourier_rhythm_3bet | ONLINE | LONG | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | midfreq_fourier_2bet | UNREGISTERED_IN_CANONICAL_LIFECYCLE_REGISTRY | SHORT | 1 | 50 | 5 | 0.1000 | 0.1178 | -0.0178 | 0.7166 | 1.0000 | NULL |
| POWER_LOTTO | midfreq_fourier_2bet | UNREGISTERED_IN_CANONICAL_LIFECYCLE_REGISTRY | MID | 1 | 300 | 30 | 0.1000 | 0.1178 | -0.0178 | 0.8533 | 1.0000 | NULL |
| POWER_LOTTO | midfreq_fourier_2bet | UNREGISTERED_IN_CANONICAL_LIFECYCLE_REGISTRY | LONG | 1 | 750 | 84 | 0.1120 | 0.1178 | -0.0058 | 0.7060 | 1.0000 | NULL |
| POWER_LOTTO | midfreq_fourier_mk_3bet | UNREGISTERED_IN_CANONICAL_LIFECYCLE_REGISTRY | SHORT | 1 | 50 | 7 | 0.1400 | 0.1178 | 0.0222 | 0.3749 | 1.0000 | NULL |
| POWER_LOTTO | midfreq_fourier_mk_3bet | UNREGISTERED_IN_CANONICAL_LIFECYCLE_REGISTRY | MID | 1 | 300 | 34 | 0.1133 | 0.1178 | -0.0045 | 0.6219 | 1.0000 | NULL |
| POWER_LOTTO | midfreq_fourier_mk_3bet | UNREGISTERED_IN_CANONICAL_LIFECYCLE_REGISTRY | LONG | 1 | 750 | 101 | 0.1347 | 0.1178 | 0.0168 | 0.0866 | 1.0000 | NULL |
| POWER_LOTTO | power_fourier_rhythm_2bet | RETIRED | SHORT | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | power_fourier_rhythm_2bet | RETIRED | MID | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | power_fourier_rhythm_2bet | RETIRED | LONG | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | power_orthogonal_5bet | ONLINE | SHORT | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | power_orthogonal_5bet | ONLINE | MID | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | power_orthogonal_5bet | ONLINE | LONG | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | power_precision_3bet | ONLINE | SHORT | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | power_precision_3bet | ONLINE | MID | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | power_precision_3bet | ONLINE | LONG | None | 0 | 0 | — | — | — | — | — | INSUFFICIENT_SUPPORT |
| POWER_LOTTO | pp3_freqort_4bet | UNREGISTERED_IN_CANONICAL_LIFECYCLE_REGISTRY | SHORT | 1 | 50 | 6 | 0.1200 | 0.1178 | 0.0022 | 0.5459 | 1.0000 | NULL |
| POWER_LOTTO | pp3_freqort_4bet | UNREGISTERED_IN_CANONICAL_LIFECYCLE_REGISTRY | MID | 1 | 300 | 28 | 0.0933 | 0.1178 | -0.0245 | 0.9238 | 1.0000 | NULL |
| POWER_LOTTO | pp3_freqort_4bet | UNREGISTERED_IN_CANONICAL_LIFECYCLE_REGISTRY | LONG | 1 | 750 | 95 | 0.1267 | 0.1178 | 0.0088 | 0.2415 | 1.0000 | NULL |
| POWER_LOTTO | zonal_entropy_2bet | RETIRED | SHORT | 1 | 50 | 6 | 0.1200 | 0.1178 | 0.0022 | 0.5459 | 1.0000 | NULL |
| POWER_LOTTO | zonal_entropy_2bet | RETIRED | MID | 1 | 300 | 35 | 0.1167 | 0.1178 | -0.0012 | 0.5515 | 1.0000 | NULL |
| POWER_LOTTO | zonal_entropy_2bet | RETIRED | LONG | 1 | 750 | 80 | 0.1067 | 0.1178 | -0.0112 | 0.8426 | 1.0000 | NULL |

## Statistical Cautions

- All cells are **retrospective**; none is confirmatory or future-only.
- Confirmatory correction is **Bonferroni (m=108)**; BH-FDR is descriptive only.
- **50-draw (SHORT)** windows cannot independently support promotion.
- Missing observations are **excluded**, never converted to failures.
- No strategy is claimed to improve future prediction success.

## Limitations

- This matrix unifies already-committed retrospective P273A evidence; it computes no new outcome data.
- All results are retrospective; none is confirmatory, future-only, or a prediction-success claim.
- No cross-strategy combination search was performed; cells are independent re-presentations.
- 50-draw (SHORT) windows are integrity guardrails and cannot independently support promotion.
- POWER second-zone-missing rows are excluded as missing eligibility; never imputed, never counted as losses.
- Lifecycle states are preserved as-is (REJECTED / RETIRED / OBSERVATION / ONLINE); none silently removed.
- Monetary budget is unsupported (no authoritative unit-cost source); it remains null.
- Prize-tier semantics retain source_verification_status=MANUAL_VERIFICATION_REQUIRED.
- No diversified-random baseline exists; only the governed exact distinct-ticket random null is used.
- No betting recommendation is made and no future predictive improvement is claimed.

_Final classification: `P275B_UNIFIED_PRIZE_AWARE_SUCCESS_MATRIX_COMPLETE`._
