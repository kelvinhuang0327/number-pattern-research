"""P271K — temporary-DB migration rehearsal for the P271J prospective ledger.

**Rehearsal only.** This module installs the *merged* P271J prospective-capture
ledger schema (``lottery_api.prospective_capture_ledger.install_schema``) onto
**caller-supplied temporary SQLite databases only** — pytest ``tmp_path`` files,
OS temporary directories *outside* the repository, or ``sqlite3 ":memory:"`` —
to prove additive compatibility, idempotence, rollback atomicity, caller
transaction ownership, locked/busy fail-closed behaviour, and temporary
backup/restore viability against a *source-grounded* representative legacy
schema.

Hard boundaries (P271K task contract):
  * It NEVER opens, attaches, copies, backs up, restores, or writes the
    canonical production database ``lottery_api/data/lottery_v2.db``. The only
    use of that path is to compute its realpath so it can be *rejected*.
  * It NEVER discovers a database from the environment or any default
    configuration; the caller must pass an explicit path.
  * Any repository-contained path (and any symlink resolving into the
    repository or onto the canonical DB realpath) is rejected before a
    connection is ever opened.
  * No import-time database access; no route / server / scheduler / network /
    runtime registration; the schema contract is taken *verbatim* from the
    merged P271J module — this script never re-defines or mutates that schema.
  * This is NOT an approved production-migration command. A passing rehearsal
    does not authorise P271L (deployment), P271M (post-deploy verification), or
    P271N (activation).

The representative legacy schema is grounded line-for-line in
``lottery_api/database.py`` (cited per statement below); it contains only
deterministic synthetic rows and never any production data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

# Make ``lottery_api`` importable when this file is run as a script from the
# repository root (``python scripts/p271k_...py``). This only manipulates
# ``sys.path``; it performs no database access.
_THIS_FILE = os.path.abspath(__file__)
REPO_ROOT = os.path.dirname(os.path.dirname(_THIS_FILE))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import lottery_api.prospective_capture_ledger as pcl  # noqa: E402  (after sys.path)

# Canonical production DB realpath — referenced ONLY so it can be rejected.
# This module never opens it.
CANONICAL_PRODUCTION_DB = os.path.realpath(
    os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")
)
_REPO_ROOT_REAL = os.path.realpath(REPO_ROOT)

MEMORY_DB = ":memory:"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RehearsalError(Exception):
    """Base class for P271K rehearsal errors."""


class PathSafetyError(RehearsalError):
    """Raised when a requested DB path is unsafe (canonical / repo-contained /
    missing / a disallowed ``:memory:`` for a file-only operation)."""


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def validate_temporary_db_path(
    path: object,
    *,
    allow_memory: bool = True,
    require_file: bool = False,
) -> str:
    """Validate a caller-supplied temporary DB path and return a safe target.

    Returns ``":memory:"`` unchanged when memory is allowed, otherwise the
    resolved real filesystem path. Fails closed (``PathSafetyError``) for a
    missing path, ``:memory:`` where a real file is required, the canonical
    production DB realpath (covering symlinks, since ``realpath`` resolves
    them), or any repository-contained path. No database is opened here.
    """

    if path is None:
        raise PathSafetyError("an explicit temporary database path is required")
    if not isinstance(path, (str, bytes, os.PathLike)):
        raise PathSafetyError(f"unsupported path type: {type(path)!r}")

    spath = os.fspath(path)
    if isinstance(spath, bytes):
        spath = spath.decode()

    if spath == MEMORY_DB:
        if require_file:
            raise PathSafetyError(
                ":memory: is not allowed for a file-level (backup/restore) "
                "operation; supply a real temporary file path outside the repo"
            )
        if not allow_memory:
            raise PathSafetyError(":memory: is not allowed for this operation")
        return MEMORY_DB

    if not spath:
        raise PathSafetyError("an explicit temporary database path is required")

    real = os.path.realpath(spath)

    if real == CANONICAL_PRODUCTION_DB:
        raise PathSafetyError(
            "refusing to operate on the canonical production database "
            f"({CANONICAL_PRODUCTION_DB!r}); P271K is temporary-DB only"
        )
    if real == _REPO_ROOT_REAL or real.startswith(_REPO_ROOT_REAL + os.sep):
        raise PathSafetyError(
            "refusing a repository-contained path "
            f"({real!r}); use an OS temp dir or pytest tmp_path outside the repo"
        )
    return real


def connect_temporary(path: object, *, allow_memory: bool = True) -> sqlite3.Connection:
    """Open a connection to a validated temporary DB path. Never the prod DB."""

    target = validate_temporary_db_path(path, allow_memory=allow_memory)
    conn = sqlite3.connect(target)
    return conn


# ---------------------------------------------------------------------------
# Source-grounded representative legacy schema
# ---------------------------------------------------------------------------
#
# Grounded verbatim in lottery_api/database.py (base CREATE statements; the
# runtime additionally applies idempotent ALTER migrations which are not needed
# to prove additive non-interference). Line citations refer to database.py at
# P271J merge commit 3dc06f76a70ff13927b63491fb4580528ed86a3d.

LEGACY_SCHEMA_STATEMENTS = (
    # draws (database.py:70-81) — representative unrelated table (non-interference).
    """
    CREATE TABLE IF NOT EXISTS draws (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        draw TEXT NOT NULL,
        date TEXT NOT NULL,
        lottery_type TEXT NOT NULL,
        numbers TEXT NOT NULL,
        special INTEGER DEFAULT 0,
        jackpot_amount REAL DEFAULT NULL,
        numbers_positional TEXT DEFAULT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(draw, lottery_type)
    )
    """,
    # prediction_runs (database.py:112-121) — prediction FK target.
    """
    CREATE TABLE IF NOT EXISTS prediction_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lottery_type TEXT NOT NULL,
        latest_known_draw TEXT NOT NULL,
        latest_known_date TEXT,
        strategy_name TEXT NOT NULL,
        snapshot_source TEXT DEFAULT 'VALID',
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # prediction_items (database.py:150-159) — FK -> prediction_runs(id).
    """
    CREATE TABLE IF NOT EXISTS prediction_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        bet_index INTEGER NOT NULL,
        numbers TEXT NOT NULL,
        special INTEGER,
        status TEXT DEFAULT 'PENDING',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (run_id) REFERENCES prediction_runs(id)
    )
    """,
    # prediction_results (database.py:164-177) — FK -> prediction_items(id).
    """
    CREATE TABLE IF NOT EXISTS prediction_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL UNIQUE,
        actual_draw TEXT NOT NULL,
        actual_date TEXT,
        actual_numbers TEXT NOT NULL,
        actual_special INTEGER,
        hit_count INTEGER NOT NULL,
        matched_numbers TEXT NOT NULL,
        special_hit INTEGER DEFAULT 0,
        researched TEXT DEFAULT '無',
        resolved_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_id) REFERENCES prediction_items(id)
    )
    """,
    # strategy_replay_runs (database.py:372-383) — replay FK target.
    """
    CREATE TABLE IF NOT EXISTS strategy_replay_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lottery_type TEXT NOT NULL,
        strategy_scope TEXT NOT NULL DEFAULT 'ALL',
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT NOT NULL DEFAULT 'RUNNING',
        generator_version TEXT NOT NULL DEFAULT 'v0.1',
        data_hash TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # strategy_prediction_replays (database.py:389-411) — the table P271J
    # deliberately does NOT reuse; FK -> strategy_replay_runs(id).
    """
    CREATE TABLE IF NOT EXISTS strategy_prediction_replays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lottery_type TEXT NOT NULL,
        target_draw TEXT NOT NULL,
        target_date TEXT,
        strategy_id TEXT NOT NULL,
        strategy_name TEXT NOT NULL,
        strategy_version TEXT NOT NULL DEFAULT 'v0.1',
        history_cutoff_draw TEXT,
        replay_status TEXT NOT NULL,
        reject_reason TEXT,
        predicted_numbers TEXT,
        predicted_special INTEGER,
        actual_numbers TEXT,
        actual_special INTEGER,
        hit_numbers TEXT,
        hit_count INTEGER DEFAULT 0,
        special_hit INTEGER DEFAULT 0,
        replay_run_id INTEGER,
        generated_at TEXT,
        FOREIGN KEY (replay_run_id) REFERENCES strategy_replay_runs(id),
        UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)
    )
    """,
)

# Representative subset of the real legacy indexes (database.py:215-225,385-386,413-418).
LEGACY_INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_pred_runs_lottery ON prediction_runs(lottery_type)",
    "CREATE INDEX IF NOT EXISTS idx_pred_items_run ON prediction_items(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_srr_lottery ON strategy_replay_runs(lottery_type)",
    "CREATE INDEX IF NOT EXISTS idx_spr_strategy ON strategy_prediction_replays(strategy_id)",
)

# Source grounding map (for the artifact / audit trail).
LEGACY_FIXTURE_SOURCE_GROUNDING = {
    "source_file": "lottery_api/database.py",
    "source_commit": "3dc06f76a70ff13927b63491fb4580528ed86a3d",
    "tables": {
        "draws": "database.py:70-81",
        "prediction_runs": "database.py:112-121",
        "prediction_items": "database.py:150-159",
        "prediction_results": "database.py:164-177",
        "strategy_replay_runs": "database.py:372-383",
        "strategy_prediction_replays": "database.py:389-411",
    },
    "note": (
        "Base CREATE statements reproduced verbatim; idempotent runtime ALTER "
        "migrations omitted (not required for additive non-interference). The "
        "legacy schema defines no global version-metadata table, so the P271J "
        "prospective_schema_meta marker cannot collide."
    ),
}

# Deterministic synthetic rows (NO production data).
_SYNTHETIC_DRAWS = (
    ("114000001", "2026/01/02", "DAILY_539", "3,11,18,27,35", 0),
    ("114000002", "2026/01/03", "DAILY_539", "5,9,22,28,38", 0),
    ("115000037", "2026/03/20", "BIG_LOTTO", "11,15,33,38,41,43", 21),
)


def build_legacy_fixture(conn: sqlite3.Connection, *, with_rows: bool = True) -> None:
    """Create the source-grounded representative legacy schema and (optionally)
    deterministic synthetic rows on a caller-supplied temporary connection."""

    conn.execute("PRAGMA foreign_keys = ON")
    for statement in LEGACY_SCHEMA_STATEMENTS:
        conn.execute(statement)
    for statement in LEGACY_INDEX_STATEMENTS:
        conn.execute(statement)
    if with_rows:
        conn.executemany(
            "INSERT INTO draws (draw, date, lottery_type, numbers, special) "
            "VALUES (?, ?, ?, ?, ?)",
            _SYNTHETIC_DRAWS,
        )
        conn.execute(
            "INSERT INTO prediction_runs (id, lottery_type, latest_known_draw, "
            "latest_known_date, strategy_name, snapshot_source, notes, created_at) "
            "VALUES (1, 'DAILY_539', '114000002', '2026/01/03', "
            "'acb_markov_midfreq_3bet', 'VALID', 'p271k synthetic', "
            "'2026-01-03T12:00:00Z')",
        )
        conn.execute(
            "INSERT INTO prediction_items (id, run_id, bet_index, numbers, special, "
            "status, created_at) VALUES "
            "(1, 1, 1, '4,10,17,34,36', NULL, 'PENDING', '2026-01-03T12:00:00Z')",
        )
        conn.execute(
            "INSERT INTO prediction_results (id, item_id, actual_draw, actual_date, "
            "actual_numbers, actual_special, hit_count, matched_numbers, special_hit, "
            "resolved_at) VALUES "
            "(1, 1, '114000003', '2026/01/06', '4,17,20,33,36', 0, 3, '4,17,36', 0, "
            "'2026-01-06T21:30:00Z')",
        )
        conn.execute(
            "INSERT INTO strategy_replay_runs (id, lottery_type, strategy_scope, "
            "started_at, status, generator_version) VALUES "
            "(1, 'DAILY_539', 'ALL', '2026-01-01T00:00:00Z', 'DONE', 'v0.1')",
        )
        conn.execute(
            "INSERT INTO strategy_prediction_replays (id, lottery_type, target_draw, "
            "strategy_id, strategy_name, strategy_version, replay_status, "
            "predicted_numbers, hit_count, special_hit, replay_run_id, generated_at) "
            "VALUES (1, 'DAILY_539', '114000002', 'acb', 'acb_1bet', 'v0.1', 'OK', "
            "'5,9,22,28,38', 5, 0, 1, '2026-01-01T00:05:00Z')",
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Fingerprints and integrity checks (legacy = everything except prospective_*)
# ---------------------------------------------------------------------------


def _legacy_master_rows(conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE tbl_name NOT LIKE 'prospective_%' "
        "AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type, name, tbl_name"
    ).fetchall()


def legacy_schema_fingerprint(conn: sqlite3.Connection) -> str:
    """SHA-256 of the legacy schema (every sqlite_master object whose table is
    not a ``prospective_*`` table and not an internal ``sqlite_*`` object)."""

    rows = [list(r) for r in _legacy_master_rows(conn)]
    blob = json.dumps(rows, ensure_ascii=False, sort_keys=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def legacy_data_fingerprint(conn: sqlite3.Connection) -> dict:
    """Per-table {count, content_hash} for every legacy (non-prospective) table."""

    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'prospective_%' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
    ]
    out: dict = {}
    for table in tables:
        rows = conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
        materialized = [list(r) for r in rows]
        blob = json.dumps(materialized, ensure_ascii=False, default=str)
        out[table] = {
            "count": len(materialized),
            "content_hash": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        }
    return out


def foreign_key_check(conn: sqlite3.Connection) -> list:
    """Return ``PRAGMA foreign_key_check`` violations (empty list == OK)."""

    return [list(r) for r in conn.execute("PRAGMA foreign_key_check").fetchall()]


def integrity_check(conn: sqlite3.Connection) -> str:
    """Return the ``PRAGMA integrity_check`` result ('ok' when consistent)."""

    row = conn.execute("PRAGMA integrity_check").fetchone()
    return row[0] if row else "<none>"


def legacy_snapshot(conn: sqlite3.Connection) -> dict:
    """Composite legacy fingerprint used for before/after non-interference."""

    return {
        "schema_fingerprint": legacy_schema_fingerprint(conn),
        "data_fingerprint": legacy_data_fingerprint(conn),
        "foreign_key_violations": foreign_key_check(conn),
        "integrity_check": integrity_check(conn),
    }


# ---------------------------------------------------------------------------
# Prospective install (delegated verbatim to the merged P271J contract)
# ---------------------------------------------------------------------------


def install_prospective_schema(conn: sqlite3.Connection) -> str:
    """Install the merged P271J prospective schema. Pure delegation — the
    schema contract is owned by ``lottery_api.prospective_capture_ledger`` and
    is never re-defined or mutated here."""

    return pcl.install_schema(conn)


def prospective_objects_present(conn: sqlite3.Connection) -> dict:
    """Which P271J objects are present (read-only inspection)."""

    objects = pcl.schema_objects(conn)
    tables = objects["tables"]
    triggers = objects["triggers"]
    indexes = objects["indexes"]
    expected_tables = set(pcl.REQUIRED_TABLES)
    expected_triggers = set()
    for table in pcl._APPEND_ONLY_TABLES:
        expected_triggers.add(f"trg_{table}_no_update")
        expected_triggers.add(f"trg_{table}_no_delete")
    expected_indexes = {"idx_ledger_identity", "idx_batch_cluster"}
    return {
        "tables_present": expected_tables <= tables,
        "triggers_present": expected_triggers <= triggers,
        "indexes_present": expected_indexes <= indexes,
        "missing_tables": sorted(expected_tables - tables),
        "missing_triggers": sorted(expected_triggers - triggers),
        "missing_indexes": sorted(expected_indexes - indexes),
    }


def has_any_prospective_object(conn: sqlite3.Connection) -> bool:
    """True if ANY prospective object (table/index/trigger) exists."""

    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE tbl_name LIKE 'prospective_%' OR name LIKE 'trg_prospective_%' "
        "OR name IN ('idx_ledger_identity', 'idx_batch_cluster')"
    ).fetchone()
    return bool(row[0])


# ---------------------------------------------------------------------------
# Temporary-only backup / restore (never the production DB)
# ---------------------------------------------------------------------------


def backup_database(src_path: object, dest_path: object) -> str:
    """Back up one *temporary* DB to another *temporary* path via the sqlite3
    online-backup API. Both paths must validate as safe temporary files."""

    src_real = validate_temporary_db_path(src_path, allow_memory=False, require_file=True)
    dest_real = validate_temporary_db_path(dest_path, allow_memory=False, require_file=True)
    src = sqlite3.connect(src_real)
    dst = sqlite3.connect(dest_real)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return dest_real


# A subclass used only to rehearse an injected mid-install DDL failure. It is a
# real ``sqlite3.Connection`` (so the module's ``isinstance`` guard accepts it)
# and raises exactly once, after a configurable number of CREATE TABLE
# statements, to prove the module's BEGIN IMMEDIATE / ROLLBACK is atomic.
class InjectedFailureConnection(sqlite3.Connection):
    fail_after_create_tables = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._armed = False
        self._create_table_count = 0
        self._injected = False

    def arm(self) -> None:
        """Begin counting CREATE TABLE statements (call AFTER building the
        legacy fixture so only the prospective install is affected)."""

        self._armed = True

    def execute(self, sql, *params):  # type: ignore[override]
        stripped = sql.lstrip().upper()
        if self._armed and stripped.startswith("CREATE TABLE") and not self._injected:
            self._create_table_count += 1
            if self._create_table_count > self.fail_after_create_tables:
                self._injected = True
                raise sqlite3.OperationalError(
                    "p271k injected mid-install failure (rehearsal)"
                )
        return super().execute(sql, *params)


# ---------------------------------------------------------------------------
# Rehearsal scenarios
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    detail: dict = field(default_factory=dict)


def _new_db_path(workdir_real: str, name: str) -> str:
    return os.path.join(workdir_real, name)


def _validate_workdir(workdir: object) -> str:
    real = validate_temporary_db_path(workdir, allow_memory=False, require_file=True)
    if not os.path.isdir(real):
        raise PathSafetyError(f"workdir does not exist or is not a directory: {real!r}")
    return real


def scenario_clean_install(workdir_real: str) -> ScenarioResult:
    path = _new_db_path(workdir_real, "scenario_a_clean.db")
    conn = connect_temporary(path)
    try:
        build_legacy_fixture(conn)
        before = legacy_snapshot(conn)
        version = install_prospective_schema(conn)
        after = legacy_snapshot(conn)
        present = prospective_objects_present(conn)
        passed = (
            version == pcl.SCHEMA_VERSION
            and before == after
            and present["tables_present"]
            and present["triggers_present"]
            and present["indexes_present"]
            and after["foreign_key_violations"] == []
            and after["integrity_check"] == "ok"
        )
        return ScenarioResult(
            "A_clean_additive_install",
            passed,
            {
                "schema_version": version,
                "legacy_schema_unchanged": before["schema_fingerprint"]
                == after["schema_fingerprint"],
                "legacy_data_unchanged": before["data_fingerprint"]
                == after["data_fingerprint"],
                "prospective_objects": present,
                "foreign_key_violations": after["foreign_key_violations"],
                "integrity_check": after["integrity_check"],
            },
        )
    finally:
        conn.close()


def scenario_idempotence(workdir_real: str) -> ScenarioResult:
    path = _new_db_path(workdir_real, "scenario_b_idem.db")
    conn = connect_temporary(path)
    try:
        build_legacy_fixture(conn)
        install_prospective_schema(conn)
        snap1 = legacy_snapshot(conn)
        objs1 = pcl.schema_objects(conn)
        v2 = install_prospective_schema(conn)
        snap2 = legacy_snapshot(conn)
        objs2 = pcl.schema_objects(conn)
        passed = (
            v2 == pcl.SCHEMA_VERSION
            and snap1 == snap2
            and objs1 == objs2
        )
        return ScenarioResult(
            "B_same_version_idempotence",
            passed,
            {
                "second_install_version": v2,
                "objects_identical": objs1 == objs2,
                "legacy_unchanged": snap1 == snap2,
            },
        )
    finally:
        conn.close()


def scenario_incompatible_version(workdir_real: str) -> ScenarioResult:
    path = _new_db_path(workdir_real, "scenario_c_incompat.db")
    conn = connect_temporary(path)
    try:
        build_legacy_fixture(conn)
        # Plant an incompatible prospective schema-version marker.
        conn.execute(
            f"CREATE TABLE {pcl._META_TABLE} (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            f"INSERT INTO {pcl._META_TABLE} (key, value) VALUES ('schema_version', ?)",
            ("p271j_prospective_capture_ledger.v0_INCOMPATIBLE",),
        )
        conn.commit()
        before = legacy_snapshot(conn)
        before_objs = pcl.schema_objects(conn)
        raised = None
        try:
            install_prospective_schema(conn)
        except pcl.SchemaVersionError as exc:
            raised = exc
        after = legacy_snapshot(conn)
        after_objs = pcl.schema_objects(conn)
        # No NEW prospective ledger tables/indexes/triggers beyond the planted meta.
        new_tables = (after_objs["tables"] - before_objs["tables"])
        new_indexes = (after_objs["indexes"] - before_objs["indexes"])
        new_triggers = (after_objs["triggers"] - before_objs["triggers"])
        passed = (
            raised is not None
            and before == after
            and not new_tables
            and not new_indexes
            and not new_triggers
        )
        return ScenarioResult(
            "C_incompatible_version_rejected",
            passed,
            {
                "raised": type(raised).__name__ if raised else None,
                "new_objects_created": sorted(new_tables | new_indexes | new_triggers),
                "legacy_unchanged": before == after,
            },
        )
    finally:
        conn.close()


def scenario_injected_failure(workdir_real: str) -> ScenarioResult:
    path = _new_db_path(workdir_real, "scenario_d_injected.db")
    conn = sqlite3.connect(
        validate_temporary_db_path(path), factory=InjectedFailureConnection
    )
    try:
        build_legacy_fixture(conn)
        conn.arm()  # only count CREATE TABLE during the prospective install
        before = legacy_snapshot(conn)
        raised = None
        try:
            install_prospective_schema(conn)
        except sqlite3.OperationalError as exc:
            raised = exc
        after = legacy_snapshot(conn)
        # Full rollback: zero prospective objects, no half-written meta marker,
        # and the connection left with no open transaction.
        no_prospective = not has_any_prospective_object(conn)
        version_marker = pcl.get_schema_version(conn)
        passed = (
            raised is not None
            and no_prospective
            and version_marker is None
            and before == after
            and conn.in_transaction is False
        )
        return ScenarioResult(
            "D_injected_failure_full_rollback",
            passed,
            {
                "raised": type(raised).__name__ if raised else None,
                "prospective_objects_remaining": not no_prospective,
                "orphan_version_marker": version_marker,
                "legacy_unchanged": before == after,
                "connection_left_in_transaction": conn.in_transaction,
            },
        )
    finally:
        conn.close()


def scenario_ambient_transaction(workdir_real: str) -> ScenarioResult:
    path = _new_db_path(workdir_real, "scenario_e_ambient.db")
    conn = connect_temporary(path)
    try:
        build_legacy_fixture(conn)
        before = legacy_snapshot(conn)
        # Open a caller-owned transaction and insert an unrelated synthetic row.
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers, special) "
            "VALUES ('999000001', '2026/06/13', 'DAILY_539', '1,2,3,4,5', 0)"
        )
        in_tx_before = conn.in_transaction
        raised = None
        try:
            install_prospective_schema(conn)
        except pcl.AmbientTransactionError as exc:
            raised = exc
        in_tx_after = conn.in_transaction
        # A second connection must NOT see the caller's uncommitted row and no
        # prospective object must exist.
        observer = sqlite3.connect(validate_temporary_db_path(path))
        try:
            observer_sees = observer.execute(
                "SELECT COUNT(*) FROM draws WHERE draw='999000001'"
            ).fetchone()[0]
            observer_prospective = has_any_prospective_object(observer)
        finally:
            observer.close()
        # Caller retains ownership: it can roll its own work back.
        conn.rollback()
        rolled = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE draw='999000001'"
        ).fetchone()[0]
        after = legacy_snapshot(conn)
        passed = (
            raised is not None
            and in_tx_before is True
            and in_tx_after is True
            and observer_sees == 0
            and observer_prospective is False
            and rolled == 0
            and before == after
        )
        return ScenarioResult(
            "E_ambient_transaction_rejected",
            passed,
            {
                "raised": type(raised).__name__ if raised else None,
                "caller_tx_open_after_rejection": in_tx_after,
                "observer_saw_uncommitted_row": bool(observer_sees),
                "observer_saw_prospective_object": observer_prospective,
                "caller_rollback_effective": rolled == 0,
            },
        )
    finally:
        conn.close()


def scenario_locked_database(workdir_real: str) -> ScenarioResult:
    path = _new_db_path(workdir_real, "scenario_f_locked.db")
    setup = connect_temporary(path)
    try:
        build_legacy_fixture(setup)
    finally:
        setup.close()

    # Holder grabs an EXCLUSIVE lock; installer must fail closed (locked), not
    # retry forever, and leave no partial prospective schema.
    holder = connect_temporary(path)
    installer = connect_temporary(path)
    try:
        holder.isolation_level = None
        holder.execute("BEGIN EXCLUSIVE")
        holder.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers, special) "
            "VALUES ('888000001', '2026/06/13', 'DAILY_539', '6,7,8,9,10', 0)"
        )
        raised = None
        try:
            install_prospective_schema(installer)
        except sqlite3.OperationalError as exc:
            raised = exc
        # ``in_transaction`` is a pure property read (no I/O), safe while locked.
        installer_in_tx = installer.in_transaction
        # Release the holder's EXCLUSIVE lock BEFORE inspecting (reads block too).
        holder.rollback()
        installer_prospective = has_any_prospective_object(installer)
        no_prospective = not installer_prospective
        passed = (
            raised is not None
            and no_prospective
            and installer_in_tx is False
        )
        return ScenarioResult(
            "F_locked_database_fail_closed",
            passed,
            {
                "raised": type(raised).__name__ if raised else None,
                "lock_message_is_locked": bool(raised)
                and "lock" in str(raised).lower(),
                "prospective_objects_after_lock": installer_prospective,
                "installer_left_in_transaction": installer_in_tx,
            },
        )
    finally:
        installer.close()
        holder.close()


def scenario_backup_restore(workdir_real: str) -> ScenarioResult:
    path = _new_db_path(workdir_real, "scenario_g_source.db")
    backup_path = _new_db_path(workdir_real, "scenario_g_backup.db")
    restore_path = _new_db_path(workdir_real, "scenario_g_restore.db")

    conn = connect_temporary(path)
    try:
        build_legacy_fixture(conn)
        pre_install = legacy_snapshot(conn)
    finally:
        conn.close()

    # Backup the legacy-only DB, THEN install prospective schema on the original.
    backup_database(path, backup_path)
    conn = connect_temporary(path)
    try:
        install_prospective_schema(conn)
    finally:
        conn.close()

    # Restore the pre-install backup into a fresh temporary path.
    backup_database(backup_path, restore_path)
    restored = connect_temporary(restore_path)
    try:
        restored_snap = legacy_snapshot(restored)
        restored_has_prospective = has_any_prospective_object(restored)
    finally:
        restored.close()

    passed = (
        restored_snap["schema_fingerprint"] == pre_install["schema_fingerprint"]
        and restored_snap["data_fingerprint"] == pre_install["data_fingerprint"]
        and restored_snap["foreign_key_violations"] == []
        and restored_snap["integrity_check"] == "ok"
        and restored_has_prospective is False
    )
    return ScenarioResult(
        "G_temporary_backup_restore",
        passed,
        {
            "restored_matches_pre_install": restored_snap["schema_fingerprint"]
            == pre_install["schema_fingerprint"]
            and restored_snap["data_fingerprint"] == pre_install["data_fingerprint"],
            "restored_has_prospective_objects": restored_has_prospective,
            "note": "Temporary-DB backup/restore only; NOT production rollback approval.",
        },
    )


def scenario_existing_prospective_rows(workdir_real: str) -> ScenarioResult:
    """H — same-version prospective rows survive a reinstall unchanged."""

    path = _new_db_path(workdir_real, "scenario_h_rows.db")
    conn = connect_temporary(path)
    try:
        build_legacy_fixture(conn)
        install_prospective_schema(conn)
        # Insert a synthetic registry row directly (append-only table); we only
        # need to prove a reinstall preserves it byte-for-byte.
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            f"INSERT INTO {pcl._REGISTRY_TABLE} (activation_id, "
            "activation_artifact_commit, deployed_implementation_commit, "
            "migration_verification_ref, activation_merged_at_utc, "
            "prospective_start_at_utc, status, created_by, recorded_at_utc) VALUES "
            "('act_p271k', 'cafe', 'beef', 'ref', '2026-06-01T00:00:00+00:00', "
            "'2026-06-01T00:00:00+00:00', 'INACTIVE', 'p271k', "
            "'2026-06-01T00:00:00+00:00')"
        )
        conn.execute("COMMIT")
        before_rows = conn.execute(
            f"SELECT * FROM {pcl._REGISTRY_TABLE} ORDER BY rowid"
        ).fetchall()
        before_hash = hashlib.sha256(
            json.dumps([list(r) for r in before_rows], default=str).encode()
        ).hexdigest()
        v2 = install_prospective_schema(conn)
        after_rows = conn.execute(
            f"SELECT * FROM {pcl._REGISTRY_TABLE} ORDER BY rowid"
        ).fetchall()
        after_hash = hashlib.sha256(
            json.dumps([list(r) for r in after_rows], default=str).encode()
        ).hexdigest()
        passed = (
            v2 == pcl.SCHEMA_VERSION
            and len(after_rows) == 1
            and before_hash == after_hash
        )
        return ScenarioResult(
            "H_existing_prospective_rows_preserved",
            passed,
            {
                "row_count_after_reinstall": len(after_rows),
                "rows_unchanged": before_hash == after_hash,
            },
        )
    finally:
        conn.close()


def scenario_constraints_enforced(workdir_real: str) -> ScenarioResult:
    """I — FK on, semantic uniqueness, and append-only UPDATE/DELETE triggers."""

    path = _new_db_path(workdir_real, "scenario_i_constraints.db")
    conn = connect_temporary(path)
    try:
        build_legacy_fixture(conn)
        install_prospective_schema(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        fk_on = conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

        # Insert a registry row, then prove UPDATE and DELETE are rejected.
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            f"INSERT INTO {pcl._REGISTRY_TABLE} (activation_id, "
            "activation_artifact_commit, deployed_implementation_commit, "
            "migration_verification_ref, activation_merged_at_utc, "
            "prospective_start_at_utc, status, created_by, recorded_at_utc) VALUES "
            "('act_i', 'a', 'b', 'r', '2026-06-01T00:00:00+00:00', "
            "'2026-06-01T00:00:00+00:00', 'INACTIVE', 'p271k', "
            "'2026-06-01T00:00:00+00:00')"
        )
        conn.execute("COMMIT")

        update_blocked = False
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                f"UPDATE {pcl._REGISTRY_TABLE} SET status='ACTIVE' "
                "WHERE activation_id='act_i'"
            )
            conn.execute("COMMIT")
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK")
            update_blocked = True
        except sqlite3.OperationalError:
            conn.execute("ROLLBACK")
            update_blocked = True

        delete_blocked = False
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                f"DELETE FROM {pcl._REGISTRY_TABLE} WHERE activation_id='act_i'"
            )
            conn.execute("COMMIT")
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK")
            delete_blocked = True
        except sqlite3.OperationalError:
            conn.execute("ROLLBACK")
            delete_blocked = True

        # Semantic uniqueness: idx_ledger_identity is a UNIQUE index.
        idx_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' "
            "AND name='idx_ledger_identity'"
        ).fetchone()
        unique_index = bool(idx_sql) and "UNIQUE" in idx_sql[0].upper()

        passed = fk_on and update_blocked and delete_blocked and unique_index
        return ScenarioResult(
            "I_constraints_and_append_only_enforced",
            passed,
            {
                "foreign_keys_on": fk_on,
                "append_only_update_blocked": update_blocked,
                "append_only_delete_blocked": delete_blocked,
                "semantic_unique_index": unique_index,
            },
        )
    finally:
        conn.close()


def scenario_path_safety(workdir_real: str) -> ScenarioResult:
    """J — canonical / repo-contained / symlink rejection; outside-tmp accept."""

    results: dict = {}

    def _rejected(call) -> bool:
        try:
            call()
            return False
        except PathSafetyError:
            return True

    # Canonical realpath rejection.
    results["canonical_rejected"] = _rejected(
        lambda: validate_temporary_db_path(CANONICAL_PRODUCTION_DB)
    )
    # Repository-contained path rejection.
    results["repo_path_rejected"] = _rejected(
        lambda: validate_temporary_db_path(os.path.join(REPO_ROOT, "tmp_x.db"))
    )
    # Symlink resolving to the canonical DB rejection (symlink created in tmp).
    symlink_path = _new_db_path(workdir_real, "canonical_symlink.db")
    try:
        if os.path.lexists(symlink_path):
            os.unlink(symlink_path)
        os.symlink(CANONICAL_PRODUCTION_DB, symlink_path)
        results["symlink_to_canonical_rejected"] = _rejected(
            lambda: validate_temporary_db_path(symlink_path)
        )
    finally:
        if os.path.lexists(symlink_path):
            os.unlink(symlink_path)
    # Outside-repo tmp acceptance.
    outside = _new_db_path(workdir_real, "accepted.db")
    try:
        accepted = validate_temporary_db_path(outside)
        results["outside_tmp_accepted"] = accepted == os.path.realpath(outside)
    except PathSafetyError:
        results["outside_tmp_accepted"] = False
    # :memory: rejected for a file-only op.
    results["memory_rejected_for_file_op"] = _rejected(
        lambda: validate_temporary_db_path(MEMORY_DB, require_file=True)
    )

    passed = all(results.values())
    return ScenarioResult("J_path_safety", passed, results)


SCENARIOS: tuple = (
    scenario_clean_install,
    scenario_idempotence,
    scenario_incompatible_version,
    scenario_injected_failure,
    scenario_ambient_transaction,
    scenario_locked_database,
    scenario_backup_restore,
    scenario_existing_prospective_rows,
    scenario_constraints_enforced,
    scenario_path_safety,
)


def run_rehearsal_suite(workdir: object, *, include_locked: bool = True) -> dict:
    """Run scenarios A–J on temporary databases under ``workdir`` (which must
    resolve outside the repository). Returns a structured, deterministic dict."""

    workdir_real = _validate_workdir(workdir)
    results = []
    for scenario in SCENARIOS:
        if scenario is scenario_locked_database and not include_locked:
            continue
        results.append(scenario(workdir_real))
    return {
        "workdir": workdir_real,
        "all_passed": all(r.passed for r in results),
        "scenarios": {r.name: {"passed": r.passed, "detail": r.detail} for r in results},
    }


def run_clean_additive_rehearsal(db_path: object) -> dict:
    """Single-scenario convenience entry point used by ``main`` against an
    explicit caller-supplied temporary DB file path."""

    real = validate_temporary_db_path(db_path, allow_memory=False, require_file=True)
    workdir_real = os.path.dirname(real)
    res = scenario_clean_install(workdir_real)
    return {res.name: {"passed": res.passed, "detail": res.detail}}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "P271K temporary-DB migration rehearsal (rehearsal only; never the "
            "production database). Requires an explicit temporary DB path "
            "outside the repository."
        )
    )
    parser.add_argument(
        "--temp-db",
        required=True,
        help="explicit temporary DB file path OUTSIDE the repository",
    )
    parser.add_argument(
        "--suite",
        action="store_true",
        help="run the full A–J scenario suite in the temp DB's directory",
    )
    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        if args.suite:
            real = validate_temporary_db_path(
                args.temp_db, allow_memory=False, require_file=True
            )
            report = run_rehearsal_suite(os.path.dirname(real))
        else:
            report = run_clean_additive_rehearsal(args.temp_db)
    except PathSafetyError as exc:
        print(json.dumps({"error": "PathSafetyError", "message": str(exc)}))
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("all_passed", True) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
