# P356B Big Lotto Replay 30/150/750/1500

- Eligible strategy count: `10`
- Excluded Big Lotto lineage count: `47`
- Warning: coverage Edge is not governance approval and not betting advice.
- Replay mode: in-memory only; canonical DB was opened read-only/immutable and was not written.

## Skipped / Excluded By Reason
```json
{
  "DB_ONLY": 2,
  "DOC_ONLY": 10,
  "ID_REUSED": 2,
  "MISSING_CODE": 9,
  "UNKNOWN": 24
}
```

## Big Lotto Ranking By 1500p Edge
| strategy_id | lineage_id | current_status | bet_count | hit_rate | baseline | edge |
| --- | --- | --- | --- | --- | --- | --- |
| biglotto_ts3_markov_4bet_w30 | biglotto_ts3_markov_4bet_w30__current | RETIRED | 4 | 0.088667 | 0.072492 | 0.016175 |
| biglotto_triple_strike | biglotto_triple_strike__current | ONLINE | 3 | 0.068000 | 0.054877 | 0.013123 |
| ts3_regime_3bet | ts3_regime_3bet__current | ONLINE | 3 | 0.067333 | 0.054877 | 0.012456 |
| biglotto_echo_aware_3bet | biglotto_echo_aware_3bet__current | RETIRED | 3 | 0.064000 | 0.054877 | 0.009123 |
| biglotto_deviation_2bet | biglotto_deviation_2bet__current | ONLINE | 2 | 0.042000 | 0.036928 | 0.005072 |
| coldpool15_biglotto | coldpool15_biglotto__current | REJECTED | 3 | 0.053333 | 0.054877 | -0.001544 |
| cold_complement_biglotto | cold_complement_biglotto__current | REJECTED | 1 | 0.016000 | 0.018638 | -0.002638 |
| markov_single_biglotto | markov_single_biglotto__current | REJECTED | 1 | 0.016000 | 0.018638 | -0.002638 |
| fourier30_markov30_biglotto | fourier30_markov30_biglotto__current | REJECTED | 2 | 0.033333 | 0.036928 | -0.003594 |
| markov_2bet_biglotto | markov_2bet_biglotto__current | REJECTED | 2 | 0.030667 | 0.036928 | -0.006261 |

## 30p Table
| strategy_id | current_status | bet_count | total_periods | hit_count | hit_rate | baseline | edge | replay_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fourier30_markov30_biglotto | REJECTED | 2 | 30 | 2 | 0.066667 | 0.036928 | 0.029739 | COMPLETED |
| cold_complement_biglotto | REJECTED | 1 | 30 | 1 | 0.033333 | 0.018638 | 0.014696 | COMPLETED |
| markov_single_biglotto | REJECTED | 1 | 30 | 1 | 0.033333 | 0.018638 | 0.014696 | COMPLETED |
| biglotto_echo_aware_3bet | RETIRED | 3 | 30 | 2 | 0.066667 | 0.054877 | 0.011790 | COMPLETED |
| biglotto_ts3_markov_4bet_w30 | RETIRED | 4 | 30 | 2 | 0.066667 | 0.072492 | -0.005825 | COMPLETED |
| biglotto_triple_strike | ONLINE | 3 | 30 | 1 | 0.033333 | 0.054877 | -0.021544 | COMPLETED |
| coldpool15_biglotto | REJECTED | 3 | 30 | 1 | 0.033333 | 0.054877 | -0.021544 | COMPLETED |
| ts3_regime_3bet | ONLINE | 3 | 30 | 1 | 0.033333 | 0.054877 | -0.021544 | COMPLETED |
| biglotto_deviation_2bet | ONLINE | 2 | 30 | 0 | 0.000000 | 0.036928 | -0.036928 | COMPLETED |
| markov_2bet_biglotto | REJECTED | 2 | 30 | 0 | 0.000000 | 0.036928 | -0.036928 | COMPLETED |

## 150p Table
| strategy_id | current_status | bet_count | total_periods | hit_count | hit_rate | baseline | edge | replay_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fourier30_markov30_biglotto | REJECTED | 2 | 150 | 7 | 0.046667 | 0.036928 | 0.009739 | COMPLETED |
| biglotto_ts3_markov_4bet_w30 | RETIRED | 4 | 150 | 12 | 0.080000 | 0.072492 | 0.007508 | COMPLETED |
| biglotto_echo_aware_3bet | RETIRED | 3 | 150 | 9 | 0.060000 | 0.054877 | 0.005123 | COMPLETED |
| biglotto_triple_strike | ONLINE | 3 | 150 | 9 | 0.060000 | 0.054877 | 0.005123 | COMPLETED |
| ts3_regime_3bet | ONLINE | 3 | 150 | 9 | 0.060000 | 0.054877 | 0.005123 | COMPLETED |
| cold_complement_biglotto | REJECTED | 1 | 150 | 3 | 0.020000 | 0.018638 | 0.001362 | COMPLETED |
| markov_single_biglotto | REJECTED | 1 | 150 | 2 | 0.013333 | 0.018638 | -0.005304 | COMPLETED |
| coldpool15_biglotto | REJECTED | 3 | 150 | 7 | 0.046667 | 0.054877 | -0.008210 | COMPLETED |
| markov_2bet_biglotto | REJECTED | 2 | 150 | 4 | 0.026667 | 0.036928 | -0.010261 | COMPLETED |
| biglotto_deviation_2bet | ONLINE | 2 | 150 | 2 | 0.013333 | 0.036928 | -0.023594 | COMPLETED |

## 750p Table
| strategy_id | current_status | bet_count | total_periods | hit_count | hit_rate | baseline | edge | replay_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| biglotto_ts3_markov_4bet_w30 | RETIRED | 4 | 750 | 69 | 0.092000 | 0.072492 | 0.019508 | COMPLETED |
| biglotto_echo_aware_3bet | RETIRED | 3 | 750 | 52 | 0.069333 | 0.054877 | 0.014456 | COMPLETED |
| ts3_regime_3bet | ONLINE | 3 | 750 | 52 | 0.069333 | 0.054877 | 0.014456 | COMPLETED |
| biglotto_triple_strike | ONLINE | 3 | 750 | 51 | 0.068000 | 0.054877 | 0.013123 | COMPLETED |
| biglotto_deviation_2bet | ONLINE | 2 | 750 | 35 | 0.046667 | 0.036928 | 0.009739 | COMPLETED |
| cold_complement_biglotto | REJECTED | 1 | 750 | 14 | 0.018667 | 0.018638 | 0.000029 | COMPLETED |
| markov_single_biglotto | REJECTED | 1 | 750 | 11 | 0.014667 | 0.018638 | -0.003971 | COMPLETED |
| fourier30_markov30_biglotto | REJECTED | 2 | 750 | 23 | 0.030667 | 0.036928 | -0.006261 | COMPLETED |
| coldpool15_biglotto | REJECTED | 3 | 750 | 35 | 0.046667 | 0.054877 | -0.008210 | COMPLETED |
| markov_2bet_biglotto | REJECTED | 2 | 750 | 21 | 0.028000 | 0.036928 | -0.008928 | COMPLETED |

## 1500p Table
| strategy_id | current_status | bet_count | total_periods | hit_count | hit_rate | baseline | edge | replay_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| biglotto_ts3_markov_4bet_w30 | RETIRED | 4 | 1500 | 133 | 0.088667 | 0.072492 | 0.016175 | COMPLETED |
| biglotto_triple_strike | ONLINE | 3 | 1500 | 102 | 0.068000 | 0.054877 | 0.013123 | COMPLETED |
| ts3_regime_3bet | ONLINE | 3 | 1500 | 101 | 0.067333 | 0.054877 | 0.012456 | COMPLETED |
| biglotto_echo_aware_3bet | RETIRED | 3 | 1500 | 96 | 0.064000 | 0.054877 | 0.009123 | COMPLETED |
| biglotto_deviation_2bet | ONLINE | 2 | 1500 | 63 | 0.042000 | 0.036928 | 0.005072 | COMPLETED |
| coldpool15_biglotto | REJECTED | 3 | 1500 | 80 | 0.053333 | 0.054877 | -0.001544 | COMPLETED |
| cold_complement_biglotto | REJECTED | 1 | 1500 | 24 | 0.016000 | 0.018638 | -0.002638 | COMPLETED |
| markov_single_biglotto | REJECTED | 1 | 1500 | 24 | 0.016000 | 0.018638 | -0.002638 | COMPLETED |
| fourier30_markov30_biglotto | REJECTED | 2 | 1500 | 50 | 0.033333 | 0.036928 | -0.003594 | COMPLETED |
| markov_2bet_biglotto | REJECTED | 2 | 1500 | 46 | 0.030667 | 0.036928 | -0.006261 | COMPLETED |
