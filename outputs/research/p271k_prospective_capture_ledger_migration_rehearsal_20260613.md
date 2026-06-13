# P271K Prospective Capture Ledger — Temporary-DB Migration Rehearsal

## 1. Executive summary

P271K rehearses installing the **merged P271J** prospective-capture ledger
schema (`lottery_api.prospective_capture_ledger.install_schema`, merge commit
`3dc06f76a70ff13927b63491fb4580528ed86a3d`) onto **temporary SQLite databases
only** — pytest `tmp_path`, OS temp directories outside the repository, and
`sqlite3 ":memory:"`. It proves the schema is **purely additive** against a
*source-grounded* representative legacy schema, is **idempotent**, **rolls back
atomically** on version drift and on an injected mid-install failure, **preserves
caller transaction ownership** (fail-closed `AmbientTransactionError`), **fails
closed when the database is locked** without an unsafe retry loop, and supports a
**temporary-only backup/restore** back to the exact pre-install fingerprint.

All ten scenarios (A–J) pass. The focused suite is **37 passed**; the combined
P271I–K suite is **149 passed**; `git diff --check` is clean. The canonical
production database `lottery_api/data/lottery_v2.db` was **never opened, copied,
or written** — its SHA-256 is identical before and after
(`3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e`).

This is a **rehearsal only**. It does **not** add a production migration, modify
the production schema, integrate any runtime path, deploy, or activate
prospective collection. `final_classification =
P271K_TEMPORARY_DB_MIGRATION_REHEARSAL_COMPLETE`. The system remains at
**HOLD / WAITING_FOR_USER_AUTHORIZATION**.

## 2. P271J merged baseline

The schema contract is owned entirely by the merged P271J module and is taken
**verbatim** — P271K never re-defines or mutates it. The module installs six
`prospective_*` tables (`prospective_schema_meta`,
`prospective_activation_registry`, `prospective_capture_batches`,
`prospective_prediction_ledger`, `prospective_capture_events`,
`prospective_outcome_links`), two unique indexes (`idx_ledger_identity`,
`idx_batch_cluster`), and append-only `BEFORE UPDATE`/`BEFORE DELETE`
`RAISE(ABORT)` triggers on the five data tables, under a single
`BEGIN IMMEDIATE` transaction with a fail-closed `AmbientTransactionError`
guard. `SCHEMA_VERSION = "p271j_prospective_capture_ledger.v1"`. The module file
SHA-256 is unchanged (`18e221ee632a81fbdb95cab171d3c3a4bae3bf2222f9f2c58c8a3398584c71db`).

## 3. Rehearsal-only authorization boundary

P271K is authorized to create the task branch, the rehearsal script, tests,
JSON/MD artifacts, and minimal governance updates, and to open one PR. It is
**not** authorized to touch the production DB, add a production migration,
modify the production schema, integrate runtime/routes, deploy, activate
prospective collection, insert an activation timestamp, fetch/verify an official
source, or begin P271L/P271M/P271N. A passing rehearsal authorizes none of those.

## 4. Safe legacy-schema fixture

A representative legacy schema is embedded in the rehearsal script and **grounded
line-for-line** in `lottery_api/database.py` (at the P271J merge commit):

| Table | Source | Role |
|-------|--------|------|
| `draws` | database.py:70-81 | unrelated table (non-interference) |
| `prediction_runs` | database.py:112-121 | prediction FK target |
| `prediction_items` | database.py:150-159 | FK → `prediction_runs(id)` |
| `prediction_results` | database.py:164-177 | FK → `prediction_items(id)` |
| `strategy_replay_runs` | database.py:372-383 | replay FK target |
| `strategy_prediction_replays` | database.py:389-411 | FK → `strategy_replay_runs(id)`; the table P271J deliberately does **not** reuse |

The base `CREATE TABLE` statements are reproduced verbatim; the runtime's
idempotent `ALTER TABLE` migrations are omitted because they are not required to
prove additive non-interference. No production rows are used — only deterministic
synthetic rows. The legacy schema defines **no global version-metadata table**,
so the P271J `prospective_schema_meta` marker cannot collide. No canonical DB was
opened to build the fixture; it is grounded purely from source text.

## 5. Temporary-path safety

`validate_temporary_db_path` fails closed before any connection is opened. It
rejects: a missing/empty path; `:memory:` where a real file is required
(backup/restore); the canonical production DB realpath; any **symlink** resolving
onto the canonical realpath (because `os.path.realpath` resolves symlinks); and
any repository-contained path (`realpath` under the repo root). It accepts only
paths that resolve **outside** the repository. The module never discovers a DB
from the environment or any default configuration, and performs no import-time
database access. Scenario J confirms every branch.

## 6. Migration contract

Installation is delegated to `pcl.install_schema` and is **additive-only**: every
created object lives in the `prospective_*` / `idx_ledger_*` / `idx_batch_*` /
`trg_prospective_*` namespace, which does not collide with any legacy table. The
install is atomic (single `BEGIN IMMEDIATE`; `COMMIT` or `ROLLBACK`), rejects an
ambient caller transaction fail-closed, and adds no `SAVEPOINT` nesting.

## 7. Clean additive installation

Scenario A builds the legacy fixture, fingerprints it, installs the prospective
schema, and re-fingerprints. Result: `schema_version =
p271j_prospective_capture_ledger.v1`; all required prospective tables, triggers,
and indexes present; legacy schema fingerprint and data fingerprint **identical**
before and after; `PRAGMA foreign_key_check` empty; `PRAGMA integrity_check =
ok`. The prospective `prospective_prediction_ledger` table carries **no**
actual-result columns (`actual_numbers`, `actual_special`, `hit_count`,
`hit_numbers`, `matched_numbers`, `special_hit` are all absent).

## 8. Legacy schema/data non-interference

The legacy fingerprint excludes only the newly authorized prospective objects
(`tbl_name NOT LIKE 'prospective_%'` and `name NOT LIKE 'sqlite_%'`). Across every
scenario — including failures and rejections — the legacy schema fingerprint, the
per-table row-count + content hashes (including the unrelated `draws` table),
`foreign_key_check`, and `integrity_check` are unchanged. No legacy table is
altered, dropped, or re-created.

## 9. Idempotence

Scenario B installs twice. The second call returns the same `SCHEMA_VERSION`,
produces an **identical** `sqlite_master` object set (tables/indexes/triggers),
and leaves the legacy snapshot unchanged. No duplicate objects and no row changes.

## 10. Existing prospective-row preservation

Scenario H installs the schema, appends a synthetic `prospective_activation_registry`
row, then re-runs the install. The row count and a content hash of the registry
are **unchanged** after reinstall — the idempotent install performs no
destructive reset or table re-creation on existing prospective data.

## 11. Incompatible-version handling

Scenario C plants an incompatible `prospective_schema_meta` version marker
(`p271j_prospective_capture_ledger.v0_INCOMPATIBLE`) and attempts an install. The
module raises `SchemaVersionError`; **no new** prospective tables/indexes/triggers
are created beyond the planted marker; the legacy snapshot is unchanged.

## 12. Injected-failure rollback

Scenario D drives the install through a real `sqlite3.Connection` subclass that
raises an `OperationalError` after a subset of the prospective `CREATE TABLE`
statements (armed only after the legacy fixture is built). The module's
`BEGIN IMMEDIATE` … `ROLLBACK` is atomic: zero prospective objects remain, the
`schema_version` marker is absent (no orphan metadata), the connection is left
with **no open transaction**, and the legacy snapshot is unchanged.

## 13. Ambient transaction ownership

Scenario E opens a caller-owned transaction, inserts an unrelated synthetic row,
then calls the install. The module raises `AmbientTransactionError`; the caller's
transaction stays open (`in_transaction` remains `True`); a second connection
sees **neither** the caller's uncommitted row **nor** any prospective object;
and the caller's own `ROLLBACK` (and, in a companion test, its own `COMMIT`)
remains entirely caller-owned. The module never commits or rolls back work it did
not start, and writes nothing on rejection.

## 14. Locked/busy behavior

Scenario F holds an `EXCLUSIVE` lock from a second connection and attempts the
install. The install fails closed with `sqlite3.OperationalError` ("database is
locked") after the module's configured `busy_timeout`, with **no unsafe retry
loop**, leaving no partial prospective schema and no open transaction on the
installer. Legacy data is unchanged.

## 15. Foreign keys and integrity checks

After every install, `PRAGMA foreign_keys` is ON, `PRAGMA foreign_key_check`
returns no violations, and `PRAGMA integrity_check` returns `ok`. The rehearsal
does not weaken any legacy constraint.

## 16. Append-only and uniqueness

Scenario I confirms the append-only triggers reject both `UPDATE` and `DELETE` on
a prospective table, that `idx_ledger_identity` is a `UNIQUE` index, and that a
direct duplicate identity-tuple insert into `prospective_prediction_ledger` is
rejected with `IntegrityError`. The module does not reuse
`strategy_prediction_replays` (verified by source scan and by the distinct table
name `prospective_prediction_ledger`).

## 17. Temporary backup/restore

Scenario G fingerprints the legacy-only DB, backs it up via the `sqlite3`
online-backup API to a second temporary path, installs the prospective schema on
the original, then restores the pre-install backup into a third temporary path.
The restored DB matches the pre-install legacy schema and data fingerprint
exactly and contains **no** prospective objects. Both source and destination
paths are validated as safe temporary files. **This temporary backup/restore is
not production rollback approval.**

## 18. Production DB and artifact integrity

The canonical production database was never opened, copied, or written; only its
raw bytes were hashed. SHA-256 before and after:
`3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e` (unchanged).
The merged P271G/P271H/P271I/P271J artifacts and the P271J module are unchanged
(module hash `18e221ee…71db`). No `.db`/WAL/SHM/journal residue is created under
any tracked repository path (the rehearsal structurally refuses repository paths).

## 19. Remaining P271L deployment risks

A temporary-DB PASS does **not** establish production readiness. P271L (controlled
deployment) must still address: the **full** production schema breadth (all
runtime tables and idempotent `ALTER` migrations, not just the representative
subset); **live concurrency** and WAL-mode/busy-timeout tuning against the real
backend rather than two local file connections; **backup orchestration** and an
operational, audited rollback procedure (the temporary backup/restore here is a
viability demonstration only); and an explicit **migration-verification record**
before any schema is installed on the production database. None of these are in
scope for P271K.

## 20. Non-actions

No production DB access/write. No production schema change. No production
migration added or approved. No runtime/route/ingest/scheduler integration. No
deployment. No prospective activation. No real activation record or timestamp.
No official-source fetch or verification (`MANUAL_VERIFICATION_REQUIRED`
retained). No baseline/statistical/scorer/adapter execution; no strategy
comparison/ranking; no temporal-window research; no feature mining. P270C
remains unauthorized; P270A/P270B were not reopened; P271L/P271M/P271N not
started.

## 21. Limitations

- Temporary-DB rehearsal only; the representative legacy fixture is a
  source-grounded subset (base `CREATE` statements; runtime idempotent `ALTER`
  migrations omitted).
- Concurrency exercised with two local file-DB connections and one `EXCLUSIVE`
  lock; production locking/busy-timeout and WAL-mode behavior are deferred to an
  authorized P271L rehearsal.
- Backup/restore demonstrated on temporary DBs only; not production rollback
  approval.
- A temporary-DB PASS does not establish production readiness.

## 22. Final classification

`P271K_TEMPORARY_DB_MIGRATION_REHEARSAL_COMPLETE`

### Required declarations

- **Temporary-DB rehearsal only.**
- **Production DB was not opened, copied, or written.**
- **No production migration was added or approved.**
- **No runtime/schema deployment occurred.**
- **No prospective activation occurred.**
- **Passing rehearsal does not authorize P271L, P271M, or P271N.**
- **Official source remains `MANUAL_VERIFICATION_REQUIRED`.**
- **HOLD / WAITING_FOR_USER_AUTHORIZATION.**
- **No prediction-success claim.**
