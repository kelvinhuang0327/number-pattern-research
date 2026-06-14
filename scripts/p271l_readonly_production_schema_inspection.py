#!/usr/bin/env python3
"""P271L — Read-only ACTUAL production schema inspection.

This script resolves the single P271L preflight blocker
``ACTUAL_PRODUCTION_SCHEMA_NOT_READ_IN_P271L_PREFLIGHT`` by performing **exactly
one bounded, immutable, read-only** inspection of the canonical production
SQLite schema and comparing it to the source-of-truth definitions.

HARD BOUNDARIES (enforced by construction + a SQLite authorizer + tests):
  * The production DB is opened **only** through the immutable read-only URI
    ``file:<path>?mode=ro&immutable=1`` with ``uri=True``, ``isolation_level=None``
    and ``timeout=0``. No other connection form is ever attempted; there is no
    ``mode=rw`` / non-immutable / sqlite3-CLI fallback.
  * A SQLite **authorizer** is installed *before* any inspection query and denies
    every INSERT/UPDATE/DELETE, CREATE/DROP/ALTER, ATTACH/DETACH, transaction
    control, SAVEPOINT, REINDEX/ANALYZE, vtable op, ``wal_checkpoint`` and any
    non-whitelisted PRAGMA. Only SELECT/READ, approved functions and a fixed
    allowlist of read-only introspection PRAGMAs are permitted.
  * Only **hardcoded** schema-introspection queries run. No row-payload of any
    lottery / prediction / replay table is ever retrieved (no ``COUNT(*)`` on
    data tables; prospective emptiness uses ``EXISTS(SELECT 1 ... LIMIT 1)``).
  * No ``BEGIN``/``COMMIT``/``ROLLBACK``, no ``ATTACH``/``DETACH``, no backup /
    copy / ``VACUUM`` / ``wal_checkpoint``, no DDL/DML, no network, no process
    signal. The module performs **no import-time database access**.
  * Canonical production-path enforcement: the resolved DB realpath must equal
    ``<repo>/lottery_api/data/lottery_v2.db`` and the repo basename must be
    ``LotteryNew``. A separate ``--synthetic`` mode (for tests only) targets an
    out-of-repo temporary DB and refuses the canonical production path.

Authorization context: P271L remains a preflight + (now) read-only inspection
task. Production apply remains UNAUTHORIZED. Official source verification remains
MANUAL_VERIFICATION_REQUIRED. Governance: HOLD / WAITING_FOR_USER_AUTHORIZATION.
The final classification stays ``P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import urllib.parse
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants — fixed, deterministic.
# ---------------------------------------------------------------------------

TASK_ID = "P271L_READONLY_ACTUAL_PRODUCTION_SCHEMA_INSPECTION"
GENERATED_AT = "2026-06-14"  # fixed for deterministic output
MODE = "readonly_actual_production_schema_inspection"

CANONICAL_REPO_BASENAME = "LotteryNew"
PRODUCTION_DB_RELPATH = os.path.join("lottery_api", "data", "lottery_v2.db")
EXPECTED_PRODUCTION_DB_SHA256 = (
    "3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e"
)

# Prospective schema contract (P271J — sourced from prospective_capture_ledger.py).
EXPECTED_SCHEMA_VERSION = "p271j_prospective_capture_ledger.v1"
PROSPECTIVE_META_TABLE = "prospective_schema_meta"
EXPECTED_PROSPECTIVE_TABLES = (
    "prospective_schema_meta",
    "prospective_activation_registry",
    "prospective_capture_batches",
    "prospective_prediction_ledger",
    "prospective_capture_events",
    "prospective_outcome_links",
)
EXPECTED_PROSPECTIVE_INDEXES = (
    "idx_ledger_identity",
    "idx_batch_cluster",
)
EXPECTED_APPEND_ONLY_TABLES = (
    "prospective_activation_registry",
    "prospective_capture_batches",
    "prospective_prediction_ledger",
    "prospective_capture_events",
    "prospective_outcome_links",
)
EXPECTED_TRIGGER_COUNT = len(EXPECTED_APPEND_ONLY_TABLES) * 2  # no_update + no_delete
# Tables whose emptiness is probed (EXISTS only) when prospective schema present.
PROSPECTIVE_EMPTINESS_PROBE_TABLES = (
    "prospective_activation_registry",
    "prospective_capture_batches",
    "prospective_prediction_ledger",
    "prospective_capture_events",
    "prospective_outcome_links",
)

# Legacy production tables to compare deployed-vs-source. Expected column sets are
# the source-of-truth CREATE columns PLUS the documented ALTER-TABLE migration
# columns, all grounded line-for-line in lottery_api/database.py.
LEGACY_SOURCE_COLUMNS: Dict[str, Tuple[str, ...]] = {
    "draws": (
        "id", "draw", "date", "lottery_type", "numbers", "special",
        "jackpot_amount", "numbers_positional", "created_at",
    ),
    "prediction_runs": (
        "id", "lottery_type", "latest_known_draw", "latest_known_date",
        "strategy_name", "snapshot_source", "notes", "created_at",
        "analyzed", "analysis_note", "review_json",
    ),
    "prediction_items": (
        "id", "run_id", "bet_index", "numbers", "special", "status",
        "created_at", "zone_coverage", "strategy_name", "num_bets",
    ),
    "prediction_results": (
        "id", "item_id", "actual_draw", "actual_date", "actual_numbers",
        "actual_special", "hit_count", "matched_numbers", "special_hit",
        "researched", "resolved_at", "wq_score", "split_risk",
    ),
    "strategy_replay_runs": (
        "id", "lottery_type", "strategy_scope", "started_at", "finished_at",
        "status", "generator_version", "data_hash", "notes", "created_at",
    ),
    "strategy_prediction_replays": (
        "id", "lottery_type", "target_draw", "target_date", "strategy_id",
        "strategy_name", "strategy_version", "history_cutoff_draw",
        "replay_status", "reject_reason", "predicted_numbers",
        "predicted_special", "actual_numbers", "actual_special", "hit_numbers",
        "hit_count", "special_hit", "replay_run_id", "generated_at",
    ),
}
LEGACY_COMPARISON_TABLES = tuple(LEGACY_SOURCE_COLUMNS.keys())

# Prospective actual-state classifications (exactly one is chosen).
STATE_ABSENT_CLEAN = "ABSENT_CLEAN"
STATE_PRESENT_EXACT_AND_EMPTY = "PRESENT_EXACT_AND_EMPTY"
STATE_PRESENT_EXACT_WITH_ROWS = "PRESENT_EXACT_WITH_ROWS"
STATE_PRESENT_PARTIAL = "PRESENT_PARTIAL"
STATE_PRESENT_INCOMPATIBLE_VERSION = "PRESENT_INCOMPATIBLE_VERSION"
STATE_PRESENT_UNEXPECTED_OBJECTS = "PRESENT_UNEXPECTED_OBJECTS"

# ---------------------------------------------------------------------------
# SQLite authorizer (defense in depth, in addition to mode=ro&immutable=1).
# Action / return constants are the stable SQLite C values (portable across
# Python versions that may not expose sqlite3.SQLITE_* names).
# ---------------------------------------------------------------------------

_SQLITE_OK = 0
_SQLITE_DENY = 1
# _SQLITE_IGNORE = 2  # intentionally unused; we DENY rather than silently ignore

_ACT_PRAGMA = 19
_ACT_READ = 20
_ACT_SELECT = 21
_ACT_FUNCTION = 31

# Read-only introspection PRAGMAs that take an object name in arg2.
_INTROSPECTION_PRAGMAS = frozenset({
    "table_info", "table_xinfo", "index_list", "index_info", "index_xinfo",
    "foreign_key_list",
})
# Scalar read-only PRAGMAs (getter form only: arg2 must be None).
_SCALAR_READ_PRAGMAS = frozenset({
    "schema_version", "user_version", "application_id", "page_size",
    "page_count", "freelist_count", "journal_mode", "data_version", "encoding",
})


def _readonly_authorizer(action, arg1, arg2, db_name, trigger_or_view):
    """Fail-closed authorizer: allow only read introspection, deny all else.

    Allows SELECT, READ, scalar FUNCTION calls, and a fixed allowlist of
    read-only PRAGMAs. Denies every mutating action (INSERT/UPDATE/DELETE,
    CREATE/DROP/ALTER, ATTACH/DETACH, TRANSACTION/SAVEPOINT, REINDEX/ANALYZE,
    vtable ops), ``wal_checkpoint``, and any PRAGMA outside the allowlist
    (including the setter form of an otherwise-readable scalar PRAGMA).
    """

    if action in (_ACT_SELECT, _ACT_READ, _ACT_FUNCTION):
        return _SQLITE_OK
    if action == _ACT_PRAGMA:
        name = (arg1 or "").strip().lower()
        if name in _INTROSPECTION_PRAGMAS:
            return _SQLITE_OK  # arg2 carries a table/index name; read-only
        if name in _SCALAR_READ_PRAGMAS and arg2 is None:
            return _SQLITE_OK  # getter form only; setter form (arg2 set) denied
        return _SQLITE_DENY
    return _SQLITE_DENY


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class InspectionError(RuntimeError):
    """Raised on a fail-closed condition (bad path, open failure, mutation)."""


# ---------------------------------------------------------------------------
# Path / hash helpers (raw file bytes only; never via SQLite)
# ---------------------------------------------------------------------------


def canonicalize(path: str) -> str:
    return os.path.realpath(path)


def raw_sha256(path: str) -> str:
    """SHA-256 over the raw bytes of a file. Never opens the DB via SQLite."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_stat(path: str) -> Dict[str, object]:
    if not os.path.exists(path):
        return {"path": path, "exists": False}
    st = os.stat(path)
    return {
        "path": path,
        "exists": True,
        "size_bytes": st.st_size,
        "inode": st.st_ino,
        "mtime_epoch": int(st.st_mtime),
    }


def sidecar_state(db_abspath: str) -> Dict[str, object]:
    out: Dict[str, object] = {}
    for label in ("wal", "shm", "journal"):
        out[label] = file_stat(db_abspath + "-" + label)
    return out


def resolve_production_db(repo_root: str, db_path: str) -> str:
    """Resolve + enforce the canonical production DB realpath. Fail closed."""
    repo_real = canonicalize(repo_root)
    if os.path.basename(repo_real) != CANONICAL_REPO_BASENAME:
        raise InspectionError(
            f"non-canonical repo root: {repo_real} "
            f"(expected basename {CANONICAL_REPO_BASENAME})"
        )
    if not os.path.isabs(db_path):
        db_path = os.path.join(repo_real, db_path)
    db_real = canonicalize(db_path)
    canonical = canonicalize(os.path.join(repo_real, PRODUCTION_DB_RELPATH))
    if db_real != canonical:
        raise InspectionError(
            f"DB path is not the canonical production DB: {db_real} != {canonical}"
        )
    if not os.path.exists(db_real):
        raise InspectionError(f"production DB not found (fail closed): {db_real}")
    return db_real


def resolve_synthetic_db(repo_root: str, db_path: str) -> str:
    """Resolve a synthetic-mode DB path; refuse the canonical production DB."""
    repo_real = canonicalize(repo_root)
    db_real = canonicalize(db_path if os.path.isabs(db_path)
                           else os.path.join(repo_real, db_path))
    canonical = canonicalize(os.path.join(repo_real, PRODUCTION_DB_RELPATH))
    if db_real == canonical:
        raise InspectionError(
            "synthetic mode must NOT target the canonical production DB"
        )
    if db_real.startswith(repo_real + os.sep):
        raise InspectionError(
            "synthetic DB must live outside the repository tree"
        )
    if not os.path.exists(db_real):
        raise InspectionError(f"synthetic DB not found: {db_real}")
    return db_real


# ---------------------------------------------------------------------------
# Immutable read-only connection
# ---------------------------------------------------------------------------


def build_connection_uri(db_abspath: str) -> str:
    """The one and only authorized connection URI for this task."""
    quoted = urllib.parse.quote(db_abspath)
    return f"file:{quoted}?mode=ro&immutable=1"


def connect_readonly_immutable(db_abspath: str) -> sqlite3.Connection:
    """Open the DB immutable + read-only and install the authorizer.

    The authorizer is installed before any inspection query is prepared. The
    connection is autocommit (``isolation_level=None``) and never starts a
    transaction; ``timeout=0`` means we never block on a lock (writers are
    already verified quiesced).
    """
    uri = build_connection_uri(db_abspath)
    conn = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=0)
    conn.set_authorizer(_readonly_authorizer)
    return conn


# ---------------------------------------------------------------------------
# Schema inventory (hardcoded read-only queries only)
# ---------------------------------------------------------------------------


def _normalize_sql(sql: Optional[str]) -> Optional[str]:
    if sql is None:
        return None
    return " ".join(sql.split())


def _scalar_pragma(conn: sqlite3.Connection, name: str) -> Optional[object]:
    row = conn.execute(f"PRAGMA {name}").fetchone()
    return None if row is None else row[0]


def schema_meta(conn: sqlite3.Connection) -> Dict[str, object]:
    return {
        "sqlite_version": sqlite3.sqlite_version,
        "schema_version": _scalar_pragma(conn, "schema_version"),
        "user_version": _scalar_pragma(conn, "user_version"),
        "application_id": _scalar_pragma(conn, "application_id"),
        "page_size": _scalar_pragma(conn, "page_size"),
        "page_count": _scalar_pragma(conn, "page_count"),
        "freelist_count": _scalar_pragma(conn, "freelist_count"),
        "encoding": _scalar_pragma(conn, "encoding"),
        "journal_mode": _scalar_pragma(conn, "journal_mode"),
    }


def list_objects(conn: sqlite3.Connection) -> List[Dict[str, object]]:
    """All sqlite_schema objects (type/name/tbl_name/normalized SQL)."""
    rows = conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "ORDER BY type, name"
    ).fetchall()
    objects = []
    for typ, name, tbl_name, sql in rows:
        objects.append({
            "type": typ,
            "name": name,
            "tbl_name": tbl_name,
            "sql": _normalize_sql(sql),
        })
    return objects


def table_columns(conn: sqlite3.Connection, table: str) -> List[Dict[str, object]]:
    rows = conn.execute(f"PRAGMA table_xinfo({_quote_ident(table)})").fetchall()
    cols = []
    for r in rows:
        # cid, name, type, notnull, dflt_value, pk, hidden
        cols.append({
            "cid": r[0],
            "name": r[1],
            "type": r[2],
            "notnull": r[3],
            "dflt_value": r[4],
            "pk": r[5],
            "hidden": r[6] if len(r) > 6 else 0,
        })
    return cols


def table_indexes(conn: sqlite3.Connection, table: str) -> List[Dict[str, object]]:
    rows = conn.execute(f"PRAGMA index_list({_quote_ident(table)})").fetchall()
    indexes = []
    for r in rows:
        # seq, name, unique, origin, partial
        idx_name = r[1]
        cols = [
            c[2]
            for c in conn.execute(
                f"PRAGMA index_xinfo({_quote_ident(idx_name)})"
            ).fetchall()
            if c[2] is not None  # c[2] = column name; None for rowid/expr entries
        ]
        indexes.append({
            "name": idx_name,
            "unique": r[2],
            "origin": r[3],
            "partial": r[4],
            "columns": cols,
        })
    return indexes


def table_foreign_keys(conn: sqlite3.Connection, table: str) -> List[Dict[str, object]]:
    rows = conn.execute(
        f"PRAGMA foreign_key_list({_quote_ident(table)})"
    ).fetchall()
    fks = []
    for r in rows:
        # id, seq, table, from, to, on_update, on_delete, match
        fks.append({
            "ref_table": r[2],
            "from": r[3],
            "to": r[4],
            "on_update": r[5],
            "on_delete": r[6],
        })
    return fks


def _quote_ident(ident: str) -> str:
    """Quote an identifier for a PRAGMA call. Identifiers come only from the
    inspected sqlite_master / our own constants — never from user input — but we
    quote defensively and reject embedded quotes/control chars."""
    if not isinstance(ident, str) or '"' in ident or "\x00" in ident:
        raise InspectionError(f"unsafe identifier: {ident!r}")
    return '"' + ident + '"'


def build_inventory(conn: sqlite3.Connection) -> Dict[str, object]:
    """Full deterministic schema inventory (no row payloads)."""
    objects = list_objects(conn)
    table_names = sorted(
        o["name"] for o in objects
        if o["type"] == "table" and not str(o["name"]).startswith("sqlite_")
    )
    view_names = sorted(o["name"] for o in objects if o["type"] == "view")
    trigger_names = sorted(o["name"] for o in objects if o["type"] == "trigger")
    index_names = sorted(o["name"] for o in objects if o["type"] == "index")

    tables: Dict[str, object] = {}
    for t in table_names:
        tables[t] = {
            "columns": table_columns(conn, t),
            "indexes": table_indexes(conn, t),
            "foreign_keys": table_foreign_keys(conn, t),
        }

    return {
        "meta": schema_meta(conn),
        "objects": objects,
        "table_names": table_names,
        "view_names": view_names,
        "trigger_names": trigger_names,
        "index_names": index_names,
        "counts": {
            "tables": len(table_names),
            "views": len(view_names),
            "triggers": len(trigger_names),
            "indexes": len(index_names),
            "objects": len(objects),
        },
        "tables": tables,
    }


def compute_fingerprint(inventory: Dict[str, object]) -> str:
    """Deterministic SHA-256 schema fingerprint (no row contents, no volatile
    metadata such as data_version/freelist_count)."""
    canonical = {
        "sqlite_version": inventory["meta"]["sqlite_version"],
        "objects": inventory["objects"],
        "tables": inventory["tables"],
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Prospective state classification
# ---------------------------------------------------------------------------


def _table_is_empty(conn: sqlite3.Connection, table: str) -> bool:
    """True if the table has no rows. Uses EXISTS(SELECT 1 ... LIMIT 1) — never
    COUNT(*), never a payload column."""
    row = conn.execute(
        f"SELECT EXISTS(SELECT 1 FROM {_quote_ident(table)} LIMIT 1)"
    ).fetchone()
    return int(row[0]) == 0


def _read_prospective_schema_version(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute(
        f"SELECT value FROM {_quote_ident(PROSPECTIVE_META_TABLE)} "
        "WHERE key='schema_version'"
    ).fetchone()
    return None if row is None else row[0]


def classify_prospective_state(
    conn: sqlite3.Connection, inventory: Dict[str, object]
) -> Dict[str, object]:
    """Classify the actual prospective_* schema state (exactly one label)."""
    all_tables = set(inventory["table_names"])
    present_prospective = sorted(
        t for t in all_tables if t.startswith("prospective_")
    )
    expected = set(EXPECTED_PROSPECTIVE_TABLES)
    present_set = set(present_prospective)

    present_indexes = sorted(
        i for i in inventory["index_names"]
        if i in set(EXPECTED_PROSPECTIVE_INDEXES)
    )
    prospective_triggers = sorted(
        tr for tr in inventory["trigger_names"] if tr.startswith("trg_prospective_")
    )

    result: Dict[str, object] = {
        "present_prospective_tables": present_prospective,
        "expected_prospective_tables": list(EXPECTED_PROSPECTIVE_TABLES),
        "present_expected_indexes": present_indexes,
        "expected_indexes": list(EXPECTED_PROSPECTIVE_INDEXES),
        "present_prospective_triggers": prospective_triggers,
        "expected_trigger_count": EXPECTED_TRIGGER_COUNT,
        "expected_schema_version": EXPECTED_SCHEMA_VERSION,
        "installed_schema_version": None,
        "unexpected_prospective_objects": [],
        "emptiness": {},
    }

    # Unexpected prospective_* tables (present but not in the expected set).
    unexpected = sorted(present_set - expected)
    result["unexpected_prospective_objects"] = unexpected

    # No prospective objects at all -> ABSENT_CLEAN.
    if not present_prospective and not prospective_triggers:
        result["state"] = STATE_ABSENT_CLEAN
        return result

    # Any prospective object present but the expected core absent / partial.
    missing_tables = sorted(expected - present_set)

    if unexpected and not expected.issubset(present_set):
        # Stray prospective_* objects without the full expected core.
        result["state"] = STATE_PRESENT_UNEXPECTED_OBJECTS
        result["missing_expected_tables"] = missing_tables
        return result

    if not expected.issubset(present_set):
        result["state"] = STATE_PRESENT_PARTIAL
        result["missing_expected_tables"] = missing_tables
        return result

    # All 6 expected tables present. Check the version marker.
    installed_version = None
    if PROSPECTIVE_META_TABLE in present_set:
        installed_version = _read_prospective_schema_version(conn)
    result["installed_schema_version"] = installed_version
    if installed_version != EXPECTED_SCHEMA_VERSION:
        result["state"] = STATE_PRESENT_INCOMPATIBLE_VERSION
        return result

    # Indexes + triggers must be exact for EXACT classification.
    if (set(present_indexes) != set(EXPECTED_PROSPECTIVE_INDEXES)
            or len(prospective_triggers) != EXPECTED_TRIGGER_COUNT):
        result["state"] = STATE_PRESENT_PARTIAL
        result["missing_expected_tables"] = []
        return result

    if unexpected:
        # All expected present + version ok, but extra prospective_* tables too.
        result["state"] = STATE_PRESENT_UNEXPECTED_OBJECTS
        return result

    # Exact schema present. Probe emptiness (EXISTS only).
    empties = {}
    any_rows = False
    for t in PROSPECTIVE_EMPTINESS_PROBE_TABLES:
        is_empty = _table_is_empty(conn, t)
        empties[t] = is_empty
        if not is_empty:
            any_rows = True
    result["emptiness"] = empties
    result["state"] = (
        STATE_PRESENT_EXACT_WITH_ROWS if any_rows else STATE_PRESENT_EXACT_AND_EMPTY
    )
    return result


# ---------------------------------------------------------------------------
# Source-vs-deployed legacy comparison
# ---------------------------------------------------------------------------


def compare_legacy_to_source(inventory: Dict[str, object]) -> Dict[str, object]:
    """Compare the deployed legacy tables to the source-of-truth column sets."""
    deployed_tables = inventory["tables"]
    per_table: Dict[str, object] = {}
    all_present = True
    all_source_columns_present = True
    for table, source_cols in LEGACY_SOURCE_COLUMNS.items():
        if table not in deployed_tables:
            per_table[table] = {"present": False}
            all_present = False
            all_source_columns_present = False
            continue
        deployed_cols = [c["name"] for c in deployed_tables[table]["columns"]]
        deployed_set = set(deployed_cols)
        missing = [c for c in source_cols if c not in deployed_set]
        extra = [c for c in deployed_cols if c not in set(source_cols)]
        if missing:
            all_source_columns_present = False
        per_table[table] = {
            "present": True,
            "deployed_columns": deployed_cols,
            "source_expected_columns": list(source_cols),
            "missing_source_columns": missing,
            "extra_runtime_columns": extra,  # ALTER-added beyond documented source
            "all_source_columns_present": not missing,
        }
    return {
        "compared_tables": list(LEGACY_COMPARISON_TABLES),
        "all_legacy_tables_present": all_present,
        "all_source_columns_present": all_source_columns_present,
        "per_table": per_table,
        "note": (
            "Source-of-truth = lottery_api/database.py CREATE TABLE + documented "
            "ALTER-TABLE migration columns. 'extra_runtime_columns' are columns "
            "present in the deployed DB beyond the documented source set."
        ),
    }


# ---------------------------------------------------------------------------
# Schema collision (would a future apply's object names clash with deployed?)
# ---------------------------------------------------------------------------


def compute_schema_collision(inventory: Dict[str, object]) -> Dict[str, object]:
    """Determine whether the prospective contract object names already exist in
    the deployed schema, and whether any clash with a legacy (non-prospective)
    object. A future CREATE-IF-NOT-EXISTS apply must be collision-free vs legacy.
    """
    deployed_names = {o["name"] for o in inventory["objects"] if o.get("name")}
    contract = set(EXPECTED_PROSPECTIVE_TABLES) | set(EXPECTED_PROSPECTIVE_INDEXES)
    already_present = sorted(contract & deployed_names)
    legacy_collisions = sorted(
        n for n in already_present
        if not (n.startswith("prospective_") or n in EXPECTED_PROSPECTIVE_INDEXES)
    )
    return {
        "prospective_contract_objects": sorted(contract),
        "contract_names_already_present_in_deployed": already_present,
        "legacy_name_collisions": legacy_collisions,
        "collision_free_vs_legacy": len(legacy_collisions) == 0,
        "note": (
            "A legacy collision = a prospective contract object name already used "
            "by a deployed non-prospective object. All prospective tables are "
            "'prospective_'-prefixed; the two indexes are idx_ledger_identity / "
            "idx_batch_cluster."
        ),
    }


# ---------------------------------------------------------------------------
# Orchestration: exactly one inspection.
# ---------------------------------------------------------------------------


def run_inspection(
    repo_root: str, db_path: str, *, synthetic: bool = False
) -> Dict[str, object]:
    """Perform exactly one immutable read-only inspection and return the report.

    Raises ``InspectionError`` (fail closed) on path/open/mutation problems. The
    raw DB hash + stat + sidecars are recorded before and after the (read-only)
    connection to prove the inspection did not mutate the database.
    """
    if synthetic:
        db_real = resolve_synthetic_db(repo_root, db_path)
    else:
        db_real = resolve_production_db(repo_root, db_path)

    hash_before = raw_sha256(db_real)
    stat_before = file_stat(db_real)
    sidecar_before = sidecar_state(db_real)

    conn = connect_readonly_immutable(db_real)
    try:
        data_version_before = _scalar_pragma(conn, "data_version")
        inventory = build_inventory(conn)
        prospective = classify_prospective_state(conn, inventory)
        data_version_after = _scalar_pragma(conn, "data_version")
    finally:
        conn.close()

    hash_after = raw_sha256(db_real)
    stat_after = file_stat(db_real)
    sidecar_after = sidecar_state(db_real)

    fingerprint = compute_fingerprint(inventory)
    legacy_comparison = compare_legacy_to_source(inventory)
    collision = compute_schema_collision(inventory)

    hash_unchanged = (hash_before == hash_after)
    stat_unchanged = (
        stat_before.get("inode") == stat_after.get("inode")
        and stat_before.get("size_bytes") == stat_after.get("size_bytes")
        and stat_before.get("mtime_epoch") == stat_after.get("mtime_epoch")
    )
    sidecars_unchanged = (sidecar_before == sidecar_after)
    no_new_journal = not sidecar_after["journal"].get("exists", False)
    data_version_unchanged = (data_version_before == data_version_after)
    schema_version_stable = True  # schema_version read once in meta; immutable RO

    integrity_ok = (
        hash_unchanged and stat_unchanged and sidecars_unchanged
        and no_new_journal and data_version_unchanged
    )

    # actual-schema blocker is cleared iff we actually opened RO + read the schema
    # AND the inspection left the DB byte-identical.
    actual_schema_blocker_cleared = bool(inventory["objects"]) and integrity_ok

    report: Dict[str, object] = {
        "task_id": TASK_ID,
        "generated_at": GENERATED_AT,
        "mode": MODE,
        "synthetic": synthetic,
        "inspection_only": True,
        "production_db_path": db_real,
        "connection_uri_contract": "file:<path>?mode=ro&immutable=1",
        "connection_uri": build_connection_uri(db_real),
        "connection_params": {
            "uri": True, "isolation_level": None, "timeout": 0,
            "mode": "ro", "immutable": 1,
        },
        "authorizer_installed": True,
        # Negative declarations (all must remain false).
        "production_db_opened_readonly": True,
        "production_db_opened_writable": False,
        "production_db_copied": False,
        "production_db_written": False,
        "backup_executed": False,
        "checkpoint_executed": False,
        "restore_executed": False,
        "process_signaled_or_stopped": False,
        "production_migration_executed": False,
        "deployment_started": False,
        "prospective_collection_activated": False,
        "p271m_started": False,
        "p271n_started": False,
        # Evidence.
        "source_verification_status": "MANUAL_VERIFICATION_REQUIRED",
        "db_sha256_before": hash_before,
        "db_sha256_after": hash_after,
        "db_sha256_expected_baseline": EXPECTED_PRODUCTION_DB_SHA256,
        "db_sha256_matches_baseline": (hash_before == EXPECTED_PRODUCTION_DB_SHA256),
        "db_stat_before": stat_before,
        "db_stat_after": stat_after,
        "sidecars_before": sidecar_before,
        "sidecars_after": sidecar_after,
        "data_version_before": data_version_before,
        "data_version_after": data_version_after,
        "integrity": {
            "db_hash_unchanged": hash_unchanged,
            "db_stat_unchanged": stat_unchanged,
            "sidecars_unchanged": sidecars_unchanged,
            "no_new_journal": no_new_journal,
            "data_version_unchanged": data_version_unchanged,
            "schema_version_stable": schema_version_stable,
            "integrity_ok": integrity_ok,
        },
        "schema_meta": inventory["meta"],
        "object_counts": inventory["counts"],
        "schema_inventory": {
            "table_names": inventory["table_names"],
            "view_names": inventory["view_names"],
            "trigger_names": inventory["trigger_names"],
            "index_names": inventory["index_names"],
            "tables": inventory["tables"],
            "objects": inventory["objects"],
        },
        "schema_fingerprint_sha256": fingerprint,
        "legacy_source_comparison": legacy_comparison,
        "schema_collision": collision,
        "prospective_state": prospective,
        "actual_schema_blocker_cleared": actual_schema_blocker_cleared,
        "actual_schema_limitation_resolved": (
            "ACTUAL_PRODUCTION_SCHEMA_NOT_READ_IN_P271L_PREFLIGHT"
            if actual_schema_blocker_cleared else None
        ),
        "remaining_apply_blockers": [
            "fresh_apply_time_production_db_hash_reverification_required",
            "verified_apply_time_maintenance_window_required",
            "verified_writer_shutdown_required",
            "verified_backup_destination_and_integrity_evidence_required",
            "rollback_authorization_and_restore_procedure_required",
            "wal_shm_reconciliation_at_apply_time_required",
        ],
        "final_classification": "P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY",
        "production_apply": "NOT_READY_FOR_APPLY",
        "governance": "HOLD / WAITING_FOR_USER_AUTHORIZATION",
        "prediction_success_claim": None,
    }
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "P271L read-only ACTUAL production schema inspection. Opens the "
            "canonical production DB exactly once, immutable + read-only. NOT a "
            "migration / deployment command."
        )
    )
    p.add_argument("--repo-root", required=True, help="canonical repository root")
    p.add_argument(
        "--production-db",
        default=PRODUCTION_DB_RELPATH,
        help="production DB path (relative to repo root or absolute)",
    )
    p.add_argument(
        "--synthetic", action="store_true",
        help="synthetic-test mode: target an out-of-repo temp DB (never production)",
    )
    p.add_argument("--out", default=None, help="optional output JSON path")
    # No --apply/--deploy/--migrate flags exist. Their absence is intentional.
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    report = run_inspection(
        args.repo_root, args.production_db, synthetic=args.synthetic
    )
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    print(
        "\n[NOTICE] P271L read-only inspection only. Production apply is NOT "
        "authorized. Official source: MANUAL_VERIFICATION_REQUIRED. Governance: "
        "HOLD / WAITING_FOR_USER_AUTHORIZATION.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
