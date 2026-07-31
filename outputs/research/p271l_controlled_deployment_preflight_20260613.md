# P271L — Controlled Deployment Preflight & Authorization Package

Task ID: `P271L_CONTROLLED_DEPLOYMENT_PREFLIGHT_AND_AUTHORIZATION_PACKAGE`
Generated: 2026-06-13 · Mode: `controlled_deployment_preflight` · Branch: `task/p271l-controlled-deployment-preflight`

> **Preflight and authorization package only.** This task does NOT perform the deployment.
> The production DB was **not opened, copied, backed up, restored, or written**.
> No production migration was executed or added. No process was stopped or restarted.
> No runtime integration or deployment occurred. No prospective activation occurred.
> **Actual production schema was not read in this task.**
> P271M verification is required after any future apply. P271N activation requires separate authorization.
> Official source remains **MANUAL_VERIFICATION_REQUIRED**. Governance: **HOLD / WAITING_FOR_USER_AUTHORIZATION**.
> No prediction-success claim is made anywhere in this artifact.

---

## 1. Executive summary

P271L produces a source-grounded, operationally complete *preflight* for a future controlled
installation of the P271J prospective capture ledger schema onto the production database
`lottery_api/data/lottery_v2.db`. It documents the exact target schema objects, the production
schema breadth and collision risks visible from source, active-writer / WAL risks, the required
maintenance-window and writer-quiescence gates, a safe backup method, a rollback method and its
triggers, exact pre-apply and post-apply invariants, a non-executable controlled-apply manifest,
the authorization wording required before any production DB operation, and the strict separation
of P271L deployment, P271M verification, and P271N activation.

**Readiness decision:** `P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY`. Because the actual
production schema is not opened in this task, and because an active/potentially-active writer
plus an unreconciled WAL/SHM sidecar state are observed, production deployment is **not**
executable now.

---

## 2. P271K merged baseline

| Item | Value |
|------|-------|
| P271K PR | #428 — **MERGED** (2026-06-13T15:00:46Z) |
| P271K merge commit | `847262bd1a6efec3fcc3bff879867f71f7555ade` |
| P271K source commit | `b7b6d883bfac6881e4b60d5453ba68ae6d79675e` |
| P271K classification | `P271K_TEMPORARY_DB_MIGRATION_REHEARSAL_COMPLETE` |
| `origin/main` HEAD at task start | `847262bd1a6efec3fcc3bff879867f71f7555ade` (== merge commit) |
| Production DB baseline SHA-256 | `3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e` |

Phase 0 gates all passed: canonical repo (`LotteryNew`), starting branch `main`, `HEAD == origin/main ==`
P271K merge commit, PR #428 MERGED, no staged whitelist files, the P271L branch absent locally and
remotely, P271I/J/K artifacts present and clean, and the production DB raw hash matching the expected
baseline exactly.

---

## 3. Preflight-only authorization boundary

Explicitly authorized in this task: create the P271L branch and six whitelisted files, commit, push,
open ONE PR; read-only repository / Git / process-metadata / filesystem-metadata / source / config /
GitHub inspection; raw-hash and stat the production DB and its sidecars **without** opening them via
SQLite.

Explicitly forbidden: open / attach / query / copy / back up / restore / checkpoint / vacuum / migrate /
write the production DB; stop / kill / restart any backend or frontend process; execute a production
migration; modify runtime or schema source; merge the PR; perform P271M or P271N.

The preflight script `scripts/p271l_controlled_deployment_preflight.py` is built to this boundary:
it does not `import sqlite3`, never opens a SQLite connection, rejects apply/deploy flags, contains
no migration / process-signal / network path, raw-hashes files only, emits a deterministic manifest,
and fails closed on missing evidence or conflicting state.

---

## 4. Production DB identity without opening

Established by raw SHA-256 over the file's bytes (never via SQLite):

| Field | Value |
|-------|-------|
| Path (realpath) | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db` |
| SHA-256 | `3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e` |
| Matches baseline | YES |
| Size | 99,368,960 bytes |
| mtime | 2026-06-11 10:43:24 |
| Mode | `0o644` |

Re-hashing after running the read-only preflight produced the identical SHA-256 — the DB was not mutated.

---

## 5. Source-defined schema inventory

All citations from `lottery_api/prospective_capture_ledger.py` (the P271J implementation, schema source).

**Schema version:** `SCHEMA_VERSION = "p271j_prospective_capture_ledger.v1"` (py:47), recorded into the
metadata table `prospective_schema_meta` via `INSERT OR IGNORE` (py:534–538).

**Tables (6):**
| Table | Key points | Source |
|-------|-----------|--------|
| `prospective_schema_meta` | `key` PK, `value` NOT NULL | py:328–333 |
| `prospective_activation_registry` | `activation_id` PK; `status` DEFAULT `'INACTIVE'`; FK target | py:335–345 |
| `prospective_capture_batches` | `batch_id` PK; UNIQUE `(activation_id, lottery_type, target_draw)`; FK→registry | py:348–366 |
| `prospective_prediction_ledger` | `ledger_id` PK; 6-col semantic UNIQUE; FK→batches, FK→registry | py:369–395 |
| `prospective_capture_events` | `event_id` PK; **no FK by design** (py:95) | py:398–410 |
| `prospective_outcome_links` | `outcome_link_id` PK; UNIQUE `(ledger_id)`; FK→ledger | py:413–421 |

**Indexes (2, both UNIQUE):**
- `idx_ledger_identity` ON `prospective_prediction_ledger (activation_id, lottery_type, target_draw, strategy_id, strategy_version, bet_index)` (py:427–431)
- `idx_batch_cluster` ON `prospective_capture_batches (activation_id, lottery_type, target_draw)` (py:432–435)

**Triggers (10 = 2 × 5 append-only tables):** `trg_{table}_no_update` (BEFORE UPDATE → `RAISE(ABORT, …)`)
and `trg_{table}_no_delete` (BEFORE DELETE → `RAISE(ABORT, …)`) for each of
`prospective_activation_registry`, `prospective_capture_batches`, `prospective_prediction_ledger`,
`prospective_capture_events`, `prospective_outcome_links` (py:439–462; append-only table list py:155–161).

**PRAGMAs at every write entry point** (`_ensure_pragmas`, py:308–320): `PRAGMA foreign_keys = ON`
(py:319) and `PRAGMA busy_timeout = 5000` (py:320); `isolation_level = None` for explicit transaction
control.

**Semantic uniqueness:** composite key `(activation_id, lottery_type, target_draw, strategy_id,
strategy_version, bet_index)` on the ledger (py:390–391), mirrored by `idx_ledger_identity` and a
deterministic `derive_ledger_id` SHA-256 (py:609–636).

**Foreign-key requirements:** batches→registry; ledger→batches and ledger→registry; outcome_links→ledger.
FK enforcement requires `PRAGMA foreign_keys = ON`, which the ledger sets per write.

**Rehearsal isolation (P271K):** `scripts/p271k_prospective_capture_ledger_migration_rehearsal.py`
references the canonical production DB path **only to reject it** (`CANONICAL_PRODUCTION_DB`, lines 56–59;
`validate_temporary_db_path` rejects the canonical path and any repo-contained path, lines 84–133). The
rehearsal installs schema on `:memory:` or validated temp paths only — it never connects to the
production DB.

---

## 6. Actual production schema limitation

**`ACTUAL_PRODUCTION_SCHEMA_NOT_READ_IN_P271L_PREFLIGHT`.** The production DB was not opened via SQLite,
so this artifact does **not** claim equivalence between the source-defined schema and the live schema.
Reading the actual production schema (e.g. `mode=ro`, `sqlite_master`, `PRAGMA integrity_check`) requires
separate explicit authorization and must precede any apply.

---

## 7. Runtime writer inventory

Source-grounded (no execution, no DB open). The LotteryNew backend opens the DB via short-lived
`sqlite3.connect()` per call in `lottery_api/database.py:_get_connection` (py:56–60). Known writer
entry points (10):

`lottery_api/database.py` (DatabaseManager: insert_draws / vacuum / etc.) · `lottery_api/routes/ingest.py`
(ingest + backfill HTTP writers) · `lottery_api/fetcher/backfill_engine.py` · `lottery_api/utils/scheduler.py`
(background scheduler / learning integration / resolve_pending / adjust_all_types / apply_learning) ·
`tools/post_draw_pipeline.py` · `tools/upload_lottery_data.py` · `tools/upload_daily539_txt.py` ·
`tools/upload_big_lotto_csv.py` · `scripts/p7_controlled_replay_row_apply.py` ·
`scripts/apply_p0_schema_migration.py`.

More than one writer can exist concurrently (backend HTTP + scheduler cron + ad-hoc tools).

**Process snapshot (read-only):** `backend.pid` = 3418 and `frontend.pid` = 1952 are **STALE** (not live).
However an out-of-band **live** LotteryNew backend exists: PID **1593** (`python app.py`, cwd
`lottery_api`, parented to launchd, with multiprocessing children). This live backend is a
potentially-active writer this read-only task may not quiesce. (PIDs 4722/1578 on port 8000 belong to a
different project — `PersonalHealthOS` — and are not LotteryNew writers.) Process checks used `ps`/`kill -0`
read semantics only; no terminating signal was sent.

---

## 8. WAL/SHM and locking risks

- `lottery_v2.db-shm` **present** (32,768 bytes, recent mtime) and `lottery_v2.db-wal` present (0 bytes).
- `lottery_api/database.py` sets **no** `journal_mode` (default rollback/`delete`), **no** `busy_timeout`
  (default 0 → immediate `SQLITE_BUSY`), and **no** `foreign_keys` PRAGMA.
- The presence of a `-shm` sidecar implies a writer opened the DB in **WAL mode**, which is **unreconciled**
  with `database.py`. This WAL/SHM-unreconciled state is a STOP gate for apply.
- The prospective ledger sets `busy_timeout = 5000` and `foreign_keys = ON` per write — a deliberate
  divergence from the legacy runtime connection. The migration must account for this difference and must
  acquire an exclusive write lock (`BEGIN IMMEDIATE`) and fail closed on busy/locked.

---

## 9. Maintenance-window contract

Required. States: announce window and freeze scheduled ingest/learning jobs; stop backend
(`lottery_api/app.py`) and frontend via `stop_all.sh`; disable launchd KeepAlive
(`com.kelvin.lottery.dev.plist`) so the backend does not auto-restart during the window; confirm no
process holds the DB (`lsof`) and PID files are stale/removed; reconcile WAL/SHM (checkpoint, ensure
`-wal` empty, account for `-shm`) before backup. Exit criteria: **all writers stopped AND verified AND
no DB holders.**

---

## 10. Writer-quiescence gates

Required evidence before apply: `backend.pid`/`frontend.pid` stale or removed; no `python app.py`
(cwd `lottery_api`) alive (note: PID 1593 must be confirmed stopped); no scheduler / post_draw_pipeline /
ingest job running; launchd KeepAlive disabled; `lsof` shows zero holders of `lottery_v2.db`; WAL/SHM
reconciled. **Conservative rule:** if any active or potentially-active writer cannot be conclusively
quiesced, the apply manifest MUST be `NOT_READY_FOR_APPLY`. (No process was stopped in this task.)

---

## 11. Backup strategy

Raw-copy-only backup while active WAL writers exist is **REJECTED**. Choose one (under separate
authorization): **(A)** maintenance window — stop & verify all writers, verify no DB holders, checkpoint
WAL if authorized, create a verified backup; or **(B)** SQLite online backup API under an explicitly
authorized controlled process with validated source and destination. Destination requirements: **outside
the repo**; timestamped immutable filename; record source DB identity + hash; explicit WAL handling;
post-backup integrity verification (`integrity_check`) + raw hash recorded; **restore rehearsal required**;
checksum recording; retention/deletion behind an explicit human gate; on failure, abort apply. Disk space
at inspection: 58 GiB free (DB ≈ 99 MB) — ample, but space must be re-checked at apply time. **No backup,
checkpoint, or restore was executed in P271L.**

---

## 12. Controlled apply manifest

Proposed, **non-executable**. Canonical repo `…/LotteryNew`; required main commit
`847262bd1a6efec3fcc3bff879867f71f7555ade`; production DB realpath
`…/lottery_api/data/lottery_v2.db`; expected pre-apply SHA-256 with a fresh re-hash rule (abort on drift);
required maintenance-window state CONFIRMED; required writer-quiescence ALL_WRITERS_STOPPED_AND_VERIFIED;
required backup evidence VERIFIED_BACKUP_OUTSIDE_REPO; migration schema version
`p271j_prospective_capture_ledger.v1`; the exact 6 prospective tables, 2 indexes, 10 triggers;
`BEGIN IMMEDIATE` exclusive-lock behavior; busy/locked → abort + rollback (never blind retry); max
boundary = single transaction, CREATE-IF-NOT-EXISTS only, no data backfill, no legacy DROP; post-apply
checks delegated to P271M; explicit no-activation declaration (no activation record, no ACTIVE status,
no prediction rows; prospective tables remain empty); P271M required after apply; P271N separately
authorized after P271M. Executable **only** when a future prompt contains the exact authorization phrase
**and** all pre-apply STOP gates pass.

---

## 13. Required explicit authorization template

The future apply requires this exact, copyable authorization (this task and this template are **NOT**
current authorization):

```
YES execute P271L controlled production schema deployment
repo=/Users/kelvin/Kelvin-WorkSpace/LotteryNew
main_commit=847262bd1a6efec3fcc3bff879867f71f7555ade
production_db=/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db
expected_pre_apply_sha256=<fresh hash>
backup_path=<outside-repo path>
maintenance_window_confirmed=YES
all_writers_stopped_and_verified=YES
rollback_plan_confirmed=YES
```

---

## 14. Pre-apply STOP gates

Apply MUST NOT proceed if any of: wrong repo/branch/HEAD; dirty or staged authorized files; production DB
hash drift; active or unverified writers; active DB lock holders; WAL/SHM state not reconciled; backup
missing or unverified; actual production schema not inspected under separate authorization; schema
collision or incompatible version; insufficient disk space; rollback destination missing; production DB
already contains unexpected prospective objects; P271M verification plan missing; P271N activation
accidentally coupled to deployment.

---

## 15. Post-apply P271M verification plan

Owner: **P271M** (separate task; not executed here). Checks: schema_version exact ==
`p271j_prospective_capture_ledger.v1`; all 6 prospective tables present exact; both indexes present exact;
trigger count == 10 (append-only enforced); `PRAGMA foreign_key_check` passes; `PRAGMA integrity_check`
== ok; legacy row-count/content invariants unchanged; prospective tables EMPTY unless separately
authorized; append-only triggers enforced (UPDATE/DELETE raise ABORT); semantic uniqueness enforced; no
runtime integration unless separately approved; DB and backup hashes recorded; backend restart only after
verification passes; **no activation timestamp, no activation record, no prediction capture.**

---

## 16. Rollback plan

Triggers: integrity/foreign-key check failure post-apply; unexpected legacy row-count/content change;
apply aborted mid-transaction / partial schema; collision or version mismatch discovered during apply;
any unexpected prospective rows. Authorization owner: human operator (explicit), same gate as apply.
Procedure: stop all writers; restore the verified pre-apply backup over the quiesced production DB path;
verify raw hash == expected pre-apply SHA-256 AND `integrity_check` == ok; remove stale `-wal`/`-shm`
after restore and verify a clean state. **Partial manual DROP of prospective objects is PROHIBITED unless
separately designed and authorized.** Incident record required.

---

## 17. P271N activation separation

P271N (prospective collection activation) is strictly separate from P271L (deployment) and P271M
(verification). The apply manifest carries an explicit no-activation declaration. P271N requires its own
explicit authorization, may only follow a passing P271M, and is **not** started here. Activation would be
the only step permitted to write an activation record / set ACTIVE status / begin prediction capture —
and only under separate authorization.

---

## 18. Production DB and artifact integrity

- Production DB SHA-256 before == after == `3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e`
  (unchanged; never opened via SQLite).
- P271I/J/K artifacts and the ledger/rehearsal sources are TRACKED and unmodified (verified via
  `git status` and raw hashing).
- No repository DB/temp residue created by the preflight (the read-only run writes no files into the repo;
  the live manifest used in this artifact was written to `/tmp`).

---

## 19. Readiness decision

`P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY`. Blockers:

1. `actual_production_schema_not_read` — separate authorization required for read-only actual production schema inspection before apply.
2. `fresh_production_db_hash_verification_required` immediately before apply.
3. `verified_maintenance_window_and_writer_shutdown_required`.
4. `verified_backup_destination_and_rollback_authorization_required`.
5. `WAL_OR_SHM_SIDECAR_PRESENT_UNRECONCILED` — a writer opened the DB in WAL mode; `database.py` sets no `journal_mode`.
6. `MULTIPLE_POTENTIAL_WRITERS_NOT_CONCLUSIVELY_QUIESCED` — incl. live backend PID 1593.

---

## 20. Non-actions

The production DB was not opened, copied, backed up, restored, checkpointed, vacuumed, migrated, or
written. No production migration was executed or added. No process was stopped or restarted. No runtime
integration or deployment occurred. No prospective activation occurred. No activation timestamp/record was
inserted. No official source was fetched or verified (remains MANUAL_VERIFICATION_REQUIRED). P271M and
P271N were not started. The PR is not merged.

---

## 21. Limitations

- `ACTUAL_PRODUCTION_SCHEMA_NOT_READ_IN_P271L_PREFLIGHT` — all schema claims are source-grounded only.
- Production DB identity established by raw SHA-256 over bytes only.
- `lsof` showed no current DB holders at inspection time, yet a live backend (PID 1593) plus a recent
  `-shm` sidecar indicate an active/potentially-active WAL-mode writer this read-only task may not quiesce.
- Process inventory is a point-in-time snapshot; writer state may change before any future apply.

---

## 22. Final classification

`P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY` ·
Official source: **MANUAL_VERIFICATION_REQUIRED** · Governance: **HOLD / WAITING_FOR_USER_AUTHORIZATION**.
P271M verification required after any future apply; P271N activation requires separate authorization.
No prediction-success claim is made.

---

### Test results
- Focused: `tests/test_p271l_controlled_deployment_preflight.py` — **50 passed / 0 failed** (50 total). PASS.
- Combined P271J–L: **158 passed / 1 failed** (159 total). The single failure is the pre-existing P271K
  forward-guard `test_p271k_…::test_p271l_m_n_not_started`, which asserts no `scripts/p271l_*.py` /
  `tests/test_p271l_*.py` exist. P271L has now legitimately started under explicit authorization, so the
  `p271l` token of that guard is expectedly stale. The P271K test file is **not** on the P271L whitelist
  and was **not** modified; the `p271m`/`p271n` tokens remain clean.
- Full-repo suite: **NOT RUN** (not required by governance).

> **Note (2026-06-14):** The "**158 passed / 1 failed**" line above is the **original pre-reconciliation**
> audit record, preserved intact. That single failure has since been reconciled under explicit
> authorization (see §23); the current combined result is **159 passed / 0 failed**.

---

## 23. Forward-guard contract reconciliation (2026-06-14)

This section records an authorized **phase-transition contract reconciliation**. It is a deliberate
contract correction — **not** a suppressed or hidden test failure. No test was skipped, xfailed, deleted,
conditionalized on an environment variable, count-lowered, or otherwise weakened.

**Original state (preserved above).** The combined P271J–L suite was **158 passed / 1 failed** (159 total).
The one failure was
`tests/test_p271k_prospective_capture_ledger_migration_rehearsal.py::test_p271l_m_n_not_started` — the
P271K forward guard that, while P271K was the latest authorized phase, forbade the existence of
`scripts/p271l_*.py` and `tests/test_p271l_*.py`. That prohibition was correct at P271K time.

**Why the P271L token was retired.** P271L (controlled-deployment **preflight**) was subsequently
authorized as its own phase and legitimately created the preflight files
`scripts/p271l_controlled_deployment_preflight.py` and
`tests/test_p271l_controlled_deployment_preflight.py`. The `p271l` token of the P271K guard therefore
became an obsolete phase-boundary assertion. Under explicit authorization it was reconciled by:

- renaming the guard `test_p271l_m_n_not_started` → `test_p271m_n_not_started`;
- removing **only** the obsolete `scripts/p271l_*.py` / `tests/test_p271l_*.py` prohibition;
- **preserving** the `p271m` and `p271n` forward guards unchanged (those phases remain unstarted and
  unauthorized); and
- **strengthening** the guard so it now also reads the committed P271L artifact and asserts the preflight
  is **present but NOT applied** (`preflight_only=true`; and `production_migration_executed`,
  `production_schema_modified`, `deployment_started`, `prospective_collection_activated`,
  `activation_timestamp_inserted`, `p271m_started`, `p271n_started` all false). The check reads a static
  file only — no live process, PID, WAL timestamp, network, or production DB connection.

No other P271K invariant was changed. The P271K artifact JSON/MD were **not** modified (not on the
whitelist); only the P271K test file was edited, as authorized.

**Phase boundaries remain intact.** Production apply is still **not** authorized — P271L is preflight-only.
P271M (post-apply verification) and P271N (activation) remain unstarted, unauthorized, and forward-guarded.

**Actual results after reconciliation (re-run 2026-06-14):**
- P271K focused (`tests/test_p271k_prospective_capture_ledger_migration_rehearsal.py`): **37 passed / 0 failed** (37 total). PASS.
- P271L focused (`tests/test_p271l_controlled_deployment_preflight.py`): **50 passed / 0 failed** (50 total). PASS.
- Combined P271J–L: **159 passed / 0 failed** (159 total). PASS.
- Full-repo suite: **NOT RUN** (not required by governance).

**Unchanged governance posture.** Readiness remains `P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY`, with all
six apply blockers from §19 still in force. Official source remains **MANUAL_VERIFICATION_REQUIRED**.
Governance remains **HOLD / WAITING_FOR_USER_AUTHORIZATION**. The production DB was not opened, copied, or
written; SHA-256 before == after == `3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e`.
No prediction-success claim is made.
