# P271J Isolated Prospective Capture Ledger Implementation

## 1. Executive summary

P271J implements the frozen P271I prospective-capture ledger contract as a single
isolated Python module, `lottery_api/prospective_capture_ledger.py`, verified only
against synthetic in-memory and pytest `tmp_path` SQLite databases. The module is a
fail-closed library that operates exclusively on a caller-supplied
`sqlite3.Connection`; it never opens a database path, never touches the production
database, and is not wired into any runtime path. **59/59** focused tests pass
(minimum required 50) and the combined P271G–J suite is **223/223** PASS;
`git diff --check` is clean and the production DB SHA-256 is identical before and
after the task.

This is an **isolated implementation only**. **No production DB was opened or
written.** **No production schema or runtime path was modified.** **No route,
scheduler, ingest, registry, strategy, replay, scorer, adapter, or controlled_apply
integration was added.** **No official source was fetched or verified.**
**Prospective collection remains inactive.** **No real activation record or
timestamp was created.** **Tests used only synthetic temporary SQLite.**
**Passing tests do not authorize migration, deployment, activation, or prediction
claims.** The system remains at **HOLD / WAITING_FOR_USER_AUTHORIZATION.**

`final_classification = P271J_ISOLATED_PROSPECTIVE_CAPTURE_LEDGER_IMPLEMENTATION_COMPLETE`.

## 2. P271I contract implemented

The module realizes the merged P271I design (merge commit
`87726a5f5067b03b7f7d0510bccc7dfc05f3cfa1`, source `ff7c3c4…`): a separate
append-only prospective ledger (activation registry, capture batches, per-ticket
prediction ledger, an immutable event stream, and a separate outcome-link table;
`strategy_prediction_replays` is not reused), a database-enforced semantic unique
key, append-only UPDATE/DELETE-rejecting triggers, timezone-aware UTC causality
with a per-source clock-skew margin, mandatory per-ticket POWER second zone, atomic
single-`BEGIN IMMEDIATE` all-or-nothing capture, hard backfill exclusion, outcome
separation, and the 14-case fail-closed failure matrix.

The P271I causality rule freezes the *form* `prediction_created_at_utc <
draw_close_at_utc` minus a conservative margin and states the margin "is configured
per draw-close source version and never silently widened." No numeric clock-skew
constant is frozen, so the module requires the caller to supply an explicit,
non-negative `clock_skew_margin_seconds` on every draw-close source. **No default
margin is invented**; a missing or invalid margin fails closed
(`SOURCE_PROVENANCE_FAILURE`). The exact rule used is
`prediction_created_at_utc < draw_close_at_utc − clock_skew_margin_seconds` with a
strict inequality.

## 3. Isolation and non-actions

This is an isolated implementation only. No production DB was opened or written. No
production schema or runtime path was modified. No route, scheduler, ingest,
registry, strategy, replay, scorer, adapter, or controlled_apply integration was
added. No official source was fetched or verified. Prospective collection remains
inactive. No real activation record or timestamp was created. No baseline,
statistical, scorer, or adapter execution, strategy comparison/ranking,
temporal-window research, or feature mining was performed. P270C remains
unauthorized; P270A/P270B were not reopened; P271K was not started.

## 4. Module boundary

`lottery_api/prospective_capture_ledger.py`:

- Imports only the standard library (`hashlib`, `json`, `sqlite3`, `dataclasses`,
  `datetime`, `typing`).
- Has no import-time database access and contains no canonical/production DB path.
- Does not import `lottery_api.database` or any replay / scorer / strategy /
  registry / controlled_apply / recommendation / production module.
- Contains no route/API/server registration, scheduler, or network call.
- Never opens a database path itself; every entry point requires a caller-supplied
  `sqlite3.Connection` and raises `LedgerUsageError` otherwise.
- Is deterministic except for explicitly supplied timestamps/identifiers, and fails
  closed with typed exceptions (`SchemaVersionError`, `LedgerUsageError`) and
  structured rejection results (`BatchCaptureResult`, `AmendmentResult`).

## 5. Temporary SQLite boundary

The schema bootstrap installs on any caller-supplied connection and is exercised
only against `sqlite3.connect(":memory:")` and pytest `tmp_path` file databases.
The module never migrates or alters a production database. Tests created no
`.db`/`.sqlite`/WAL/SHM/journal file under tracked repository paths (in-memory and
`tmp_path` only).

## 6. Schema objects

Six tables: `prospective_schema_meta`, `prospective_activation_registry`,
`prospective_capture_batches`, `prospective_prediction_ledger`,
`prospective_capture_events`, `prospective_outcome_links`. Installation enables
foreign keys, creates DB-level unique constraints and unique indexes
(`idx_ledger_identity`, `idx_batch_cluster`), creates BEFORE UPDATE/DELETE
RAISE(ABORT) triggers on all five prospective tables, records a `schema_version`
marker, is idempotent on an empty/same-version DB, and raises `SchemaVersionError`
on incompatible pre-existing schema (wrong version marker or stray `prospective_*`
tables without a recognized marker). `strategy_prediction_replays` is not reused.
The event stream carries no foreign key so it can record rejections of attempted,
rolled-back entities.

## 7. Identity and uniqueness

Identity is the deterministic tuple `(activation_id, lottery_type, target_draw,
strategy_id, strategy_version, bet_index)`. `ledger_id` is a deterministic SHA-256
function of that tuple (caller cannot supply or override it), and `payload_hash` is
a SHA-256 over canonical prediction content using sorted main numbers. Uniqueness
is enforced by both the ledger PRIMARY KEY and a UNIQUE index over the identity
tuple. A conflicting insert raises `IntegrityError`, the whole transaction rolls
back, and a `DUPLICATE_IDENTITY` rejection event is appended; no second eligible row
is created and an existing row is never overwritten. Two concurrent connections
attempting the same identity on a `tmp_path` file DB result in exactly one commit.

## 8. Atomic batch transaction

`capture_batch` validates the entire batch fail-closed before opening a single
`BEGIN IMMEDIATE` transaction (foreign keys on, `busy_timeout=5000`). The batch row,
all ticket rows, and one CAPTURE event per ticket are written together; any invalid
ticket, duplicate, or in-transaction error rolls the whole batch back with no
partial ledger/batch/event rows, after which an immutable rejection event is
appended. One batch per `(activation_id, lottery_type, target_draw)` cluster is
enforced by a UNIQUE constraint, so all bets for a draw are captured all-or-nothing.
No retry loop is used.

## 9. UTC and draw-close causality

Both `prediction_created_at_utc` and `draw_close_at_utc` are parsed as
timezone-aware ISO-8601 and normalized to UTC before comparison. Naive,
unparseable, or ambiguous timestamps fail closed (`AMBIGUOUS_TIMESTAMP`); a missing
close time fails closed (`CLOSE_TIME_MISSING`). The causality gate is
`prediction_created_at_utc < draw_close_at_utc − clock_skew_margin_seconds` (strict).
Boundary behavior: a prediction exactly at `close − margin` is rejected
(`POST_CLOSE_SUBMISSION`); one unit earlier is accepted. The capture path never
queries any outcome/result table.

## 10. Draw-close evidence validation

The four source classes — `official_machine_readable`,
`official_published_schedule`, `repository_configured_deterministic_schedule`, and
`manual` — are validated for type, identity/version, non-empty provenance, an
explicit non-negative clock-skew margin, and freshness (a stale snapshot fails
closed). Manual sources can never be confirmatory
(`MANUAL_SOURCE_NOT_CONFIRMATORY`); official and deterministic sources are
confirmatory only when `manually_verified=True`
(`SOURCE_PENDING_MANUAL_VERIFICATION` otherwise). No schedule was fetched and no
official verification was claimed; `source_verification_status =
MANUAL_VERIFICATION_REQUIRED`.

## 11. Lottery validation

P271C-compatible capture validation (no scoring): POWER_LOTTO 6 main in 1–38 plus a
mandatory second zone 1–8; BIG_LOTTO 6 main in 1–49 with no second zone; DAILY_539
5 main in 1–39 with no second zone. Booleans-as-integers, non-integers,
out-of-range values, duplicates, wrong counts, strings/bytes lists, and unsupported
lottery types are rejected. Caller input is never mutated (a sorted copy is taken
internally). No hits, tiers, prizes, M3+, or success rates are computed.

## 12. POWER second-zone enforcement

For POWER_LOTTO, `predicted_second_zone` is mandatory and validated at creation; a
missing or invalid value rejects the whole POWER batch
(`MISSING_OR_INVALID_PREDICTED_SECOND_ZONE`). It cannot be filled later or sourced
from an actual value. BIG_LOTTO and DAILY_539 must not carry a second zone
(`SECOND_ZONE_NOT_PERMITTED`).

## 13. Prospective membership

Eligibility is computed exactly once at insert, before any outcome, and is never
upgraded later. Only `LIVE_PRE_CLOSE` capture with an active activation, a
confirmatory fresh source, and a passing causality gate is stored as an ELIGIBLE
row. The ledger holds only ELIGIBLE rows; rejected and non-live captures are omitted
and recorded as immutable rejection events. Combined with append-only UPDATE
triggers and the unique key, an ineligible identity can never be upgraded to
prospective and there is no public upgrade/promote function.

## 14. Backfill exclusion

`MANUAL`, `RECONSTRUCTED`, `BACKFILL`, and `IMPORT` capture modes are excluded from
the prospective population (`BACKFILL_EXCLUDED`). Capture requires an active
activation and a creation time at or after the activation start; a retrospective row
can never be converted to prospective and no status upgrade path exists.

## 15. Append-only immutability

All five prospective tables are protected by BEFORE UPDATE and BEFORE DELETE
RAISE(ABORT) triggers; a prediction payload cannot change after insert. `payload_hash`
plus the append-only event stream provide tamper evidence, and `verify_payload_hash`
recomputes and compares the stored hash.

## 16. Amendment and deactivation

Amendments are append-only: `append_amendment` writes a new AMENDMENT event
referencing the original ledger row; the original is never updated or deleted. A
post-close amendment is ineligible (`POST_CLOSE_AMENDMENT`), and an amendment that
would alter any identity-tuple field (silently changing membership) is rejected
(`AMENDMENT_ALTERS_IDENTITY`). Deactivation appends a DEACTIVATION event and never
rewrites the activation registry row; active-state is derived from the append-only
event stream.

## 17. Outcome separation

The ledger contains no actual-result columns and the capture path never reads any
result table or imports the prize-aware scorer. Outcome linkage lives in a separate
`prospective_outcome_links` table that references ledger rows only; actual values can
never populate predicted fields, and membership is frozen before any outcome exists.

## 18. Failure-matrix results

All 14 P271I fail-closed cases (F01–F14) are implemented and tested: missing close
time, stale schedule, unsupported lottery, invalid predicted numbers, missing/invalid
POWER second zone, duplicate identity, clock/timezone ambiguity, post-close
submission, inactive activation, unknown strategy version, transaction failure,
partial multi-ticket write (all-or-nothing rollback), backfill/import source, and
source-provenance failure. See `failure_matrix_results` in the JSON artifact for the
per-case rejection reason and test reference.

## 19. Synthetic test coverage

`tests/test_p271j_prospective_capture_ledger_implementation.py` contains 59 tests
covering import isolation, no production path/import, schema install/idempotence/
incompatible-rejection, foreign keys, required tables/indexes/triggers, append-only
UPDATE/DELETE rejection, activation append/deactivation/inactive rejection,
deterministic identity and payload hash, duplicate rejection and no-overwrite,
single/multi-ticket atomic capture, one-invalid/duplicate-in-batch/transaction-error
rollback with no orphan rows, naive/ambiguous/non-UTC timestamp handling,
missing/stale/post-close/clock-skew-boundary causality, official/deterministic/manual
source validation, POWER/BIG/DAILY_539 validation including second-zone rules,
booleans/duplicates/unsupported-lottery rejection, caller-input immutability,
backfill/unknown-strategy/provenance rejection, amendment append-and-preserve,
post-close/identity-altering amendment rejection, ineligible-cannot-become-prospective,
payload-hash verification, outcome/scoring/route absence, concurrent-duplicate single
commit, production-DB-hash unchanged, and P271G/H/I artifact integrity. All use
`:memory:` or `tmp_path`.

## 20. Production DB and artifact integrity

The canonical production database `lottery_api/data/lottery_v2.db` was hashed before
and after the task with an identical SHA-256
`3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e`; it was never
opened by the module or tests. The merged P271G/P271H/P271I artifacts are unchanged
(hash-pinned in the test suite). No `.db`/`.sqlite`/WAL/SHM/journal residue was
created under tracked repository paths.

## 21. Limitations and remaining P271K–P271N gates

This module is a library only and is not connected to any production path. Passing
these synthetic tests does not authorize migration, deployment, activation, or
prediction claims. The remaining gates are separately authorized and **not started**:
P271K temporary-DB migration rehearsal, P271L controlled schema/runtime deployment,
P271M post-deployment verification, and P271N explicit prospective activation. No
phase implicitly authorizes the next. **P271K migration rehearsal is not
authorized.** Concurrency was exercised only with two `tmp_path` connections;
production locking/busy-timeout tuning is deferred to an authorized rehearsal.

## 22. Final classification

`P271J_ISOLATED_PROSPECTIVE_CAPTURE_LEDGER_IMPLEMENTATION_COMPLETE`

Official source status remains `MANUAL_VERIFICATION_REQUIRED`. Current governance
remains **HOLD / WAITING_FOR_USER_AUTHORIZATION.** Recommended next task is the
separately authorized P271K temporary-DB migration rehearsal.
