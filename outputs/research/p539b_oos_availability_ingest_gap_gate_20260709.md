# P539B — OOS Availability / Ingest-Gap Gate

> Historical replay availability gate only; not a prediction, betting edge, future-winning, or production-readiness claim.

Upstream: P539A, P538A, P537A, P536K, P536C, P333

## OOS Feasibility Summary

- feasible_now: `False`
- classification: `blocked_needs_readonly_ingest_gap_audit`
- note: Rolling/OOS evaluation is NOT feasible today for any candidate. New official draws already exist in the raw draws table beyond every candidate's recovered replay cutoff for at least one lottery, but zero of those draws have been run through strategy replay/prediction generation, so P539A's per-draw source table (strategy_prediction_replays) still has no post-cutoff rows. The primary blocker is therefore a replay-generation gap between the raw draws table and the strategy_prediction_replays table, not an absence of new lottery draws.
- caveat: P539A's own readiness.new_draws_found_since_last_replay_cutoff=false is accurate only for the strategy_prediction_replays table; it should not be read as 'no new lottery draws have occurred' -- see new_draw_availability_by_lottery for the draws-table cross-check.

- **BIG_LOTTO**: `blocked_needs_readonly_ingest_gap_audit` — 12 new official draw(s) already exist beyond the replay cutoff but have never been run through strategy replay/prediction generation; even after generation, this is short of P536C's minimum_support_draws floor -- both replay generation and further new draws are needed.
- **DAILY_539**: `blocked_needs_readonly_ingest_gap_audit` — 42 new official draw(s) already exist beyond the replay cutoff and already meet P536C's minimum_support_draws floor, but none have been run through strategy replay/prediction generation yet -- the blocker is a replay-generation gap, not a shortage of new draws.
- **POWER_LOTTO**: `blocked_needs_readonly_ingest_gap_audit` — 13 new official draw(s) already exist beyond the replay cutoff but have never been run through strategy replay/prediction generation; even after generation, this is short of P536C's minimum_support_draws floor -- both replay generation and further new draws are needed.

## New Draw Availability By Lottery

- **BIG_LOTTO**: draws.max_draw=`115000067`, replay.max_target_draw=`115000055`, new_beyond_all_candidates_cutoff=`12`, meets_minimum_support_draws_if_replayed=`False`
- **DAILY_539**: draws.max_draw=`115000163`, replay.max_target_draw=`115000121`, new_beyond_all_candidates_cutoff=`42`, meets_minimum_support_draws_if_replayed=`True`
- **POWER_LOTTO**: draws.max_draw=`115000054`, replay.max_target_draw=`115000041`, new_beyond_all_candidates_cutoff=`13`, meets_minimum_support_draws_if_replayed=`False`

## Missing Data / Ingest Gaps

- **BIG_LOTTO** (`replay_generation_gap`): 12 official draw(s) already ingested into the `draws` table (up to draw 115000067) beyond every candidate's recovered replay cutoff (max_latest=115000055), but strategy_prediction_replays.MAX(target_draw) for this lottery is still 115000055. No strategy replay/prediction row has ever been generated for these draws.
- **DAILY_539** (`replay_generation_gap`): 42 official draw(s) already ingested into the `draws` table (up to draw 115000163) beyond every candidate's recovered replay cutoff (max_latest=115000121), but strategy_prediction_replays.MAX(target_draw) for this lottery is still 115000121. No strategy replay/prediction row has ever been generated for these draws.
- **POWER_LOTTO** (`replay_generation_gap`): 13 official draw(s) already ingested into the `draws` table (up to draw 115000054) beyond every candidate's recovered replay cutoff (max_latest=115000041), but strategy_prediction_replays.MAX(target_draw) for this lottery is still 115000041. No strategy replay/prediction row has ever been generated for these draws.

## Minimum Data Needed For P539C / OOS Evaluator

- **BIG_LOTTO**:
  - Run strategy replay/prediction generation for the existing 12 new official draw(s) (target_draw > 115000055) for this lottery's candidate strategies, so strategy_prediction_replays gains post-cutoff rows -- this is a distinct, separately-authorized task, not part of this read-only gate.
  - Wait for 18 more official draw(s) to be ingested (minimum_support_draws=30 per P536C's window_policy).
- **DAILY_539**:
  - Run strategy replay/prediction generation for the existing 42 new official draw(s) (target_draw > 115000121) for this lottery's candidate strategies, so strategy_prediction_replays gains post-cutoff rows -- this is a distinct, separately-authorized task, not part of this read-only gate.
- **POWER_LOTTO**:
  - Run strategy replay/prediction generation for the existing 13 new official draw(s) (target_draw > 115000041) for this lottery's candidate strategies, so strategy_prediction_replays gains post-cutoff rows -- this is a distinct, separately-authorized task, not part of this read-only gate.
  - Wait for 17 more official draw(s) to be ingested (minimum_support_draws=30 per P536C's window_policy).

## Recommended Next Single-Worker Task

- proposed_task_id: `P539C (proposed, not yet authorized)`
- title: Read-write strategy replay/prediction generation for existing new draws
- scope: For each lottery with new_official_draws_beyond_all_candidates_cutoff > 0 (see new_draw_availability_by_lottery), run the existing replay/prediction generation pipeline for the shortlisted candidate strategy_ids against the specific new target_draw values already present in the `draws` table, writing new rows into strategy_prediction_replays. This is a DB-write task and requires its own explicit canonical-DB-write authorization; it is proposed here, not executed.

## Provenance

- P539A: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539B-oos-availability-ingest-gap-gate/outputs/research/p539a_readonly_per_draw_replay_export_20260709.json` (sha256 `d104c47122a33d6d...`)
- P538A: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539B-oos-availability-ingest-gap-gate/outputs/research/p538a_strategy_candidate_evaluation_readiness_20260709.json` (sha256 `b05a9c6cb5f8da1c...`)
- P537A: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539B-oos-availability-ingest-gap-gate/outputs/research/p537a_shortlist_robustness_review_20260709.json` (sha256 `a2e5658ef40462d9...`)
- P536K: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539B-oos-availability-ingest-gap-gate/outputs/research/p536k_lift_candidate_shortlist_20260708.json` (sha256 `07de31005900cce5...`)
- P536C: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539B-oos-availability-ingest-gap-gate/outputs/research/p536c_success_matrix_lift_extension_20260708.json` (sha256 `e98443bbe549ec23...`)
- db_unchanged: `True`

## Limitations

- Availability gate only; does not compute any rolling/out-of-sample statistical test.
- Does not rank, score, or promote any strategy.
- additional_official_draws_needed_to_reach_minimum_support_draws assumes all new draws would be usable once replayed; does not account for any candidate-specific exclusion that might apply once replay rows actually exist.
- Retrospective availability snapshot as of generated_at; re-run after any new ingestion or replay-generation run.

