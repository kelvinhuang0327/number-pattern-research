# P539A — Read-Only Per-Draw Replay Export

> Historical replay source export only; not a prediction, betting edge, future-winning, or production-readiness claim.

Derived from: **P538A**; upstream: P537A, P536K, P536C, P333

## Candidate Scope

- included: stable_review_candidate, combination_review_candidate
- excluded `cross_lottery_review_candidate`: Excluded per P538A's own rolling_or_out_of_sample_feasibility finding: cross_lottery_normalized_lift rows lose strategy_id and target_draw range during upstream aggregation and are not traceable to a single walk-forward-able series without a separate aggregation-identity task.
- excluded `insufficient_context_candidate`: Excluded per P538A's own finding: these rows are excluded upstream because avg_prize_signal_lift_across_present_windows is null in the P536K source; not a DB-export-resolvable gap.

## Readiness

- rows_exported_by_lottery: `{}`
- rows_exported_by_candidate_group: `{'stable_review_candidate': 177, 'combination_review_candidate': 102}`
- distinct_strategy_ids_covered: `34`
- db_max_target_draw_by_lottery: `{'BIG_LOTTO': 115000055, 'DAILY_539': 115000121, 'POWER_LOTTO': 115000041}`
- new_draws_found_since_last_replay_cutoff: `False`
- p539b_rolling_oos_evaluator_feasible_from_this_export_alone: `False`

**Feasibility note:** Zero rows found with target_draw strictly after each candidate strategy's own recovered latest_target_draw (checked against the live DB's own max target_draw per lottery, which is <= the recovered cutoff for every included candidate strategy). No new out-of-sample window is possible yet; re-run this export after new draws are ingested.

## Provenance

- P538A: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539A-readonly-per-draw-replay-export/outputs/research/p538a_strategy_candidate_evaluation_readiness_20260709.json` (sha256 `b05a9c6cb5f8da1c...`)
- P537A: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539A-readonly-per-draw-replay-export/outputs/research/p537a_shortlist_robustness_review_20260709.json` (sha256 `a2e5658ef40462d9...`)
- P536K: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539A-readonly-per-draw-replay-export/outputs/research/p536k_lift_candidate_shortlist_20260708.json` (sha256 `07de31005900cce5...`)
- P536C: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539A-readonly-per-draw-replay-export/outputs/research/p536c_success_matrix_lift_extension_20260708.json` (sha256 `e98443bbe549ec23...`)
- new_rows_data_hash_sha256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

## Limitations

- Retrospective replay source export only; does not imply future performance.
- Does not compute any rolling/out-of-sample statistical test itself.
- hit_count/special_hit on exported rows reflect each bet row's full predicted_numbers list at ingestion time, not a pick_k-limited selection.
- schema_sample_rows_illustrative_only rows are already covered by P536C's committed replayed window and carry no new temporal information.

