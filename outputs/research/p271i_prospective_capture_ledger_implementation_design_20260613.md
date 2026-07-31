# P271I Prospective Capture Ledger Implementation Design

## 1. Executive summary

This is a design-only task. It produces an implementation-ready but non-executable architecture for a prospective prediction capture system that satisfies the merged P271G preregistration protocol and closes every gap recorded by the merged P271H feasibility audit (`P271H_PROSPECTIVE_CAPTURE_BLOCKED_SCHEMA_OR_CAUSALITY_GAP`).

The core proposal is a **separate, append-only prospective ledger** — activation registry, capture batches, per-ticket prediction ledger, an immutable event stream, and a separate outcome-link table — protected by a database-enforced semantic unique key, append-only triggers, a versioned authoritative draw-close resolver, strict timezone-aware pre-close causality, mandatory POWER second-zone values, and atomic fail-closed capture. No existing prediction, replay, or result table is reused as the confirmatory population.

Nothing here is executed. No schema, runtime code, migration, deployment, or prospective activation was created. `final_classification = P271I_PROSPECTIVE_CAPTURE_LEDGER_IMPLEMENTATION_DESIGN_COMPLETE`.

## 2. P271G/P271H context

P271G (merged PR #424) preregistered the null/prospective protocol and left `prospective_prediction_start_at = PENDING_P271G_MERGE_TIMESTAMP`; its merge is context, not activation. P271H (merged PR #425, merge commit `24c170759350ac756a2b20dc08817986cba3dcb0`) audited the current infrastructure and found it cannot enforce that protocol: no authoritative `draw_close_at`, no timezone-normalized pre-close gate, no `target_draw` on persisted prediction rows, no protocol/activation membership, no append-only protection, no atomic prospective identity, no hard backfill exclusion, and no per-ticket POWER second-zone requirement, while ingest still references deleted tracker/scheduler modules.

This task converts those blocking findings into an enforceable design. It does not fix them in code.

## 3. Non-actions and authorization boundary

- This is a design-only task.
- No prospective collection was activated.
- No activation timestamp was inserted.
- No DB was opened; no schema, runtime code, or migration was modified.
- No deployment was started.
- No baseline, statistical, scorer, adapter, or strategy comparison work was performed.
- No P271G or P271H artifact was changed.
- P270C remains unauthorized.
- P270A and P270B remain closed and were not reopened.
- Official source status remains MANUAL_VERIFICATION_REQUIRED.
- Implementation, migration, deployment, and activation remain separate authorization gates.

## 4. Current write-path constraints

Grounded in `lottery_api/database.py`, `lottery_api/routes/ingest.py`, and `scripts/p4c3_supported_prediction_apply.py`:

- `prediction_runs` has no `target_draw`, no `draw_close_at`, no protocol/activation membership, and no semantic unique key beyond an AUTOINCREMENT id.
- `prediction_items.special` is nullable with no conditional POWER constraint, and there is no `UNIQUE(run_id, bet_index)`.
- `snapshot_schedule` uniquely keys `(lottery_type, target_draw)` and has a target date, but no close instant, no timezone, and is mutable.
- `strategy_prediction_replays` is retrospective, mutable, and co-locates predicted and actual payloads.
- The controlled apply path opens a read-only `mode=ro` preflight, checks a fingerprint via `notes`/`review_json` `LIKE`, then inserts on a separate connection under `BEGIN IMMEDIATE` — with no matching database unique key, leaving a time-of-check/time-of-use race.
- `ingest.py` still imports `engine.prediction_tracker.resolve_pending` and `engine.snapshot_scheduler.ensure_next_schedule` inside try/except blocks that degrade to warnings; both modules are absent.
- `clear_all_data()` and `delete_draw()` issue `DELETE`, confirming the current tables are not append-only.

## 5. Proposed append-only ledger

Five new, separate, append-only tables (full column lists in the JSON `ledger_schema_design`):

- **`prospective_activation_registry`** — one immutable row per merged activation artifact; the only source of an active `activation_id` and `prospective_start_at_utc`.
- **`prospective_capture_batches`** — one immutable row per `(activation_id, lottery_type, target_draw)` cluster, carrying the resolved `draw_close_at_utc` and its source id/version.
- **`prospective_prediction_ledger`** — append-only per-ticket record; the primary confirmatory population. Columns include `ledger_id`, `activation_id`, `preregistration_version`, `prospective_protocol_version`, `lottery_type`, `target_draw`, `strategy_id`, `strategy_version`, `bet_index`, `predicted_main_numbers`, `predicted_second_zone`, `prediction_created_at_utc`, `draw_close_at_utc`, `eligibility_status`, `rejection_reason`, `source_provenance`, `payload_hash`, `created_by`, `recorded_at_utc`.
- **`prospective_capture_events`** — append-only capture/rejection/amendment/invalidation/outcome-link events with actor, service identity, code commit, source artifact hash, and transaction id.
- **`prospective_outcome_links`** — separate outcome linkage created only after draw completion; never writes predicted fields and never changes ledger membership.

The retrospective `strategy_prediction_replays` table is explicitly **not** reused.

## 6. Identity and uniqueness

Prospective identity is deterministic over the tuple `(activation_id, lottery_type, target_draw, strategy_id, strategy_version, bet_index)`. `ledger_id` is a deterministic function of that tuple, and `payload_hash` is a SHA-256 over the canonical prediction content. Uniqueness is enforced by a database `UNIQUE` constraint on that tuple — not by a preflight text search. A conflicting insert fails closed: it is rejected idempotently and recorded as a `DUPLICATE_IDENTITY` event; a second eligible row is never created.

## 7. Timestamp and draw-close authority

Every batch stores `draw_close_at_utc` resolved from a **versioned** authoritative source. Four source types are classified in the JSON `draw_close_source_contract` — official machine-readable (highest), official published schedule, repository-configured deterministic schedule, and manual (lowest) — each with authority level, provenance fields, versioning, refresh/failure behavior, timezone, a fail-closed rule, and whether confirmatory use is allowed. A manual close time can never silently become confirmatory. No official source is claimed as verified; status stays `MANUAL_VERIFICATION_REQUIRED`.

## 8. Timezone normalization

Official schedules are resolved in `Asia/Taipei`, then both `prediction_created_at_utc` and `draw_close_at_utc` are converted to canonical timezone-aware UTC instants before any comparison. Naive or ambiguous timestamps are rejected. A single comparison contract governs all persisted instants.

## 9. Causality gate

The gate is `prediction_created_at_utc < draw_close_at_utc`, evaluated on UTC instants with an explicit, conservative clock-skew margin subtracted from the close time. Missing timestamps fail closed. Ambiguous timezones fail closed. The authoritative close-time source is versioned, and a fallback or manually entered close time cannot silently become confirmatory. The capture service never queries any outcome/result table.

## 10. Immutability and amendments

The ledger, batch, and event tables are append-only, enforced by database `BEFORE UPDATE` and `BEFORE DELETE` triggers that `RAISE(ABORT)`. A prediction payload cannot change after insert. Amendments create a **new** append-only record/event that references the original; there is no update-in-place and no delete-and-reinsert replacement. The original remains auditable, an amended record is never silently substituted, and a post-close amendment is ineligible. `payload_hash` plus the append-only event stream provide tamper-evidence.

## 11. POWER second-zone enforcement

For POWER_LOTTO, `predicted_second_zone` is mandatory and must exist at prediction creation time. It cannot be filled later and cannot use the actual second-zone value. A missing or invalid value causes an ineligible rejection that invalidates the whole POWER target-draw cluster; it is never defaulted, inferred, or backfilled.

## 12. Prospective membership and backfill exclusion

Eligibility is computed exactly once, atomically at insert, before any outcome, and is never upgraded later. A row may be eligible only when an `activation_id` is active, the prediction was created after `prospective_start_at_utc`, the target draw is not closed, and the capture mode is `LIVE_PRE_CLOSE`. Historical, import, backfill, reconciliation, manual, and reconstructed rows can never enter the prospective population, and no later status change can convert a retrospective row into a prospective one.

## 13. Outcome separation

The prediction ledger contains no actual results. Result ingestion occurs in a separate path; analysis uses a read-only join after draw completion via `prospective_outcome_links`. Membership is frozen before outcome ingestion and cannot change afterward, and actual values can never populate predicted fields.

## 14. Draw clustering

The confirmatory cluster key is exactly `(lottery_type, target_draw)`, persisted directly on every batch and ticket and validated against the versioned authoritative schedule. There is no `latest_known_draw + 1` inference.

## 15. Concurrency and atomic multi-ticket writes

Capture runs in a single `BEGIN IMMEDIATE` transaction with foreign keys enabled and a busy timeout. Validation and insert occur in the same transaction; the semantic unique key closes the race that the current preflight/insert split leaves open. Multi-ticket batches are all-or-nothing: any failed ticket rolls back the entire batch, leaving no partial ledger or event rows.

## 16. Failure matrix

The JSON `failure_matrix` defines fail-closed behavior for all fourteen required cases: missing close time, stale schedule, unsupported lottery, invalid predicted numbers, missing POWER second zone, duplicate identity, clock ambiguity, post-close submission, inactive activation, unknown strategy version, transaction failure, partial multi-ticket write, backfill/import source, and source-provenance failure. Every case rejects fail-closed and records an immutable rejection event; none coerces, defaults, or silently accepts.

## 17. Migration and rehearsal sequence

The migration is additive only (new `CREATE TABLE`/`CREATE TRIGGER`/`CREATE UNIQUE INDEX`; no `ALTER`/`DROP` of existing tables) and is rehearsed only against synthetic or temporary-copy databases. No production database is written in the design or the future implementation task. Production migration execution is deferred to a separately authorized P271K rehearsal and a later controlled deployment.

## 18. Deployment and rollback

Deployment lands the implementation **disabled** and verifies schema objects, unique constraints, append-only triggers, the versioned draw-close resolver, and the worker's no-write preflight before anything is enabled. Deactivation sets the activation registry status to `DEACTIVATED`; it never rewrites captured records. Rollback of the additive schema is permitted only on a non-production rehearsal copy, and captured prospective records are never deleted.

## 19. Explicit activation sequence

Activation is not performed in P271I. It is reached only through separate gates: P271J (implementation + synthetic tests), P271K (temporary-DB migration rehearsal), P271L (controlled schema/runtime deployment), P271M (post-deployment verification), and P271N (explicit activation artifact). The activation artifact records `activation_id` and an activation timestamp, sets the earliest allowed prospective start no earlier than its own merge and deployment verification, excludes all earlier rows, and is reversible only by deactivation — never by rewriting captured records. The P271G merge timestamp alone is never an activation.

## 20. Future task split and whitelists

The JSON `proposed_future_allowed_files` lists each future production/runtime/schema/config path (`lottery_api/database.py`, `lottery_api/engine/prospective_capture.py`, `lottery_api/engine/draw_close_resolver.py`, `scripts/p271_prospective_capture_schema_migration.py`, `scripts/p271_prospective_capture_worker.py`, `config/prospective_draw_schedule.json`) plus synthetic tests and evidence artifacts. Every entry is a proposal only and is marked `separate_explicit_authorization_required = true`. No phase implicitly authorizes the next.

## 21. Final classification

`P271I_PROSPECTIVE_CAPTURE_LEDGER_IMPLEMENTATION_DESIGN_COMPLETE`

Schema change required: **YES** (additive, future, separately authorized). Runtime code change required: **YES** (future, separately authorized). Activation: **not performed and not authorized here**. Current governance remains **HOLD / WAITING_FOR_USER_AUTHORIZATION**. The next round is not allowed without explicit authorization, and the recommended next task is the separately authorized P271J implementation-and-synthetic-tests task.
