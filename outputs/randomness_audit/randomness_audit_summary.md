# Lottery Randomness Audit Report

**Run timestamp:** 2026-07-18T13:35:18.685255Z
**Audit version:** 2.0.0-p20r
**Audit commit:** `precommit:0586c611cf23a9b30225c9f43273c2325e5972e9:2cb535a4814d89064fc94a48f849a8c74a0ba7a8372779ac21332480642b98ec`
**Simulations:** 2,000
**Seed:** 42
**Alpha:** 0.05
**Total confirmatory tests:** 44
**Exploratory sorted-position diagnostics:** 17
**Cadence anchor:** `run_timestamp` (UTC)
**Reanalysis performed:** YES
**New draws analyzed:** YES

## FINAL VERDICT

**WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION**

> Strategy implication: NO_EXPLOITABLE_EDGE_FROM_DRAW_PROCESS

## Canonical Data Binding

| Game | Source | Rows | Date min | Date max | Excluded | SHA-256 |
|---|---|---:|---|---|---:|---|
| power_lotto | `draws WHERE lottery_type='POWER_LOTTO'` | 1929 | 2008-01-24 | 2026-07-16 | 0 | `fe5a3fff685d5fdfdd023f6ea69eca9b05b8da8a74f5fbe9793255e5a16a12f3` |
| big_lotto | `draws_big_lotto_canonical_main` | 2125 | 2007-01-02 | 2026-07-14 | 1025 | `d04e44247626f3264744db39019ce680788acf7dd864c6400f7d417490f2a5cb` |
| daily_539 | `draws WHERE lottery_type='DAILY_539'` | 5916 | 2007-01-01 | 2026-07-16 | 0 | `965f2aafd08c4a08eb10fd0819c85daf43ea2c9b46b81a9f728c35d020f892dd` |

## Data Quality Classification

- **power_lotto**: duplicate draw IDs 0; duplicate full records 0; repeated main combinations on different draw IDs 0; invalid repeated numbers inside a draw 0.
- **big_lotto**: duplicate draw IDs 0; duplicate full records 0; repeated main combinations on different draw IDs 0; invalid repeated numbers inside a draw 0.
- **daily_539**: duplicate draw IDs 0; duplicate full records 0; repeated main combinations on different draw IDs 34; invalid repeated numbers inside a draw 0.

Repeated winning combinations across distinct draw IDs are possible outcomes, not duplicate database rows.

## Confirmatory Results

| Test ID | Statistic | p raw | Bonferroni p | BH-FDR q | Verdict |
|---|---:|---:|---:|---:|---|
| `power_lotto_overall_frequency` | 33.342 | 0.382309 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_special_uniformity` | 9.06947 | 0.247707 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_pattern_consecutive_count` | 0.757387 | 0.073963 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_pattern_same_tail_count` | 1.14515 | 0.752624 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_pattern_odd_count` | 2.98963 | 0.695652 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_pattern_low_count` | 3.01244 | 0.635182 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_pattern_sum` | 116.745 | 0.670165 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_pattern_span` | 27.9114 | 0.65967 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_pattern_repeat_from_prev` | 0.934129 | 0.501749 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_pattern_pair_cooccurrence_gini` | 0.0857202 | 0.738631 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_pattern_gap_distribution` | 5.58227 | 0.65967 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_ljungbox_sum` | 16.5382 | 0.682726 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_runs_odd` | -0.0532787 | 0.95751 | 1 | 0.999585 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_runs_repeat` | 1.21163 | 0.225655 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `power_lotto_drift_halves` | 38.8053 | 0.189405 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_overall_frequency` | 40.03 | 0.603198 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_special_uniformity` | 65.6574 | 0.0459634 | 1 | 0.872616 | WEAK_DEVIATION_NOT_SIGNIFICANT_AFTER_CORRECTION |
| `big_lotto_pattern_consecutive_count` | 0.618353 | 0.724138 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_pattern_same_tail_count` | 1.22494 | 0.981009 | 1 | 0.999585 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_pattern_odd_count` | 3.09176 | 0.238881 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_pattern_low_count` | 2.89506 | 0.089955 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_pattern_sum` | 151 | 0.165417 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_pattern_span` | 35.9393 | 0.167916 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_pattern_repeat_from_prev` | 0.738701 | 0.789605 | 1 | 0.890837 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_pattern_pair_cooccurrence_gini` | 0.104828 | 0.355322 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_pattern_gap_distribution` | 7.18786 | 0.167916 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_ljungbox_sum` | 19.1622 | 0.511309 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_runs_odd` | -0.485122 | 0.62759 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_runs_repeat` | 0.122533 | 0.902477 | 1 | 0.992725 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `big_lotto_drift_halves` | 37.3065 | 0.713643 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_overall_frequency` | 34.2558 | 0.43928 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_pattern_consecutive_count` | 0.508283 | 0.624188 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_pattern_same_tail_count` | 0.782116 | 0.21989 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_pattern_odd_count` | 2.57015 | 0.652174 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_pattern_low_count` | 2.44067 | 0.753623 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_pattern_sum` | 99.8879 | 0.723638 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_pattern_span` | 26.7449 | 0.385807 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_pattern_repeat_from_prev` | 0.645647 | 0.614193 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_pattern_pair_cooccurrence_gini` | 0.0606757 | 0.350325 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_pattern_gap_distribution` | 6.68623 | 0.385807 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_ljungbox_sum` | 9.82246 | 0.971278 | 1 | 0.999585 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_runs_odd` | -0.000519739 | 0.999585 | 1 | 0.999585 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_runs_repeat` | 0.483882 | 0.628469 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |
| `daily_539_drift_halves` | 33.224 | 0.492254 | 1 | 0.872616 | CONSISTENT_WITH_RANDOM_DRAW_MODEL |

## Exploratory Sorted-Position Diagnostics

All 17 position tests compare sorted values with an intentionally inapplicable marginal-uniform reference. They are retained only to expose the sorted-order artifact and are excluded from Bonferroni and BH-FDR.

## Cadence

A new executable audit is required after more than 14 calendar days or after 50 new canonical draws, whichever occurs first. Re-attestation of unchanged evidence resets neither trigger.

## Provenance and Limitations

- Implementation: **RECONSTRUCTED** from the committed 44-test registry; historical parity is not claimed.
- Big Lotto special-number marginal null: uniform over **1..49**, matching the sequential 6+special draw mechanism.
- Big Lotto source: `draws_big_lotto_canonical_main`; the older 2,130-row artifact matched legacy `49_LOTTO`.
- Statistical compatibility does not prove physical randomness.
- The confirmatory family contains correlated tests; Bonferroni is the conservative family-wise gate.
- Monte Carlo p-values have finite resolution determined by simulations + 1.
- Sorted-position diagnostics are exploratory artifacts and are excluded from correction.
- The Big Lotto source is the canonical-main view; the historical artifact used a legacy 49_LOTTO population.
- No result is a prediction, strategy promotion, or betting recommendation.

Research and entertainment only; not betting advice.
