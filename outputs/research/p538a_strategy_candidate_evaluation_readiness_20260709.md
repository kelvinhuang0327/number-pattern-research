# P538A — Strategy Candidate Evaluation Readiness

> Historical replay review artifact only; not a prediction, betting edge, future-winning, or production-readiness claim.

Source task ids: **P537A, P536K, P536C**
Generated at: `2026-07-09T03:54:18.970763+00:00`

## Artifact Schema Capability Map

### P537A (`outputs/research/p537a_shortlist_robustness_review_20260709.json`)

- task_id: **P537A**, generated_at: `2026-07-09T02:23:29.040633+00:00`
- sections:
  - `stable_candidates_for_owner_review`: 177 rows
  - `short_window_spike_caution_list`: 90 rows
  - `combination_candidates_for_followup`: 102 rows
  - `cross_lottery_candidates_for_followup`: 60 rows
  - `insufficient_or_ambiguous_candidates`: 31 rows

### P536K (`outputs/research/p536k_lift_candidate_shortlist_20260708.json`)

- task_id: **P536K**, generated_at: `2026-07-08T13:12:26.151998+00:00`
- sections:
  - `stable_300_750_review_candidates`: 177 rows
  - `short_window_spike_review_candidates`: 90 rows
  - `combination_review_candidates`: 133 rows
  - `cross_lottery_review_candidates`: 60 rows

### P536C (`outputs/research/p536c_success_matrix_lift_extension_20260708.json`)

- task_id: **P536C**, generated_at: `2026-07-08T07:42:01.782116+00:00`
- sections:
  - `strategy_pick_matrix_lift_extension`: 603 rows
  - `cross_lottery_normalized_lift`: 195 rows
  - `combination_leaderboard_with_lift`: 510 rows
  - `combination_stability_rank`: 170 rows

## Candidate Groups For Next-Stage Review

### stable_review_candidates (count=177)

- source field in P537A: `stable_candidates_for_owner_review`
- lottery_type_breakdown: {'BIG_LOTTO': 62, 'DAILY_539': 62, 'POWER_LOTTO': 53}
- distinct_strategy_id_count: 31
- distinct_feature_families: ['acb', 'cold', 'deviation', 'echo', 'entropy', 'fourier', 'frequency', 'markov', 'orthogonal', 'other', 'precision', 'ts3', 'zone']
- distinct_windows: [300, 750]

### short_window_spike_cautions (count=90)

- source field in P537A: `short_window_spike_caution_list`
- lottery_type_breakdown: {'BIG_LOTTO': 42, 'DAILY_539': 36, 'POWER_LOTTO': 12}
- distinct_strategy_id_count: 31
- distinct_feature_families: ['acb', 'cold', 'deviation', 'echo', 'entropy', 'fourier', 'markov', 'orthogonal', 'other', 'precision', 'ts3', 'zone']
- distinct_windows: [50]

### combination_followup_candidates (count=102)

- source field in P537A: `combination_candidates_for_followup`
- lottery_type_breakdown: {'BIG_LOTTO': 26, 'DAILY_539': 32, 'POWER_LOTTO': 44}
- distinct_combo_id_count: 102

### cross_lottery_followup_candidates (count=60)

- source field in P537A: `cross_lottery_candidates_for_followup`
- lottery_type_participation_counts: {'BIG_LOTTO': 45, 'DAILY_539': 60, 'POWER_LOTTO': 45}
- distinct_feature_families: ['cold', 'fourier', 'markov', 'orthogonal']
- distinct_windows: [50, 300, 750]

### insufficient_context_candidates (count=31)

- source field in P537A: `insufficient_or_ambiguous_candidates`
- lottery_type_breakdown: {'BIG_LOTTO': 17, 'DAILY_539': 10, 'POWER_LOTTO': 4}
- distinct_combo_id_count: 31

## Rolling / Out-of-Sample Feasibility

| group | feasible directly | feasible via join to P536C | join target |
|---|---|---|---|
| stable_review_candidates | False | True | P536C.strategy_pick_matrix_lift_extension |
| short_window_spike_cautions | False | True | P536C.strategy_pick_matrix_lift_extension |
| combination_followup_candidates | False | True | P536C.combination_leaderboard_with_lift |
| cross_lottery_followup_candidates | False | False | None |
| insufficient_context_candidates | False | False | None |

> No committed artifact among P537A/P536K/P536C contains per-draw outcome rows (one row per target_draw with hit/miss). All feasibility above is about whether a draw-range cutoff can be recovered to avoid lookahead when defining a new OOS window -- not about whether the OOS window can actually be computed from these artifacts alone. Actually running a new rolling/OOS window always requires a further read-only DB export scoped to target_draw values after the recovered cutoff, which this task does not perform (no DB open permitted).

## Missing Fields Or Blockers

| required field | stable/spike | combination | cross-lottery |
|---|---|---|---|
| strategy / family / combo identity | True | True | True |
| lottery_type | True | True | False |
| window | True | True | True |
| target draw or draw index | False | False | False |
| observed rate / baseline / lift | True | True | True |
| support / sample size | True | True | True |
| source artifact data_hash / provenance | True | True | True |
| temporal information to avoid lookahead leakage | False | False | False |

### Hard Blockers

- No per-draw outcome rows (one row per target_draw with hit/miss) exist in any of P537A/P536K/P536C; only pre-aggregated window-level rates. A new rolling/OOS window cannot be computed from these three artifacts alone regardless of identity/draw-range availability.
- cross_lottery_followup_candidates rows lose strategy_id and target_draw range entirely during upstream aggregation in P536C; this group is not traceable back to a single walk-forward-able series without a new aggregation-identity task.
- insufficient_context_candidates rows are excluded specifically because a required upstream metric (avg_prize_signal_lift_across_present_windows) is null; this is an upstream data gap in P536K/P536C, not something this read-only readiness pass can resolve.
- target_draw range (earliest_target_draw/latest_target_draw) is present in upstream P536C rows but is not carried into the P536K/P537A shortlist/review rows -- any consumer of P537A alone would need to re-join to P536C to know where a new OOS window could safely start.

## Recommended Next Single-Worker Task

- proposed_task_id: **P539A (proposed, not yet authorized)**
- title: Read-only per-draw replay export for stable/combination candidate draw-range cutoffs
- scope: Open lottery_api/data/lottery_v2.db read-only (sqlite3 URI mode=ro + PRAGMA query_only=ON, matching P536C's own source.db_open_mode) and, restricted to the strategy_ids/combo_ids already present in P537A's stable_review_candidates and combination_followup_candidates groups, export one row per target_draw (hit/miss, prize_signal boolean) for target_draw values strictly after each candidate's earliest/latest_target_draw range recovered from P536C -- to check whether enough NEW draws now exist to support even a first out-of-sample window (P536C's own window_policy.minimum_support_draws=30).
- why_smallest_next_step: This answers the binary question 'is OOS evaluation possible today' before any actual walk-forward statistical test is attempted, and stays strictly read-only (no DB write, no new strategy, no promotion gate) -- consistent with this task's own DB-write prohibition, which is why it is proposed rather than executed here.
- excluded_from_this_proposed_task:
  - cross_lottery_followup_candidates (no recoverable strategy identity; needs a separate aggregation-identity task first)
  - insufficient_context_candidates (blocked on an upstream P536K/P536C metric gap, not a DB export)

## Provenance & Limits

- replay_data_hash_chain.verified_equal_across_all_three: **True**
- P537A file_sha256: `a2e5658ef40462d9e9bf5aac5429e9acc965f3b6ac2439a9d3e49492fe946a56`
- P536K file_sha256: `07de31005900cce5192597ff48f684078a9b3a699aa8dd8320b98be06b62b768`
- P536C file_sha256: `e98443bbe549ec23d46187689bd810423bfa07d2626fa2b98d919c96b54ac316`
- selection_method: Descriptive read-only synthesis over fields already present in the committed P537A/P536K/P536C artifacts only. No database access, no route/API/UI change, no new statistical metric, and no artifact regeneration -- every count and sample row is copied verbatim or derived by simple counting/grouping over existing fields. Feasibility findings are computed by checking for field presence in the loaded artifacts, not asserted from memory.
- limitations:
  - Retrospective replay evidence only; does not imply future performance.
  - This artifact does not open the database, does not recompute P536C/P536K/P537A, and does not perform any rolling/out-of-sample statistical test itself -- it only assesses whether the committed artifacts contain enough fields to attempt one.
  - candidate_groups_for_next_stage_review samples are the first rows in each source section's existing order, not a re-ranking by any new or existing metric.
  - rolling_or_out_of_sample_feasibility describes whether a draw-range cutoff can be recovered to avoid lookahead, not whether an OOS window can actually be computed from these three artifacts alone -- that always requires a further read-only DB export, proposed but not performed here.

> Historical replay review artifact only; not a prediction, betting edge, future-winning, or production-readiness claim.

