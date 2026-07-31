# P333 — Strategy Pick / Combination Scoreboard

> 歷史回放統計只描述既有 replay 的過去表現；不代表未來中獎率，不提供投注建議，也不代表策略可直接上線。

## Summary

- strategy_pick_records: **603**
- combination_leaderboard_records: **510**
- primary_windows: 50, 300, 750
- strategy_window_decision_counts: `{'HISTORICAL_WINDOW_PASS': 13, 'HISTORICAL_WINDOW_FAIL': 23}`

## Best 750-Window Equal-Budget Combinations

| lottery | budget | combo | support | any-hit | prize-signal | any-hit edge | prize edge |
|---|---:|---|---:|---:|---:|---:|---:|
| BIG_LOTTO | 1 | `ts3_regime_3bet:1` | 750 | 13.07% | 0.00% | +0.82pp | +0.00pp |
| BIG_LOTTO | 2 | `biglotto_deviation_2bet:2` | 750 | 25.07% | 0.00% | +1.85pp | +0.00pp |
| BIG_LOTTO | 3 | `bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:2` | 750 | 34.13% | 0.00% | +2.59pp | -0.16pp |
| BIG_LOTTO | 4 | `bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2` | 750 | 40.67% | 0.27% | +1.06pp | -0.32pp |
| BIG_LOTTO | 5 | `bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:2 + markov_single_biglotto:2` | 750 | 46.13% | 0.93% | +2.71pp | -0.08pp |
| BIG_LOTTO | 6 | `bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + markov_single_biglotto:2` | 750 | 51.73% | 1.47% | +1.88pp | -0.45pp |
| DAILY_539 | 1 | `p0c_539_3bet_f_cold_x2:1` | 750 | 13.47% | 0.00% | +0.65pp | +0.00pp |
| DAILY_539 | 2 | `midfreq_fourier_2bet:2` | 750 | 27.60% | 1.60% | +3.31pp | +0.25pp |
| DAILY_539 | 3 | `daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2` | 750 | 36.40% | 4.53% | +3.08pp | +0.99pp |
| DAILY_539 | 4 | `acb_single_539:2 + midfreq_fourier_2bet:2` | 750 | 46.00% | 7.87% | +2.52pp | +0.68pp |
| DAILY_539 | 5 | `acb_single_539:2 + daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2` | 750 | 53.07% | 11.60% | +2.75pp | +0.90pp |
| POWER_LOTTO | 1 | `midfreq_fourier_mk_3bet:1` | 750 | 18.80% | 2.13% | +3.01pp | +0.16pp |
| POWER_LOTTO | 2 | `midfreq_fourier_mk_3bet:2` | 750 | 34.40% | 4.00% | +4.95pp | +0.32pp |
| POWER_LOTTO | 3 | `cold_complement_2bet:1 + midfreq_fourier_mk_3bet:2` | 750 | 43.87% | 10.67% | +3.01pp | +1.12pp |
| POWER_LOTTO | 4 | `fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2` | 750 | 51.73% | 13.20% | +4.25pp | +1.70pp |
| POWER_LOTTO | 5 | `cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2` | 750 | 58.53% | 21.60% | +2.32pp | +1.68pp |
| POWER_LOTTO | 6 | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2` | 750 | 64.53% | 24.13% | +0.87pp | +0.75pp |

## Top Strategy Pick-K at 750 Window

| lottery | K | strategy | support | any-hit | prize-signal | any-hit edge | prize edge |
|---|---:|---|---:|---:|---:|---:|---:|
| BIG_LOTTO | 1 | `ts3_regime_3bet` | 750 | 13.07% | 0.00% | +0.82pp | +0.00pp |
| BIG_LOTTO | 2 | `biglotto_deviation_2bet` | 750 | 25.07% | 0.00% | +1.85pp | +0.00pp |
| BIG_LOTTO | 3 | `biglotto_deviation_2bet` | 750 | 33.33% | 0.27% | +0.32pp | +0.08pp |
| BIG_LOTTO | 4 | `biglotto_deviation_2bet` | 750 | 45.07% | 0.67% | +3.31pp | -0.04pp |
| BIG_LOTTO | 5 | `biglotto_deviation_2bet` | 750 | 52.40% | 1.87% | +2.88pp | +0.21pp |
| BIG_LOTTO | 6 | `coldpool15_biglotto` | 750 | 59.20% | 2.80% | +2.80pp | -0.30pp |
| DAILY_539 | 1 | `p0c_539_3bet_f_cold_x2` | 750 | 13.47% | 0.00% | +0.65pp | +0.00pp |
| DAILY_539 | 2 | `midfreq_fourier_2bet` | 750 | 27.60% | 1.60% | +3.31pp | +0.25pp |
| DAILY_539 | 3 | `midfreq_fourier_2bet` | 750 | 38.27% | 5.07% | +3.74pp | +1.24pp |
| DAILY_539 | 4 | `midfreq_fourier_2bet` | 750 | 46.53% | 7.87% | +2.92pp | +0.63pp |
| DAILY_539 | 5 | `midfreq_fourier_2bet` | 750 | 53.20% | 13.47% | +1.53pp | +2.07pp |
| POWER_LOTTO | 1 | `midfreq_fourier_mk_3bet` | 750 | 18.80% | 2.13% | +3.01pp | +0.16pp |
| POWER_LOTTO | 2 | `midfreq_fourier_mk_3bet` | 750 | 34.40% | 4.00% | +4.95pp | +0.32pp |
| POWER_LOTTO | 3 | `midfreq_fourier_mk_3bet` | 750 | 44.67% | 5.87% | +3.46pp | +0.51pp |
| POWER_LOTTO | 4 | `midfreq_fourier_mk_3bet` | 750 | 53.87% | 8.27% | +2.58pp | +1.08pp |
| POWER_LOTTO | 5 | `midfreq_fourier_mk_3bet` | 750 | 62.13% | 10.93% | +2.25pp | +1.63pp |
| POWER_LOTTO | 6 | `midfreq_fourier_mk_3bet` | 750 | 70.40% | 13.47% | +3.22pp | +1.68pp |

## Requested Example

BIG_LOTTO: `bet2_fourier_expansion_biglotto:2 + cold_complement_biglotto:2 + biglotto_deviation_2bet:2`

| window | support | any-hit | prize-signal | any-hit edge | prize edge |
|---:|---:|---:|---:|---:|---:|
| 50 | 50 | 50.00% | 4.00% | -0.37pp | +1.98pp |
| 300 | 300 | 49.33% | 1.00% | -0.34pp | -0.85pp |
| 750 | 750 | 49.07% | 1.07% | +1.20pp | -0.53pp |

## Cross-Lottery Feature Family Reference

| lottery | family | strategies | avg any-hit | avg prize-signal | avg any-hit edge |
|---|---|---:|---:|---:|---:|
| POWER_LOTTO | fourier | 5 | 30.08% | 2.05% | +0.63pp |
| POWER_LOTTO | frequency | 1 | 29.47% | 4.00% | +0.02pp |
| POWER_LOTTO | entropy | 1 | 29.47% | 3.87% | +0.02pp |
| POWER_LOTTO | orthogonal | 1 | 28.93% | 0.00% | -0.51pp |
| POWER_LOTTO | precision | 1 | 28.93% | 0.00% | -0.51pp |
| POWER_LOTTO | cold | 1 | 28.00% | 3.73% | -1.45pp |
| DAILY_539 | fourier | 1 | 27.60% | 1.60% | +3.31pp |
| DAILY_539 | acb | 3 | 25.20% | 1.42% | +0.91pp |
| BIG_LOTTO | deviation | 1 | 25.07% | 0.00% | +1.85pp |
| DAILY_539 | orthogonal | 1 | 24.00% | 1.33% | -0.29pp |
| BIG_LOTTO | echo | 1 | 23.87% | 0.00% | +0.65pp |
| DAILY_539 | cold | 6 | 23.73% | 1.93% | -0.56pp |
| DAILY_539 | markov | 3 | 23.38% | 1.51% | -0.91pp |
| DAILY_539 | zone | 1 | 23.33% | 1.33% | -0.96pp |
| BIG_LOTTO | cold | 2 | 23.07% | 0.00% | -0.15pp |
| BIG_LOTTO | markov | 3 | 22.36% | 0.00% | -0.86pp |
| BIG_LOTTO | other | 1 | 22.27% | 0.00% | -0.95pp |
| BIG_LOTTO | ts3 | 1 | 22.27% | 0.00% | -0.95pp |
| BIG_LOTTO | fourier | 2 | 21.20% | 0.00% | -2.01pp |

## Safety

- db_read_only: `true`
- db_write: `false`
- replay_generation: `false`
- model_training: `false`
- registry_mutation: `false`
- strategy_promotion: `false`
- betting_advice: `false`

