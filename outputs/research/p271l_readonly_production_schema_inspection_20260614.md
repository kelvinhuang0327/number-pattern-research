# P271L — Read-only ACTUAL Production Schema Inspection

**Task:** `P271L_READONLY_ACTUAL_PRODUCTION_SCHEMA_INSPECTION`  ·  **Generated:** 2026-06-14  ·  **Mode:** `readonly_actual_production_schema_inspection`
**Classification:** `P271L_READONLY_PRODUCTION_SCHEMA_INSPECTION_COMPLETE`
**Final classification (retained):** `P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY`
**Production apply:** `NOT_READY_FOR_APPLY`  ·  **Governance:** HOLD / WAITING_FOR_USER_AUTHORIZATION
**Official source:** MANUAL_VERIFICATION_REQUIRED

> **Post-inspection correction:** `P271L_PR430_TRUTHFULNESS_AND_CLASSIFIER_HARDENING`
> hardened classifier/tests/artifact/governance without opening production.
> Historical execution commit: `327554cb249c3c7039b3060a05c1477e8457bbbc`.
> The corrected classifier was **not** used for the historical production connection,
> and production was **not** re-inspected.

---

## 1. Executive summary

The single P271L preflight blocker **`ACTUAL_PRODUCTION_SCHEMA_NOT_READ_IN_P271L_PREFLIGHT`**
is now **RESOLVED**. The canonical production database
`lottery_api/data/lottery_v2.db` was reported opened once, **immutable + read-only**
(`file:<path>?mode=ro&immutable=1`), under a verified writer-quiescence maintenance
window, and its full schema was inventoried without retrieving any row payload.
The committed execution path contains one bounded connection call, a guaranteed
`finally` close, no writable fallback, and no retry path. Exact historical execution
count lacks independent persisted telemetry and is therefore an
**`EVIDENCE_LIMITATION`**, with no contradictory evidence.

- **Historical prospective state: `ABSENT_CLEAN`** — the committed production inventory
  contains **zero** prospective or expected-name objects. This supports the historical
  clean-additive finding; any future controlled apply still requires the mandated fresh
  read-only re-audit.
- **Deployed application schema:** 17 tables, 42 indexes, 1 view,
  0 triggers = **60 categorized non-internal objects**.
- **Internal schema:** `sqlite_sequence` = 1 object. Raw `sqlite_schema` total:
  **60 + 1 = 61**.
- **All six legacy comparison tables present** with all source-of-truth columns.
- **Schema collision vs legacy: none** (`collision_free_vs_legacy = True`).
- **DB unchanged by the inspection:** SHA-256 before == after ==
  `3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e` (matches the authorized baseline); `data_version`
  1 → 1; no new journal; sidecars unchanged.

This inspection clears the actual-schema blocker **only**. Production apply remains
**NOT_READY_FOR_APPLY**; P271M / P271N remain unstarted and unauthorized. No prediction-
success claim is made.

## 2. Maintenance-window evidence

- Prior task classification: **`P271L_WRITER_QUIESCENCE_VERIFIED`** (effective start
  2026-06-14 12:13:53 CST). LotteryNew launchd services remain **booted out / stopped**
  for this inspection. This is historical inspection-time state.
- **Pre-connection recheck (Phase 5):** lottery launchd labels loaded = none;
  LotteryNew processes = none; PID 1593 = DEAD; DB holders = none; 3-sample DB SHA-256
  all equal and == expected; WAL zero-byte; journal absent. Gate **PASS**.
- **Post-close recheck (Phase 6):** labels = none; processes = none; PID 1593 = DEAD;
  holders = none; DB SHA-256 == expected; WAL zero-byte (inode/mtime unchanged);
  journal absent. Gate **PASS**.
- `writer_quiescence_verified = True` ·
  `db_holders_absent = True` ·
  `wal_stability_passed = True`.

### Post-inspection operational state

After inspection completion, all eight `com.kelvin.lottery.*` launchd labels were
restored. At correction time, backend port 8002 (`/health` and `/api/ping`) and frontend
port 8081 return HTTP 200; services are currently running. Restoration occurred outside
the inspection transaction, changed no repository files, and did not re-open production
for schema inspection. Historical maintenance-window evidence remains unchanged.

## 3. Read-only authorization boundary

This task performed **only** a bounded immutable read-only schema inspection. It did
**not**: open the DB writable; copy/back up/checkpoint/restore the DB; delete or mutate
any WAL/SHM/journal sidecar; run any migration/deployment/`controlled_apply`; signal,
stop, restart, or start any process; restart LotteryNew services; perform a `logout`,
`reboot`, or `launchctl bootstrap`; start P271M or P271N; or merge any PR.

## 4. Production DB identity

| Field | Value |
|---|---|
| Path | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db` |
| SHA-256 (before) | `3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e` |
| SHA-256 (after) | `3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e` |
| Matches authorized baseline | True |
| Size (bytes) | 99368960 |
| inode | 90843138 |

## 5. Connection and authorizer contract

- **URI:** `file:<path>?mode=ro&immutable=1` · params `mode=ro`, `immutable=1`,
  `uri=True`, `isolation_level=None`, `timeout=0`. No `mode=rw` / non-immutable /
  sqlite3-CLI fallback exists.
- **SQLite authorizer** installed before any inspection query; allows only
  `SELECT`/`READ`, an explicit approved-function allowlist, and a fixed allowlist of
  read-only introspection
  PRAGMAs; **denies** all INSERT/UPDATE/DELETE, CREATE/DROP/ALTER, ATTACH/DETACH,
  transaction control, SAVEPOINT, REINDEX/ANALYZE, vtable ops, `wal_checkpoint`, and
  every non-allowlisted (and setter-form) PRAGMA. Only hardcoded schema-introspection
  queries run; prospective emptiness uses `EXISTS(SELECT 1 ... LIMIT 1)` (never
  `COUNT(*)`, never a payload column).
- **Approved SQL functions:** none. The hardcoded inspection queries require no SQLite
  function calls; all functions default-deny.
- `immutable_gate_passed = True`.

## 6. Actual schema inventory

**Tables (17):** `agent_locks`, `agent_task_runs`, `agent_tasks`, `draws`, `prediction_explanations`, `prediction_items`, `prediction_results`, `prediction_review_status`, `prediction_runs`, `review_actions`, `review_findings`, `review_hypotheses`, `review_sessions`, `shadow_experiments`, `snapshot_schedule`, `strategy_prediction_replays`, `strategy_replay_runs`
**Views (1):** `draws_big_lotto_canonical_main`
**Triggers (0):** none

Count reconciliation: 17 tables + 42 indexes + 0 triggers + 1 view =
**60 categorized application objects**; internal `sqlite_sequence` = **1**;
raw `sqlite_schema` total = **61**. `sqlite_sequence` is not described as an
application table.

| Table | Columns | Indexes | Foreign keys |
|---|---:|---:|---:|
| `agent_locks` | 5 | 1 | 1 |
| `agent_task_runs` | 7 | 2 | 1 |
| `agent_tasks` | 19 | 3 | 1 |
| `draws` | 11 | 4 | 0 |
| `prediction_explanations` | 6 | 1 | 0 |
| `prediction_items` | 10 | 2 | 1 |
| `prediction_results` | 13 | 1 | 1 |
| `prediction_review_status` | 6 | 3 | 2 |
| `prediction_runs` | 11 | 1 | 0 |
| `review_actions` | 13 | 3 | 1 |
| `review_findings` | 7 | 1 | 1 |
| `review_hypotheses` | 10 | 2 | 1 |
| `review_sessions` | 13 | 3 | 0 |
| `shadow_experiments` | 11 | 3 | 1 |
| `snapshot_schedule` | 8 | 2 | 1 |
| `strategy_prediction_replays` | 28 | 8 | 0 |
| `strategy_replay_runs` | 10 | 2 | 0 |

## 7. Schema fingerprint

Deterministic SHA-256 over the normalized object set + per-table columns/indexes/FKs
(no row contents, no volatile metadata):

`af25321f7d24f3b396f183febffab261eefe3ab55dabeb5189a11ef6a074d04a`

SQLite engine version at inspection: `3.53.0`;
`schema_version=86`, `user_version=0`,
`application_id=0`, `page_size=4096`,
`page_count=24260`, `freelist_count=7040`,
`journal_mode=delete`, `encoding=UTF-8`.

Historical `schema_version` was captured only once. Corrected evidence representation:
`schema_version_before=86`, `schema_version_after=NOT_CAPTURED`,
`schema_version_stable=NOT_PROVEN`;
classification **`EVIDENCE_LIMITATION_SCHEMA_VERSION_SINGLE_READ`**. A fresh execution
of the corrected script reads before and after and blocks stability when they differ.

## 8. Source-vs-deployed comparison (legacy tables)

Source of truth = `lottery_api/database.py` `CREATE TABLE` + documented `ALTER TABLE`
migration columns.

| Table | Deployed | Columns (source coverage) | OK |
|---|---|---|---|
| `draws` | ✅ present | 11 cols (missing source: none; extra runtime: ['sell_amount', 'total_amount']) | ✅ |
| `prediction_runs` | ✅ present | 11 cols (missing source: none; extra runtime: none) | ✅ |
| `prediction_items` | ✅ present | 10 cols (missing source: none; extra runtime: none) | ✅ |
| `prediction_results` | ✅ present | 13 cols (missing source: none; extra runtime: none) | ✅ |
| `strategy_replay_runs` | ✅ present | 10 cols (missing source: none; extra runtime: none) | ✅ |
| `strategy_prediction_replays` | ✅ present | 28 cols (missing source: none; extra runtime: ['truth_level', 'controlled_apply_id', 'source', 'provenance_hash', 'provenance_source', 'dry_run', 'prediction_cutoff_date', 'prediction_generated_at', 'bet_index']) | ✅ |

`all_legacy_tables_present = True` ·
`all_source_columns_present = True`.

This proves table existence and documented source-column-name coverage only.
Types, nullability, defaults, primary keys, foreign keys, and index equivalence are
**`NOT_FULLY_VERIFIED`**; no full schema-equivalence claim is made.

**Deployed-only tables relative to `database.py`'s 13 source-defined tables:**
`agent_locks`, `agent_task_runs`, `agent_tasks`, `prediction_explanations`.
None are prospective objects or collisions.

## 9. Expected prospective contract (P271J)

`schema_version=p271j_prospective_capture_ledger.v1`; 6 tables
(`prospective_schema_meta`, `prospective_activation_registry`, `prospective_capture_batches`, `prospective_prediction_ledger`, `prospective_capture_events`, `prospective_outcome_links`); 2 unique indexes
(`idx_ledger_identity`, `idx_batch_cluster`); 10
append-only triggers; 6-column semantic unique key — sourced verbatim from
`lottery_api/prospective_capture_ledger.py`.

## 10. Actual prospective state

**`ABSENT_CLEAN`** — present prospective tables: none;
present expected indexes: none;
present prospective triggers: none;
unexpected prospective objects: none;
installed schema version: None.

This historical conclusion remains supported by the committed inventory, which contains
none of the six expected tables, two explicit indexes, ten expected triggers, or
unexpected prospective-prefixed objects. The corrected classifier was not used for the
historical connection; it revalidates this conclusion from committed inventory only.

## 11. Collision / compatibility result

`collision_free_vs_legacy = True`;
contract names already present in deployed = none;
legacy/orphan name collisions = none in the historical inventory. The corrected
classifier covers all 18 object names and fails closed on orphan expected indexes,
triggers, registry/version objects, wrong object types, and wrong target tables. This is
a historical collision finding, not a current apply authorization; fresh read-only
re-audit remains required.

## 12. Concurrency and integrity proof

| Check | Result |
|---|---|
| DB hash unchanged (before==after) | True |
| DB stat unchanged (size/inode/mtime) | True |
| Sidecars unchanged | True |
| No new journal created | True |
| `data_version` unchanged (1→1) | True |
| `schema_version` before/after stability | NOT_PROVEN (single historical read) |
| Overall integrity_ok | True |

## 13. Cleared blocker

`actual_schema_blocker_cleared = True` —
**`ACTUAL_PRODUCTION_SCHEMA_NOT_READ_IN_P271L_PREFLIGHT` is RESOLVED.**

## 14. Remaining apply blockers

Production apply stays **NOT_READY_FOR_APPLY**; the following independent blockers remain
(unchanged by this inspection):

- fresh_apply_time_production_db_hash_reverification_required
- verified_apply_time_maintenance_window_required
- verified_writer_shutdown_required
- verified_backup_destination_and_integrity_evidence_required
- rollback_authorization_and_restore_procedure_required
- wal_shm_reconciliation_at_apply_time_required

## 15. P271M / P271N separation

`p271m_started = False`,
`p271n_started = False`,
`production_apply_authorized = False`.
P271M (post-apply verification) and P271N (activation) remain unstarted, each requiring
its own separate explicit authorization; no phase implicitly authorizes the next.

## 16. Non-actions

`production_db_opened_writable=False`,
`production_db_copied=False`,
`production_db_written=False`,
`backup_executed=False`,
`checkpoint_executed=False`,
`restore_executed=False`,
`process_signaled_stopped_restarted_by_this_task=False`,
`production_migration_executed=False`,
`deployment_started=False`,
`prospective_collection_activated=False`.

## 17. Limitations

- This is an **actual-schema** read; it asserts schema structure only — no data content,
  row counts, integrity_check, or foreign_key_check were run (out of scope; would read
  data / be heavy). `journal_mode` is reported as read from the immutable connection.
- Writer quiescence and DB-holder absence are evidenced operationally
  (launchctl/ps/lsof) at the orchestration layer, recorded under
  `maintenance_window_evidence`; the inspection script itself inspects only the DB.
- Official source verification status remains **MANUAL_VERIFICATION_REQUIRED**. This
  report makes **no prediction-success claim**.
- Historical single-connection count is an **EVIDENCE_LIMITATION**: one bounded code
  path and guaranteed close support the report, but independent execution telemetry was
  not persisted.
- Historical source comparison is limited to table and column-name presence.

## 18. Post-correction tests

- Focused:
  `./venv/bin/python -m pytest tests/test_p271l_readonly_production_schema_inspection.py -q`
  — **72 collected / 72 passed / 0 failed / PASS**.
- Combined P271J-L:
  `./venv/bin/python -m pytest tests/test_p271j_prospective_capture_ledger_implementation.py tests/test_p271k_prospective_capture_ledger_migration_rehearsal.py tests/test_p271l_controlled_deployment_preflight.py tests/test_p271l_readonly_production_schema_inspection.py -q`
  — **231 collected / 231 passed / 0 failed / PASS**.
- Full repository suite: **NOT_RUN** — governance requires the focused and combined
  suites for this correction.

## 19. Final classification

- Correction: **`P271L_PR430_TRUTHFULNESS_HARDENING_COMPLETE`**
- Inspection: **`P271L_READONLY_PRODUCTION_SCHEMA_INSPECTION_COMPLETE`**
- Overall: **`P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY`**
- PR merge readiness: **`REQUIRES_FRESH_READ_ONLY_REAUDIT`**
- Production apply: **`NOT_READY_FOR_APPLY`**
- Governance: **HOLD / WAITING_FOR_USER_AUTHORIZATION**
- Current services: **restored, running, and healthy**.
