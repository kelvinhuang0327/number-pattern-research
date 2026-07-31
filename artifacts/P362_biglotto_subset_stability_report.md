# P362 Big Lotto no-DB Rolling Subset Stability Drilldown

## Scope statements

- This is historical descriptive subset stability only.
- No future prediction guarantee. Past coverage stability does not predict future draws.
- No betting advice. Nothing here recommends placing any bet.
- No DB was opened or written. The data source remains the committed JSONL fixture and P360/P361 no-DB evidence.
- No production registry import, no deploy, no migration/backfill, and no strategy status change.
- No blended leaderboard: P356/P358/P360/P361 results are not merged into any cross-task ranking.
- Shape/safety-only adapters and blocked targets were excluded from scoring: `adapt_biglotto_10bet_combined`, `adapt_biglotto_5bet_orthogonal`, `adapt_biglotto_zonal_pruning`, `adapt_predict_biglotto_regime_3bet`.

## Method

- Source modules: `recovered_strategies/biglotto/no_db_multiwindow_validation.py` and `recovered_strategies/biglotto/no_db_coverage_utility.py`.
- Fixture: `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl`
- Fixture SHA256: `f4accb6f527694e739689242c929e87e4b031a364becb4fadb4aaea50ef2e3f8`
- BIG_LOTTO rows: 2139; scoreable periods: 1619.
- Adapter cohort: `adapt_biglotto_p0_2bet`, `adapt_predict_biglotto_echo_2bet`, `adapt_predict_biglotto_echo_phase2_2bet`, `adapt_predict_biglotto_echo_phase2_3bet`, `adapt_predict_biglotto_echo_mixed_3bet`.
- Windows: 30, 150, 750, 1500 trailing periods.
- Subsets: all 31 non-empty subsets of the parity-only adapter cohort.
- Baseline: `1 - (1 - 0.0186375) ** total_ticket_count`; same-total-bet-count independent-ticket approximation, not proof of edge.

## Best subset by size and window

| window_size | subset_size | adapter_subset | any_hit_count | full_cohort_any_hit_count | hit_gap_to_full_cohort | coverage_rate | duplicate_hit_events | mean_pairwise_jaccard |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 1 | adapt_predict_biglotto_echo_mixed_3bet | 2 | 2 | 0 | 0.06666667 | 0 |  |
| 30 | 2 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 2 | 2 | 0 | 0.06666667 | 0 | 0.00000000 |
| 30 | 3 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_mixed_3bet | 2 | 2 | 0 | 0.06666667 | 1 | 0.16666667 |
| 30 | 4 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_mixed_3bet | 2 | 2 | 0 | 0.06666667 | 2 | 0.33333333 |
| 30 | 5 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 2 | 2 | 0 | 0.06666667 | 4 | 0.40000000 |
| 150 | 1 | adapt_predict_biglotto_echo_mixed_3bet | 11 | 15 | 4 | 0.07333333 | 0 |  |
| 150 | 2 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 15 | 15 | 0 | 0.10000000 | 0 | 0.00000000 |
| 150 | 3 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_mixed_3bet | 15 | 15 | 0 | 0.10000000 | 6 | 0.18181818 |
| 150 | 4 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_mixed_3bet | 15 | 15 | 0 | 0.10000000 | 12 | 0.34848485 |
| 150 | 5 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 15 | 15 | 0 | 0.10000000 | 23 | 0.41818182 |
| 750 | 1 | adapt_predict_biglotto_echo_mixed_3bet | 52 | 86 | 34 | 0.06933333 | 0 |  |
| 750 | 2 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 85 | 86 | 1 | 0.11333333 | 3 | 0.03529412 |
| 750 | 3 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 86 | 86 | 0 | 0.11466667 | 53 | 0.33813488 |
| 750 | 4 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 86 | 86 | 0 | 0.11466667 | 89 | 0.40934549 |
| 750 | 5 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 86 | 86 | 0 | 0.11466667 | 125 | 0.48977412 |
| 1500 | 1 | adapt_predict_biglotto_echo_mixed_3bet | 97 | 160 | 63 | 0.06466667 | 0 |  |
| 1500 | 2 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 158 | 160 | 2 | 0.10533333 | 8 | 0.05063291 |
| 1500 | 3 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 160 | 160 | 0 | 0.10666667 | 94 | 0.32048124 |
| 1500 | 4 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 160 | 160 | 0 | 0.10666667 | 156 | 0.39097005 |
| 1500 | 5 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 160 | 160 | 0 | 0.10666667 | 223 | 0.46001861 |

## Compact candidate thresholds

| row_type | window_size | subset_size | adapter_subset | any_hit_count | full_cohort_any_hit_count | hit_gap_to_full_cohort |
| --- | --- | --- | --- | --- | --- | --- |
| smallest_within_1_hit_of_full_cohort | 30 | 1 | adapt_predict_biglotto_echo_mixed_3bet | 2 | 2 | 0 |
| smallest_within_3_hit_of_full_cohort | 30 | 1 | adapt_predict_biglotto_echo_mixed_3bet | 2 | 2 | 0 |
| smallest_within_1_hit_of_full_cohort | 150 | 2 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 15 | 15 | 0 |
| smallest_within_3_hit_of_full_cohort | 150 | 2 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 15 | 15 | 0 |
| smallest_within_1_hit_of_full_cohort | 750 | 2 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 85 | 86 | 1 |
| smallest_within_3_hit_of_full_cohort | 750 | 2 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 85 | 86 | 1 |
| smallest_within_1_hit_of_full_cohort | 1500 | 3 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 160 | 160 | 0 |
| smallest_within_3_hit_of_full_cohort | 1500 | 2 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 158 | 160 | 2 |

## P361 compact pair check

| window_size | adapter_subset | any_hit_count | full_cohort_any_hit_count | hit_gap_to_full_cohort | within_3_hits_of_full_cohort | note |
| --- | --- | --- | --- | --- | --- | --- |
| 30 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 2 | 2 | 0 | true | P361 compact pair remains within 3 hits of full cohort. |
| 150 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 15 | 15 | 0 | true | P361 compact pair remains within 3 hits of full cohort. |
| 750 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 85 | 86 | 1 | true | P361 compact pair remains within 3 hits of full cohort. |
| 1500 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 158 | 160 | 2 | true | P361 compact pair remains within 3 hits of full cohort. |

## Rank stability summary

| adapter_subset | subset_size | average_rank_by_coverage_rate | rank_variance_by_coverage_rate | top_1_window_count | top_3_window_count | within_3_hits_of_full_cohort_window_count |
| --- | --- | --- | --- | --- | --- | --- |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 2 | 4.0000 | 5.0000 | 1 | 2 | 4 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 3 | 6.2500 | 37.6875 | 2 | 2 | 4 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_mixed_3bet | 3 | 6.5000 | 5.2500 | 0 | 1 | 4 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_3bet | 2 | 6.5000 | 13.2500 | 0 | 1 | 3 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_mixed_3bet | 3 | 7.0000 | 6.0000 | 0 | 0 | 4 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_3bet | 3 | 8.2500 | 6.1875 | 0 | 0 | 3 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 4 | 9.0000 | 57.5000 | 0 | 2 | 4 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 4 | 9.5000 | 64.2500 | 0 | 2 | 4 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_mixed_3bet | 4 | 9.7500 | 18.1875 | 0 | 0 | 4 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet | 3 | 10.2500 | 6.1875 | 0 | 0 | 3 |

## Artifact inventory

- `artifacts/P362_biglotto_subset_stability_window_metrics.csv`
- `artifacts/P362_biglotto_subset_stability_rank_summary.csv`
- `artifacts/P362_biglotto_subset_stability_compact_candidates.csv`
- `artifacts/P362_biglotto_subset_stability_manifest.csv`
- `artifacts/P362_biglotto_subset_stability_report.md`
