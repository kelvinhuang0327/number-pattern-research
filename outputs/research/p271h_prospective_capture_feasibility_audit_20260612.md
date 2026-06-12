# P271H Prospective Capture Feasibility Audit

## 1. Executive summary

**Final classification:** `P271H_PROSPECTIVE_CAPTURE_BLOCKED_SCHEMA_OR_CAUSALITY_GAP`.

The repository has useful fragments: prediction run/item/result tables, a target-draw schedule table, storage timestamps, a controlled legacy apply script, and a separate result table. Those fragments do not form an enforceable P271G prospective population. The persisted prediction rows lack `target_draw`, draw-close instants, protocol and activation membership, an atomic prospective identity, append-only protection, and a per-ticket POWER second-zone requirement.

The current ingest route also references `engine.prediction_tracker` and `engine.snapshot_scheduler`, but both modules are absent from the current tree. Their last tracked implementation inferred the next draw numerically, allowed reconstructed snapshots, lacked authoritative close-time causality, and was not suitable for confirmatory capture.

## 2. Audit boundaries and non-actions

This was a read-only source, schema, configuration, git-history, and bounded structural-metadata audit. No runtime, schema, database, prediction, replay, scorer, adapter, strategy, API, frontend, package, pytest, or CI behavior was changed.

- No prospective collection was activated.
- PENDING_P271G_MERGE_TIMESTAMP was not changed.
- No baseline or statistical analysis was run.
- No prediction outcome metrics were read or calculated.
- No row-level prediction or result data was exported.
- DB access, if used, was read-only.
- No DB/schema/runtime code was modified.
- Existing scorer, adapter, replay, strategy, API, and frontend behavior remain unchanged.
- P270C remains unauthorized.
- Official source status remains MANUAL_VERIFICATION_REQUIRED.

## 3. P271G activation context

P271G merged in PR #424 at `2026-06-12T15:47:00Z`, merge commit `369354787009ffe65f3f99ca47d8f00f7a693c23`. That merge is context, not activation.

This audit records `prospective_prediction_start_at=PENDING_SEPARATE_ACTIVATION_TASK`. A future start cannot precede a separate activation artifact's merge timestamp, and that artifact may merge only after the capture implementation, schema migration, deployment, and fail-closed guards are verified. Every prediction before that later activation remains retrospective.

## 4. Current prediction-generation flow

1. `POST /api/predict` and `POST /api/predict-from-backend` return generated predictions but do not persist a prospective record.
2. `tools/quick_predict.py --dry-run` reads history through SQLite URI `mode=ro`, computes a next-draw label by numeric suffix increment, and emits a JSON artifact.
3. `scripts/p4c3_supported_prediction_apply.py --apply` can convert approved artifacts into `prediction_runs` and `prediction_items`. It uses `BEGIN IMMEDIATE`, but persists no direct target draw, close time, protocol membership, or activation version.
4. The deleted historical scheduler/tracker modules once created snapshots and resolved results. `lottery_api/routes/ingest.py` still imports them after draw ingestion, so those hooks currently fail into warning handling.
5. Replay apply/backfill scripts populate a retrospective store and are not an eligible prospective capture path.

## 5. Current persistence and schema

`prediction_runs` stores lottery, latest-known draw/date, strategy label, free-form provenance, snapshot source, and `created_at`. It does not store the target draw or P271G membership fields.

`prediction_items` stores run, bet index, numbers, nullable special value, status, and `created_at`. It has no unique `(run_id, bet_index)` constraint and no conditional POWER requirement.

`prediction_results` is separate and uniquely keyed by item, which is a useful outcome-separation primitive.

`snapshot_schedule` uniquely keys `(lottery_type, target_draw)`, but has only a target date and scheduling timestamp. It has no close instant, timezone, source version, or immutability control.

`strategy_prediction_replays` is retrospective, mutable, and co-locates prediction and actual-result payloads. It must not become the confirmatory population.

## 6. Prediction identity and uniqueness

Current status: **BLOCKED**.

The database has row ids, run ids, and bet indices, but the persisted production prediction has no immutable target draw or source/version identity. The controlled apply fingerprint is stored in mutable text and checked before the write on a separate read-only connection. It is not an atomic semantic uniqueness guarantee.

The future semantic key should include activation version, lottery type, canonical target draw, source/version, strategy/version, and ticket identity. `prediction_created_at` and a content hash must be retained immutably. A database unique constraint must close concurrent races.

## 7. Timestamp and draw-close causality

Current status: **BLOCKED**.

Storage timestamps exist, but they do not prove a prediction existed before close. There is no `draw_close_at`, no official-source-backed resolver, no exception calendar, and no fail-closed comparison. Draw dates and weekday inference cannot establish causality.

The future capture service must require an application-supplied `prediction_created_at_utc`, resolve an authoritative `draw_close_at_utc`, and reject unless the former is strictly earlier.

## 8. Timezone semantics

Current status: **BLOCKED**.

The system mixes SQLite `CURRENT_TIMESTAMP`, local `astimezone()` output, UTC `Z` artifacts, and naive draw dates. The required contract is: resolve official schedules in `Asia/Taipei`, convert both instants to UTC, persist canonical timezone-aware strings, and reject naive or ambiguous inputs.

## 9. Immutability and amendment paths

Current status: **BLOCKED**.

No database trigger prevents update or deletion of prediction payloads. Existing code contains status updates, metadata updates, replay timestamp backfills, rollback deletes, reconstructed snapshots, and broad administrative deletion. Those operations are legitimate in their historical contexts, but demonstrate that current tables are not an immutable confirmatory ledger.

Use new append-only prospective batch, ticket, and event tables. Reject `UPDATE` and `DELETE` with triggers. Corrections must become new ineligible amendment events that preserve and invalidate, never replace, the original.

## 10. Outcome-ingestion separation

Current status: **PARTIAL**.

Prediction and result payloads have separate tables, and generation does not need result fields. However, prediction rows do not carry an authoritative target or frozen membership before resolution. The current resolver module is absent; its last implementation selected the first numerically later draw rather than joining an immutable target.

Future result linkage must use the immutable ticket identity after eligibility is frozen. Actual-result fields must never be accepted by the capture service.

## 11. POWER second-zone preservation

Current status: **BLOCKED**.

`prediction_items.special` is nullable and has no conditional constraint. Bounded structural inspection found that most existing POWER items lack this value. The last scheduler implementation attached one shared special value only to the first ticket.

Every eligible POWER ticket must carry a prediction-time second-zone value plus source/version provenance. Missing values must invalidate the affected target-draw cluster; they must never be filled from the result or a later fallback.

## 12. Prospective membership model

Current status: **BLOCKED**.

No table persists preregistration version, prospective protocol version, activation version, immutable eligibility, or rejection reason. Free-form notes are insufficient.

The preferred design is a separate append-only ledger:

- batch: activation/protocol versions, lottery, target draw, close instant, source snapshot and deployment identity;
- ticket: bet identity, prediction payload, POWER second zone, creation instant, content hash;
- event: capture, rejection, amendment, invalidation, and later outcome-link events.

Eligibility is computed once, before outcomes, and never upgraded later.

## 13. Draw-cluster construction

Current status: **PARTIAL**.

`snapshot_schedule` and replay rows support `(lottery_type, target_draw)`, but production prediction rows require a derivation from `latest_known_draw`. Numeric `+1` is not an authoritative draw identity across exceptions or malformed inputs.

Persist the canonical target directly on every prospective batch and ticket. Validate it through the versioned schedule resolver. The confirmatory cluster key is exactly lottery type plus target draw.

## 14. Backfill and contamination risks

Current status: **BLOCKED**.

Historical code supports `RECONSTRUCTED`, manual apply, backfill, repair, timestamp update, and rollback paths. No field or constraint permanently excludes those records from a future prospective label.

Only `LIVE_PRE_CLOSE` capture after activation may be eligible. `MANUAL`, `RECONSTRUCTED`, `BACKFILL`, post-close, unknown-schedule, and ambiguous-time attempts must be stored only as immutable rejections or omitted from the prospective payload tables.

## 15. Concurrency and transaction risks

Current status: **PARTIAL**.

`BEGIN IMMEDIATE` in the controlled apply path is useful. The duplicate preflight occurs on a separate read-only connection, though, and no matching database unique key closes the time-of-check/time-of-use race.

The future service needs one transaction, foreign keys enabled, a busy timeout, an atomic semantic unique constraint, deterministic conflict handling, and synthetic concurrent-writer tests.

## 16. Readiness matrix

| Dimension | Status |
|---|---|
| identity | BLOCKED |
| timestamp availability | PARTIAL |
| authoritative draw-close resolution | BLOCKED |
| timezone normalization | BLOCKED |
| database uniqueness | PARTIAL |
| application duplicate prevention | PARTIAL |
| immutability | BLOCKED |
| update/amendment protection | BLOCKED |
| outcome separation | PARTIAL |
| POWER second zone | BLOCKED |
| prospective membership | BLOCKED |
| draw clustering | PARTIAL |
| audit trail | PARTIAL |
| backfill exclusion | BLOCKED |
| concurrent-write safety | PARTIAL |
| activation mechanism | BLOCKED |

No dimension is marked READY merely because a similarly named field exists.

## 17. Required implementation controls

1. Add separate append-only prospective batch, ticket, and event tables.
2. Persist canonical target, prediction and close instants, source/strategy versions, protocol/activation versions, eligibility, rejection reason, and content hashes.
3. Add atomic semantic uniqueness and one-transaction capture.
4. Reject updates and deletes with database triggers.
5. Add an official-source-verified, exception-aware `Asia/Taipei` draw-close resolver.
6. Enforce strict pre-close UTC causality.
7. Require second-zone values on every eligible POWER ticket.
8. Freeze membership before any outcome link.
9. Permanently exclude reconstructed, manual, backfill, post-close, duplicate, and ambiguous captures.
10. Record actor/service, source artifact, code/deployment commit, schedule version, activation artifact, and transaction provenance.
11. Pass synthetic migration, race, boundary, immutability, POWER, and contamination tests before any production migration.
12. Keep implementation, migration execution, deployment, and activation as separate authorization gates.

## 18. Proposed activation sequence

1. Authorize a schema/runtime implementation task that does not activate collection.
2. Implement the ledger, resolver, worker, and synthetic/temp-copy tests.
3. Separately authorize and execute the additive production migration.
4. Deploy the capture implementation disabled and verify schema, constraints, close-time resolution, and no-write preflight.
5. Merge a separate activation artifact naming the deployed commit and verification evidence.
6. Set the earliest allowed start to that activation artifact's merge timestamp, never the P271G merge timestamp alone.
7. Enable capture only after the activation artifact is merged; fail closed on any verification drift.

## 19. Recommended next task whitelist

The proposed next task is `SEPARATE_PROSPECTIVE_CAPTURE_IMPLEMENTATION_TASK_PENDING_USER_AUTHORIZATION`. It should be limited to the new capture service, draw-close resolver, additive schema definition and migration implementation, one-shot disabled worker, versioned schedule configuration, synthetic tests, implementation evidence, and minimal governance updates.

Every production/runtime/schema path in that proposed whitelist requires separate explicit authorization. Migration execution, deployment, and activation remain outside that task.

## 20. Final classification

`P271H_PROSPECTIVE_CAPTURE_BLOCKED_SCHEMA_OR_CAUSALITY_GAP`

Schema change required: **YES**. Runtime code change required: **YES**. Activation mechanism verdict: **BLOCKED** until a separately authorized implementation, migration, deployment verification, and activation artifact complete.

Current governance remains **HOLD / WAITING_FOR_USER_AUTHORIZATION**. The next round is not allowed without explicit authorization.
