# P541A — BIG_LOTTO Strategy Inventory / Replay Coverage Audit

> generated_at: 2026-07-09T12:19:50.507063+00:00
> Historical strategy inventory and replay coverage audit only; not a prediction, betting edge, future-winning, or production-readiness claim.

## Owner question answer: PARTIAL

11 distinct BIG_LOTTO strategy_ids have at least one replay row (24140 rows total, all resolved with actual outcomes). All of them are also referenced in the P536C success/lift matrix. However 2 formally-registered id(s) (biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet) have zero replay rows, 4 id(s) referenced only in the D3 UI/test artifact (p1_dev_sum5bet, p1_deviation_4bet, p1_neighbor_cold_2bet, regime_2bet) have no code/registry definition and no replay rows, the most recent 13 ingested draw(s) have not been replayed by any strategy yet, and 451 legacy tools/analysis script(s) reference BIG_LOTTO but were not individually traced to a replay-backed strategy_id by this static audit. Therefore coverage is PARTIAL, not YES.

## Replay coverage totals

- total_rows: 24140
- distinct_strategy_ids_with_rows: 11
- max_replayed_draw: 115000055
- max_ingested_draw: 115000068
- draws_ingested_count: 3148
- unreplayed_recent_draw_gap: 13

## Strategy inventory

| strategy_id | classification | replay_rows | statuses seen |
|---|---|---|---|
| bet2_fourier_expansion_biglotto | replayed_and_artifact_covered | 1500 | DRY_RUN, REJECTED |
| biglotto_deviation_2bet | replayed_and_artifact_covered | 1570 | ONLINE |
| biglotto_echo_aware_3bet | replayed_and_artifact_covered | 4500 | ONLINE, RETIRED |
| biglotto_triple_strike | replayed_and_artifact_covered | 1570 | ONLINE |
| biglotto_ts3_acb_4bet | code_or_registry_only_no_replay_rows | None | REJECTED |
| biglotto_ts3_markov_4bet_w30 | replayed_and_artifact_covered | 6000 | ONLINE, RETIRED |
| biglotto_ts3_markov_freq_5bet | code_or_registry_only_no_replay_rows | None | REJECTED |
| cold_complement_biglotto | replayed_and_artifact_covered | 1500 | DRY_RUN, REJECTED |
| coldpool15_biglotto | replayed_and_artifact_covered | 1500 | DRY_RUN, REJECTED |
| fourier30_markov30_biglotto | replayed_and_artifact_covered | 1500 | DRY_RUN, REJECTED |
| markov_2bet_biglotto | replayed_and_artifact_covered | 1500 | DRY_RUN, REJECTED |
| markov_single_biglotto | replayed_and_artifact_covered | 1500 | DRY_RUN, REJECTED |
| p1_dev_sum5bet | artifact_only_unmapped_to_code | None | - |
| p1_deviation_4bet | artifact_only_unmapped_to_code | None | - |
| p1_neighbor_cold_2bet | artifact_only_unmapped_to_code | None | - |
| regime_2bet | artifact_only_unmapped_to_code | None | - |
| ts3_regime_3bet | replayed_and_artifact_covered | 1500 | ONLINE |

## Coverage gaps

- registered_zero_replay_rows: ['biglotto_ts3_acb_4bet', 'biglotto_ts3_markov_freq_5bet']
- d3_phantom_no_code_no_replay: ['p1_dev_sum5bet', 'p1_deviation_4bet', 'p1_neighbor_cold_2bet', 'regime_2bet']
- recency_gap_draws: 13
- lifecycle_status_conflicts_retired_vs_online: ['biglotto_echo_aware_3bet', 'biglotto_ts3_markov_4bet_w30']

## Deprecated / excluded

- rejected_registered_ids: ['bet2_fourier_expansion_biglotto', 'biglotto_ts3_acb_4bet', 'biglotto_ts3_markov_freq_5bet', 'cold_complement_biglotto', 'coldpool15_biglotto', 'fourier30_markov30_biglotto', 'markov_2bet_biglotto', 'markov_single_biglotto']
- retired_registered_ids: ['biglotto_echo_aware_3bet', 'biglotto_ts3_markov_4bet_w30']
- dry_run_shadow_ids: ['bet2_fourier_expansion_biglotto', 'cold_complement_biglotto', 'coldpool15_biglotto', 'fourier30_markov30_biglotto', 'markov_2bet_biglotto', 'markov_single_biglotto']

## Ambiguous / unmapped legacy scripts

- tools/*.py matched: 385
- analysis/*.py matched: 66
- This static audit enumerates these files by keyword match only; it does not import or execute them, so it cannot confirm whether each implements a method distinct from the 11 replay-backed strategy_ids above, is a duplicate/exploratory variant, or was ever wired to a registry adapter. Individual triage is out of scope per task spec (no execution, no imports with side effects) and is recommended as follow-up.

## Recommended next task

P541B_BIG_LOTTO_LEGACY_METHOD_CLASSIFICATION_AUDIT

## Provenance and limits

Static regex/text parsing of registry + shadow adapter files, git grep keyword file listing (no import/execution), read-only SQLite (mode=ro, PRAGMA query_only=ON) query of strategy_prediction_replays and draws, and substring membership check against 9 committed upstream JSON artifacts.

Canonical DB (lottery_api/data/lottery_v2.db) is gitignored and not present inside this isolated worktree; read via absolute path into the main checkout (same precedent as P539A). DB_PATH overridable via LOTTERY_DB_PATH env var.

Not performed by this task:
- DB writes of any kind
- replay row generation
- import/execution of tools/*.py or analysis/*.py strategy modules
- OOS evaluator runs, strategy scoring, or promotion gating
- recomputation or overwrite of P536-P540 artifacts
- individual file-by-file triage of the ~350+ legacy tools/analysis scripts

*Historical strategy inventory and replay coverage audit only; not a prediction, betting edge, future-winning, or production-readiness claim.*
