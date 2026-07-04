# P361 Big Lotto no-DB Coverage Utility Drilldown

## Scope statements

- This is historical descriptive coverage utility only.
- No future prediction guarantee. Past coverage does not predict future draws.
- No betting advice. Nothing here recommends placing any bet.
- No DB was opened or written. The only data source is the committed JSONL fixture.
- No production registry import, no deploy, no migration/backfill, and no strategy status change.
- Shape/safety-only adapters and blocked targets were excluded from scoring: `adapt_biglotto_10bet_combined`, `adapt_biglotto_5bet_orthogonal`, `adapt_biglotto_zonal_pruning`, `adapt_predict_biglotto_regime_3bet`.

## Method

- Source module: `recovered_strategies/biglotto/no_db_multiwindow_validation.py`
- Fixture: `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl`
- Fixture SHA256: `f4accb6f527694e739689242c929e87e4b031a364becb4fadb4aaea50ef2e3f8`
- BIG_LOTTO rows: 2139; scoreable periods: 1619.
- Adapter cohort: `adapt_biglotto_p0_2bet`, `adapt_predict_biglotto_echo_2bet`, `adapt_predict_biglotto_echo_phase2_2bet`, `adapt_predict_biglotto_echo_phase2_3bet`, `adapt_predict_biglotto_echo_mixed_3bet`.
- Hit definition: any ticket matching >= 3 main numbers.
- Subset utility: every non-empty adapter subset is ranked by any-adapter historical hit coverage.
- Marginal utility: every adapter is evaluated against every possible context subset of the other adapters.

## Best subset by size

| subset_size | adapter_subset | any_hit_count | coverage_rate | duplicate_hit_events | mean_pairwise_jaccard |
| --- | --- | --- | --- | --- | --- |
| 1 | adapt_predict_biglotto_echo_mixed_3bet | 104 | 0.06423718 | 0 |  |
| 2 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 168 | 0.10376776 | 9 | 0.05357143 |
| 3 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 171 | 0.10562075 | 102 | 0.32277212 |
| 4 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 171 | 0.10562075 | 169 | 0.39021449 |
| 5 | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 171 | 0.10562075 | 240 | 0.45768700 |

## Full-cohort marginal contribution

| candidate_adapter | candidate_total_hit_count | candidate_overlap_count | marginal_unique_hit_count | candidate_marginal_share |
| --- | --- | --- | --- | --- |
| adapt_biglotto_p0_2bet | 73 | 10 | 63 | 0.86301370 |
| adapt_predict_biglotto_echo_2bet | 71 | 71 | 0 | 0.00000000 |
| adapt_predict_biglotto_echo_mixed_3bet | 104 | 99 | 5 | 0.04807692 |
| adapt_predict_biglotto_echo_phase2_2bet | 67 | 67 | 0 | 0.00000000 |
| adapt_predict_biglotto_echo_phase2_3bet | 96 | 95 | 1 | 0.01041667 |

## Near-duplicate pair screen

| adapter_a | adapter_b | both_hit_count | union_hit_count | jaccard |
| --- | --- | --- | --- | --- |
| adapt_predict_biglotto_echo_2bet | adapt_predict_biglotto_echo_phase2_2bet | 64 | 74 | 0.86486486 |
| adapt_predict_biglotto_echo_phase2_3bet | adapt_predict_biglotto_echo_mixed_3bet | 92 | 108 | 0.85185185 |

## Artifact inventory

- `artifacts/P361_biglotto_coverage_utility_subset_metrics.csv`
- `artifacts/P361_biglotto_coverage_utility_marginal_contribution.csv`
- `artifacts/P361_biglotto_coverage_utility_hit_matrix.csv`
- `artifacts/P361_biglotto_coverage_utility_manifest.csv`
- `artifacts/P361_biglotto_coverage_utility_report.md`
