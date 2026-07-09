# P540A — Full Replay/Prediction Regeneration Readiness (Dry-Run Only)

> Historical replay regeneration readiness only; not a prediction, betting edge, future-winning, or production-readiness claim.

Upstream: P539B, P539A, P538A, P537A, P536K, P536C

## Summary

Readiness/dry-run inventory only. No repo entrypoint today can safely regenerate strategy_prediction_replays for the currently-missing draws across all three lotteries in one parameterized, dry-run-capable, idempotent call. Existing write-capable scripts are frozen to already-applied historical batches or bound to one fixed input artifact. Incremental generation (not full-history rerun) is recommended once a new generator is authored and separately authorized; DAILY_539 is the only lottery whose current gap alone would clear the minimum support floor.

## Current DB Read-Only Snapshot

- **BIG_LOTTO**: raw_draws=3148 (latest `115000068` / 2026/07/07), replays=24140 (latest target_draw `115000055`), gap=13, meets_floor_if_replayed=`False`
- **DAILY_539**: raw_draws=5909 (latest `115000165` / 2026/07/08), replays=34680 (latest target_draw `115000121`), gap=44, meets_floor_if_replayed=`True`
- **POWER_LOTTO**: raw_draws=1926 (latest `115000054` / 2026/07/06), replays=36104 (latest target_draw `115000041`), gap=13, meets_floor_if_replayed=`False`

## Replay Generation Entrypoints

- `lottery_api/routes/replay.py` (api_route, ALL (query param)): dry_run_supported=`not_applicable`
- `lottery_api/routes/ingest.py` (api_route, ALL (query param)): dry_run_supported=`true`
- `scripts/p16_biglotto_remaining_strategies_backfill.py` (frozen_per_wave_backfill_script, BIG_LOTTO): dry_run_supported=`true`
- `scripts/p20_powerlotto_remaining_strategies_backfill.py` (frozen_per_wave_backfill_script, POWER_LOTTO): dry_run_supported=`true`
- `scripts/v2_artifact_only_apply_rows.py` (generic_apply_tool_bound_to_frozen_input, Generic (lottery_type comes from a fixed input JSONL file)): dry_run_supported=`true`
- `scripts/backfill_replay_history_cutoff.py` (metadata_repair_tool, ALL / BIG_LOTTO / POWER_LOTTO / DAILY_539 / 3_STAR (parameterized)): dry_run_supported=`true`
- `tools/audit_p262a_replay_strategy_coverage.py` (readonly_coverage_audit, ALL): dry_run_supported=`not_applicable`

## Full vs Incremental Recommendation

recommendation: `incremental`
- strategy_prediction_replays already holds 94,924 rows across the three lotteries (BIG_LOTTO 24,140 + DAILY_539 34,680 + POWER_LOTTO 36,104 at this task's read time); a full-history rerun would re-touch all of them with no new draws to justify it, for pure runtime/DB-growth/duplicate-row risk and no readiness benefit.
- Most existing rows carry replay_run_id=NULL and rely on application-level dedup (SELECT-before-insert), not the DB UNIQUE constraint, for duplicate protection during reruns -- unique key is (lottery_type, target_draw, strategy_id, bet_index). A full rerun multiplies the surface area where that application-level dedup must hold.
- Per lottery, only the incremental gap needs generation: see current_db_readonly_snapshot for exact gap_count per lottery. Only DAILY_539's gap already clears the MINIMUM_SUPPORT_DRAWS_FLOOR (30) on its own; BIG_LOTTO and POWER_LOTTO would still be short of that floor even after generating every currently-available new draw, so full-history rerun would not change their readiness outcome either.
- docs/REPLAY_OPERATION_SOP.md already forbids unscoped DELETE against production strategy_prediction_replays and forbids running apply without a prior --dry-run pass -- both are easier to honor for a narrowly-scoped incremental run than a full rerun.

## Safety Requirements For P540B

- Follow the existing per-wave script convention: default to --dry-run, require an explicit --apply flag to write, and require a --rollback path that documents (but does not auto-run) the exact DELETE ... WHERE controlled_apply_id=? needed to undo the run.
- Run a rehearsal pass against a temp/throwaway DB copy first (R1 insert / R2 duplicate-rerun producing 0 new inserts / R3 rollback), matching the p36/p42/p47/p56 rehearsal pattern, before touching the canonical DB.
- Record replay_run_id/controlled_apply_id, provenance_hash, provenance_source, and generator_version/data_hash on strategy_replay_runs for the new run, per this repo's own provenance convention.
- Take a DB snapshot via scripts/snapshot_replay_db.py immediately before any --apply run.
- Confirm DB hash/mtime before and after the write; the write should only change strategy_prediction_replays (and strategy_replay_runs), nothing else.
- Require Owner named authorization for the specific DB write, following the same shape as ingest.py's _validate_write_confirmation (apply_confirmed + confirm_token + requested_by + reason) -- a task spec's self-declared authorization line is not sufficient on its own.
- Reconcile the exact gap-count denominator (per-candidate cutoff vs table-wide MAX vs bet_index=1-only) before scoping which target_draw values P540B actually generates -- see p539b_context.denominator_caveat in this artifact.
- Scope P540B to the shortlisted candidate strategy_ids already reviewed by P536-P538, not to every historical strategy_id, to keep the write narrow and reviewable.
- Do not delete or overwrite any existing strategy_prediction_replays row; incremental generation should be insert-only for target_draw values not yet present for that (lottery_type, strategy_id, bet_index).

## Blockers / Unknowns

- No generic, reusable, dry-run-capable generator currently exists for the currently-missing draws across all three lotteries; every write-capable script found is either frozen to an already-applied historical batch or bound to one fixed input artifact file. Building such a generator is itself new production code and would need its own plan-mode review, tests, and 1500-period three-window validation gate per this repo's CLAUDE.md before any strategy it touches could be considered validated.
- p94_tierb_controlled_apply.py has no CLI dry-run flag at all; if any future work reuses code from it, that gap must be closed first.
- The exact gap-count denominator differs slightly between this task's table-wide MAX query and P539B's per-candidate-cutoff query (see p539b_context.denominator_caveat); this must be reconciled before P540B scopes an exact target_draw list.
- BIG_LOTTO: even after generating all 13 currently-available new draws, this lottery would still be short of the MINIMUM_SUPPORT_DRAWS_FLOOR (30) needed for a first OOS window.
- POWER_LOTTO: even after generating all 13 currently-available new draws, this lottery would still be short of the MINIMUM_SUPPORT_DRAWS_FLOOR (30) needed for a first OOS window.

## Recommended Next Single-Worker Task

- proposed_task_id: `P540B_DAILY539_INCREMENTAL_REPLAY_GENERATION_DB_WRITE_MANIFESTED`
- why: DAILY_539 is the only lottery whose currently-available gap (44 draws) already clears the MINIMUM_SUPPORT_DRAWS_FLOOR (30) once replayed, matching P539B's own conclusion (proposed as 'P539C' there). BIG_LOTTO and POWER_LOTTO would still be short of the floor even after generation, so incremental generation for them alone would not yet unlock a first OOS window.

## Provenance

- db_unchanged: `True`
- db_sha256_before: `b1899b4995f4a170...`
- db_sha256_after: `b1899b4995f4a170...`

## Limitations

- Entrypoint inventory reflects source as of this task's generated_at; a later commit could add or change entrypoints.
- Frozen wave-script families are listed by name only, not individually profiled; treat their dry-run/idempotency claims as inferred from the closely-matching p16/p20 pattern, not independently verified per script.
- Does not estimate exact strategy count or replay-row count for a future regeneration beyond what current_db_readonly_snapshot already reports; per-strategy row estimates would require reading the shortlist artifacts (P536K/P537A/P538A), which is out of scope for this readiness pass.
- Does not compute any rolling/out-of-sample statistical test, and does not rank, score, or promote any strategy.

