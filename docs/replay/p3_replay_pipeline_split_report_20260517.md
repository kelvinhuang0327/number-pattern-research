# P3 Replay Pipeline Split Report - 20260517

Generated at: `2026-05-17T08:24:42.352876+00:00`

## Final Classification
P3_REPLAY_PIPELINE_SPLIT_COMPLETED

## P0/P1 Input Summary
- Total strategies: **506**
- Lifecycle breakdown: PRODUCTION 68, WATCHING 7, PROVISIONAL 6, REJECTED 90, OFFLINE 0, EXPERIMENTAL 307, UNKNOWN 28
- Replay coverage gap: 13 strategies with replay rows, 86 with historical records but no replay, 407 with no records anywhere
- P1 lifecycle states: PRODUCTION / WATCHING / PROVISIONAL / REJECTED / OFFLINE / EXPERIMENTAL / UNKNOWN

## Blocking Map
- `lottery_api/routes/replay.py`
  - Current assumption: history, summary, and fixture paths are handled as one replay surface with lifecycle filtering but no explicit pipeline split.
  - Why it mixes reconstruction / waiting: The endpoint can show historical rows and fixture rows, yet it does not distinguish historical reconstruction from future draw waiting.
  - Recommended split: Keep the endpoint read-only, but attach pipeline classification metadata so historical reconstruction and future waiting are rendered as separate concerns.
  - Risk level: MEDIUM | Code change required: NO_FOR_P3_DRY_RUN
- `scripts/p6_next_draw_watcher_readonly.py`
  - Current assumption: Watcher output represents pending prediction_items awaiting official draw publication.
  - Why it mixes reconstruction / waiting: If reused as replay evidence, it collapses future waiting into historical coverage accounting.
  - Recommended split: Keep it as FUTURE_WAITING only and exclude it from historical replay coverage denominators.
  - Risk level: LOW | Code change required: NO
- `scripts/p3_retrospective_regeneration_dryrun.py`
  - Current assumption: Retrospective regeneration already behaves like historical replay reconstruction, but only as a dry-run utility.
  - Why it mixes reconstruction / waiting: The script name and surrounding docs can be read as a replay regeneration path rather than a pure historical reconstruction lane.
  - Recommended split: Classify its outputs as HISTORICAL_RECONSTRUCTION and keep its result dry-run only.
  - Risk level: LOW | Code change required: NO
- `scripts/replay_lifecycle_drift_guard.py`
  - Current assumption: The drift guard validates database row distribution only and is intentionally blind to pipeline semantics.
  - Why it mixes reconstruction / waiting: It can be mistakenly treated as replay coverage logic even though it only guards baseline drift.
  - Recommended split: Leave drift guarding separate from pipeline classification; use the P3 classifier for coverage splits.
  - Risk level: LOW | Code change required: NO
- `docs/replay/strategy_historical_replay_roadmap_20260515.md`
  - Current assumption: The roadmap interleaves lifecycle, replay, and waiting-state language in one planning document.
  - Why it mixes reconstruction / waiting: The same doc describes historical replay coverage and waiting-for-draw monitoring, which obscures the product split.
  - Recommended split: Use a dedicated historical reconstruction policy and keep future waiting in operational watcher docs.
  - Risk level: LOW | Code change required: NO

## Pipeline Split Result
- HISTORICAL_RECONSTRUCTION: 97
- FUTURE_WAITING: 2
- DISPLAY_ONLY: 407
- UNSUPPORTED: 0

## Future Waiting Summary
- Count: 2
- These strategies are waiting on official draw publication and do not block historical coverage.

## Display-Only / Unsupported Summary
- DISPLAY_ONLY: 407
- UNSUPPORTED: 0

## Top Historical Reconstruction Candidates
- `acb_1bet` | PRODUCTION | DAILY_539 | prediction_runs | historical_record_source=prediction_runs; dry_run_only
- `daily539_f4cold` | PRODUCTION | DAILY_539 | prediction_runs | historical_replay_rows_present; eligible_for_dry_run_reconstruction_baseline
- `daily539_markov_cold` | PRODUCTION | DAILY_539 | prediction_runs | historical_replay_rows_present; eligible_for_dry_run_reconstruction_baseline
- `f4cold_5bet` | PRODUCTION | DAILY_539 | prediction_runs | historical_record_source=prediction_runs; dry_run_only
- `p1_deviation_2bet_539` | PRODUCTION | DAILY_539 | prediction_runs | historical_replay_rows_present; eligible_for_dry_run_reconstruction_baseline
- `biglotto_2bet_deviation_complement` | PRODUCTION | BIG_LOTTO | simulation_log | historical_record_source=simulation_log; dry_run_only
- `biglotto_2bet_fourier_rhythm` | PRODUCTION | BIG_LOTTO | simulation_log | historical_record_source=simulation_log; dry_run_only
- `biglotto_3bet_triple_strike_v2` | PRODUCTION | BIG_LOTTO | simulation_log | historical_record_source=simulation_log; dry_run_only
- `biglotto_4bet_ts3_markov_w30` | PRODUCTION | BIG_LOTTO | simulation_log | historical_record_source=simulation_log; dry_run_only
- `biglotto_5bet_ts3_markov_freq` | PRODUCTION | BIG_LOTTO | simulation_log | historical_record_source=simulation_log; dry_run_only

## Safety Confirmation
- No DB writes
- No draw imports
- No replay rows generated
- No prediction updates
- No strategy execution

## Next Step
Proceed to P4 replay page product acceptance, or move to P5 persistence/deployment source-of-truth decision after CTO review.
