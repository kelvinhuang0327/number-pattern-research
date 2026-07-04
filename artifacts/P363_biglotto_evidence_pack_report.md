# P363 Big Lotto no-DB Consolidated Evidence Pack

## Scope statements

- This is historical descriptive evidence only.
- No future prediction guarantee. Past hit rates, coverage, and stability do not predict future draws.
- No betting advice. Nothing here recommends placing any bet.
- No DB was opened or written. P363 reads only committed P360/P361/P362 artifacts.
- No production registry import, no deploy, no migration/backfill, and no strategy status change.
- No blended leaderboard: P363 creates cards and checks, not a cross-task ranking.
- Shape-only and blocked targets remain excluded; P363 keeps the same five parity adapters from P360/P361/P362.

## Consolidated dimensions

- Adapter cards: 5
- Subset cards: 31
- Source artifacts fingerprinted: 14
- P361 scoreable periods: 1619
- P362 windows: 30;150;750;1500

## Consistency checks

| check_name | status | expected | actual | details |
| --- | --- | --- | --- | --- |
| exact_5_parity_adapter_names_consistent | PASS | adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_mixed_3bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet | P360=adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_mixed_3bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet \| P361=adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_mixed_3bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet \| hit_matrix=adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_mixed_3bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet \| P362=adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_mixed_3bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet | Adapter names are read from committed P360/P361/P362 artifacts. |
| expected_windows_present | PASS | 30;150;750;1500 | P360=30;150;750;1500 \| P362=30;150;750;1500 | P363 does not add or remove evaluation windows. |
| p361_subset_count | PASS | 31 | 31 | Every non-empty subset of five adapters should appear exactly once. |
| p361_hit_matrix_period_count | PASS | 1619 | 1619 | Period-level historical hit matrix remains the P360 scoreable range. |
| p362_compact_candidates_reference_valid_subsets | PASS | all compact candidate subsets present in P361 and P362 subset artifacts | all valid | Compact candidate cards are descriptive labels over existing subsets. |
| source_artifact_row_counts_match_manifests | PASS | all manifest-backed source row counts match | p360_results=20/20;p360_coverage=20/20;p361_subset_metrics=31/31;p361_marginal_contribution=80/80;p361_hit_matrix=1619/1619;p362_window_metrics=124/124;p362_rank_summary=31/31;p362_compact_candidates=32/32 | Manifest-backed checks are applied where P360/P361/P362 publish expected row counts. |
| p360_manifest_adapter_and_window_counts | PASS | adapter_count=5; windows=30;150;750;1500 | adapter_count=5; windows=30;150;750;1500 | Confirms P360 manifest agrees with the card dimensions. |
| p361_manifest_subset_and_matrix_counts | PASS | subset_metric_rows=31; hit_matrix_rows=1619 | subset_metric_rows=31; hit_matrix_rows=1619 | Confirms P361 manifest remains aligned with committed artifact rows. |
| p362_manifest_subset_stability_counts | PASS | subset_count_per_window=31; rank_summary_rows=31; compact_candidate_rows=32 | subset_count_per_window=31; rank_summary_rows=31; compact_candidate_rows=32 | Confirms P362 subset/card dimensions are unchanged. |

## Adapter cards

| adapter_function | bet_count | p360_windows_present | p361_total_hit_count | p361_unique_hit_count | p362_singleton_average_rank_by_coverage_rate | p362_singleton_top_3_window_count |
| --- | --- | --- | --- | --- | --- | --- |
| adapt_biglotto_p0_2bet | 2 | 30;150;750;1500 | 73 | 63 | 29.5000 | 0 |
| adapt_predict_biglotto_echo_2bet | 2 | 30;150;750;1500 | 71 | 0 | 28.0000 | 0 |
| adapt_predict_biglotto_echo_phase2_2bet | 2 | 30;150;750;1500 | 67 | 0 | 29.0000 | 0 |
| adapt_predict_biglotto_echo_phase2_3bet | 3 | 30;150;750;1500 | 96 | 1 | 16.5000 | 1 |
| adapt_predict_biglotto_echo_mixed_3bet | 3 | 30;150;750;1500 | 104 | 5 | 14.0000 | 1 |

## Compact candidate subset summary

| adapter_subset | subset_size | p361_any_hit_count | p362_top_3_window_count | compact_candidate_row_types | compact_candidate_windows |
| --- | --- | --- | --- | --- | --- |
| adapt_predict_biglotto_echo_mixed_3bet | 1 | 104 | 1 | best_subset_for_size;smallest_within_1_hit_of_full_cohort;smallest_within_3_hit_of_full_cohort;best_subset_for_size;best_subset_for_size;best_subset_for_size | 30;30;30;150;750;1500 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet | 2 | 168 | 2 | best_subset_for_size;p361_compact_pair_check;best_subset_for_size;p361_compact_pair_check;smallest_within_1_hit_of_full_cohort;smallest_within_3_hit_of_full_cohort;best_subset_for_size;p361_compact_pair_check;smallest_within_1_hit_of_full_cohort;smallest_within_3_hit_of_full_cohort;best_subset_for_size;p361_compact_pair_check;smallest_within_3_hit_of_full_cohort | 30;30;150;150;150;150;750;750;750;750;1500;1500;1500 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 3 | 171 | 2 | best_subset_for_size;best_subset_for_size;smallest_within_1_hit_of_full_cohort | 750;1500;1500 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_mixed_3bet | 3 | 168 | 1 | best_subset_for_size;best_subset_for_size | 30;150 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 4 | 171 | 2 | best_subset_for_size | 1500 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 4 | 171 | 2 | best_subset_for_size | 750 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_mixed_3bet | 4 | 170 | 0 | best_subset_for_size;best_subset_for_size | 30;150 |
| adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_2bet;adapt_predict_biglotto_echo_phase2_2bet;adapt_predict_biglotto_echo_phase2_3bet;adapt_predict_biglotto_echo_mixed_3bet | 5 | 171 | 0 | best_subset_for_size;best_subset_for_size;best_subset_for_size;best_subset_for_size | 30;150;750;1500 |

## Source artifact manifest

| artifact_role | path | data_row_count | line_count | sha256 | row_count_matches_manifest |
| --- | --- | --- | --- | --- | --- |
| p360_results | artifacts/P360_biglotto_no_db_multiwindow_validation_results.csv | 20 | 21 | 60b1cb5affed752fe3a174f588b65a1470354d7dd4b9a63e7d2e43c5779e2d88 | true |
| p360_manifest | artifacts/P360_biglotto_no_db_multiwindow_validation_manifest.csv | 19 | 20 | 9a9488c16a149a867ee6f87ef2b540efd3c08c27085497cfe7793b9c3c15485f |  |
| p360_coverage | artifacts/P360_biglotto_no_db_multiwindow_validation_coverage.csv | 20 | 21 | 0e3b850de155242d66b84d4f57b62947ac46093d6f0c66f84eb577be84ee3332 | true |
| p360_report | artifacts/P360_biglotto_no_db_multiwindow_validation_report.md |  | 109 | 0a19264a77804916c7369bfaac1061c74f4f054cd5cd360e35ff5f307fd93f08 |  |
| p361_subset_metrics | artifacts/P361_biglotto_coverage_utility_subset_metrics.csv | 31 | 32 | a9b12b21c8bb2f9fab9a3326735542668c03c40d652ebb5ceb79e2d9966c30b7 | true |
| p361_marginal_contribution | artifacts/P361_biglotto_coverage_utility_marginal_contribution.csv | 80 | 81 | 86afebac0d4a904bd483cb06251418772a0f86747d98b0e5c2130ed4b9bdb86a | true |
| p361_hit_matrix | artifacts/P361_biglotto_coverage_utility_hit_matrix.csv | 1619 | 1620 | 0afac099dfdfd7f23dd5b2c0ab605bba6ee280463a44c634670eafe1388cd99f | true |
| p361_manifest | artifacts/P361_biglotto_coverage_utility_manifest.csv | 22 | 23 | be425759df5f3d11ae6a2f9276942446725083b48857a622a4b6fad88a5d35e6 |  |
| p361_report | artifacts/P361_biglotto_coverage_utility_report.md |  | 56 | 20e2c4bfb9174b2ad8dc6326dd36f8b5ca6ec6dbd8730b6348f67d107b9fe599 |  |
| p362_window_metrics | artifacts/P362_biglotto_subset_stability_window_metrics.csv | 124 | 125 | 71046f2e786fbcb295deb82c70e4f43275b508c27635af37bb5c863e57d05907 | true |
| p362_rank_summary | artifacts/P362_biglotto_subset_stability_rank_summary.csv | 31 | 32 | 05b79a4e6fe8e869f14424f2a90b435a5db1e48dfa822a43194900a9ca425553 | true |
| p362_compact_candidates | artifacts/P362_biglotto_subset_stability_compact_candidates.csv | 32 | 33 | 97f043ab4fc9b45f862f4ee18fdc33ccf0a20b3be1db32de0fd4b4b6d84b0271 | true |
| p362_manifest | artifacts/P362_biglotto_subset_stability_manifest.csv | 31 | 32 | bb0425633c421083f94a92863bdbf89f8bf4abcb03a71f151bc6e8a8a2c7360b |  |
| p362_report | artifacts/P362_biglotto_subset_stability_report.md |  | 92 | a1c6a834c5cead91e2f3f98a68032d433770e29300d26d924c3af8771864edee |  |

## Exclusions

- Shape-only scoring remains excluded.
- Blocked target scoring remains excluded.
- P363 does not call adapters, re-score strategies, or create a new scoring cohort.
- P363 does not publish betting advice or future-performance claims.
