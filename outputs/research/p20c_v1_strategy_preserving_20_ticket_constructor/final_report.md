# P20C v1 Strategy-Preserving 20-Ticket Constructor

Status: **COMPLETED**. The explicit adapter mode completed 12 of 12 formerly partial strategy identities at the 99% draw/replicate threshold. Native strategy governance states were not changed, and adapter-assisted identities remain qualified with `@sp20_v1`.

This is a historical empirical backtest for research and entertainment, not a future winning probability, betting recommendation, or strategy-promotion decision.

## Constructor contract

- Identifier: `strategy_preserving_20_ticket/v1`
- Native tickets are canonicalized, deduplicated, and retained.
- Tier B uses strategy-owned number scores/rankings; Tier C derives frequency signal only from native ticket membership, never ticket position.
- Synthesized tickets meet the fixed signal-pool minimums (3 of 6 for pools 6–8, 4 for 9–14, 5 for 15+) and disclose neutral 1–49 fills.
- Selection combines signal score, maximum-overlap penalty, number-concentration penalty, and SHA-256 tie-breaking.
- Constants fixed before the historical run: `{"candidate_pool_size": 80, "constructor_identifier": "strategy_preserving_20_ticket/v1", "max_candidate_attempts": 4096, "max_overlap_penalty": 12.0, "number_concentration_penalty": 2.0, "parity_portfolio_sha256": "8f756025c8818987101b2b61f7c296d0341d7fea52ffa95f7272ca121c9b30d6", "signal_score_weight": 100.0}`.

## Repository and data identity

| Field | Value |
| --- | --- |
| Base commit | `520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f` |
| Branch | `codex/p20c-v1-strategy-preserving-constructor` |
| Canonical DB SHA-256 | `bf608f13d05e8ceae59e457c0b72a2eb30329eeb6415a09930bb8fde6971fd77` |
| Canonical dataset SHA-256 | `cd56bcca2fd61152f1812bc9c524dcbff3070f06d1c457e81a64bb4d441dd93f` |
| Draws | 2125 (2007/01/02 through 2026/07/14) |
| Common window | 2025 draws after 100 prior draws |
| Random replicates | 10 |

The raw-data quality pass found 1025 noncanonical BIG_LOTTO rows outside the selected view, 0 duplicate canonical draw IDs, 0 invalid JSON rows, 0 range errors, and 0 negative financial rows. All 2,125 positional-order fields are null, so the constructor never treats sorted ticket position as signal.

## Formerly partial strategy completion

| Base strategy | Governance | Native mean | Constructed mean | Native share | Completion | Adapter M4+ |
| --- | --- | --- | --- | --- | --- | --- |
| history::lottery_api/models/social_wisdom_predictor.py | candidate | 8.000000 | 12.000000 | 0.400000 | 1.000000 | 0.019802 |
| registry::biglotto_triple_strike | accepted | 3.000000 | 17.000000 | 0.150000 | 1.000000 | 0.020247 |
| registry::biglotto_deviation_2bet | accepted | 2.000000 | 18.000000 | 0.100000 | 1.000000 | 0.015802 |
| registry::ts3_regime_3bet | accepted | 3.000000 | 17.000000 | 0.150000 | 1.000000 | 0.015802 |
| registry::biglotto_echo_aware_3bet | deprecated | 3.000000 | 17.000000 | 0.150000 | 1.000000 | 0.021235 |
| registry::biglotto_ts3_markov_4bet_w30 | deprecated | 4.000000 | 16.000000 | 0.200000 | 1.000000 | 0.017284 |
| registry::bet2_fourier_expansion_biglotto | rejected | 1.000000 | 19.000000 | 0.050000 | 1.000000 | 0.016296 |
| registry::cold_complement_biglotto | rejected | 1.000000 | 19.000000 | 0.050000 | 1.000000 | 0.020247 |
| registry::coldpool15_biglotto | rejected | 1.000000 | 19.000000 | 0.050000 | 1.000000 | 0.019259 |
| registry::fourier30_markov30_biglotto | rejected | 1.000000 | 19.000000 | 0.050000 | 1.000000 | 0.015309 |
| registry::markov_2bet_biglotto | rejected | 1.000000 | 19.000000 | 0.050000 | 1.000000 | 0.018765 |
| registry::markov_single_biglotto | rejected | 1.000000 | 19.000000 | 0.050000 | 1.000000 | 0.015309 |

Every valid native ticket remains in its final portfolio. Exact behavior for representative native counts is pinned by unit/parity tests: 1→19 constructed, 2→18, 4→16, and 8→12, all with 20 unique legal final tickets.

## Native-complete 20-ticket ranking

| Rank | Strategy | M4+ hits | Portfolios | Rate | CI low | CI high | vs baseline |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | history::lottery_api/models/core_satellite.py | 360 | 20235 | 0.017791 | 0.016005 | 0.019610 | -0.002557 |
| 2 | history::lottery_api/models/zone_split.py | 314 | 20250 | 0.015506 | 0.010716 | 0.020889 | -0.004840 |

Occasional duplicate native portfolios are not silently counted as native-complete; constructor-assisted repairs carry the adapter-qualified identity and are excluded from the native ranking row.

## Adapter-assisted 20-ticket ranking

| Rank | Effective strategy | Governance | M4+ hits | Portfolios | Rate | CI low | CI high | vs baseline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | registry::biglotto_echo_aware_3bet@sp20_v1 | deprecated | 43 | 2025 | 0.021235 | 0.015803 | 0.028479 | 0.000889 |
| 2 | registry::biglotto_triple_strike@sp20_v1 | accepted | 41 | 2025 | 0.020247 | 0.014960 | 0.027351 | -0.000099 |
| 3 | registry::cold_complement_biglotto@sp20_v1 | rejected | 41 | 2025 | 0.020247 | 0.014960 | 0.027351 | -0.000099 |
| 4 | history::lottery_api/models/social_wisdom_predictor.py@sp20_v1 | candidate | 401 | 20250 | 0.019802 | 0.017926 | 0.021778 | -0.000543 |
| 5 | registry::coldpool15_biglotto@sp20_v1 | rejected | 39 | 2025 | 0.019259 | 0.014120 | 0.026219 | -0.001086 |
| 6 | registry::markov_2bet_biglotto@sp20_v1 | rejected | 38 | 2025 | 0.018765 | 0.013702 | 0.025651 | -0.001580 |
| 7 | registry::biglotto_ts3_markov_4bet_w30@sp20_v1 | deprecated | 35 | 2025 | 0.017284 | 0.012454 | 0.023942 | -0.003062 |
| 8 | registry::bet2_fourier_expansion_biglotto@sp20_v1 | rejected | 33 | 2025 | 0.016296 | 0.011627 | 0.022797 | -0.004049 |
| 9 | registry::biglotto_deviation_2bet@sp20_v1 | accepted | 32 | 2025 | 0.015802 | 0.011216 | 0.022223 | -0.004543 |
| 10 | registry::ts3_regime_3bet@sp20_v1 | accepted | 32 | 2025 | 0.015802 | 0.011216 | 0.022223 | -0.004543 |
| 11 | registry::fourier30_markov30_biglotto@sp20_v1 | rejected | 31 | 2025 | 0.015309 | 0.010806 | 0.021647 | -0.005037 |
| 12 | registry::markov_single_biglotto@sp20_v1 | rejected | 31 | 2025 | 0.015309 | 0.010806 | 0.021647 | -0.005037 |

These rows measure the versioned adapter portfolios, not the native strategies. A rejected or deprecated base strategy remains rejected or deprecated regardless of rank.

## Native partial results

| Base strategy | Native tickets | Native M4+ hits | Native M4+ rate |
| --- | --- | --- | --- |
| history::lottery_api/models/social_wisdom_predictor.py | 8.000000 | 167 | 0.008247 |
| registry::biglotto_triple_strike | 3.000000 | 6 | 0.002963 |
| registry::biglotto_deviation_2bet | 2.000000 | 2 | 0.000988 |
| registry::ts3_regime_3bet | 3.000000 | 4 | 0.001975 |
| registry::biglotto_echo_aware_3bet | 3.000000 | 8 | 0.003951 |
| registry::biglotto_ts3_markov_4bet_w30 | 4.000000 | 7 | 0.003457 |
| registry::bet2_fourier_expansion_biglotto | 1.000000 | 1 | 0.000494 |
| registry::cold_complement_biglotto | 1.000000 | 1 | 0.000494 |
| registry::coldpool15_biglotto | 1.000000 | 1 | 0.000494 |
| registry::fourier30_markov30_biglotto | 1.000000 | 3 | 0.001481 |
| registry::markov_2bet_biglotto | 1.000000 | 2 | 0.000988 |
| registry::markov_single_biglotto | 1.000000 | 2 | 0.000988 |

Native partial rates use unequal 1–8-ticket budgets and are descriptive only; they are not mixed with either 20-ticket ranking.

## Random baseline

The paired uniform-random 20-ticket baseline produced 412 M4+ replicate-draws in 20250 portfolios: 2.034568% (95% draw-cluster CI 1.846914%–2.232099%). The independent-ticket approximation is 1.955877%; the empirical baseline enforces unique tickets.

Point estimates and historical confidence intervals do not establish future advantage. Multiple comparisons, historical reuse, and correlated strategy families remain material limitations.

## Leakage, determinism, and recomputation

- The constructor API has no target-result or database parameter.
- Every integration slice ends strictly before its target draw; mutation and cutoff tests are included in the focused suite.
- Detail read-back independently checked legality, uniqueness, portfolio SHA-256, hit counts, cutoffs, and aggregate totals: `{"aggregate_recomputation_mismatches": 0, "constructor_metadata_mismatches": 0, "detail_rows_recounted": 107385, "history_cutoff_failures": 0, "hit_recomputation_mismatches": 0, "native_preservation_failures": 0, "portfolio_hash_mismatches": 0, "portfolio_uniqueness_failures": 0, "row_count_matches": true, "ticket_legality_failures": 0}`.
- Constructor reproducibility sample mismatches: 0.
- The known outcome-aware `tools/big_lotto_exhaustive_audit.py` surface remains excluded with `DATA_LEAKAGE_RISK`.

## Remaining failures and skipped strategies

| Reason | Count |
| --- | --- |
| DATA_LEAKAGE_RISK | 1 |
| DOCUMENT_ONLY | 47 |
| MISSING_APPROVED_MULTI_TICKET_ENTRYPOINT | 29 |
| MISSING_ENTRYPOINT | 8 |
| PARTIAL_IMPLEMENTATION | 312 |
| UNKNOWN_FAILURE | 174 |
| UNSAFE_EXTERNAL_STATE | 35 |

Skipped identities retain their committed lifecycle/classification. No missing entrypoint was fabricated, no dependency was installed, and no constructor constant was adjusted after viewing M4+ results.

## Reproducibility

The committed runner, constructor, focused tests, manifest, compact CSVs, validation JSON, and this report reproduce the result. The temporary draw/replicate detail contained 107385 rows, SHA-256 `3c7ef5b8e1c05b1eccc52c8524034092b1cc9cea95f521ea8ad4a0d130b976e0`, and independent stream digest `db6c323c2cd75b338264b51e7e4d2976e25a781fb8fa103fbeb078dfb2b363b6`; it was removed after verification.

Focused test command: `python -m pytest -q -p no:cacheprovider tests/test_strategy_preserving_20_ticket.py tests/test_p20c_strategy_preserving_backtest.py tests/test_replay_strategy_lifecycle_registry.py tests/test_replay_strategy_lifecycle_exposure.py tests/test_replay_strategy_registry_online_candidates.py`

Focused result: {'passed': 146, 'failed': 0, 'skipped': 0, 'xfailed': 0, 'xpassed': 0} (status `PASS`). Exact-head GitHub CI is reported in the PR lifecycle state, not inferred here.
