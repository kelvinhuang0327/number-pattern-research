# P543D — Contract Validation Pilot

> Descriptive-only and pilot-only: this report is not betting advice and makes no future prediction.
> No true OOS evaluation was performed; chronological splits are descriptive only.
> This does not establish production or go-live readiness. The selected candidates were pre-filtered, so selection bias remains.

## Sources

| role | artifact | SHA256 | bytes |
|---|---|---|---:|
| primary_p543c_contract | `outputs/research/p543c_candidate_per_draw_validation_contract_20260710.json` | `71be8549daddbc0e810e17e3e6afbd49eedc02eee402c017e562a834ef1448a5` | 515478 |
| optional_p543b | `outputs/research/p543b_scoreboard_validation_feasibility_pilot_20260710.json` | `78e13eb255dac6e283e0d61a88c217019c9a4a9cc6f85f8a2b911c542742767f` | 229734 |
| optional_p543a | `outputs/research/p543a_scoreboard_stability_packet_20260710.json` | `190fc9f9a8f2d4817a955204b5af1f5d9cf1fb186fa0695713202235f306e0e5` | 987573 |
| optional_p542a | `outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.json` | `c23a993c570de2f09c757f8ddbcf0e04b444d3312cd370c915222844ee927d5b` | 1999750 |

## Contract Schema

- candidates: 10
- rows: 500
- linkage: candidate_id = strategy_id:bet_index
- chronological fields: draw_order, draw_id, draw_date

## Per-candidate Metrics

| candidate | rows | draw range | ≥1 hit rate | average hits | hit distribution |
|---|---:|---|---:|---:|---|
| `bet2_fourier_expansion_biglotto:1` | 50 | 115000005–115000054 | 0.600 | 0.880 | 0:20, 1:19, 2:8, 3:3 |
| `biglotto_deviation_2bet:1` | 50 | 115000004–115000053 | 0.640 | 0.780 | 0:18, 1:26, 2:5, 3:1 |
| `biglotto_echo_aware_3bet:1` | 50 | 115000006–115000055 | 0.600 | 0.880 | 0:20, 1:18, 2:10, 3:2 |
| `biglotto_triple_strike:1` | 50 | 115000004–115000053 | 0.620 | 0.900 | 0:19, 1:20, 2:8, 3:3 |
| `biglotto_ts3_markov_4bet_w30:1` | 50 | 115000006–115000055 | 0.620 | 0.920 | 0:19, 1:19, 2:9, 3:3 |
| `coldpool15_biglotto:1` | 50 | 115000005–115000054 | 0.540 | 0.740 | 0:23, 1:19, 2:6, 3:2 |
| `fourier30_markov30_biglotto:1` | 50 | 115000005–115000054 | 0.600 | 0.720 | 0:20, 1:25, 2:4, 3:1 |
| `markov_2bet_biglotto:1` | 50 | 115000005–115000054 | 0.540 | 0.700 | 0:23, 1:19, 2:8 |
| `markov_single_biglotto:1` | 50 | 115000005–115000054 | 0.540 | 0.700 | 0:23, 1:19, 2:8 |
| `ts3_regime_3bet:1` | 50 | 115000004–115000053 | 0.620 | 0.900 | 0:19, 1:20, 2:8, 3:3 |

## Chronological Split (not true OOS)

| candidate | first half | second half | absolute delta | label |
|---|---:|---:|---:|---|
| `bet2_fourier_expansion_biglotto:1` | 0.560 | 0.640 | 0.080 | `stable_descriptive` |
| `biglotto_deviation_2bet:1` | 0.680 | 0.600 | 0.080 | `stable_descriptive` |
| `biglotto_echo_aware_3bet:1` | 0.720 | 0.480 | 0.240 | `late_drop` |
| `biglotto_triple_strike:1` | 0.560 | 0.680 | 0.120 | `late_improvement` |
| `biglotto_ts3_markov_4bet_w30:1` | 0.560 | 0.680 | 0.120 | `late_improvement` |
| `coldpool15_biglotto:1` | 0.640 | 0.440 | 0.200 | `late_drop` |
| `fourier30_markov30_biglotto:1` | 0.720 | 0.480 | 0.240 | `late_drop` |
| `markov_2bet_biglotto:1` | 0.520 | 0.560 | 0.040 | `stable_descriptive` |
| `markov_single_biglotto:1` | 0.520 | 0.560 | 0.040 | `stable_descriptive` |
| `ts3_regime_3bet:1` | 0.560 | 0.680 | 0.120 | `late_improvement` |

## Fixed-seed Permutation Baseline

| candidate | observed ≥1 rate | baseline mean | empirical percentile | at/above count |
|---|---:|---:|---:|---:|
| `bet2_fourier_expansion_biglotto:1` | 0.600 | 0.582 | 0.638 | 638 |
| `biglotto_deviation_2bet:1` | 0.640 | 0.689 | 0.267 | 267 |
| `biglotto_echo_aware_3bet:1` | 0.600 | 0.625 | 0.399 | 399 |
| `biglotto_triple_strike:1` | 0.620 | 0.582 | 0.773 | 773 |
| `biglotto_ts3_markov_4bet_w30:1` | 0.620 | 0.584 | 0.749 | 749 |
| `coldpool15_biglotto:1` | 0.540 | 0.654 | 0.066 | 66 |
| `fourier30_markov30_biglotto:1` | 0.600 | 0.650 | 0.255 | 255 |
| `markov_2bet_biglotto:1` | 0.540 | 0.611 | 0.186 | 186 |
| `markov_single_biglotto:1` | 0.540 | 0.610 | 0.180 | 180 |
| `ts3_regime_3bet:1` | 0.620 | 0.576 | 0.777 | 777 |

## Pilot Classification

| candidate | classification | evidence |
|---|---|---|
| `bet2_fourier_expansion_biglotto:1` | `pilot_near_permutation_baseline` | split=stable_descriptive; percentile=0.638; rows=50 |
| `biglotto_deviation_2bet:1` | `pilot_near_permutation_baseline` | split=stable_descriptive; percentile=0.267; rows=50 |
| `biglotto_echo_aware_3bet:1` | `chronologically_unstable` | split=late_drop; percentile=0.399; rows=50 |
| `biglotto_triple_strike:1` | `chronologically_unstable` | split=late_improvement; percentile=0.773; rows=50 |
| `biglotto_ts3_markov_4bet_w30:1` | `chronologically_unstable` | split=late_improvement; percentile=0.749; rows=50 |
| `coldpool15_biglotto:1` | `chronologically_unstable` | split=late_drop; percentile=0.066; rows=50 |
| `fourier30_markov30_biglotto:1` | `chronologically_unstable` | split=late_drop; percentile=0.255; rows=50 |
| `markov_2bet_biglotto:1` | `pilot_near_permutation_baseline` | split=stable_descriptive; percentile=0.186; rows=50 |
| `markov_single_biglotto:1` | `pilot_near_permutation_baseline` | split=stable_descriptive; percentile=0.18; rows=50 |
| `ts3_regime_3bet:1` | `chronologically_unstable` | split=late_improvement; percentile=0.777; rows=50 |

## Limitations

- Candidate selection was pre-filtered before this pilot, so selection bias remains.
- The rows are committed historical contract rows, not a prospectively held-out protocol.
- Chronological half splits are descriptive and are not true out-of-sample evaluation.
- Outcome shuffling is a fixed-seed descriptive baseline, not proof or a statistical significance claim.
- No result establishes usefulness for betting, future performance, production readiness, or go-live readiness.

## Recommended Next Task

Define and authorize a prospective, leakage-controlled evaluation protocol before any true out-of-sample claim.
