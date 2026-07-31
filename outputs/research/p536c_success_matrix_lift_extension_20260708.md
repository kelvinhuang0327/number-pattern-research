# P536C — Strategy Success-Rate Matrix Lift Extension

> This evaluates historical replay performance only, not guaranteed future winning.
> Retrospective historical replay evidence only; no prediction, betting, edge, future-winning, or production-readiness claim.

Extends: **P333** (analysis/p333_strategy_pick_combination_scoreboard.py)

## Summary

- matrix_records: **603**
- cross_lottery_normalized_lift_records: **195**
- combination_leaderboard_with_lift_records: **510**
- combination_stability_rank_records: **170**
- data_hash_sha256: `46d49ea1fc20e240205ab6fa87b70800e6dbfabfee927fc06e532b4b61b4c8d2`
- row_counts_by_lottery: `{'BIG_LOTTO': 24140, 'DAILY_539': 34680, 'POWER_LOTTO': 36104}`

## Top Prize-Signal Lift Cells Per Window

| window | lottery | strategy | pick_k | support | prize-signal rate | baseline | lift | log10(lift) |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 50 | BIG_LOTTO | `biglotto_echo_aware_3bet` | 4 | 50 | 2.00% | 0.71% | 2.816x | 0.450 |
| 50 | BIG_LOTTO | `bet2_fourier_expansion_biglotto` | 6 | 50 | 8.00% | 3.10% | 2.585x | 0.412 |
| 50 | BIG_LOTTO | `biglotto_triple_strike` | 6 | 50 | 8.00% | 3.10% | 2.585x | 0.412 |
| 50 | BIG_LOTTO | `biglotto_ts3_markov_4bet_w30` | 6 | 50 | 8.00% | 3.10% | 2.585x | 0.412 |
| 50 | BIG_LOTTO | `ts3_regime_3bet` | 6 | 50 | 8.00% | 3.10% | 2.585x | 0.412 |
| 300 | DAILY_539 | `daily539_f4cold` | 2 | 300 | 2.67% | 1.35% | 1.976x | 0.296 |
| 300 | DAILY_539 | `daily539_f4cold_3bet` | 2 | 300 | 2.67% | 1.35% | 1.976x | 0.296 |
| 300 | DAILY_539 | `daily539_f4cold_5bet` | 2 | 300 | 2.67% | 1.35% | 1.976x | 0.296 |
| 300 | DAILY_539 | `p0b_539_3bet_f_cold_fmid` | 2 | 300 | 2.67% | 1.35% | 1.976x | 0.296 |
| 300 | DAILY_539 | `p0c_539_3bet_f_cold_x2` | 2 | 300 | 2.67% | 1.35% | 1.976x | 0.296 |
| 750 | POWER_LOTTO | `fourier_rhythm_3bet` | 3 | 750 | 0.40% | 0.24% | 1.687x | 0.227 |
| 750 | POWER_LOTTO | `power_fourier_rhythm_2bet` | 3 | 750 | 0.40% | 0.24% | 1.687x | 0.227 |
| 750 | POWER_LOTTO | `power_orthogonal_5bet` | 3 | 750 | 0.40% | 0.24% | 1.687x | 0.227 |
| 750 | POWER_LOTTO | `power_precision_3bet` | 3 | 750 | 0.40% | 0.24% | 1.687x | 0.227 |
| 750 | POWER_LOTTO | `fourier_rhythm_3bet` | 5 | 750 | 3.33% | 2.07% | 1.608x | 0.206 |

## Methodology Notes

- **reuse**: All selection (select_strategy_numbers), scoring (score_selection), hypergeometric-baseline (_hypergeom_at_least), replay loading (_load_replay_draws), and combination-search (build_combination_leaderboard/_combo_candidates/evaluate_combo) logic is imported unmodified from analysis/p333_strategy_pick_combination_scoreboard.py. This module adds only m3+, baseline/lift derivations, and a presentation layer.
- **combination_stability_rank_scope**: Computed only over combo_ids that already appear in P333's own top-10-per-bucket leaderboard for at least one of the three windows. This is an enrichment pass over existing search results, not an independent re-search across all combo candidates in all windows -- no combination search-space expansion was performed.
- **cross_lottery_normalization**: Never pools raw hit rates across lotteries. Each lottery's lift is rate/baseline computed against its own lottery-specific hypergeometric baseline; lotteries are shown side-by-side only at pick_k values common to all three games (pick_k <= 5).

## Safety

- db_read_only: `true`
- db_write: `false`
- replay_generation: `false`
- model_training: `false`
- registry_mutation: `false`
- strategy_promotion: `false`
- betting_advice: `false`

