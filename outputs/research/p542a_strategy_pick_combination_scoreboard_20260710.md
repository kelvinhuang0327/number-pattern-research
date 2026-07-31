# P542A — Strategy Pick / Combination Scoreboard

> 本報告僅描述既有 replay 的歷史統計與隨機基準比較；不預測未來、不構成投注建議，也不表示任何策略可上線或可獲利。

## Scope

- Historical replay rows only; no prediction, replay generation, training, or betting advice.
- Draw windows: 50, 300, and 750 latest eligible target draws.
- Random comparisons are analytic baselines matched to the selected budget.

## Summary

- strategy_pick_records: **603**
- combination_leaderboard_records: **510**
- power_lotto_zone2_records: **360**
- deterministic_payload_sha256: `71f3df75c85a2f243ab42673f2abe27e8bfc7cd8fce94e7583d5726548d90b39`

## Best Equal-Budget Combinations (750 Draw Window)

| lottery | budget | combination | support | any-main hit | prize-aware hit | prize edge |
|---|---:|---|---:|---:|---:|---:|
| BIG_LOTTO | 1 | `ts3_regime_3bet:1` | 750 | 13.07% | 0.00% | +0.00pp |
| BIG_LOTTO | 2 | `biglotto_deviation_2bet:2` | 750 | 25.07% | 0.00% | +0.00pp |
| BIG_LOTTO | 3 | `bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:2` | 750 | 34.13% | 0.00% | -0.16pp |
| BIG_LOTTO | 4 | `bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2` | 750 | 40.67% | 0.27% | -0.32pp |
| BIG_LOTTO | 5 | `bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:2 + markov_single_biglotto:2` | 750 | 46.13% | 0.93% | -0.08pp |
| BIG_LOTTO | 6 | `bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + markov_single_biglotto:2` | 750 | 51.73% | 1.47% | -0.45pp |
| DAILY_539 | 1 | `p0c_539_3bet_f_cold_x2:1` | 750 | 13.47% | 0.00% | +0.00pp |
| DAILY_539 | 2 | `midfreq_fourier_2bet:2` | 750 | 27.60% | 1.60% | +0.25pp |
| DAILY_539 | 3 | `daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2` | 750 | 36.40% | 4.53% | +0.99pp |
| DAILY_539 | 4 | `acb_single_539:2 + midfreq_fourier_2bet:2` | 750 | 46.00% | 7.87% | +0.68pp |
| DAILY_539 | 5 | `acb_single_539:2 + daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2` | 750 | 53.07% | 11.60% | +0.90pp |
| POWER_LOTTO | 1 | `midfreq_fourier_mk_3bet:1` | 750 | 18.80% | 2.13% | +0.16pp |
| POWER_LOTTO | 2 | `midfreq_fourier_mk_3bet:2` | 750 | 34.40% | 4.00% | +0.32pp |
| POWER_LOTTO | 3 | `cold_complement_2bet:1 + midfreq_fourier_mk_3bet:2` | 750 | 43.87% | 10.67% | +1.12pp |
| POWER_LOTTO | 4 | `fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2` | 750 | 51.73% | 13.20% | +1.70pp |
| POWER_LOTTO | 5 | `cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2` | 750 | 58.53% | 21.60% | +1.68pp |
| POWER_LOTTO | 6 | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2` | 750 | 64.53% | 24.13% | +0.75pp |

## Top Strategy Pick-K (750 Draw Window)

| lottery | K | strategy | support | any-main hit | prize-aware hit | random prize baseline |
|---|---:|---|---:|---:|---:|---:|
| BIG_LOTTO | 1 | `ts3_regime_3bet` | 750 | 13.07% | 0.00% | 0.00% |
| BIG_LOTTO | 2 | `biglotto_deviation_2bet` | 750 | 25.07% | 0.00% | 0.00% |
| BIG_LOTTO | 3 | `biglotto_deviation_2bet` | 750 | 33.33% | 0.27% | 0.19% |
| BIG_LOTTO | 4 | `biglotto_deviation_2bet` | 750 | 45.07% | 0.67% | 0.71% |
| BIG_LOTTO | 5 | `biglotto_deviation_2bet` | 750 | 52.40% | 1.87% | 1.66% |
| BIG_LOTTO | 6 | `coldpool15_biglotto` | 750 | 59.20% | 2.80% | 3.10% |
| DAILY_539 | 1 | `p0c_539_3bet_f_cold_x2` | 750 | 13.47% | 0.00% | 0.00% |
| DAILY_539 | 2 | `midfreq_fourier_2bet` | 750 | 27.60% | 1.60% | 1.35% |
| DAILY_539 | 3 | `midfreq_fourier_2bet` | 750 | 38.27% | 5.07% | 3.83% |
| DAILY_539 | 4 | `midfreq_fourier_2bet` | 750 | 46.53% | 7.87% | 7.24% |
| DAILY_539 | 5 | `midfreq_fourier_2bet` | 750 | 53.20% | 13.47% | 11.40% |
| POWER_LOTTO | 1 | `midfreq_fourier_mk_3bet` | 750 | 18.80% | 2.13% | 1.97% |
| POWER_LOTTO | 2 | `midfreq_fourier_mk_3bet` | 750 | 34.40% | 4.00% | 3.68% |
| POWER_LOTTO | 3 | `midfreq_fourier_mk_3bet` | 750 | 44.67% | 5.87% | 5.36% |
| POWER_LOTTO | 4 | `midfreq_fourier_mk_3bet` | 750 | 53.87% | 8.27% | 7.19% |
| POWER_LOTTO | 5 | `midfreq_fourier_mk_3bet` | 750 | 62.13% | 10.93% | 9.30% |
| POWER_LOTTO | 6 | `midfreq_fourier_mk_3bet` | 750 | 70.40% | 13.47% | 11.78% |

## Power Lotto Zone-2 Metrics (750 Draw Window)

| scope | identifier | support | zone-2 hit | random zone-2 baseline | zone-2 edge |
|---|---|---:|---:|---:|---:|
| combination | `cold_complement_2bet:1` | 750 | 11.87% | 12.50% | -0.63pp |
| combination | `cold_complement_2bet:1 + fourier30_markov30_2bet:1` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:1 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2` | 750 | 32.67% | 33.53% | -0.87pp |
| combination | `cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:1` | 750 | 32.67% | 33.53% | -0.87pp |
| combination | `cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2` | 750 | 32.67% | 33.53% | -0.87pp |
| combination | `cold_complement_2bet:1 + fourier30_markov30_2bet:2 + power_orthogonal_5bet:1` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:1 + fourier30_markov30_2bet:2 + power_precision_3bet:1` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:1 + midfreq_fourier_mk_3bet:1` | 750 | 21.33% | 22.95% | -1.62pp |
| combination | `cold_complement_2bet:1 + midfreq_fourier_mk_3bet:2` | 750 | 21.33% | 22.95% | -1.62pp |
| combination | `cold_complement_2bet:1 + midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:1` | 750 | 21.33% | 22.95% | -1.62pp |
| combination | `cold_complement_2bet:1 + midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:2` | 750 | 21.33% | 22.95% | -1.62pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:1` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:1` | 750 | 32.67% | 33.53% | -0.87pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2` | 750 | 32.67% | 33.53% | -0.87pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + fourier_rhythm_3bet:1` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + fourier_rhythm_3bet:2` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_2bet:1` | 750 | 32.67% | 33.53% | -0.87pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_2bet:2` | 750 | 32.67% | 33.53% | -0.87pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:1` | 750 | 32.67% | 33.53% | -0.87pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2` | 750 | 32.67% | 33.53% | -0.87pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:1` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:2` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_orthogonal_5bet:1` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_orthogonal_5bet:2` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_precision_3bet:1` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_precision_3bet:2` | 750 | 24.80% | 24.95% | -0.15pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + pp3_freqort_4bet:1` | 750 | 32.67% | 33.53% | -0.87pp |
| combination | `cold_complement_2bet:2 + fourier30_markov30_2bet:2 + pp3_freqort_4bet:2` | 750 | 32.67% | 33.53% | -0.87pp |
| combination | `cold_complement_2bet:2 + midfreq_fourier_2bet:2 + zonal_entropy_2bet:2` | 750 | 21.33% | 22.95% | -1.62pp |
| combination | `cold_complement_2bet:2 + midfreq_fourier_mk_3bet:1` | 750 | 21.33% | 22.95% | -1.62pp |
| combination | `cold_complement_2bet:2 + midfreq_fourier_mk_3bet:2` | 750 | 21.33% | 22.95% | -1.62pp |
| combination | `cold_complement_2bet:2 + midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:2` | 750 | 21.33% | 22.95% | -1.62pp |
| combination | `cold_complement_2bet:2 + pp3_freqort_4bet:2 + zonal_entropy_2bet:2` | 750 | 21.33% | 22.95% | -1.62pp |
| combination | `fourier30_markov30_2bet:1` | 750 | 12.93% | 12.48% | +0.45pp |
| combination | `fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:1` | 750 | 22.80% | 23.13% | -0.33pp |
| combination | `fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2` | 750 | 22.80% | 23.13% | -0.33pp |
| combination | `fourier30_markov30_2bet:1 + power_fourier_rhythm_2bet:1` | 750 | 12.93% | 12.48% | +0.45pp |
| combination | `fourier30_markov30_2bet:1 + power_orthogonal_5bet:1` | 750 | 12.93% | 12.50% | +0.43pp |
| combination | `fourier30_markov30_2bet:1 + power_precision_3bet:1` | 750 | 12.93% | 12.50% | +0.43pp |
| combination | `fourier30_markov30_2bet:2` | 750 | 12.93% | 12.48% | +0.45pp |
| combination | `fourier30_markov30_2bet:2 + fourier_rhythm_3bet:1` | 750 | 12.93% | 12.48% | +0.45pp |
| combination | `fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:1` | 750 | 22.80% | 23.13% | -0.33pp |
| combination | `fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2` | 750 | 22.80% | 23.13% | -0.33pp |
| combination | `fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:1` | 750 | 12.93% | 12.48% | +0.45pp |
| combination | `fourier30_markov30_2bet:2 + power_orthogonal_5bet:1` | 750 | 12.93% | 12.50% | +0.43pp |
| combination | `fourier30_markov30_2bet:2 + power_precision_3bet:1` | 750 | 12.93% | 12.50% | +0.43pp |
| combination | `fourier_rhythm_3bet:1` | 750 | 0.00% | 0.00% | +0.00pp |
| combination | `midfreq_fourier_2bet:1` | 750 | 11.47% | 12.50% | -1.03pp |
| combination | `midfreq_fourier_mk_3bet:1` | 750 | 11.47% | 12.50% | -1.03pp |
| combination | `midfreq_fourier_mk_3bet:2` | 750 | 11.47% | 12.50% | -1.03pp |
| combination | `midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:1` | 750 | 21.33% | 22.95% | -1.62pp |
| combination | `midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:2` | 750 | 21.33% | 22.95% | -1.62pp |
| combination | `power_fourier_rhythm_2bet:1` | 750 | 0.00% | 0.00% | +0.00pp |
| combination | `power_orthogonal_5bet:1` | 750 | 0.00% | 0.00% | +0.00pp |
| combination | `power_precision_3bet:1` | 750 | 0.00% | 0.00% | +0.00pp |
| combination | `pp3_freqort_4bet:1` | 750 | 11.47% | 12.50% | -1.03pp |
| combination | `pp3_freqort_4bet:2` | 750 | 11.47% | 12.50% | -1.03pp |
| combination | `zonal_entropy_2bet:1` | 750 | 11.87% | 12.50% | -0.63pp |
| combination | `zonal_entropy_2bet:2` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `cold_complement_2bet` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `cold_complement_2bet` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `cold_complement_2bet` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `cold_complement_2bet` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `cold_complement_2bet` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `cold_complement_2bet` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `fourier30_markov30_2bet` | 750 | 12.93% | 12.48% | +0.45pp |
| strategy_pick | `fourier30_markov30_2bet` | 750 | 12.93% | 12.48% | +0.45pp |
| strategy_pick | `fourier30_markov30_2bet` | 750 | 12.93% | 12.48% | +0.45pp |
| strategy_pick | `fourier30_markov30_2bet` | 750 | 12.93% | 12.48% | +0.45pp |
| strategy_pick | `fourier30_markov30_2bet` | 750 | 12.93% | 12.48% | +0.45pp |
| strategy_pick | `fourier30_markov30_2bet` | 750 | 12.93% | 12.48% | +0.45pp |
| strategy_pick | `fourier_rhythm_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `fourier_rhythm_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `fourier_rhythm_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `fourier_rhythm_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `fourier_rhythm_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `fourier_rhythm_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `midfreq_fourier_2bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `midfreq_fourier_2bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `midfreq_fourier_2bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `midfreq_fourier_2bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `midfreq_fourier_2bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `midfreq_fourier_2bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `midfreq_fourier_mk_3bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `midfreq_fourier_mk_3bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `midfreq_fourier_mk_3bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `midfreq_fourier_mk_3bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `midfreq_fourier_mk_3bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `midfreq_fourier_mk_3bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `power_fourier_rhythm_2bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_fourier_rhythm_2bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_fourier_rhythm_2bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_fourier_rhythm_2bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_fourier_rhythm_2bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_fourier_rhythm_2bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_orthogonal_5bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_orthogonal_5bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_orthogonal_5bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_orthogonal_5bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_orthogonal_5bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_orthogonal_5bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_precision_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_precision_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_precision_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_precision_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_precision_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `power_precision_3bet` | 750 | 0.00% | 0.00% | +0.00pp |
| strategy_pick | `pp3_freqort_4bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `pp3_freqort_4bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `pp3_freqort_4bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `pp3_freqort_4bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `pp3_freqort_4bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `pp3_freqort_4bet` | 750 | 11.47% | 12.50% | -1.03pp |
| strategy_pick | `zonal_entropy_2bet` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `zonal_entropy_2bet` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `zonal_entropy_2bet` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `zonal_entropy_2bet` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `zonal_entropy_2bet` | 750 | 11.87% | 12.50% | -0.63pp |
| strategy_pick | `zonal_entropy_2bet` | 750 | 11.87% | 12.50% | -0.63pp |

## Safety

- db_read_only: `true`
- db_opened: `false`
- db_write: `false`
- replay_generation: `false`
- model_training: `false`
- production_code_change: `false`
- betting_advice: `false`
